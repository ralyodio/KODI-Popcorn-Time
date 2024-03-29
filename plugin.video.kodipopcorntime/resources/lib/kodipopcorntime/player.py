import xbmc, xbmcgui, urllib, os, time
from kodipopcorntime import torrent2http
from kodipopcorntime.providers.yifysubs import get_subtitle, clear_subtitle
from kodipopcorntime.common import plugin, RESOURCES_PATH, PLATFORM
from kodipopcorntime.utils import url_get_json
from contextlib import contextmanager, closing, nested

TORRENT2HTTP_TIMEOUT = 20
TORRENT2HTTP_POLL = 200
PLAYING_EVENT_INTERVAL = 60

WINDOW_FULLSCREEN_VIDEO = 12005

XBFONT_LEFT = 0x00000000
XBFONT_RIGHT = 0x00000001
XBFONT_CENTER_X = 0x00000002
XBFONT_CENTER_Y = 0x00000004
XBFONT_TRUNCATED = 0x00000008
XBFONT_JUSTIFY = 0x00000010

VIEWPORT_WIDTH = 1920.0
VIEWPORT_HEIGHT = 1088.0
OVERLAY_WIDTH = int(VIEWPORT_WIDTH * 0.7) # 70% size
OVERLAY_HEIGHT = 150

ENCRYPTION_SETTINGS = {
    "Forced": 0,
    "Enabled": 1,
    "Disabled": 2,
}

class OverlayText(object):
    def __init__(self, w, h, *args, **kwargs):
        self.window = xbmcgui.Window(WINDOW_FULLSCREEN_VIDEO)
        viewport_w, viewport_h = self._get_skin_resolution()
        # Adjust size based on viewport, we are using 1080p coordinates
        w = int(w * viewport_w / VIEWPORT_WIDTH)
        h = int(h * viewport_h / VIEWPORT_HEIGHT)
        x = (viewport_w - w) / 2
        y = (viewport_h - h) / 2
        self._shown = False
        self._text = ""
        self._label = xbmcgui.ControlLabel(x, y, w, h, self._text, *args, **kwargs)
        self._background = xbmcgui.ControlImage(x, y, w, h, os.path.join(RESOURCES_PATH, "media", "black.png"))
        self._background.setColorDiffuse("0xD0000000")

    def show(self):
        if not self._shown:
            self.window.addControls([self._background, self._label])
            self._shown = True

    def hide(self):
        if self._shown:
            self._shown = False
            self.window.removeControls([self._background, self._label])

    def close(self):
        self.hide()

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, text):
        self._text = text
        if self._shown:
            self._label.setLabel(self._text)

    # This is so hackish it hurts.
    def _get_skin_resolution(self):
        import xml.etree.ElementTree as ET
        skin_path = xbmc.translatePath("special://skin/")
        tree = ET.parse(os.path.join(skin_path, "addon.xml"))
        res = tree.findall("./extension/res")[0]
        return int(res.attrib["width"]), int(res.attrib["height"])

