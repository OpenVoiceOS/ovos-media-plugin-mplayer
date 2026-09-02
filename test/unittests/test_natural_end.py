"""Regression test: a track that ends naturally (mplayer fires its
``on_media_finished`` callback on its own, no stop() ever called) must
report MediaState.END_OF_MEDIA / PlayerState.STOPPED on the bus, exactly
like an explicit stop does.

The mplayer control lib is not available in CI, so
``ovos_plugin_mplayer.mplayerlib`` is mocked in ``sys.modules`` before
importing the plugin, matching test_backends.py.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock

_mplayerlib = types.ModuleType("ovos_plugin_mplayer.mplayerlib")
_mplayerlib.MplayerCtrl = MagicMock()
sys.modules["ovos_plugin_mplayer.mplayerlib"] = _mplayerlib

import ovos_plugin_mplayer
ovos_plugin_mplayer.MplayerCtrl = MagicMock()

from ovos_utils.fakebus import FakeBus
from ovos_utils.ocp import MediaState, PlayerState

from ovos_plugin_mplayer import MplayerOCPAudioService


class TestNaturalEndOfMedia(unittest.TestCase):

    def _service(self):
        bus = FakeBus()
        states = []
        player_states = []
        bus.on("ovos.common_play.media.state",
               lambda msg: states.append(msg.data.get("state")))
        bus.on("ovos.common_play.player.state",
               lambda msg: player_states.append(msg.data.get("state")))
        service = MplayerOCPAudioService({}, bus=bus)
        service._now_playing = "file:///tmp/track.wav"
        return service, states, player_states

    def test_natural_track_end_emits_end_of_media(self):
        service, states, player_states = self._service()

        # simulate mplayer's on_media_finished callback firing on its own,
        # with no stop() ever called by us
        service.handle_media_finished(None)

        self.assertIn(MediaState.END_OF_MEDIA, states,
                       f"natural end-of-media never emitted END_OF_MEDIA; saw: {states}")
        self.assertIn(PlayerState.STOPPED, player_states,
                       f"natural end-of-media never emitted PlayerState.STOPPED; saw: {player_states}")


if __name__ == "__main__":
    unittest.main()
