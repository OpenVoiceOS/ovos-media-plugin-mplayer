"""get_track_position when playback stops mid-call.

``get_track_position`` reads ``self.mpc.playing`` and then calls
``self.mpc.get_time_pos()``. ``mplayerlib._get_from_queue`` checks
``self.playing`` again inside that call, so a stop that lands between the
two checks makes ``get_time_pos()`` return ``None`` even though the outer
check saw ``True``. ``None * 1000`` then raises ``TypeError``.

``MediaBackend.get_track_position`` (``ovos_plugin_manager.templates.media``)
documents the sentinel this resolves to:

    None -- nothing is playing, so there is no position.

A player that stops between the two checks is, by the time the engine
answers, not playing. So ``None`` is the existing sentinel applied at the
right point, not a new one.

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


def _backend(position):
    """A backend that is playing, whose engine answers the given position."""
    svc = MplayerOCPAudioService({}, bus=MagicMock())
    svc.mpc = MagicMock()
    svc.mpc.playing = True
    svc.mpc.get_time_pos.return_value = position
    return svc


class TestPositionRace(unittest.TestCase):
    def test_a_dropped_answer_is_none_not_a_crash(self):
        """get_time_pos() answering None while playing=True reproduces the
        race: playback stopped between the outer check and this call."""
        self.assertIsNone(_backend(position=None).get_track_position())

    def test_a_real_position_still_multiplies(self):
        """The control: a normal answer is unaffected by the guard."""
        self.assertEqual(_backend(position=7.0).get_track_position(), 7000)


if __name__ == "__main__":
    unittest.main()
