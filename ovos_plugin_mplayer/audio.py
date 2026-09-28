"""Legacy ``ovos-audio`` (mycroft.plugin.audioservice) adapter.

The same mplayer engine as the new ovos-media :class:`MplayerOCPAudioService`,
exposed under the legacy audio-service contract so this plugin works on both
stacks:

* new ``ovos-media`` — ``opm.media.audio`` → :class:`~ovos_plugin_mplayer.MplayerOCPAudioService`
* legacy ``ovos-audio`` — ``mycroft.plugin.audioservice`` → :class:`MplayerAudioService`
  (discovered via :func:`load_service`)
"""
from ovos_plugin_manager.templates.audio import AudioBackend
from ovos_utils.log import LOG

from ovos_plugin_mplayer import MplayerBaseService


class MplayerAudioService(MplayerBaseService, AudioBackend):
    """mplayer backend for the legacy ovos-audio service.

    Reuses every playback method (``play``/``stop``/``pause``/``resume``/
    seek/volume/track-info) from :class:`MplayerBaseService`; only the
    constructor differs because the legacy ``AudioBackend`` takes a ``name``.

    ``MplayerBaseService`` is listed first so its concrete methods satisfy the
    abstract playback methods declared on ``AudioBackend`` (MRO order matters).
    """

    def __init__(self, config, bus=None, name='mplayer'):
        AudioBackend.__init__(self, config, bus, name)
        # set up the mplayer engine without the new MediaBackend constructor
        self._init_mplayer(config, bus, video=False)


def load_service(base_config, bus):
    backends = base_config.get('backends', {})
    services = [(b, backends[b]) for b in backends
                if backends[b].get('type') in ['mplayer', 'ovos_mplayer'] and
                backends[b].get('active', True)]
    instances = [MplayerAudioService(s[1], bus, s[0]) for s in services]
    if len(instances) == 0:
        LOG.warning("No mplayer backends have been configured")
    return instances
