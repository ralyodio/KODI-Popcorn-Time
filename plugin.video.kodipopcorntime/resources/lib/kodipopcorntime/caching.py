import xbmc, os, threading
from kodipopcorntime.common import plugin, PLATFORM, CACHE_DIR
from contextlib import contextmanager, closing

LOCKS = {}

@contextmanager
def shelf(filename, ttl=0):
    import shelve
    filename = os.path.join(CACHE_DIR, filename)
    with LOCKS.get(filename, threading.RLock()):
        with closing(shelve.open(filename, writeback=True)) as d:
            import time
            if not d:
                d.update({
                    "created_at": time.time(),
                    "data": {},
                })
            elif ttl > 0 and (time.time() - d["created_at"]) > ttl:
                d["data"] = {}
            yield d["data"]

def cached_route(*args, **kwargs):
    from functools import wraps
    def cached(fn):
        @wraps(fn)
        def _fn(*a, **kwds):
            import hashlib
            basename = "kodipopcorntime.route.%s" % hashlib.sha1(plugin.request.path).hexdigest()
            with shelf(basename, ttl=kwargs.get("ttl") or 0) as result:
                if not result.get("value"):
                    ret = fn(*a, **kwds)
                    import types
                    if isinstance(ret, types.GeneratorType):
                        ret = list(ret)
                    result["value"] = ret
                if kwargs.get("content_type"):
                    plugin.set_content(kwargs.get("content_type"))
                return result["value"]
        return _fn
    if len(args) == 1 and callable(args[0]):
        return cached(args[0])
    return cached
