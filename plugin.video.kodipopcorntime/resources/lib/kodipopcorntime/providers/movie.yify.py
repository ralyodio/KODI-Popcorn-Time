from os import path
from kodipopcorntime.common import plugin
from kodipopcorntime.library import library_context
from kodipopcorntime.magnet import from_meta_data

BASE_URLS = [
    "http://yts.to/",
    "http://eqwww.image.yt"
]
if not Plugin.get_setting("base_yify") in BASE_URLS:
    BASE_URLS.insert(0, "%s/" % Plugin.get_setting("base_yify"))
else:
    BASE_URLS.remove("%s/" % Plugin.get_setting("base_yify"))
    BASE_URLS.insert(0, "%s/" % Plugin.get_setting("base_yify"))

MOVIES_PER_PAGE = 20
GENRES = [
    "Action",
    "Adventure",
    "Animation",
    "Biography",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "Film-Noir",
    "Game-Show",
    "History",
    "Horror",
    "Music",
    "Musical",
    "Mystery",
    "News",
    "Reality-TV",
    "Romance",
    "Sci-Fi",
    "Sport",
    "Talk-Show",
    "Thriller",
    "War",
    "Western",
]

def index():
    return [
        {
            "label": Plugin.addon.getLocalizedString(30002),
            "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Search.png'),
            "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Search.png'),
            "path": Plugin.url_for("search")
        },
        {
            "label": Plugin.addon.getLocalizedString(30003),
            "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Genres.png'),
            "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Genres.png'),
            "path": Plugin.url_for("genres")
        },
        {
            "label": Plugin.addon.getLocalizedString(30004),
            "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Top.png'),
            "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Top.png'),
            "path": Plugin.url_for("movies", sort_by="seeds", order="desc", quality="all", page=1, limit=MOVIES_PER_PAGE)
        },
        {
            "label": Plugin.addon.getLocalizedString(30005),
            "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Top.png'),
            "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Top.png'),
            "path": Plugin.url_for("movies", sort_by="rating", order="desc", quality="all", page=1, limit=MOVIES_PER_PAGE)
        },
        {
            "label": Plugin.addon.getLocalizedString(30006),
            "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Recently.png'),
            "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'media', 'Recently.png'),
            "path": Plugin.url_for("movies", sort_by="date", order="desc", quality="all", page=1, limit=MOVIES_PER_PAGE)
        },
    ]

@library_context
def show_data(callback):
    import xbmc
    import xbmcgui
    from contextlib import nested, closing
    from itertools import izip, chain
    from concurrent import futures
    from kodipopcorntime.providers import tmdb, yifysubs
    from kodipopcorntime.utils import url_get_json, SafeDialogProgress

    Plugin.set_content("movies")
    args = dict((k, v[0]) for k, v in Plugin.request.args.items())

    current_page = int(args["page"])
    limit = int(args["limit"])

    with closing(SafeDialogProgress(delay_close=0)) as dialog:
        dialog.create(Plugin.name)
        dialog.update(percent=0, line1=Plugin.addon.getLocalizedString(30007), line2="", line3="")

        search_result = {}
        for url in BASE_URLS:
            search_result = url_get_json("%s/api/v2/list_movies.json" % url, params=args, headers={"Referer": url,})
            if search_result:
                break

        if not search_result:
            Plugin.notify(Plugin.addon.getLocalizedString(30304))
            Plugin.log.error('Could not connect to %s/movie/%s?api_key=%s' %(BASE_URL, imdb_id, API_KEY))
            yield {
                    "label": Plugin.addon.getLocalizedString(30305)
                }
            return

        movies = search_result.get("data").get("movies") or []
        movie_count = int(search_result.get("data")["movie_count"])
        if not movies:
            if callback == "search_query":
                yield {
                        "label": Plugin.addon.getLocalizedString(30008),
                        "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'icons', 'Search.png'),
                        "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'icons', 'Search.png'),
                        "path": Plugin.url_for("search")
                    }
            return

        state = {"done": 0}
        def on_movie(future):
            data = future.result()
            state["done"] += 1
            dialog.update(
                percent=int(state["done"] * 100.0 / len(movies)),
                line2=data.get("title") or data.get("MovieTitleClean") or "",
            )

        with futures.ThreadPoolExecutor(max_workers=2) as pool_tmdb:
            tmdb_list = [pool_tmdb.submit(tmdb.get, movie["imdb_code"]) for movie in movies]
            [future.add_done_callback(on_movie) for future in tmdb_list]
            while not all(job.done() for job in tmdb_list):
                if dialog.iscanceled():
                    return
                xbmc.sleep(100)

        tmdb_list = map(lambda job: job.result(), tmdb_list)
        for movie, tmdb_meta in izip(movies, tmdb_list):
            if tmdb_meta:

                tmdb_meta = tmdb.get_list_item(tmdb_meta)
                sub = yifysubs.get_sub_items(movie["imdb_code"])
                if sub == None:
                    sub = ["none", ""]

                for torrent in movie["torrents"]:
                    item = tmdb_meta.copy()

                    if args.get("quality") == "all" and torrent["quality"] != "720p":
                        item["label"] = "%s (%s)" % (item["label"], torrent["quality"])

                    if item.get("info").get("duration") == 0:
                        item["info"]["duration"] = movie["runtime"]

                    item.update({
                        "path": Plugin.url_for("play", sub=sub[0], uri=from_meta_data(torrent["hash"], movie["title_long"], torrent["quality"])),
                        "is_playable": True,
                    })

                    item.setdefault("info", {}).update({
                        "code": movie["imdb_code"],
                        "size": torrent["size_bytes"],
                    })

                    width = 1920
                    height = 1080
                    if torrent["quality"] == "720p":
                        width = 1280
                        height = 720
                    item.setdefault("stream_info", {}).update({
                        "video": {
                            "codec": "h264",
                            "width": width,
                            "height": height,
                        },
                        "audio": {
                            "codec": "aac",
                            "language": "en",
                        },
                        "subtitle": {
                            "language": sub[1],
                        },
                    })

                    yield item

        if current_page < (movie_count / limit):
            next_args = args.copy()
            next_args["page"] = int(next_args["page"]) + 1
            yield {
                "label": Plugin.addon.getLocalizedString(30009),
                "path": Plugin.url_for(callback, **next_args),
            }

