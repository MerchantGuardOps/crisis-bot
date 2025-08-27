"""
Payment Adapter Base Classes
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

@dataclass
class CheckoutResult:
    """Result from creating a checkout session."""
    provider: str
    order_id: str
    redirect_url: Optional[str] = None
    html: Optional[str] = None

@dataclass 
class PaymentEvent:
    """Webhook event from payment provider."""
    provider: str
    order_id: str
    provider_tx_id: str
    amount_cents: int
    currency: str
    status: str   # paid|failed|refunded
    raw: Dict = None

class ProductCodes:
    """Product code constants and utilities."""
    VAMP_199 = "VAMP_199"
    MATCH_499 = "MATCH_499" 
    ATTEST_49 = "ATTEST_49"
    
    # Legacy codes
    SKU_VAMP_PROTECTION_199 = "SKU_VAMP_PROTECTION_199"
    SKU_MATCH_HYBRID_499 = "SKU_MATCH_HYBRID_499"
    SKU_ATTEST_49 = "SKU_ATTEST_49"
    
    @classmethod
    def get_amount_cents(cls, product_code: str) -> int:
        """Get amount in cents for product code."""
        if product_code in [cls.VAMP_199, cls.SKU_VAMP_PROTECTION_199]:
            return 19900
        elif product_code in [cls.MATCH_499, cls.SKU_MATCH_HYBRID_499]:
            return 49900
        elif product_code in [cls.ATTEST_49, cls.SKU_ATTEST_49]:
            return 4900
        else:
            return 0
    
    @classmethod
    def get_description(cls, product_code: str) -> str:
        """Get human-readable description."""
        if product_code in [cls.VAMP_199, cls.SKU_VAMP_PROTECTION_199]:
            return "VAMP Protection Package"
        elif product_code in [cls.MATCH_499, cls.SKU_MATCH_HYBRID_499]:
            return "MATCH Liberation Package"
        elif product_code in [cls.ATTEST_49, cls.SKU_ATTEST_49]:
            return "Blockchain Attestation"
        else:
            return "Unknown Product"

class PaymentAdapter(ABC):
    """Base payment adapter interface."""
    
    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    async def create_checkout(self, *, order_id: str, user_id: str, product_code: str, 
                            amount_cents: int, currency: str = "USD", 
                            metadata: Optional[Dict[str, Any]] = None) -> CheckoutResult:
        """Create checkout session."""
        pass
    
    @abstractmethod
    async def handle_webhook(self, headers: Dict[str, str], body: bytes) -> PaymentEvent:
        """Handle webhook from provider."""
        pass