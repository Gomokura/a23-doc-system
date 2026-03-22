import os

# 1. requirements.txt
with open('requirements.txt', 'r', encoding='utf-8') as f:
    c = f.read()
if 'redis==5.0.0' not in c:
    with open('requirements.txt', 'a', encoding='utf-8') as f:
        f.write('\nredis==5.0.0\n')
print('OK requirements.txt')

# 2. config.py
with open('config.py', 'r', encoding='utf-8') as f:
    c = f.read()
if 'redis_host' not in c:
    c = c.replace(
        '    # 服务配置',
        '    # Redis\n    redis_host: str = "localhost"\n    redis_port: int = 6379\n    redis_db: int = 0\n    redis_ttl: int = 3600\n\n    # 服务配置'
    )
    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(c)
print('OK config.py')

# 3. 创建 modules/cache 目录
os.makedirs('modules/cache', exist_ok=True)
with open('modules/cache/__init__.py', 'a', encoding='utf-8') as f:
    pass
print('OK modules/cache/')

# 4. redis_client.py
code = """\
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
"""
with open('modules/cache/redis_client.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('OK modules/cache/redis_client.py')

print('\nDone! 接下来手动改 hybrid_retriever.py 和 api/query.py')