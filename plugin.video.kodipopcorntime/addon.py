import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'resources', 'lib'))
from kodipopcorntime.common import plugin, PLATFORM, RESOURCES_PATH

if __name__ == '__main__':
    try:
        plugin.run()
    except Exception, e:
        import xbmc
        import traceback
        map(xbmc.log, traceback.format_exc().split("\n"))
        sys.exit(0)

if PLATFORM["os"] not in ["android", "linux", "windows", "darwin"]:
    plugin.notify(plugin.addon.getLocalizedString(30302) % PLATFORM, delay=15000)
    sys.exit(0)

from kodipopcorntime.caching import cached_route
from kodipopcorntime.utils import ensure_fanart
from kodipopcorntime.providers import yify
from kodipopcorntime.player import TorrentPlayer

# Cache TTLs
DEFAULT_TTL = 24 * 3600 # 24 hours

@plugin.route("/")
@ensure_fanart
def index():
    for provider in providers['movie']:
        yield {
            "label": provider['label'],
            "icon": path.join(RESOURCES_PATH, 'media', provider['icon']),
            "thumbnail": path.join(RESOURCES_PATH, 'media', provider['thumbnail']),
            "path": plugin.url_for(provider['path'])
        }
    return yify.list()

@plugin.route("/list/<provider>/<item>/<page>")
@ensure_fanart
def list():
    return yify.list(item, page)

@plugin.route("/browse/<provider>/<item>/<page>")
#contents = ['files', 'songs', 'artists', 'albums', 'movies', 'tvshows', 'episodes', 'musicvideos']
@cached_route(ttl=DEFAULT_TTL, content_type="movies")
@ensure_fanart
def browse(item, page):
    return yify.browse(item, page)

@plugin.route("/search/<provider>")
def search(provider):
    query = plugin.keyboard("", plugin.addon.getLocalizedString(30001))
    if query:
        Plugin.redirect(Plugin.url_for("search_query", provider=provider, query=query, page=1))

@plugin.route("/search/<provider>/<query>/<page>")
@ensure_fanart
def search_query(query, page):
    return yify.search_query(query, page)

@plugin.route("/play/<uri>")
def play(uri):
    TorrentPlayer().init(uri, sub).loop()
