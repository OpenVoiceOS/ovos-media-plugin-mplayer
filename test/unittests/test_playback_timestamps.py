"""The playback timestamp contract for the mplayer backends.

``MediaBackend`` gives the two timestamp methods three answers, and a stopped
player and a live stream are not the same answer:

    None    nothing is playing, so there is no track to be anywhere in
    -1      something is playing but it has no finite duration
    a value milliseconds

So ``None`` from ``get_track_position`` is correct when playback is stopped.
Both consumers of a relative seek skip it on ``None``: the v1
``AudioBackend.seek_forward``/``seek_backward`` return early, and the media
daemon's seek handler does not offset. ``-1`` belongs to the length of a live
stream, which mplayer answers as a falsy number of seconds; passing that
through would claim a track of zero duration instead.

The mplayer control lib is not available in CI, so
``ovos_plugin_mplayer.mplayerlib`` is mocked in ``sys.modules`` before the
plugin is imported, matching test_backends.py.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock

_mplayerlib = types.ModuleType("ovos_plugin_mplayer.mplayerlib")
_mplayerlib.MplayerCtrl = MagicMock()
sys.modules["ovos_plugin_mplayer.mplayerlib"] = _mplayerlib

# the stub above must be in place before this import, so it is late on
# purpose. CI pins ruff==0.15.22, whose default set enables E402.
import ovos_plugin_mplayer  # noqa: E402

ovos_plugin_mplayer.MplayerCtrl = MagicMock()

from ovos_plugin_mplayer import MplayerOCPAudioService  # noqa: E402
from ovos_plugin_mplayer.audio import MplayerAudioService  # noqa: E402

# seconds as mplayer reports them, and the milliseconds they are worth
POSITION_SECONDS, POSITION_MS = 12.5, 12500
LENGTH_SECONDS, LENGTH_MS = 200.0, 200000


def _backend(playing, length=LENGTH_SECONDS, pos=POSITION_SECONDS,
             cls=MplayerOCPAudioService, **kwargs):
    """A backend whose mplayer engine answers the given seconds.

    Each call gets its own engine stub: ``MplayerCtrl`` is a MagicMock, so
    every backend would otherwise share one return_value and leak state
    between tests.
    """
    svc = cls({}, bus=MagicMock(), **kwargs)
    svc.mpc = MagicMock()
    svc.mpc.playing = playing
    svc.mpc.get_time_pos.return_value = pos
    svc.mpc.get_time_length.return_value = length
    return svc


class TestNothingPlaying(unittest.TestCase):
    """Stopped is None, and it is not either of the other two answers."""

    def test_position_is_none(self):
        self.assertIsNone(_backend(playing=False).get_track_position())

    def test_length_is_none(self):
        self.assertIsNone(_backend(playing=False).get_track_length())

    def test_neither_is_minus_one(self):
        """-1 would claim a live stream, which a stopped player is not."""
        svc = _backend(playing=False)
        self.assertNotEqual(svc.get_track_position(), -1)
        self.assertNotEqual(svc.get_track_length(), -1)

    def test_neither_is_zero(self):
        """0 is a legitimate position and a legitimate length is never 0."""
        svc = _backend(playing=False)
        self.assertNotEqual(svc.get_track_position(), 0)
        self.assertNotEqual(svc.get_track_length(), 0)

    def test_the_engine_is_not_asked(self):
        """A stopped engine has no answer to give, so it is not queried."""
        svc = _backend(playing=False)
        svc.get_track_position()
        svc.get_track_length()
        svc.mpc.get_time_pos.assert_not_called()
        svc.mpc.get_time_length.assert_not_called()


class TestLiveStream(unittest.TestCase):
    """A stream has an elapsed position but no length."""

    def test_length_is_minus_one(self):
        self.assertEqual(_backend(playing=True, length=0.0).get_track_length(),
                         -1)

    def test_length_is_not_zero(self):
        """0 would be a track of zero duration, a different claim."""
        self.assertNotEqual(
            _backend(playing=True, length=0.0).get_track_length(), 0)

    def test_position_is_the_elapsed_time(self):
        svc = _backend(playing=True, length=0.0, pos=7.0)
        self.assertEqual(svc.get_track_position(), 7000)

    def test_an_unparsed_length_is_still_minus_one(self):
        """The engine yields None when its answer does not parse, and
        multiplying that by 1000 would raise instead."""
        self.assertEqual(_backend(playing=True, length=None).get_track_length(),
                         -1)


class TestATrack(unittest.TestCase):
    """Real seconds become real milliseconds."""

    def test_position_in_milliseconds(self):
        self.assertEqual(_backend(playing=True).get_track_position(),
                         POSITION_MS)

    def test_length_in_milliseconds(self):
        self.assertEqual(_backend(playing=True).get_track_length(), LENGTH_MS)


class TestLegacyAudioAdapter(unittest.TestCase):
    """The ovos-audio adapter shares the engine, so it shares the contract.

    The v1 ``AudioBackend.seek_forward`` reads the position and returns early
    on None, which is the behaviour a stopped player needs from it.
    """

    def _legacy(self, playing, **kwargs):
        return _backend(playing, cls=MplayerAudioService, name='mplayer',
                        **kwargs)

    def test_position_is_none_when_stopped(self):
        self.assertIsNone(self._legacy(playing=False).get_track_position())

    def test_length_is_minus_one_for_a_stream(self):
        self.assertEqual(
            self._legacy(playing=True, length=0.0).get_track_length(), -1)

    def test_position_in_milliseconds(self):
        self.assertEqual(self._legacy(playing=True).get_track_position(),
                         POSITION_MS)

    def test_a_stopped_player_does_not_seek(self):
        """The guard that absorbs None, exercised through the real helper."""
        svc = self._legacy(playing=False)
        svc.set_track_position = MagicMock()
        svc.seek_forward(5)
        svc.seek_backward(5)
        svc.set_track_position.assert_not_called()

    def test_a_playing_track_does_seek(self):
        """The control for the test above: the guard is not always on."""
        svc = self._legacy(playing=True)
        svc.set_track_position = MagicMock()
        svc.seek_forward(5)
        svc.set_track_position.assert_called_once_with(POSITION_MS + 5000)


if __name__ == "__main__":
    unittest.main()
