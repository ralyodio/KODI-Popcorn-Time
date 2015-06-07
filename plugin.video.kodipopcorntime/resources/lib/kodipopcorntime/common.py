import sys, os, xbmc
from xbmcswift2 import Plugin

def cacheDir():
    dir = xbmc.translatePath("special://profile/addon_data/%s/cache" % plugin.id)
    if not os.path.exists(dir):
        os.makedirs(dir)
    return dir

def platform():
    ret = {
        "arch": sys.maxsize > 2**32 and "x64" or "x86",
    }

    if xbmc.getCondVisibility("system.platform.android"):
        ret["os"] = "android"
        if "arm" in os.uname()[4]:
            ret["arch"] = "arm"
    elif xbmc.getCondVisibility("system.platform.linux"):
        ret["os"] = "linux"
        if "arm" in os.uname()[4]:
            ret["arch"] = "arm"
    elif xbmc.getCondVisibility("system.platform.xbox"):
        system_platform = "xbox"
        ret["arch"] = ""
    elif xbmc.getCondVisibility("system.platform.windows"):
        ret["os"] = "windows"
    elif xbmc.getCondVisibility("system.platform.osx"):
        ret["os"] = "darwin"
    elif xbmc.getCondVisibility("system.platform.ios"):
        ret["os"] = "ios"
        ret["arch"] = "arm"

    return ret

plugin = Plugin()
CACHE_DIR = cacheDir()
PLATFORM = platform()
RESOURCES_PATH = os.path.join(plugin.addon.getAddonInfo('path'), 'resources')
