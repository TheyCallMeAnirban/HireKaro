"""
cache.py — In-memory JD result cache with TTL + LRU eviction.

Replaces Redis for local/single-process deployments.
Same hash(JD) → result logic; swap for Redis by replacing get/set calls.
"""
import time
import hashlib
from config import get_logger

log = get_logger(__name__)

_store: dict[str, tuple[dict, float]] = {}   # key -> (result, stored_at) 
CACHE_TTL   = 3600   # seconds — cached results expire after 1 hour
MAX_ENTRIES = 200    # max entries before LRU eviction kicks in


def _key(jd_text: str) -> str:
    return hashlib.sha256(jd_text.strip().lower().encode()).hexdigest()


def get_cached(jd_text: str) -> dict | None:
    """Return cached result if it exists and hasn't expired."""
    k = _key(jd_text)
    if k in _store:
        result, ts = _store[k]
        if time.time() - ts < CACHE_TTL:
            log.info("cache.hit", extra={"key": k[:8]})
            return result
        del _store[k]   # expired — evict silently
    return None


def set_cached(jd_text: str, result: dict) -> None:
    """Store a result. Evicts the oldest entry if the store is full."""
    if len(_store) >= MAX_ENTRIES:
        oldest = min(_store, key=lambda k: _store[k][1])
        del _store[oldest]
        log.info("cache.evict", extra={"evicted": oldest[:8]})
    k = _key(jd_text)
    _store[k] = (result, time.time())
    log.info("cache.set", extra={"key": k[:8], "size": len(_store)})


def invalidate(jd_text: str) -> bool:
    """Manually remove a cached result (e.g. after data changes)."""
    k = _key(jd_text)
    if k in _store:
        del _store[k]
        return True
    return False


def stats() -> dict:
    now   = time.time()
    valid = sum(1 for _, (_, ts) in _store.items() if now - ts < CACHE_TTL)
    return {"total": len(_store), "valid": valid, "ttl_seconds": CACHE_TTL,
            "max_entries": MAX_ENTRIES}
