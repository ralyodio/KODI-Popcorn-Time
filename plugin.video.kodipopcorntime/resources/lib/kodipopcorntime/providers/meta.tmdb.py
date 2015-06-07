from kodipopcorntime.common import plugin

API_KEY = "57983e31fb435df4df77afb854740ea9"
BASE_URL = "http://api.themoviedb.org/3"
HEADERS = {
    "Referer": BASE_URL,
}

DEFAULT_TTL = 24 * 3600 # 24 hours

def tmdb_config():
    from kodipopcorntime.caching import shelf
    try:
        with shelf("com.imdb.conf", DEFAULT_TTL) as conf:
            if not conf:
                from kodipopcorntime.utils import url_get_json
                conf.update(url_get_json("%s/configuration" % BASE_URL, params={"api_key": API_KEY}, headers=HEADERS))
                if not conf:
                    raise
            return dict(conf)
    except:
        plugin.notify(plugin.addon.getLocalizedString(30304))
        plugin.log.error('Could not connect to %s/configuration?api_key=%s' %(BASE_URL, API_KEY))
tmdb_config()

def image(rel_url, size="original"):
    conf = tmdb_config()
    if not conf:
        return ''
    return "%s/%s%s" % (conf["images"]["base_url"], size, rel_url)


def get(imdb_id):
    from kodipopcorntime.caching import shelf
    try:
        with shelf("com.imdb.%s" % imdb_id, DEFAULT_TTL) as movie:
            if not movie:
                import xbmc
                from kodipopcorntime.utils import url_get_json
                sys_lang = xbmc.getLanguage(xbmc.ISO_639_1)
                movie.update(url_get_json("%s/movie/%s" % (BASE_URL, imdb_id), params={"api_key": API_KEY, "append_to_response": "credits", "language": "en", "include_image_language": "en,null"}, headers=HEADERS))
                if not sys_lang == 'en':
                    movie.update(url_get_json("%s/movie/%s" % (BASE_URL, imdb_id), params={"api_key": API_KEY, "append_to_response": "credits", "language": sys_lang, "include_image_language": "%s" % sys_lang}, headers=HEADERS) or {})
                if not movie:
                    raise
        return dict(movie)
    except:
        plugin.notify(plugin.addon.getLocalizedString(30304))
        plugin.log.error('Could not connect to %s/movie/%s?api_key=%s' %(BASE_URL, imdb_id, API_KEY))

def search(query):
    from kodipopcorntime.utils import url_get_json
    return url_get_json("%s/search/movie" % BASE_URL, params={"api_key": API_KEY, "query": query, "language": "en"}, headers=HEADERS)


def get_list_item(meta):
    from kodipopcorntime.utils import first

    def img(key, size="original", default=""):
        return meta.get(key) and image(meta[key], size=size) or default
    def m(key, default=""):
        return meta.get(key) or default
    def m_crew(job):
        return first([crew["name"] for crew in (m("credits", default={}).get("crew") or []) if crew["job"] == job])
    def get_studio():
        return (first(sorted(m("production_companies") or [], key=lambda x: x["id"])) or {}).get("name") or ""

    return {
        "label": m("title"),
        "icon": img("poster_path", size="w500"),
        "thumbnail": img("poster_path", size="w500"),
        "is_playable": True,
        "info": {
            "title": m("title"),
            "originaltitle": m("original_title"),
            "genre": meta.get("genres") and " / ".join([genre["name"] for genre in meta["genres"]]) or "",
            "plot": m("overview"),
            "plot_outline": m("overview"),
            "tagline": m("tagline"),
            "rating": m("vote_average"),
            "duration": m("runtime", 0),
            "code": m("imdb_id"),
            "cast": [cast["name"] for cast in (m("credits", default={}).get("cast") or [])],
            "director": m_crew("Director"),
            "writer": m_crew("Writer") or m_crew("Novel") or m_crew("Screenplay"),
            "studio": get_studio(),
            "year": meta.get("release_date") and meta["release_date"].split("-")[0] or "",
        },
        "properties": {
            "fanart_image": img("backdrop_path"),
        },
    }
