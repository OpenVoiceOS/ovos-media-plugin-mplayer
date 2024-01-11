# ovos-media-plugin-mplayer

Mplayer plugin for [ovos-media](https://github.com/OpenVoiceOS/ovos-media)

## Install

`pip install ovos-media-plugin-mplayer`

## Configuration

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