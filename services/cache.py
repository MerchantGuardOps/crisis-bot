<<<<<<< Updated upstream
"""
Redis caching layer for hot data
Moves read pressure off PostgreSQL during spikes
"""
import os, aioredis, json, asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://10.79.124.171:6379/0")
_redis = None
_lock = asyncio.Lock()

async def get_redis():
    """Get Redis connection (singleton per instance)"""
    global _redis
    if _redis is None:
        async with _lock:
            if _redis is None:
                logger.info(f"Connecting to Redis: {REDIS_URL}")
                _redis = await aioredis.from_url(
                    REDIS_URL, 
                    encoding="utf-8", 
                    decode_responses=True,
                    socket_keepalive=True,
                    retry_on_timeout=True
                )
                logger.info("✅ Redis connection established")
    return _redis

async def cache_json(key: str, obj: Any, ttl: int = 300):
    """Cache JSON-serializable object"""
    try:
        r = await get_redis()
        await r.set(key, json.dumps(obj, default=str), ex=ttl)
        logger.debug(f"Cached {key} (TTL: {ttl}s)")
    except Exception as e:
        logger.error(f"Cache set error for {key}: {e}")

async def get_json(key: str) -> Optional[Any]:
    """Get cached JSON object"""
    try:
        r = await get_redis()
        s = await r.get(key)
        if s:
            logger.debug(f"Cache hit: {key}")
            return json.loads(s)
        logger.debug(f"Cache miss: {key}")
        return None
    except Exception as e:
        logger.error(f"Cache get error for {key}: {e}")
        return None

async def cached_call(key: str, loader_func, ttl: int = 300):
    """Get from cache or call loader function and cache result"""
    # Try cache first
    cached = await get_json(key)
    if cached is not None:
        return cached
    
    # Call loader and cache result
    try:
        result = await loader_func() if asyncio.iscoroutinefunction(loader_func) else loader_func()
        await cache_json(key, result, ttl)
        return result
    except Exception as e:
        logger.error(f"Loader function failed for {key}: {e}")
        raise

async def invalidate(key: str):
    """Remove key from cache"""
    try:
        r = await get_redis()
        await r.delete(key)
        logger.debug(f"Invalidated cache key: {key}")
    except Exception as e:
        logger.error(f"Cache invalidation error for {key}: {e}")

async def get_cache_stats():
    """Get Redis cache statistics for monitoring"""
    try:
        r = await get_redis()
        info = await r.info("stats")
        return {
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_ratio": info.get("keyspace_hits", 0) / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)),
            "evictions": info.get("evicted_keys", 0),
            "memory_usage": info.get("used_memory", 0)
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"error": str(e)}

# Hot data caching patterns
async def cache_merchant_profile(merchant_id: str, profile_data: dict, ttl: int = 300):
    """Cache non-PII merchant profile subset"""
    key = f"merchant_profile:{merchant_id}"
    # Remove PII fields before caching
    safe_profile = {k: v for k, v in profile_data.items() 
                   if k not in ['legal_name', 'tax_id', 'email', 'phone']}
    await cache_json(key, safe_profile, ttl)

async def get_cached_merchant_profile(merchant_id: str):
    """Get cached merchant profile"""
    key = f"merchant_profile:{merchant_id}"
    return await get_json(key)

async def cache_guardscore_summary(user_id: str, score_data: dict, ttl: int = 300):
    """Cache GuardScore summary for fast retrieval"""
    key = f"guardscore_summary:{user_id}"
    await cache_json(key, score_data, ttl)

async def get_cached_guardscore_summary(user_id: str):
    """Get cached GuardScore summary"""
    key = f"guardscore_summary:{user_id}"
    return await get_json(key)

async def cache_provider_stats(stats_data: dict, ttl: int = 900):
    """Cache provider success stats (15min TTL)"""
    key = "provider_success_mv_snapshot"
    await cache_json(key, stats_data, ttl)

async def get_cached_provider_stats():
    """Get cached provider statistics"""
    key = "provider_success_mv_snapshot"
    return await get_json(key)

async def close_redis():
    """Close Redis connection gracefully"""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("Redis connection closed")
=======
async def get_redis():
    return None

async def get_cache_stats():
    return {"status": "ok"}
>>>>>>> Stashed changes
