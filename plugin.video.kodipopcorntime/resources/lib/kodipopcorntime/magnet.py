PUBLIC_TRACKERS = [
    "udp://tracker.publicbt.com:80/announce",
    "udp://tracker.openbittorrent.com:80/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.istole.it:6969",
    "udp://tracker.coppersurfer.tk:80",
    "udp://open.demonii.com:1337",
    "udp://tracker.istole.it:80",
    "http://tracker.yify-torrents.com/announce",
    "udp://tracker.publicbt.com:80",
    "udp://tracker.openbittorrent.com:80",
    "udp://tracker.coppersurfer.tk:6969",
    "udp://exodus.desync.com:6969",
    "http://exodus.desync.com:6969/announce",
]

def from_meta_data(torrent_hash, title, quality):
    import urllib
    name = "%s [%s]" %(title, quality)
    return "magnet:?xt=urn:btih:%s&%s" % (torrent_hash, urllib.urlencode({'dn' : name, 'tr': PUBLIC_TRACKERS}, doseq=True))

def display_name(magnet_uri):
    import urlparse
    from kodipopcorntime.utils import first
    magnet_args = urlparse.parse_qs(magnet_uri.replace("magnet:?", ""))
    return first(magnet_args.get("dn", []))