from kodipopcorntime.common import plugin

@plugin.route("/cmd/clear_cache")
def clear_cache():
    import os, glob
    from kodipopcorntime.common import CACHE_DIR

    for directory in [CACHE_DIR, plugin.storage_path]:
        for dbfile in glob.glob(os.path.join(directory, "*.db")):
            os.remove(dbfile)
    for file in glob.glob(CACHE_DIR + '/com.imdb.*'):
        os.remove(file)
    for file in glob.glob(CACHE_DIR + '/kodipopcorntime.route.*'):
        os.remove(file)
    plugin.notify(plugin.addon.getLocalizedString(30301))
