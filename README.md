# ovos-media-plugin-mplayer

This plugin adds mplayer as an audio and video backend for [ovos-media](https://github.com/OpenVoiceOS/ovos-media).

## Install

Run this command to install the plugin.

```
pip install ovos-media-plugin-mplayer
```

## Configuration

This plugin supports either audio or video playback, not both at the same time. If you enable both, the plugin loads but plays each stream twice.

Add the plugin to the `media` section of your OVOS configuration. Set `mplayer` in `preferred_audio_services` or `preferred_video_services` to select it.

```javascript
{
 "media": {

    // keys are the strings defined in "audio_players"
    "preferred_audio_services": ["qt5", "mplayer", "vlc", "cli"],

    // keys are the strings defined in "video_players"
    "preferred_video_services": ["qt5", "mplayer", "vlc", "cli"],

    // PlaybackType.AUDIO handlers
    "audio_players": {
        // mplayer player uses a slave mplayer instance to handle uris
        "mplayer": {
            // the plugin name
            "module": "ovos-media-audio-plugin-mplayer",

            // users may request specific handlers in the utterance
            // using these aliases
            "aliases": ["M Player"],

            // deactivate a plugin by setting to false
            "active": true
        }
    },

    // PlaybackType.VIDEO handlers
    "video_players": {
        // mplayer player uses a slave mplayer instance to handle uris
        "mplayer": {
            // the plugin name
            "module": "ovos-media-video-plugin-mplayer",

            // users may request specific handlers in the utterance
            // using these aliases
            "aliases": ["M Player"],

            // deactivate a plugin by setting to false
            "active": true
        }
    }
}
```

## Related projects

- [ovos-media](https://github.com/OpenVoiceOS/ovos-media) — the media service this plugin extends.
