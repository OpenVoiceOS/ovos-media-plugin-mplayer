"""Regression test: a track that ends naturally (mplayer fires its
``on_media_finished`` callback on its own, no stop() ever called) must
report ``PlaybackEvent.END_OF_MEDIA`` to the daemon, never ``STOPPED`` -
``handle_media_finished`` cannot itself tell a requested stop from a
natural end, so it always routes through the template's
``report_track_end``, which discriminates on ``self._stop_requested``
(set by ``stop()``) and carries the loaded ``uri`` for staleness checks.

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

from ovos_plugin_manager.templates.media import PlaybackEvent

from ovos_plugin_mplayer import MplayerOCPAudioService

URI = "file:///tmp/track.wav"


class TestNaturalEndOfMedia(unittest.TestCase):

    def _service(self):
        service = MplayerOCPAudioService({}, bus=MagicMock())
        events = []
        service.bind_event_reporter(lambda event, **data: events.append((event, data)))
        service.load_track(URI)
        return service, events

    def test_natural_track_end_reports_end_of_media_with_uri(self):
        service, events = self._service()

        # simulate mplayer's on_media_finished callback firing on its own,
        # with no stop() ever called by us
        service.handle_media_finished(None)

        self.assertIn((PlaybackEvent.END_OF_MEDIA, {"uri": URI}), events,
                       f"natural end-of-media never reported END_OF_MEDIA with uri; saw: {events}")


if __name__ == "__main__":
    unittest.main()
