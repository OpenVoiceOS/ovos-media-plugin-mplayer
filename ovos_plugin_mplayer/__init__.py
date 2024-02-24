import time

from ovos_utils.log import LOG

from ovos_plugin_manager.templates.media import MediaBackend, AudioPlayerBackend, VideoPlayerBackend
from ovos_plugin_mplayer.mplayerlib import MplayerCtrl, NoMplayerRunning

mpc = MplayerCtrl()


class MplayerBaseService(MediaBackend):
    def __init__(self, config, bus=None, video=False):
        super().__init__(config, bus)
        self.config = config
        self.bus = bus

        self.index = 0
        self.normal_volume = 100
        self.low_volume = 50
        self.is_video = video
        self._paused = False
        self.tracks = []
        mpc.callbacks["started"].append(self.handle_media_started)
        mpc.callbacks["finished"].append(self.handle_media_finished)

    def restart_mpc(self):
        global mpc
        if mpc:
            try:
                mpc.quit()
            except:
                pass
            try:
                mpc.destroy()
            except:
                pass
        mpc = None
        mpc = MplayerCtrl()
        mpc.callbacks["started"].append(self.handle_media_started)
        mpc.callbacks["finished"].append(self.handle_media_finished)

    def handle_media_started(self, evt):
        if self._now_playing:
            LOG.debug('mplayer playback start')
            self._paused = False
            if self._track_start_callback:
                self._track_start_callback(self.track_info().get('name', "track"))

    def handle_media_finished(self, evt):
        if self._now_playing:
            LOG.debug('mplayer playback ended')
            self._now_playing = None
            self._paused = False
            if self._track_start_callback:
                self._track_start_callback(None)

    # audio service
    def supported_uris(self):
        return ['file', 'http', 'https']

    def play(self, repeat=False):
        """ Play playlist using mplayer. """
        if self._now_playing:
            LOG.debug('mplayerService Play')

            # start playback
            try:
                mpc.loadfile(self._now_playing)
            except NoMplayerRunning:
                self.restart_mpc()
                mpc.loadfile(self._now_playing)
            if self.is_video:
                if self.config.get("fullscreen", True):
                    mpc.set_property('fullscreen', 1)
                else:
                    mpc.set_property('fullscreen', 0)

    def stop(self):
        """ Stop mplayer playback. """
        LOG.info('mplayerService Stop')
        if self._now_playing:
            try:
                mpc.stop()
                return True
            except NoMplayerRunning:
                pass
        return False

    def pause(self):
        """ Pause mplayer playback. """
        if mpc.playing and not self._paused:
            self._paused = True
            try:
                mpc.pause()
            except NoMplayerRunning:
                pass

    def resume(self):
        """ Resume paused playback. """
        if mpc.playing and self._paused:
            self._paused = False
            try:
                mpc.pause()
            except NoMplayerRunning:
                pass

    def track_info(self):
        """ Extract info of current track. """
        ret = {}
        if mpc.playing:
            try:
                ret['title'] = mpc.get_meta_title()
                ret['artist'] = mpc.get_meta_artist()
                ret['album'] = mpc.get_meta_album()
                ret['genre'] = mpc.get_meta_genre()
                ret['year'] = mpc.get_meta_year()
                ret['track'] = mpc.get_meta_track()
                ret['comment'] = mpc.get_meta_comment()
            except NoMplayerRunning:
                pass
        return ret

    def get_track_length(self):
        """
        getting the duration of the audio in milliseconds
        """
        if mpc.playing:
            return mpc.get_time_length() * 1000  # seconds to milliseconds

    def get_track_position(self):
        """
        get current position in milliseconds
        """
        if mpc.playing:
            return mpc.get_time_pos() * 1000  # seconds to milliseconds

    def set_track_position(self, milliseconds):
        """
        go to position in milliseconds

          Args:
                milliseconds (int): number of milliseconds of final position
        """
        if mpc.playing:
            mpc.set_property("time_pos", milliseconds / 1000)

    def lower_volume(self):
        """Lower volume.

        This method is used to implement audio ducking. It will be called when
        OpenVoiceOS is listening or speaking to make sure the media playing isn't
        interfering.
        """
        if mpc.playing:
            mpc.set_property("volume", self.low_volume)

    def restore_volume(self):
        """Restore normal volume.

        Called when to restore the playback volume to previous level after
        OpenVoiceOS has lowered it using lower_volume().
        """
        if mpc.playing:
            mpc.set_property("volume", self.normal_volume)

    def shutdown(self):
        """
            Shutdown mplayer
        """
        try:
            mpc.destroy()
        except:
            pass


class MplayerOCPAudioService(AudioPlayerBackend, MplayerBaseService):
    def __init__(self, config, bus=None):
        super().__init__(config, bus, video=False)


class MplayerOCPVideoService(VideoPlayerBackend, MplayerBaseService):
    def __init__(self, config, bus=None):
        super().__init__(config, bus, video=True)


if __name__ == "__main__":
    from ovos_utils.fakebus import FakeBus

    pl = MplayerBaseService({}, FakeBus(), video=True)
    pl.load_track(
        "https://rr3---sn-1vo-v2vs.googlevideo.com/videoplayback?expire=1704899978&ei=KmGeZYCyCYjZxN8PsImlmAM&ip=89.154.90.167&id=o-AF5egbINNYqohjrqKtSjAwuVWy-P73vWkRInRYBAePsn&itag=22&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&mh=UA&mm=31%2C29&mn=sn-1vo-v2vs%2Csn-1vo-apns&ms=au%2Crdu&mv=m&mvi=3&pcm2cms=yes&pl=20&initcwndbps=1300000&spc=UWF9f3_FCRmEJLNmTOwAJtKrjmq0Z7dmub--&vprv=1&svpuc=1&mime=video%2Fmp4&cnr=14&ratebypass=yes&dur=4082.555&lmt=1487255922390266&mt=1704878219&fvip=3&fexp=24007246&c=ANDROID&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cspc%2Cvprv%2Csvpuc%2Cmime%2Ccnr%2Cratebypass%2Cdur%2Clmt&sig=AJfQdSswRQIhANRh5x4E4n3Orq99hZbMV64QI5z0Phb3cAvjuqCD-1lkAiBm_c2QNlKDZLDEB2z_sdvOw2QfPxKLN7DhenBTTEeceg%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpcm2cms%2Cpl%2Cinitcwndbps&lsig=AAO5W4owRAIgGlQJrEews_VqyuAmZc0NRQQnvMr4IotnUDmSjkx5TwQCIEIcoYhhfi3rBedoP-2e0q5TBpfmUk46pYNRIR60wGz_")
    pl.play()
    time.sleep(3)
    pl.lower_volume()
    time.sleep(5)
    pl.restore_volume()
    time.sleep(2)
    pl.pause()
    time.sleep(2)
    pl.resume()
    time.sleep(2)
    pl.stop()
