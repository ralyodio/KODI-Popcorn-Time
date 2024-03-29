import os
import sys
import stat
import subprocess
from kodipopcorntime.common import RESOURCES_PATH
from kodipopcorntime.platform import PLATFORM
from kodipopcorntime.utils import url_get
from xbmcswift2 import Plugin


ANDROID_XBMC_IDS = [
    "org.xbmc.kodi",                        # KODI XBMC
    "org.xbmc.xbmc",                        # Stock XBMC
    "tv.ouya.xbmc",                         # OUYA XBMC
    "com.semperpax.spmc",                   # SemPer Media Center (OUYA XBMC fork)
    "hk.minix.xbmc",                        # Minix XBMC
    Plugin.get_setting("android_app_id"),   # Whatever the user sets
]


def ensure_exec_perms(file_):
    st = os.stat(file_)
    os.chmod(file_, st.st_mode | stat.S_IEXEC)
    return file_


def get_torrent2http_binary():
    binary = "torrent2http%s" % (PLATFORM["os"] == "windows" and ".exe" or "")

    platform = PLATFORM.copy()
    if platform["os"] == "darwin": # 64 bits anyway on Darwin
        platform["arch"] = "x64"
    elif platform["os"] == "windows": # 32 bits anyway on Windows
        platform["arch"] = "x86"

    binary_dir = os.path.join(RESOURCES_PATH, "bin", "%(os)s_%(arch)s" % platform)
    binary_path = os.path.join(binary_dir, binary)

    # On Android, we need to copy torrent2http to ext4, since the sdcard is noexec
    if platform["os"] == "android":

        # Find wether on XBMC or OUYA XBMC
        uid = os.getuid()
        for app_id in ANDROID_XBMC_IDS:
            xbmc_data_path = os.path.join("/data", "data", app_id)
            if os.path.exists(xbmc_data_path) and uid == os.stat(xbmc_data_path).st_uid:
                android_binary_dir = os.path.join(xbmc_data_path, "files", "plugin.video.kodipopcorntime")
                break

        if not os.path.exists(android_binary_dir):
            os.makedirs(android_binary_dir)
        android_binary_path = os.path.join(android_binary_dir, binary)
        if not os.path.exists(android_binary_path) or os.path.getsize(android_binary_path) != os.path.getsize(binary_path):
            import shutil
            shutil.copy2(binary_path, android_binary_path)
        binary_path = android_binary_path
        binary_dir = android_binary_dir

    return binary_dir, ensure_exec_perms(binary_path)


def find_free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start(**kwargs):
    torrent2http_dir, torrent2http_bin = get_torrent2http_binary()
    args = [torrent2http_bin]
    bind_port = find_free_port()
    kwargs["bind"] = ":%d" % bind_port

    for k, v in kwargs.items():
        args.append("--%s" % k)
        if v:
            args.append(v)

    # Needed because torrent2http is vendored with Boost and libtorrent-rasterbar
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = torrent2http_dir
    env["DYLD_LIBRARY_PATH"] = torrent2http_dir

    import xbmc
    xbmc.log(repr(args))
    kwargs = {
        "cwd": torrent2http_dir,
        "env": env,
    }
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= 1
        si.wShowWindow = 0
        kwargs["startupinfo"] = si
    proc = subprocess.Popen(args, **kwargs)
    proc.bind_address = "localhost:%d" % bind_port
    def proc_close():
        if not proc.poll():
            url_get("http://%s/shutdown" % proc.bind_address)
    proc.close = proc_close
    return proc
