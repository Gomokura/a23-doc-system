import json
import time
from loguru import logger
from config import settings

_redis_client = None

# ── 内存缓存（Redis 不可用时的兜底，进程内有效）─────────────────────
# ⚠️ M3-009 修复: 使用有序字典实现 LRU 淘汰 + 容量上限，防止 OOM
from collections import OrderedDict

_mem_cache: OrderedDict = OrderedDict()  # key -> (value_str, expire_at)
_MEM_TTL = 3600                         # 默认 1 小时
_MEM_MAX_SIZE = 1000                     # 内存缓存最大条目数，超过则淘汰最旧条目


def _mem_evict_if_needed():
    """内存缓存超出容量上限时，淘汰最旧的（LRU）条目"""
    while len(_mem_cache) >= _MEM_MAX_SIZE:
        oldest_key, _ = _mem_cache.popitem(last=False)  # popitem(last=False) = FIFO，最旧
        logger.debug(f"[MEM_CACHE] LRU 淘汰: {oldest_key}, 剩余 {len(_mem_cache)} 条")


def _mem_get(key: str):
    entry = _mem_cache.get(key)
    if entry is None:
        return None
    value_str, expire_at = entry
    if time.time() > expire_at:
        _mem_cache.pop(key, None)
        return None
    _mem_cache.move_to_end(key)
    return value_str


def _mem_set(key: str, value_str: str, ttl: int = _MEM_TTL):
    _mem_evict_if_needed()
    _mem_cache[key] = (value_str, time.time() + ttl)
    _mem_cache.move_to_end(key)


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


# ── 问答缓存（key 由调用方构建，含 file_ids 信息）──────────────────
# key 格式: a23:query:<md5_hash>:fi:<file_ids_str>
# file_ids_str: 逗号分隔的有序 id，空则 "all"


def get_cached_result(cache_key: str):
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(cache_key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

    raw = _mem_get(cache_key)
    return json.loads(raw) if raw else None


def set_cached_result(cache_key: str, result: dict, ttl: int = None) -> bool:
    ttl = ttl or settings.redis_ttl
    value_str = json.dumps(result, ensure_ascii=False)

    client = _get_redis()
    if client is not None:
        try:
            client.setex(cache_key, ttl, value_str)
            return True
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    _mem_set(cache_key, value_str, ttl)
    return True


def invalidate_cache(pattern: str = "*", file_ids: list = None) -> int:
    """
    清除问答缓存。
    - invalidate_cache("*")                    → 清全部
    - invalidate_cache(file_ids=["id1","id2"]) → 只清涉及这些 file_id 的问答缓存
    """
    total = 0
    client = _get_redis()

    if file_ids:
        # 只清除涉及指定文件的缓存
        # key 格式: a23:query:<hash>:fi:<file_ids_str>
        mem_keys = list(_mem_cache.keys())
        for key in mem_keys:
            for fid in file_ids:
                if f":fi:{fid}" in key:
                    _mem_cache.pop(key, None)
                    total += 1
                    break

        if client is not None:
            for fid in file_ids:
                try:
                    keys = client.keys(f"a23:query:*:fi:{fid}")
                    if keys:
                        total += client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Cache clear error: {e}")

        logger.info(f"[CACHE] 按 file_ids 清缓存: {file_ids}, 清除 {total} 条")
        return total

    # ── 全部清除（原逻辑）──────────────────────────────────────────
    key_pattern = f"a23:query:{pattern}"
    if client is not None:
        try:
            keys = client.keys(key_pattern)
            total += client.delete(*keys) if keys else 0
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")

    total += _mem_delete_pattern(key_pattern)
    return total
