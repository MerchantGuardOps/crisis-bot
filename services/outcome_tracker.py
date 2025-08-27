import asyncpg
import datetime as dt
from typing import Optional

class OutcomeTracker:
    """Track merchant outcomes for provider success rate calculation"""
    
    def __init__(self, pool):
        self.pool = pool

    async def log_interaction(self, merchant_id: str, week: int, question: str, response: str):
        """Log a check-in interaction response"""
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO match_interactions (merchant_id, check_in_week, question, response)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, merchant_id, week, question, response)

    async def log_outcome(self, merchant_id: str, provider: str, 
                         outcome: str, applied_date: Optional[dt.date] = None,
                         response_date: Optional[dt.date] = None, 
                         reserve_percent: Optional[float] = None,
                         notes: Optional[str] = None, 
                         verification_level: int = 1):
        """
        Log a provider application outcome.
        
        Args:
            merchant_id: Unique merchant identifier
            provider: Provider name (fastspring, durango, etc.)
            outcome: 'approved', 'rejected', or 'pending'
            applied_date: When application was submitted
            response_date: When provider responded (if known)
            reserve_percent: Reserve percentage if approved
            notes: Additional notes about the outcome
            verification_level: 1=self-report, 2=screenshot, 3=dashboard
        """
        applied_date = applied_date or dt.date.today()
        
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO match_outcomes
                    (merchant_id, provider, applied_date, response_date, outcome, 
                     reserve_percent, notes, verification_level)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (merchant_id, provider, applied_date) 
                DO UPDATE SET
                    response_date = EXCLUDED.response_date,
                    outcome = EXCLUDED.outcome,
                    reserve_percent = EXCLUDED.reserve_percent,
                    notes = EXCLUDED.notes,
                    verification_level = EXCLUDED.verification_level
            """, merchant_id, provider, applied_date, response_date, 
                 outcome, reserve_percent, notes, verification_level)

    async def get_merchant_outcomes(self, merchant_id: str):
        """Get all outcomes for a specific merchant"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT provider, applied_date, response_date, outcome, 
                       reserve_percent, notes, verification_level, created_at
                FROM match_outcomes 
                WHERE merchant_id = $1 
                ORDER BY applied_date DESC
            """, merchant_id)
            return [dict(row) for row in rows]

    async def get_provider_stats(self, provider: str):
        """Get stats for a specific provider"""
        async with self.pool.acquire() as con:
            row = await con.fetchrow("""
                SELECT provider, decided, approved, success_ratio, avg_days
                FROM provider_success_mv 
                WHERE provider = $1
            """, provider)
            return dict(row) if row else None

    async def refresh_success_rates(self):
        """Refresh the materialized view (call nightly)"""
        async with self.pool.acquire() as con:
            await con.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY provider_success_mv")

    async def get_merchant_interactions(self, merchant_id: str):
        """Get all check-in interactions for a merchant"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT check_in_week, question, response, responded_at
                FROM match_interactions 
                WHERE merchant_id = $1 
                ORDER BY check_in_week, responded_at
            """, merchant_id)
            return [dict(row) for row in rows]

    # Convenience methods for common outcome patterns
    async def log_application_submitted(self, merchant_id: str, provider: str, 
                                      applied_date: Optional[dt.date] = None):
        """Log that an application was submitted (pending outcome)"""
        await self.log_outcome(merchant_id, provider, 'pending', applied_date)

    async def log_approval(self, merchant_id: str, provider: str, 
                          reserve_percent: Optional[float] = None,
                          response_date: Optional[dt.date] = None,
                          notes: Optional[str] = None):
        """Log a provider approval"""
        await self.log_outcome(merchant_id, provider, 'approved', 
                             response_date=response_date,
                             reserve_percent=reserve_percent, 
                             notes=notes)

    async def log_rejection(self, merchant_id: str, provider: str,
                           response_date: Optional[dt.date] = None,
                           reason: Optional[str] = None):
        """Log a provider rejection"""
        await self.log_outcome(merchant_id, provider, 'rejected',
                             response_date=response_date,
                             notes=reason)