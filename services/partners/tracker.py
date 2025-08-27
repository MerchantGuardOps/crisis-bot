import hmac, hashlib, time, urllib.parse
from typing import Dict, Any, Optional
import asyncpg
from fastapi import HTTPException

class PartnerTracker:
    def __init__(self, pool: asyncpg.pool.Pool, base_url: str, secret: str):
        self.pool = pool
        self.base = base_url.rstrip("/")
        self.secret = secret.encode("utf-8")

    def signed_redirect_url(self, provider: str, user_id: str, source: str) -> str:
        """
        Generates /r/{provider}?u=...&s=...&t=...
        We log the click on GET and 302 to real provider URL.
        """
        t = str(int(time.time()))
        q = f"provider={provider}&u={user_id}&source={source}&t={t}"
        sig = hmac.new(self.secret, q.encode("utf-8"), hashlib.sha256).hexdigest()
        qp = urllib.parse.urlencode({"u": user_id, "s": sig, "t": t, "source": source})
        return f"{self.base}/r/{provider}?{qp}"

    def verify(self, provider: str, user_id: str, source: str, t: str, sig: str) -> bool:
        msg = f"provider={provider}&u={user_id}&source={source}&t={t}"
        want = hmac.new(self.secret, msg.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(want, sig)

    async def log_click(self, *, user_id: str, provider: str, source: str, user_agent: Optional[str], ip_hash: Optional[str], meta: Optional[Dict[str, Any]] = None):
        import json
        async with self.pool.acquire() as con:
            meta_json = json.dumps(meta or {})
            await con.execute("""
                INSERT INTO internal_referral_tracking (user_id, provider, source, user_agent, ip_hash, meta)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """, user_id, provider, source, user_agent, ip_hash, meta_json)

    async def pipeline_report(self) -> Dict[str, Any]:
        async with self.pool.acquire() as con:
            rows = await con.fetch("""
                SELECT provider, source, COUNT(*) AS clicks
                FROM internal_referral_tracking
                GROUP BY provider, source
                ORDER BY clicks DESC
            """)
        return {"items": [dict(r) for r in rows]}