class TorrentPlayer(xbmc.Player):
    def init(self, uri, sub=None):
        self.subtitles = sub
        self.torrent2http_options = {
            "uri": uri,
            "dlpath": xbmc.validatePath(xbmc.translatePath(plugin.get_setting("dlpath"))) or ".",
            "dlrate": plugin.get_setting("max_download_rate") or "0",
            "encryption": plugin.get_setting("encryption"),
        }

        if "://" in self.torrent2http_options["dlpath"]:
            # Translate smb:// url to UNC path on windows, very hackish
            if PLATFORM["os"] == "windows" and self.torrent2http_options["dlpath"].lower().startswith("smb://"):
                self.torrent2http_options["dlpath"] = self.torrent2http_options["dlpath"].replace("smb:", "").replace("/", "\\")
            else:
                plugin.notify("Downloading to an unmounted network share is not supported. Resetting.", delay=15000)
                plugin.set_setting("dlpath", "")
                self.torrent2http_options["dlpath"] = "."

        # Check for Android and FAT32 SD card issues
        if PLATFORM["os"] == "android" and self.torrent2http_options["dlpath"] != ".":
            from kodipopcorntime.utils import get_path_fs
            fs = get_path_fs(self.torrent2http_options["dlpath"])
            plugin.log.info("Download path filesytem is %s" % fs)
            if fs == "vfat": # FAT32 is not supported
                plugin.notify("Downloading to FAT32 is not supported. Resetting.", delay=15000)
                plugin.set_setting("dlpath", "")
                self.torrent2http_options["dlpath"] = "."

        if plugin.get_setting("keep_files", bool):
            plugin.log.info("Will keep file after playback.")
            self.torrent2http_options["keep"] = None
        self.on_playback_started = []
        self.on_playback_resumed = []
        self.on_playback_paused = []
        self.on_playback_stopped = []
        return self

    def onPlayBackStarted(self):
        for f in self.on_playback_started:
            f()

    def onPlayBackResumed(self):
        for f in self.on_playback_resumed:
            f()
        self.onPlayBackStarted()

    def onPlayBackPaused(self):
        for f in self.on_playback_paused:
            f()

    def onPlayBackStopped(self):
        for f in self.on_playback_stopped:
            f()

    def _get_status_lines(self, status):
		if not status["name"] == '':
			return [
				"%(name)s" % status,
				"Speed: %(download_rate).1f kB/s" % status,
				"Seeds: %(num_seeds)d" % status
			]

		return ["Waiting..."]

    @contextmanager
    def attach(self, callback, *events):
        for event in events:
            event.append(callback)
        yield
        for event in events:
            event.remove(callback)

    def _wait_t2h_startup(self, t2h):
        start = time.time()
        while (time.time() - start) < TORRENT2HTTP_TIMEOUT:
            try:
                t2h("status")
                return True
            except:
                pass
            xbmc.sleep(TORRENT2HTTP_POLL)
        return False

    def loop(self):
        from kodipopcorntime.utils import SafeDialogProgress

        has_resolved = False

        plugin.log.info("Starting torrent2http...")
        with closing(torrent2http.start(**self.torrent2http_options)) as t2h_instance:
            t2h = lambda cmd: url_get_json("http://%s/%s" % (t2h_instance.bind_address, cmd))

            if not self._wait_t2h_startup(t2h):
                return

            plugin.log.info("Opening download dialog...")
            with closing(SafeDialogProgress(delay_create=0)) as dialog:
                dialog.create(plugin.name)

                plugin.log.info("Waiting for file resolution...")
                progress = 0
                while not has_resolved:
                    if xbmc.abortRequested or dialog.iscanceled():
                        return

                    status = t2h("status")

                    if status["state"] >= 0:
                        new_progress = status["progress"] * 9091
                        if new_progress > progress:
                            progress = new_progress
                        if progress > int(progress):
                            progress = progress + 1
                        if progress > 100:
                            progress = 100
                        dialog.update(int(progress), *self._get_status_lines(status))

                    if status["state"] >= 3 and progress == 100:
                        files = t2h("ls")["files"]
                        biggest_file = sorted(files, key=lambda x: x["size"])[-1]
                        biggest_file["name"] = biggest_file["name"].encode("utf-8")
                        plugin.log.info("Resolving to http://%s/files/%s" % (t2h_instance.bind_address, biggest_file["name"]))
                        item = {"path": "http://%s/files/%s" % (t2h_instance.bind_address, urllib.quote(biggest_file["name"])),}
                        if not xbmc.getInfoLabel("ListItem.Title"):
                            item["label"] = status["name"]

                        self.subtitles = get_subtitle(self.subtitles)
                        plugin.set_resolved_url(item, self.subtitles)
                        break

                    xbmc.sleep(TORRENT2HTTP_POLL)

            # We are now playing
            plugin.log.info("Now playing torrent...")
            last_playing_event = 0
            with closing(OverlayText(w=OVERLAY_WIDTH, h=OVERLAY_HEIGHT, alignment=XBFONT_CENTER_X | XBFONT_CENTER_Y)) as overlay:
                with nested(self.attach(overlay.show, self.on_playback_paused),
                            self.attach(overlay.hide, self.on_playback_resumed, self.on_playback_stopped)):
                    while not xbmc.abortRequested and self.isPlaying():
                        overlay.text = "\n".join(self._get_status_lines(t2h("status")))
                        now = time.time()
                        if (now - last_playing_event) > PLAYING_EVENT_INTERVAL:
                            last_playing_event = now
                        xbmc.sleep(TORRENT2HTTP_POLL)

        clear_subtitle(self.subtitles)
        plugin.log.info("Closing Torrent player.")
