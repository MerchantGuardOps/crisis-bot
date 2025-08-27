import os
import hmac
import hashlib
import urllib.parse
from typing import Optional, Dict, Any
import asyncpg
from datetime import datetime, timezone


class AffiliateTracker:
    """
    High-ROI affiliate tracking system for MerchantGuard partner integrations.
    Handles PSP handoffs, legal referrals, LLC formation with full attribution.
    """
    
    def __init__(self, pool: asyncpg.pool.Pool, base_url: str, hmac_secret: str):
        self.pool = pool
        self.base_url = base_url.rstrip("/")
        self.hmac_secret = bytes(hmac_secret, "utf-8")

    async def create_offer(
        self,
        merchant_id: str,
        *,
        offer_type: str,
        partner_key: str,
        affiliate_link: str,
        payout_estimated: float,
        source: str,
        purchase_id: Optional[str] = None
    ) -> int:
        """Create a new partner offer with tracking."""
        async with self.pool.acquire() as con:
            row = await con.fetchrow("""
                INSERT INTO partner_referrals (
                    merchant_id, offer_type, partner_key, status,
                    affiliate_link, payout_estimated, source, purchase_id, updated_at
                )
                VALUES ($1,$2,$3,'offered',$4,$5,$6,$7,NOW())
                RETURNING id
            """, merchant_id, offer_type, partner_key, affiliate_link, 
                 payout_estimated, source, purchase_id)
            return int(row["id"])

    async def update_status(self, referral_id: int, status: str):
        """Update referral status with timestamp."""
        async with self.pool.acquire() as con:
            await con.execute(
                "UPDATE partner_referrals SET status=$1, updated_at=NOW() WHERE id=$2",
                status, referral_id
            )

    async def record_click(
        self,
        referral_id: int,
        merchant_id: str,
        partner_key: str,
        user_agent: str,
        dest_url: str
    ):
        """Record affiliate click and update referral status."""
        async with self.pool.acquire() as con:
            await con.execute("""
                INSERT INTO partner_clicks (referral_id, merchant_id, partner_key, user_agent, dest_url)
                VALUES ($1,$2,$3,$4,$5)
            """, referral_id, merchant_id, partner_key, user_agent, dest_url)
            
            # Move referral to 'clicked' if still earlier in funnel
            await con.execute("""
                UPDATE partner_referrals SET status='clicked', updated_at=NOW()
                WHERE id=$1 AND status IN ('offered','accepted','intro_sent')
            """, referral_id)

    def signed_redirect(
        self,
        referral_id: int,
        partner_key: str,
        dest_url: str,
        merchant_id: str
    ) -> str:
        """
        Generate secure signed redirect URL.
        Returns /r/partner?rid=&k=&u=&m=&sig= (HMAC-SHA256 signed)
        """
        rid = str(referral_id)
        u_enc = urllib.parse.quote_plus(dest_url)
        base = f"{rid}|{partner_key}|{u_enc}|{merchant_id}"
        sig = hmac.new(self.hmac_secret, base.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{self.base_url}/r/partner?rid={rid}&k={partner_key}&u={u_enc}&m={merchant_id}&sig={sig}"

    def verify_sig(self, rid: str, k: str, u: str, m: str, sig: str) -> bool:
        """Verify HMAC signature for redirect security."""
        base = f"{rid}|{k}|{u}|{m}"
        calc = hmac.new(self.hmac_secret, base.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(calc, sig)

    async def build_intro_email(
        self,
        referral_id: int,
        merchant_summary: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Build warm intro email for PSP partners.
        Returns subject/body for manual or automated sending.
        """
        biz = merchant_summary
        partner_name = os.getenv('PARTNER_PSP_NAME', 'Partner')
        
        subject = f"[Intro] MATCH recovery merchant — {biz.get('legal_name','Unknown')} — {biz.get('country','')}"
        
        body = f"""Hi {partner_name} Team,

We're introducing a MATCH-listed merchant who purchased our MATCH Liberation package and requested a warm handoff:

• Legal name: {biz.get('legal_name')}
• Country: {biz.get('country')}
• Site: {biz.get('website')}
• Business model: {biz.get('business_model')}
• Monthly volume: ${biz.get('volume_monthly')}
• Avg ticket: ${biz.get('avg_ticket')}
• Current dispute rate (30d): {biz.get('dispute_rate_30d')}
• Notes: {biz.get('notes','(none provided)')}

They've implemented: 3DS default-on, AVS/CVV strict, 24h refunds, RDR/Ethoca auto-accept.

Please prioritize this intro if possible. We've advised the merchant to watch for your email.

Thanks!
MerchantGuard Intake
"""
        return {"subject": subject, "body": body}

    async def get_referral_stats(self, partner_key: Optional[str] = None) -> Dict[str, Any]:
        """Get referral performance statistics for reporting."""
        async with self.pool.acquire() as con:
            where_clause = "WHERE partner_key = $1" if partner_key else ""
            params = [partner_key] if partner_key else []
            
            rows = await con.fetch(f"""
                SELECT partner_key, offer_type, status, COUNT(*) as count,
                       SUM(payout_estimated) as total_payout
                FROM partner_referrals
                {where_clause}
                GROUP BY partner_key, offer_type, status
                ORDER BY partner_key, offer_type, status
            """, *params)
            
            return {"referral_stats": [dict(row) for row in rows]}

    async def get_monthly_pipeline(self) -> Dict[str, Any]:
        """Get current month pipeline view for revenue reporting."""
        async with self.pool.acquire() as con:
            rows = await con.fetch("SELECT * FROM partner_pipeline")
            pipeline = [dict(r) for r in rows]

            # Calculate EPC (earnings per click)
            epc = []
            for r in pipeline:
                top = r["top_funnel"] or 0
                payout = float(r["est_payouts"] or 0)
                epc_value = (payout / top) if top > 0 else 0.0
                epc.append({
                    "partner_key": r["partner_key"],
                    "offer_type": r["offer_type"],
                    "epc": epc_value
                })

            return {"partner_pipeline": pipeline, "epc": epc}

    async def update_from_outcome(
        self,
        merchant_id: str,
        partner_key: str,
        outcome_status: str
    ):
        """Update referral status based on PSP application outcome."""
        status_map = {
            "applied": "applied",
            "approved": "approved", 
            "rejected": "rejected"
        }
        
        if outcome_status in status_map:
            async with self.pool.acquire() as con:
                await con.execute("""
                    UPDATE partner_referrals
                    SET status=$1, updated_at=NOW()
                    WHERE merchant_id=$2 AND partner_key=$3
                      AND status IN ('applied','clicked','intro_sent','accepted')
                """, status_map[outcome_status], merchant_id, partner_key)