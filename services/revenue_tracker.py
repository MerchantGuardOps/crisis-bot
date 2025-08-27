from typing import Optional, Dict, List
import datetime as dt

class RevenueTracker:
    """Track revenue across all MerchantGuard products"""
    
    def __init__(self, pool):
        self.pool = pool

    async def log_sale(self, merchant_id: str, product: str, amount_usd: float, 
                      source: str = 'stripe', meta: Optional[Dict] = None):
        """
        Log a sale/revenue event.
        
        Args:
            merchant_id: Unique merchant identifier
            product: Product SKU (VAMP_199, MATCH_499, ATTEST_49, etc.)
            amount_usd: Amount in USD
            source: Payment source (stripe, manual, promo, etc.)
            meta: Additional metadata (payment_intent_id, discount_code, etc.)
        """
        cents = int(round(amount_usd * 100))
        
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO revenue_events 
                    (merchant_id, product, amount_cents, currency, source, meta)
                VALUES ($1, $2, $3, 'USD', $4, $5)
            """, merchant_id, product, cents, source, meta or {})

    async def log_match_purchase(self, merchant_id: str, payment_intent_id: str):
        """Convenience method for MATCH package purchases"""
        await self.log_sale(
            merchant_id=merchant_id,
            product='MATCH_499',
            amount_usd=499.0,
            source='stripe',
            meta={'payment_intent_id': payment_intent_id, 'package_type': 'hybrid'}
        )

    async def log_vamp_purchase(self, merchant_id: str, payment_intent_id: str):
        """Convenience method for VAMP package purchases"""
        await self.log_sale(
            merchant_id=merchant_id,
            product='VAMP_199',
            amount_usd=199.0,
            source='stripe',
            meta={'payment_intent_id': payment_intent_id, 'package_type': 'prevention'}
        )

    async def get_monthly_report(self) -> List[Dict]:
        """Get monthly revenue breakdown by product"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT date_trunc('month', created_at) AS month, 
                       product,
                       COUNT(*) as transactions,
                       SUM(amount_cents)/100.0 AS revenue_usd,
                       AVG(amount_cents)/100.0 AS avg_sale_usd
                FROM revenue_events
                GROUP BY 1, 2 
                ORDER BY 1 DESC, 2
            """)
            return [dict(r) for r in rows]

    async def get_daily_revenue(self, days: int = 30) -> List[Dict]:
        """Get daily revenue for the last N days"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT date_trunc('day', created_at) AS day,
                       COUNT(*) as transactions,
                       SUM(amount_cents)/100.0 AS revenue_usd
                FROM revenue_events 
                WHERE created_at >= NOW() - INTERVAL '%s days'
                GROUP BY 1 
                ORDER BY 1 DESC
            """, days)
            return [dict(r) for r in rows]

    async def get_merchant_purchases(self, merchant_id: str) -> List[Dict]:
        """Get all purchases for a specific merchant"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT product, amount_cents/100.0 as amount_usd, 
                       source, meta, created_at
                FROM revenue_events 
                WHERE merchant_id = $1 
                ORDER BY created_at DESC
            """, merchant_id)
            return [dict(r) for r in rows]

    async def get_product_performance(self) -> List[Dict]:
        """Get performance metrics by product"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT product,
                       COUNT(*) as total_sales,
                       SUM(amount_cents)/100.0 as total_revenue,
                       AVG(amount_cents)/100.0 as avg_sale_price,
                       MIN(created_at) as first_sale,
                       MAX(created_at) as latest_sale
                FROM revenue_events 
                GROUP BY product 
                ORDER BY total_revenue DESC
            """)
            return [dict(r) for r in rows]

    async def calculate_ltv_by_cohort(self) -> List[Dict]:
        """Calculate customer LTV by acquisition month"""
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                WITH merchant_cohorts AS (
                    SELECT merchant_id, 
                           date_trunc('month', MIN(created_at)) as cohort_month
                    FROM revenue_events 
                    GROUP BY merchant_id
                ),
                revenue_by_cohort AS (
                    SELECT mc.cohort_month,
                           COUNT(DISTINCT re.merchant_id) as merchants,
                           SUM(re.amount_cents)/100.0 as total_revenue,
                           AVG(re.amount_cents)/100.0 as avg_revenue_per_transaction
                    FROM merchant_cohorts mc
                    JOIN revenue_events re ON mc.merchant_id = re.merchant_id
                    GROUP BY mc.cohort_month
                )
                SELECT cohort_month,
                       merchants,
                       total_revenue,
                       total_revenue / merchants as ltv_per_merchant,
                       avg_revenue_per_transaction
                FROM revenue_by_cohort
                ORDER BY cohort_month DESC
            """)
            return [dict(r) for r in rows]

    async def get_conversion_funnel(self) -> Dict:
        """Get basic conversion metrics (requires additional tracking)"""
        async with self.pool.acquire() as con:
            # This would need additional event tracking for full funnel analysis
            total_purchases = await con.fetchval("SELECT COUNT(*) FROM revenue_events")
            unique_customers = await con.fetchval("SELECT COUNT(DISTINCT merchant_id) FROM revenue_events")
            
            return {
                'total_purchases': total_purchases,
                'unique_customers': unique_customers,
                'repeat_purchase_rate': (total_purchases - unique_customers) / max(unique_customers, 1)
            }