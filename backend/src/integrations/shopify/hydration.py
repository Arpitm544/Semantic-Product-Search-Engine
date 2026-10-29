"""Bounded short-lived detail cache. Never serve expired price/availability."""
import time
from threading import Lock
from .queries import DETAILS

_cache = {}
_lock = Lock()


def invalidate(shop):
    with _lock:
        for key in list(_cache):
            if key[0] == shop:
                del _cache[key]


def hydrate(client, ids):
    s = client.settings
    values, missing = {}, []
    with _lock:
        for gid in ids:
            cached = _cache.get((s.shop, gid))
            if cached and cached[0] > time.monotonic():
                values[gid] = cached[1]
            else:
                missing.append(gid)
    for offset in range(0, len(missing), 100):
        chunk = missing[offset:offset + 100]
        nodes = client.query(DETAILS, {'ids': chunk}, storefront=True)['nodes']
        if len(nodes) != len(chunk):
            raise ValueError('Incomplete Shopify details.')
        with _lock:
            for gid, node in zip(chunk, nodes):
                values[gid] = node
                _cache[(s.shop, gid)] = (time.monotonic() + s.ttl, node)
            while len(_cache) > 2000:
                del _cache[next(iter(_cache))]
    return values
