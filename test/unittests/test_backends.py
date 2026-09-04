"""Unit tests for the mplayer backends.

The mplayer control lib is not available in CI, so
``ovos_plugin_mplayer.mplayerlib`` is mocked in ``sys.modules`` before
importing the plugin. The tests assert wiring/contract, not real playback:
both the new ovos-media backends and the legacy ovos-audio adapter build,
expose the right base classes, and the supported URIs + entry points are
declared correctly.
"""
import sys
import types
import unittest
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

    def _service(self):
        svc = MplayerOCPAudioService({}, bus=MagicMock())
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
        svc, events = self._service()
        svc.load_track(URI)
        svc.stop()
        svc.handle_media_finished(None)
        self.assertIn((PlaybackEvent.STOPPED, {"uri": URI}), events)
        self.assertNotIn(PlaybackEvent.END_OF_MEDIA, [e for e, _ in events])

    def test_stop_requested_flag_cleared_after_report_track_end(self):
        svc, events = self._service()
        svc.load_track(URI)
        svc.stop()
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
    """Both the new and legacy entry-point groups must be declared."""

    def test_setup_declares_new_and_legacy_groups(self):
        import os
        here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        with open(os.path.join(here, "pyproject.toml")) as f:
            setup_src = f.read()
        self.assertIn("opm.media.audio", setup_src)
        self.assertIn("opm.media.video", setup_src)
        self.assertIn("mycroft.plugin.audioservice", setup_src)
        self.assertIn("ovos_plugin_mplayer.audio", setup_src)


if __name__ == "__main__":
    unittest.main()
