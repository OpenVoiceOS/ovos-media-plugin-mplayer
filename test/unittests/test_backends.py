"""Unit tests for the mplayer backends.

The mplayer control lib is not available in CI, so
``ovos_plugin_mplayer.mplayerlib`` is mocked in ``sys.modules`` before
importing the plugin. The tests assert wiring/contract, not real playback:
both the new ovos-media backends and the legacy ovos-audio adapter build,
expose the right base classes, and the supported URIs + entry points are
declared correctly.
"""
import os
import re
import sys
import types
import unittest
from importlib.metadata import EntryPoint
from unittest.mock import MagicMock


# --- mock the mplayer control lib so the plugin imports without mplayer -------
# ``ovos_plugin_mplayer.mplayerlib`` is a submodule of the package, so stub the
# whole module with a MagicMock ``MplayerCtrl`` attribute before import.
_mplayerlib = types.ModuleType("ovos_plugin_mplayer.mplayerlib")
_mplayerlib.MplayerCtrl = MagicMock()
sys.modules["ovos_plugin_mplayer.mplayerlib"] = _mplayerlib

from ovos_plugin_manager.templates.media import (
    AudioPlayerBackend, VideoPlayerBackend, PlaybackEvent)
from ovos_plugin_manager.templates.audio import AudioBackend
from ovos_utils.fakebus import FakeBus

import ovos_plugin_mplayer
# Force-mock the MplayerCtrl bound in the package namespace. The sys.modules stub
# above only wins if this module is imported first; a sibling test (e.g. test_e2e)
# that imports the package earlier would already have bound the real MplayerCtrl
# (which spawns the `mplayer` binary at construction). Patching the package symbol
# makes the contract tests order-independent.
ovos_plugin_mplayer.MplayerCtrl = MagicMock()

from ovos_plugin_mplayer import (
    MplayerBaseService, MplayerOCPAudioService, MplayerOCPVideoService)
from ovos_plugin_mplayer.audio import MplayerAudioService, load_service

URI = "http://example.com/song.mp3"


class TestNewBackends(unittest.TestCase):
    def test_audio_backend_is_audioplayerbackend(self):
        svc = MplayerOCPAudioService({}, bus=MagicMock())
        self.assertIsInstance(svc, AudioPlayerBackend)
        self.assertIsInstance(svc, MplayerBaseService)

    def test_video_backend_is_videoplayerbackend(self):
        svc = MplayerOCPVideoService({}, bus=MagicMock())
        self.assertIsInstance(svc, VideoPlayerBackend)

    def test_supported_uris(self):
        svc = MplayerOCPAudioService({}, bus=MagicMock())
        self.assertEqual(svc.supported_uris(), ['file', 'http', 'https'])

    def test_capabilities(self):
        svc = MplayerOCPAudioService({}, bus=MagicMock())
        self.assertTrue(svc.can_seek)
        self.assertTrue(svc.can_pause)


