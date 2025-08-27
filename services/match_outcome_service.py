import asyncpg
from typing import Optional

class MatchOutcomeService:
    """Service for tracking MATCH recovery outcomes and interactions"""
    
    def __init__(self, pool: asyncpg.pool.Pool):
        self.pool = pool

    async def log_interaction(self, merchant_id: str, week: int, response: str, outcome: Optional[str]=None):
        """Log interactive check-in response"""
        async with self.pool.acquire() as con:
            await con.execute("""
              INSERT INTO match_interactions (merchant_id, week_number, response, outcome)
              VALUES ($1,$2,$3,$4)
            """, merchant_id, week, response, outcome)

    async def record_application_submission(self, merchant_id: str, provider: str):
        """Record when merchant submits application to provider"""
        async with self.pool.acquire() as con:
            await con.execute("""
              INSERT INTO match_outcomes (merchant_id, provider, applied_date, outcome)
              VALUES ($1,$2, CURRENT_DATE, 'pending')
              ON CONFLICT DO NOTHING
            """, merchant_id, provider)

    async def record_outcome(self, merchant_id: str, provider: str, approved: bool, reserve_percent: Optional[float]=None):
        """Record final outcome (approved/rejected) from provider"""
        outcome = 'approved' if approved else 'rejected'
        async with self.pool.acquire() as con:
            await con.execute("""
              UPDATE match_outcomes
              SET outcome = $3, response_date = CURRENT_DATE, reserve_percent = COALESCE($4, reserve_percent)
              WHERE merchant_id=$1 AND provider=$2 AND outcome IN ('pending','rejected','approved')
            """, merchant_id, provider, outcome, reserve_percent)

    async def get_merchant_applications(self, merchant_id: str):
        """Get all applications for a merchant"""
        async with self.pool.acquire() as con:
            return await con.fetch("""
              SELECT provider, applied_date, response_date, outcome, reserve_percent
              FROM match_outcomes 
              WHERE merchant_id = $1
              ORDER BY applied_date DESC
            """, merchant_id)