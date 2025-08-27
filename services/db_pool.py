<<<<<<< Updated upstream
"""
Database connection pooling with smart scaling controls
Prevents connection exhaustion when Cloud Run scales out
"""
import os, asyncpg, asyncio
import logging

logger = logging.getLogger(__name__)

# Pool sizing based on scaling runbook formula
POOL_MIN = int(os.getenv("POOL_MIN", "2"))
POOL_MAX = int(os.getenv("POOL_MAX", "7"))
POOL_MAX_LIFETIME = int(os.getenv("POOL_MAX_LIFETIME_SEC", "120"))
DSN = os.getenv("DATABASE_URL")

_pool = None
_pool_lock = asyncio.Lock()

async def get_pool():
    """Get connection pool (singleton per instance)"""
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                logger.info(f"Creating DB pool: min={POOL_MIN}, max={POOL_MAX}, lifetime={POOL_MAX_LIFETIME}s")
                _pool = await asyncpg.create_pool(
                    dsn=DSN,
                    min_size=POOL_MIN,
                    max_size=POOL_MAX,
                    max_inactive_connection_lifetime=POOL_MAX_LIFETIME,
                    statement_cache_size=1024,
                    command_timeout=30
                )
                logger.info("✅ DB pool created successfully")
    return _pool

async def get_pool_stats():
    """Get pool statistics for monitoring"""
    if _pool is None:
        return {"status": "not_initialized"}
    
    return {
        "size": _pool.get_size(),
        "idle": _pool.get_idle_size(),
        "min_size": _pool.get_min_size(),
        "max_size": _pool.get_max_size(),
        "utilization": (_pool.get_size() - _pool.get_idle_size()) / _pool.get_max_size()
    }

async def close_pool():
    """Close pool gracefully"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("DB pool closed")

# Context manager for transactions
class PooledConnection:
    def __init__(self, pool):
        self.pool = pool
        self.conn = None
        
    async def __aenter__(self):
        self.conn = await self.pool.acquire()
        return self.conn
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.pool.release(self.conn)

async def get_connection():
    """Get managed connection (use with async with)"""
    pool = await get_pool()
    return PooledConnection(pool)
=======
import asyncpg

async def get_pool():
    return None

async def get_pool_stats():
    return {"status": "ok"}
>>>>>>> Stashed changes