class TestV2EventReporting(unittest.TestCase):
    """MediaBackend v2 contract: physical events go through report(), never
    the bus - the daemon owns every ``ovos.common_play.*`` transition."""

    def _service(self, playing: bool = False):
        svc = MplayerOCPAudioService({}, bus=MagicMock())
        # One MagicMock stands in for the MplayerCtrl CLASS, so every service
        # built from it gets the same MplayerCtrl.return_value as self.mpc.
        # That makes engine state shared between tests: handle_media_finished
        # sets mpc.playing = False, and because these methods run in
        # alphabetical order, the end-of-media test below would leave a later
        # _stop() looking at a backend that is not playing. Give each service
        # its own engine mock so a test cannot be decided by its neighbours.
        svc.mpc = MagicMock()
        # A fresh MagicMock attribute is truthy, so mpc.playing reads as
        # "playing" unless a test says otherwise. Be explicit either way
        # rather than inheriting that accident.
        svc.mpc.playing = playing
        events = []
        svc.bind_event_reporter(lambda event, **data: events.append((event, data)))
        return svc, events

    def test_load_track_returns_bool_and_reports_nothing(self):
        svc, events = self._service()
        self.assertTrue(svc.load_track(URI))
        self.assertEqual(events, [], "load_track must not report - the "
                                      "daemon owns LOADED_MEDIA")

    def test_track_start_reports_with_uri(self):
        svc, events = self._service()
        svc.load_track(URI)
        svc.handle_media_started(None)
        self.assertIn((PlaybackEvent.TRACK_START, {"uri": URI}), events)

    def test_mplayer_error_reports_error_and_uri(self):
        svc, events = self._service()
        svc.load_track(URI)
        svc.handle_mplayer_error({"data": "boom"})
        self.assertEqual(len(events), 1)
        event, data = events[0]
        self.assertEqual(event, PlaybackEvent.ERROR)
        self.assertEqual(data.get("uri"), URI)
        self.assertEqual(data.get("error"), "boom")

    def test_explicit_stop_then_end_callback_reports_stopped(self):
        # playing=True is the precondition, not decoration: mplayer's _stop()
        # returns False when nothing is playing, and the template then clears
        # the pending-stop flag because that stop did not take - so the next
        # end callback is a natural END_OF_MEDIA. STOPPED is only owed for a
        # stop that actually took.
        svc, events = self._service(playing=True)
        svc.load_track(URI)
        self.assertTrue(svc.stop(), "the stop must take for STOPPED to be owed")
        svc.handle_media_finished(None)
        self.assertIn((PlaybackEvent.STOPPED, {"uri": URI}), events)
        self.assertNotIn(PlaybackEvent.END_OF_MEDIA, [e for e, _ in events])

    def test_stop_requested_flag_cleared_after_report_track_end(self):
        # same precondition as above: the flag stays pending only for a stop
        # that took.
        svc, events = self._service(playing=True)
        svc.load_track(URI)
        self.assertTrue(svc.stop(), "the stop must take for the flag to stay set")
        self.assertTrue(svc._stop_requested)
        svc.handle_media_finished(None)
        self.assertFalse(svc._stop_requested)

    def test_end_callback_without_stop_reports_end_of_media(self):
        svc, events = self._service()
        svc.load_track(URI)
        svc.handle_media_finished(None)
        self.assertIn((PlaybackEvent.END_OF_MEDIA, {"uri": URI}), events)
        self.assertNotIn(PlaybackEvent.STOPPED, [e for e, _ in events])
        self.assertFalse(svc._stop_requested)

    def test_stop_that_did_not_take_is_followed_by_end_of_media(self):
        # The other half of the contract, and the one a daemon actually rides
        # on: mplayer is not playing, so _stop() returns False, so the stop
        # did not take and nothing is pending. When the track then ends on its
        # own, that is a natural end - reporting STOPPED here would make the
        # daemon stop advancing the playlist with nothing in the log to say
        # why.
        svc, events = self._service(playing=False)
        svc.load_track(URI)
        self.assertFalse(svc.stop(), "nothing is playing, so the stop cannot take")
        self.assertFalse(svc._stop_requested)
        svc.handle_media_finished(None)
        self.assertIn((PlaybackEvent.END_OF_MEDIA, {"uri": URI}), events)
        self.assertNotIn(PlaybackEvent.STOPPED, [e for e, _ in events])

    def test_each_service_gets_its_own_engine(self):
        # Guards the isolation _service() installs. MplayerCtrl is mocked at
        # class level, so without it two services share one engine object and
        # one test's mpc.playing decides another's result.
        a, _ = self._service()
        b, _ = self._service()
        self.assertIsNot(a.mpc, b.mpc)

    def test_stop_renamed_to_underscore_stop(self):
        svc, _ = self._service()
        # stop() is now the template's concrete method; plugins implement
        # _stop() for the actual engine call
        self.assertNotEqual(type(svc).stop, type(svc)._stop)
        self.assertTrue(callable(svc._stop))

    def test_full_verb_cycle_emits_no_common_play_bus_messages(self):
        bus = FakeBus()
        seen = []
        bus.on("ovos.common_play.playback_time",
               lambda msg: seen.append(msg.msg_type))

        def _catch_all(msg):
            if msg.msg_type.startswith("ovos.common_play."):
                seen.append(msg.msg_type)

        bus.on("message", _catch_all)

        svc = MplayerOCPAudioService({}, bus=bus)
        svc.bind_event_reporter(lambda event, **data: None)
        svc.load_track(URI)
        svc.play()
        svc.handle_media_started(None)
        svc.pause()
        svc.resume()
        svc.get_track_position()
        svc.set_track_position(1000)
        svc.stop()
        svc.handle_media_finished(None)
        svc.handle_mplayer_error({"data": "boom"})

        self.assertEqual(seen, [], f"backend emitted state on the bus: {seen}")


