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
    AudioPlayerBackend, VideoPlayerBackend)
from ovos_plugin_manager.templates.audio import AudioBackend

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