@library_context
def search_show_data():
    import xbmc
    import xbmcgui
    from contextlib import nested, closing
    from itertools import izip, chain
    from concurrent import futures
    from kodipopcorntime.providers import tmdb, yifysubs
    from kodipopcorntime.utils import url_get_json, SafeDialogProgress

    Plugin.set_content("movies")
    args = dict((k, v[0]) for k, v in Plugin.request.args.items())

    current_page = int(args["page"])
    limit = int(args["limit"])

    with closing(SafeDialogProgress(delay_close=0)) as dialog:
        dialog.create(Plugin.name)
        dialog.update(percent=0, line1=Plugin.addon.getLocalizedString(30007), line2="", line3="")

        try:
            search_result = tmdb.search(args[query])
        except:
            pass

        if not movies:
            if callback == "search_query":
                yield {
                        "label": Plugin.addon.getLocalizedString(30008),
                        "icon": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'icons', 'Search.png'),
                        "thumbnail": path.join(Plugin.addon.getAddonInfo('path'), 'resources', 'icons', 'Search.png'),
                        "path": Plugin.url_for("search")
                    }
            return

        state = {"done": 0}
        def on_movie(future):
            data = future.result()
            state["done"] += 1
            dialog.update(
                percent=int(state["done"] * 100.0 / len(movies)),
                line2=data.get("title") or data.get("MovieTitleClean") or "",
            )

        with futures.ThreadPoolExecutor(max_workers=2) as pool_tmdb:
            tmdb_list = [pool_tmdb.submit(tmdb.get, movie["imdb_code"]) for movie in movies]
            [future.add_done_callback(on_movie) for future in tmdb_list]
            while not all(job.done() for job in tmdb_list):
                if dialog.iscanceled():
                    return
                xbmc.sleep(100)

        tmdb_list = map(lambda job: job.result(), tmdb_list)
        for movie, tmdb_meta in izip(movies, tmdb_list):
            if tmdb_meta:
                sub = yifysubs.get_sub_items(movie["imdb_code"])
                if sub == None:
                    sub = ["none", ""]

                item = tmdb.get_list_item(tmdb_meta)
                for torrent in movie["torrents"]:
                    if args.get("quality") == "all" and torrent["quality"] != "720p":
                        item["label"] = "%s (%s)" % (item["label"], torrent["quality"])

                    if item.get("info").get("duration") == 0:
                        item["info"]["duration"] = movie["runtime"]

                    item.update({
                        "path": Plugin.url_for("play", sub=sub[0], uri=from_meta_data(torrent["hash"], movie["title_long"], torrent["quality"])),
                        "is_playable": True,
                    })

                    item.setdefault("info", {}).update({
                        "code": movie["imdb_code"],
                        "size": torrent["size_bytes"],
                    })

                    width = 1920
                    height = 1080
                    if torrent["quality"] == "720p":
                        width = 1280
                        height = 720
                    item.setdefault("stream_info", {}).update({
                        "video": {
                            "codec": "h264",
                            "width": width,
                            "height": height,
                        },
                        "audio": {
                            "codec": "aac",
                            "language": "en",
                        },
                        "subtitle": {
                            "language": sub[1],
                        },
                    })

                    yield item

        if current_page < (movie_count / limit):
            next_args = args.copy()
            next_args["page"] = int(next_args["page"]) + 1
            yield {
                "label": Plugin.addon.getLocalizedString(30009),
                "path": Plugin.url_for("search_query", **next_args),
            }

def genres():
    for k, v in enumerate(GENRES):
        yield {
            "label": Plugin.addon.getLocalizedString((30400 + k)),
            "path": Plugin.url_for("genre", genre=v, sort_by="seeds", order="desc", quality="all", page=1, limit=MOVIES_PER_PAGE),
        }

def genre(genre, page):
    Plugin.request.args.update({
        "genre": [genre],
        "page": [page],
    })
    return show_data("genre")

def movies(sort_by, quality, page):
    Plugin.request.args.update({
        "sort_by": [sort_by],
        "quality": [quality],
        "page": [page],
    })
    return show_data("movies")

def search(query):
    Plugin.redirect(Plugin.url_for("search_query", query=query, quality="all", page=1, limit=MOVIES_PER_PAGE))

def search_query(query, page):
    Plugin.request.args.update({
        "query_term": [query],
        "page": [page],
    })
    return show_data("search_query")