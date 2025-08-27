<<<<<<< Updated upstream
# infra/cache.py
"""
Redis caching layer for performance optimization
"""

import json
import logging
import os
from typing import Any, Callable, Optional, Union
import aioredis

logger = logging.getLogger(__name__)

class CacheManager:
    """Redis-based cache manager"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.enabled = False
        
    async def initialize(self):
        """Initialize Redis connection"""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            logger.warning("REDIS_URL not set - caching disabled")
            return
            
        try:
            self.redis = aioredis.from_url(
                redis_url, 
                encoding="utf-8", 
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True
            )
            # Test connection
            await self.redis.ping()
            self.enabled = True
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.enabled = False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled:
            return None
            
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.enabled:
            return False
            
        try:
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled:
            return False
            
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def cached_call(self, key: str, loader: Callable, ttl: int = 300) -> Any:
        """Get cached result or call loader function"""
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached
        
        # Call loader function
        result = await loader() if callable(loader) else loader
        
        # Cache the result
        await self.set(key, result, ttl)
        return result
    
    async def increment(self, key: str, amount: int = 1, ttl: int = 3600) -> int:
        """Increment a counter with TTL"""
        if not self.enabled:
            return 0
            
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key, amount)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0

# Global cache instance
cache = CacheManager()

# Convenience functions
async def cached_json(key: str, loader: Callable, ttl: int = 300) -> Any:
    """Cache JSON data with automatic serialization"""
    return await cache.cached_call(key, loader, ttl)

async def rate_limit_check(identifier: str, limit: int, window: int = 60) -> bool:
    """Check if identifier is within rate limit"""
    key = f"ratelimit:{identifier}"
    count = await cache.increment(key, ttl=window)
    return count <= limit
=======
class Cache:
    async def initialize(self):
        pass

cache = Cache()
>>>>>>> Stashed changes
