<<<<<<< Updated upstream
# infra/security_filters.py
"""
Security filters for logging and request handling
Prevents PII leakage and adds security controls
"""

import re
import logging
import hmac
import os
import time
from typing import Optional

# PII masking patterns
MASK = "[REDACTED]"
PII_PATTERNS = [
    re.compile(r'([\w\.-]+@[\w\.-]+\.\w+)'),     # emails
    re.compile(r'(\+?\d[\d\-\s]{7,}\d)'),        # phones  
    re.compile(r'(0x[a-fA-F0-9]{40})'),          # eth addresses
    re.compile(r'([1-9A-HJ-NP-Za-km-z]{25,35})'), # btc-ish addresses
    re.compile(r'(\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b)'),  # credit cards
    re.compile(r'(\bsk_[a-zA-Z0-9_]{24,})\b'),   # stripe secret keys
    re.compile(r'(\brk_[a-zA-Z0-9_]{24,})\b'),   # stripe restricted keys
]

class PiiMaskFilter(logging.Filter):
    """Filter that masks PII in log messages"""
    
    def filter(self, record):
        if hasattr(record, 'msg') and record.msg:
            msg = str(record.msg)
            for pattern in PII_PATTERNS:
                msg = pattern.sub(MASK, msg)
            record.msg = msg
            record.args = ()
        return True

class WebhookSecurityValidator:
    """Validates webhook requests for security"""
    
    def __init__(self):
        self.telegram_secret = os.getenv("TG_WEBHOOK_SECRET")
        self.replay_window = 300  # 5 minutes
        self.seen_events = {}  # In production, use Redis
    
    def validate_telegram_webhook(self, secret_token: Optional[str]) -> bool:
        """Validate Telegram webhook secret token"""
        if not self.telegram_secret:
            logging.warning("TG_WEBHOOK_SECRET not set - webhook validation disabled")
            return True
        
        if not secret_token:
            logging.warning("Missing X-Telegram-Bot-Api-Secret-Token header")
            return False
            
        return hmac.compare_digest(secret_token, self.telegram_secret)
    
    def validate_payment_webhook(self, event_id: str, signature: str, expected_sig: str) -> bool:
        """Validate payment webhook with replay protection"""
        # Check for replay
        if self.is_replay(event_id):
            logging.warning(f"Webhook replay attempt: {event_id}")
            return False
        
        # Verify signature
        if not hmac.compare_digest(signature, expected_sig):
            logging.warning(f"Invalid webhook signature: {event_id}")
            return False
        
        # Record event to prevent replay
        self.record_event(event_id)
        return True
    
    def is_replay(self, event_id: str) -> bool:
        """Check if event was already processed (simple in-memory cache)"""
        now = time.time()
        
        # Clean old entries
        expired = [eid for eid, ts in self.seen_events.items() if now - ts > self.replay_window]
        for eid in expired:
            del self.seen_events[eid]
        
        return event_id in self.seen_events
    
    def record_event(self, event_id: str):
        """Record processed event"""
        self.seen_events[event_id] = time.time()

# Global instance
webhook_validator = WebhookSecurityValidator()
=======
import logging

class PiiMaskFilter(logging.Filter):
    def filter(self, record):
        return True
>>>>>>> Stashed changes
