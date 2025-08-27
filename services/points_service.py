"""
Points Service - Idempotent point award system
"""
from typing import Optional, Dict, Any
from datetime import datetime

class PointsService:
    """
    Thin facade: uses your robust adapter if present; else no-op with logs.
    """
    def __init__(self, adapter=None, logger=print):
        self.adapter = adapter
        self.log = logger

    async def award(self, event_type: str, user_id: str, points: Optional[int] = None, meta: Optional[Dict[str,Any]] = None, idem_key: Optional[str] = None) -> bool:
        """Award points for an event type."""
        meta = meta or {}
        if self.adapter:
            try:
                # your existing adapter signature may differ; adapt as needed
                await self.adapter.award(user_id, event_type, meta=meta, idempotency_key=idem_key)
                return True
            except Exception as e:
                self.log(f"[points] adapter error {e}")
                return False
        self.log(f"[points] (noop) event={event_type} user={user_id} meta={meta}")
        return True

    async def get_balance(self, user_id: str) -> int:
        """Get current point balance."""
        if self.adapter and hasattr(self.adapter, 'get_balance'):
            try:
                return await self.adapter.get_balance(user_id)
            except Exception as e:
                self.log(f"[points] get_balance error {e}")
        return 0

    async def transfer(self, from_user: str, to_user: str, amount: int, reason: str = None) -> bool:
        """Transfer points between users."""
        if self.adapter and hasattr(self.adapter, 'transfer'):
            try:
                return await self.adapter.transfer(from_user, to_user, amount, reason)
            except Exception as e:
                self.log(f"[points] transfer error {e}")
                return False
        self.log(f"[points] (noop) transfer {amount} from {from_user} to {to_user}")
        return True