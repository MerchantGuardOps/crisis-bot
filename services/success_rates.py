import asyncpg
from typing import Dict

async def load_provider_stats(pool) -> Dict[str, Dict]:
    """Load observed success rates and average timeframes from database"""
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT provider, success_ratio, avg_days FROM provider_success_mv")
        return {r['provider']: {'success': float(r['success_ratio'] or 0.0),
                                'days': float(r['avg_days'] or 0.0)} for r in rows}