class TestLegacyAdapter(unittest.TestCase):
    def test_legacy_is_audiobackend(self):
        svc = MplayerAudioService({}, bus=MagicMock(), name='mplayer')
        self.assertIsInstance(svc, AudioBackend)
        # reuses the shared mplayer engine/methods
        self.assertIsInstance(svc, MplayerBaseService)
        self.assertTrue(hasattr(svc, "play"))
        self.assertTrue(hasattr(svc, "lower_volume"))

    def test_supported_uris(self):
        svc = MplayerAudioService({}, bus=MagicMock(), name='mplayer')
        self.assertEqual(svc.supported_uris(), ['file', 'http', 'https'])

    def test_load_service_builds_active_mplayer_backends(self):
        cfg = {"backends": {
            "a": {"type": "mplayer", "active": True},
            "b": {"type": "mplayer", "active": False},
            "c": {"type": "mpv", "active": True},
        }}
        services = load_service(cfg, bus=MagicMock())
        self.assertEqual(len(services), 1)
        self.assertIsInstance(services[0], MplayerAudioService)

    def test_load_service_empty(self):
        self.assertEqual(load_service({"backends": {}}, bus=MagicMock()), [])


class TestEntryPoints(unittest.TestCase):
    """Both entry-point groups must be declared, and every target must resolve.

    ``find_plugins`` loads an entry point and swallows a failure with a log
    line, so an unresolvable target does not raise anywhere: the backend is
    simply missing from the stack. Asserting that the group names appear in
    pyproject.toml cannot see that, so these resolve the declared targets.
    """

    GROUPS = ("opm.media.audio", "opm.media.video")

    def setUp(self):
        here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        with open(os.path.join(here, "pyproject.toml")) as f:
            self.pyproject = f.read()

    def declared(self, group):
        """The name -> target pairs declared under one entry-point group."""
        body = re.search(rf'^\[project\.entry-points\."{re.escape(group)}"\]$'
                         r'(.*?)(?=^\[|\Z)',
                         self.pyproject, re.M | re.S)
        self.assertIsNotNone(body, f"{group} is not declared")
        return dict(re.findall(r'^([\w.-]+)\s*=\s*"([^"]+)"$',
                               body.group(1), re.M))

    def test_both_media_groups_are_declared(self):
        for group in self.GROUPS:
            self.assertTrue(self.declared(group), f"{group} declares nothing")

    def test_legacy_audioservice_group_is_declared(self):
        legacy = self.declared("mycroft.plugin.audioservice")
        self.assertEqual(legacy, {"ovos_mplayer": "ovos_plugin_mplayer.audio"})

    def test_every_media_entry_point_resolves_to_a_backend(self):
        for group in self.GROUPS:
            expected = AudioPlayerBackend if group.endswith("audio") \
                else VideoPlayerBackend
            for name, target in self.declared(group).items():
                with self.subTest(entry_point=name):
                    cls = EntryPoint(name, target, group).load()
                    self.assertTrue(issubclass(cls, expected),
                                    f"{target} is not a {expected.__name__}")


if __name__ == "__main__":
    unittest.main()
