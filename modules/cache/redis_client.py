import json
from typing import Optional
import redis
from loguru import logger
from config import settings

_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
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
            logger.warning(f"Redis unavailable: {e}")
            _redis_client = None
    return _redis_client

def get_cached_result(query_hash: str):
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(f"a23:query:{query_hash}")
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None

def set_cached_result(query_hash: str, result: dict, ttl: int = None) -> bool:
    client = _get_redis()
    if client is None:
        return False
    ttl = ttl or settings.redis_ttl
    try:
        client.setex(f"a23:query:{query_hash}", ttl, json.dumps(result, ensure_ascii=False))
        return True
    except Exception as e:
        logger.warning(f"Cache write error: {e}")
        return False

def invalidate_cache(pattern: str = "*") -> int:
    client = _get_redis()
    if client is None:
        return 0
    try:
        keys = client.keys(f"a23:query:{pattern}")
        return client.delete(*keys) if keys else 0
    except Exception as e:
        logger.warning(f"Cache clear error: {e}")
        return 0
