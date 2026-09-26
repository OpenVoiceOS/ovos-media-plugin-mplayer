"""Every declared entry point must load the object it names.

The audio entry point separated module and class with a ``.`` instead of a
``:``, so ``importlib`` read the whole value as a module path and the audio
backend could not be loaded at all from an installed package. The video entry
point two lines below it was correct, so the fault was invisible to anything
that only looked at the video side, and CI reported it for months as
"OPM could not detect opm.media.audio".

These tests read the installed distribution's metadata, so they fail on a bad
separator in ``pyproject.toml`` and cannot be satisfied by importing the class
by hand.

The mplayer control lib is not available in CI, so
``ovos_plugin_mplayer.mplayerlib`` is mocked in ``sys.modules`` before the
plugin is imported, matching test_backends.py.
"""
import sys
import types
import unittest
from importlib.metadata import distribution
from unittest.mock import MagicMock

_mplayerlib = types.ModuleType("ovos_plugin_mplayer.mplayerlib")
_mplayerlib.MplayerCtrl = MagicMock()
sys.modules["ovos_plugin_mplayer.mplayerlib"] = _mplayerlib

import ovos_plugin_mplayer  # noqa: E402 - the stub above must be in place first

ovos_plugin_mplayer.MplayerCtrl = MagicMock()

DIST = "ovos-media-plugin-mplayer"


def _entry_points(group):
    return [e for e in distribution(DIST).entry_points if e.group == group]


class TestEntryPointsLoad(unittest.TestCase):
    def test_audio_entry_point_loads(self):
        eps = _entry_points("opm.media.audio")
        self.assertEqual(len(eps), 1)
        # e.load() raises ModuleNotFoundError when the separator is a dot
        self.assertTrue(callable(eps[0].load()))

    def test_video_entry_point_loads(self):
        eps = _entry_points("opm.media.video")
        self.assertEqual(len(eps), 1)
        self.assertTrue(callable(eps[0].load()))

    def test_legacy_audioservice_entry_point_loads(self):
        """The legacy entry point names a MODULE, not a class, and that module
        must expose load_service. So a colon would be wrong here."""
        eps = _entry_points("mycroft.plugin.audioservice")
        self.assertEqual(len(eps), 1)
        module = eps[0].load()
        self.assertTrue(hasattr(module, "load_service"))

    def test_every_class_entry_point_uses_a_colon(self):
        """The control for the three tests above: a value with no ``:`` names a
        module, and only the legacy entry point is allowed to do that."""
        for group in ("opm.media.audio", "opm.media.video"):
            for ep in _entry_points(group):
                with self.subTest(group=group, name=ep.name):
                    self.assertIn(":", ep.value)


if __name__ == "__main__":
    unittest.main()
