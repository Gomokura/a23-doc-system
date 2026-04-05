import json
import time
from loguru import logger
from config import settings

_redis_client = None

# ── 内存缓存（Redis 不可用时的兜底，进程内有效）─────────────────────
_mem_cache: dict = {}          # key -> (value_str, expire_at)
_MEM_TTL = 3600                # 默认 1 小时


def _mem_get(key: str):
    entry = _mem_cache.get(key)
    if entry is None:
        return None
    value_str, expire_at = entry
    if time.time() > expire_at:
        _mem_cache.pop(key, None)
        return None
    return value_str


def _mem_set(key: str, value_str: str, ttl: int = _MEM_TTL):
    _mem_cache[key] = (value_str, time.time() + ttl)


def _mem_delete_pattern(pattern: str) -> int:
    if pattern == "*":
        count = len(_mem_cache)
        _mem_cache.clear()
        return count
    keys = [k for k in list(_mem_cache.keys()) if pattern.strip("*") in k]
    for k in keys:
        _mem_cache.pop(k, None)
    return len(keys)


# ── Redis 连接（懒加载，失败后不重试，直接走内存缓存）──────────────
def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}，降级使用内存缓存")
            _redis_client = None
    return _redis_client


def get_cached_result(query_hash: str):
    key = f"a23:query:{query_hash}"
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

    # 降级：内存缓存
    raw = _mem_get(key)
    return json.loads(raw) if raw else None


def set_cached_result(query_hash: str, result: dict, ttl: int = None) -> bool:
    key = f"a23:query:{query_hash}"
    ttl = ttl or settings.redis_ttl
    value_str = json.dumps(result, ensure_ascii=False)

    client = _get_redis()
    if client is not None:
        try:
            client.setex(key, ttl, value_str)
            return True
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    # 降级：内存缓存
    _mem_set(key, value_str, ttl)
    return True


def invalidate_cache(pattern: str = "*") -> int:
    key_pattern = f"a23:query:{pattern}"
    total = 0

    client = _get_redis()
    if client is not None:
        try:
            keys = client.keys(key_pattern)
            total += client.delete(*keys) if keys else 0
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")

    # 同步清内存缓存
    total += _mem_delete_pattern(key_pattern)
    return total
