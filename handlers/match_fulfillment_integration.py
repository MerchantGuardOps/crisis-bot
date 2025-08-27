"""
MATCH fulfillment integration with partner offers.
Triggers PSP partner offers after MATCH package purchases.
"""

import os
from services.affiliate_tracker import AffiliateTracker
from modules.analytics.ltv_tracking import PointsService
from bot.partners_router import send_psp_partner_offer


async def handle_match_499_fulfillment(
    bot,
    merchant_id: str,
    purchase_id: str,
    pg_pool
):
    """
    Handle MATCH $499 package fulfillment with partner integration.
    
    This is called after successful MATCH Liberation package purchase
    to offer PSP partner warm intros.
    """
    
    # Check if partner features are enabled
    if not os.getenv("FEATURE_PARTNERS", "true").lower() == "true":
        return
    
    if not os.getenv("FEATURE_PARTNER_PSP", "true").lower() == "true":
        return
    
    try:
        # Initialize services
        base_url = os.getenv("BASE_URL", "https://merchantguard.ai")
        hmac_secret = os.getenv("PARTNER_REDIRECT_HMAC_SECRET", "default_secret")
        
        affiliate_tracker = AffiliateTracker(pg_pool, base_url, hmac_secret)
        points_service = PointsService(pg_pool)
        
        # Send PSP partner offer (warm intro option)
        await send_psp_partner_offer(
            bot=bot,
            merchant_id=merchant_id,
            tracker=affiliate_tracker,
            points=points_service,
            purchase_id=purchase_id
        )
        
    except Exception as e:
        # Log error but don't fail fulfillment
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Partner offer failed for merchant {merchant_id}: {e}")


async def handle_guardscore_violation_legal_offer(
    bot,
    merchant_id: str,
    violation_risk: float,
    pg_pool
):
    """
    Handle legal partner offers for high GuardScore violation risk.
    
    Called when GuardScore shows violation_risk >= 0.70
    """
    from bot.partners_router import maybe_send_legal_offer
    
    if not os.getenv("FEATURE_PARTNER_LEGAL", "true").lower() == "true":
        return
        
    try:
        base_url = os.getenv("BASE_URL", "https://merchantguard.ai")
        hmac_secret = os.getenv("PARTNER_REDIRECT_HMAC_SECRET", "default_secret")
        
        affiliate_tracker = AffiliateTracker(pg_pool, base_url, hmac_secret)
        points_service = PointsService(pg_pool)
        
        await maybe_send_legal_offer(
            bot=bot,
            merchant_id=merchant_id,
            tracker=affiliate_tracker,
            points=points_service,
            violation_risk=violation_risk
        )
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Legal partner offer failed for merchant {merchant_id}: {e}")


async def handle_llc_formation_offer(
    bot,
    merchant_id: str,
    needs_new_entity: bool,
    pg_pool
):
    """
    Handle LLC formation partner offers during onboarding.
    
    Called when user indicates they need a new entity for PSP applications.
    """
    from bot.partners_router import maybe_send_llc_offer
    
    if not os.getenv("FEATURE_PARTNER_LLC", "true").lower() == "true":
        return
        
    try:
        base_url = os.getenv("BASE_URL", "https://merchantguard.ai")
        hmac_secret = os.getenv("PARTNER_REDIRECT_HMAC_SECRET", "default_secret")
        
        affiliate_tracker = AffiliateTracker(pg_pool, base_url, hmac_secret)
        
        await maybe_send_llc_offer(
            bot=bot,
            merchant_id=merchant_id,
            tracker=affiliate_tracker,
            needs_new_entity=needs_new_entity
        )
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"LLC partner offer failed for merchant {merchant_id}: {e}")


async def update_partner_outcome(
    merchant_id: str,
    partner_key: str,
    outcome_status: str,
    pg_pool
):
    """
    Update partner referral status based on PSP application outcome.
    
    Called when user reports PSP application results through /outcome command.
    """
    try:
        base_url = os.getenv("BASE_URL", "https://merchantguard.ai")
        hmac_secret = os.getenv("PARTNER_REDIRECT_HMAC_SECRET", "default_secret")
        
        affiliate_tracker = AffiliateTracker(pg_pool, base_url, hmac_secret)
        
        await affiliate_tracker.update_from_outcome(
            merchant_id=merchant_id,
            partner_key=partner_key,
            outcome_status=outcome_status
        )
        
        # Award points for successful applications/approvals
        if outcome_status in ["applied", "approved"]:
            points_service = PointsService(pg_pool)
            points_action = f"partner_psp_{outcome_status}"
            
            await points_service.award(
                user_id=merchant_id,
                action=points_action,
                meta={"partner": partner_key, "outcome": outcome_status},
                idempotency_key=f"partner_outcome:{merchant_id}:{partner_key}:{outcome_status}"
            )
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Partner outcome update failed for {merchant_id}: {e}")