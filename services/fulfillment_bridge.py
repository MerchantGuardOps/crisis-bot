"""
Fulfillment bridge service that connects payment processing to existing business logic.
This service maintains the separation between payment processing and fulfillment.
"""

import os
import logging
from typing import Dict, Any, Optional
import asyncpg

from services.payments.adapter_base import ProductCodes

logger = logging.getLogger(__name__)

class FulfillmentBridge:
    """Bridge between payment processing and existing fulfillment systems."""
    
    def __init__(self, app_state):
        self.app_state = app_state
        
    async def fulfill_order(
        self,
        pool: asyncpg.Pool,
        order_id: str,
        user_id: str,
        product_code: str,
        amount_cents: int,
        provider: str,
        provider_tx_id: str
    ) -> bool:
        """
        Main fulfillment entry point that routes to appropriate handlers.
        Returns True if fulfillment was successful.
        """
        try:
            logger.info(f"Starting fulfillment for order {order_id}, product {product_code}, user {user_id}")
            
            # Log revenue event
            await self._log_revenue_event(
                pool, user_id, product_code, amount_cents, provider, provider_tx_id, order_id
            )
            
            # Route to specific fulfillment handler
            success = False
            
            if product_code == ProductCodes.MATCH_499:
                success = await self._fulfill_match_liberation(user_id, order_id)
            elif product_code == ProductCodes.VAMP_199:
                success = await self._fulfill_vamp_protection(user_id, order_id)
            elif product_code == ProductCodes.ATTEST_49:
                success = await self._fulfill_attestation(user_id, order_id)
            else:
                logger.error(f"Unknown product code: {product_code}")
                return False
            
            # Award points if system available and fulfillment succeeded
            if success:
                await self._award_points(user_id, product_code)
            
            logger.info(f"Fulfillment {'successful' if success else 'failed'} for order {order_id}")
            return success
            
        except Exception as e:
            logger.error(f"Fulfillment error for order {order_id}: {e}")
            return False
    
    async def _log_revenue_event(
        self,
        pool: asyncpg.Pool,
        user_id: str,
        product_code: str,
        amount_cents: int,
        provider: str,
        provider_tx_id: str,
        order_id: str
    ):
        """Log revenue event to the database."""
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO revenue_events 
                    (merchant_id, product_code, amount_cents, provider, provider_tx_id, order_id)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT DO NOTHING
                """, user_id, product_code, amount_cents, provider, provider_tx_id, order_id)
            
            logger.info(f"Logged revenue event: {user_id}, {product_code}, ${amount_cents/100:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to log revenue event: {e}")
            # Don't fail fulfillment due to logging error
    
    async def _fulfill_match_liberation(self, user_id: str, order_id: str) -> bool:
        """Fulfill MATCH Liberation Package ($499)."""
        try:
            logger.info(f"Fulfilling MATCH Liberation for user {user_id}")
            
            # 1. Deliver MATCH recovery ZIP package
            try:
                from services.package_builder_match import deliver_match_zip
                await deliver_match_zip(self.app_state, user_id, order_id)
                logger.info(f"MATCH ZIP package delivered to {user_id}")
            except ImportError:
                logger.warning("MATCH package builder not available")
            except Exception as e:
                logger.error(f"Failed to deliver MATCH ZIP: {e}")
                return False
            
            # 2. Schedule interactive check-ins (Week 1, 2, 4, Month 2, Month 3)
            try:
                from bot.match_fulfillment import schedule_match_checkins
                await schedule_match_checkins(self.app_state, user_id)
                logger.info(f"MATCH check-ins scheduled for {user_id}")
            except ImportError:
                logger.warning("MATCH check-in scheduler not available")
            except Exception as e:
                logger.error(f"Failed to schedule MATCH check-ins: {e}")
                # Continue with fulfillment even if check-ins fail
            
            # 3. Include on-chain attestation if enabled
            attestation_enabled = os.environ.get("FEATURE_ATTESTATION_INCLUDED_IN_MATCH", "false").lower() == "true"
            if attestation_enabled:
                try:
                    from services.attestation_service import issue_included_attestation
                    await issue_included_attestation(self.app_state, user_id)
                    logger.info(f"Included attestation issued for {user_id}")
                except ImportError:
                    logger.warning("Attestation service not available")
                except Exception as e:
                    logger.error(f"Failed to issue included attestation: {e}")
                    # Continue with fulfillment
            
            # 4. Send fulfillment notification via Telegram
            await self._send_fulfillment_notification(user_id, "MATCH Liberation Package")
            
            return True
            
        except Exception as e:
            logger.error(f"MATCH Liberation fulfillment failed: {e}")
            return False
    
    async def _fulfill_vamp_protection(self, user_id: str, order_id: str) -> bool:
        """Fulfill VAMP Protection Package ($199)."""
        try:
            logger.info(f"Fulfilling VAMP Protection for user {user_id}")
            
            # 1. Deliver VAMP protection tools
            try:
                from services.vamp_fulfillment import deliver_vamp_pack
                await deliver_vamp_pack(self.app_state, user_id)
                logger.info(f"VAMP protection pack delivered to {user_id}")
            except ImportError:
                logger.warning("VAMP fulfillment service not available")
            except Exception as e:
                logger.error(f"Failed to deliver VAMP pack: {e}")
                return False
            
            # 2. Attach prevention guide PDF
            try:
                from services.vamp_fulfillment import attach_prevention_guide_pdf
                await attach_prevention_guide_pdf(self.app_state, user_id)
                logger.info(f"VAMP prevention guide attached for {user_id}")
            except ImportError:
                logger.warning("VAMP prevention guide not available")
            except Exception as e:
                logger.error(f"Failed to attach prevention guide: {e}")
                # Continue with fulfillment
            
            # 3. Set up monitoring alerts (12 months)
            try:
                from services.vamp_monitoring import setup_monitoring_alerts
                await setup_monitoring_alerts(self.app_state, user_id)
                logger.info(f"VAMP monitoring alerts set up for {user_id}")
            except ImportError:
                logger.warning("VAMP monitoring service not available")
            except Exception as e:
                logger.error(f"Failed to set up monitoring: {e}")
                # Continue with fulfillment
            
            # 4. Send fulfillment notification
            await self._send_fulfillment_notification(user_id, "VAMP Protection Package")
            
            return True
            
        except Exception as e:
            logger.error(f"VAMP Protection fulfillment failed: {e}")
            return False
    
    async def _fulfill_attestation(self, user_id: str, order_id: str) -> bool:
        """Fulfill Blockchain Attestation ($49)."""
        try:
            logger.info(f"Fulfilling attestation for user {user_id}")
            
            # Issue blockchain attestation
            try:
                from services.attestation_service import issue_attestation_for_user
                await issue_attestation_for_user(self.app_state, user_id)
                logger.info(f"Attestation issued for {user_id}")
                
                # Send fulfillment notification
                await self._send_fulfillment_notification(user_id, "Blockchain Attestation")
                
                return True
                
            except ImportError:
                logger.error("Attestation service not available")
                return False
            except Exception as e:
                logger.error(f"Failed to issue attestation: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Attestation fulfillment failed: {e}")
            return False
    
    async def _award_points(self, user_id: str, product_code: str):
        """Award points for successful purchase if points system available."""
        try:
            if not hasattr(self.app_state, 'points_service'):
                return
            
            points_service = self.app_state.points_service
            if not hasattr(points_service, 'award'):
                return
            
            # Award points based on product
            point_awards = {
                ProductCodes.MATCH_499: "match_purchase",
                ProductCodes.VAMP_199: "vamp_purchase", 
                ProductCodes.ATTEST_49: "attestation_purchase"
            }
            
            award_type = point_awards.get(product_code)
            if award_type:
                await points_service.award(award_type, user_id)
                logger.info(f"Awarded points ({award_type}) to {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to award points: {e}")
            # Don't fail fulfillment due to points error
    
    async def _send_fulfillment_notification(self, user_id: str, product_name: str):
        """Send fulfillment notification to user via Telegram."""
        try:
            # Try to send notification via existing bot system
            if hasattr(self.app_state, 'bot') and hasattr(self.app_state, 'dp'):
                bot = self.app_state.bot
                
                message = f"""
🎉 **Purchase Complete!**

Your **{product_name}** has been delivered successfully.

📦 **What's Next:**
• Check your downloads and materials
• Follow any setup instructions provided
• Reach out if you need assistance

Thank you for your purchase! 🙏
                """.strip()
                
                await bot.send_message(chat_id=int(user_id), text=message, parse_mode="Markdown")
                logger.info(f"Fulfillment notification sent to {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to send fulfillment notification: {e}")
            # Don't fail fulfillment due to notification error

# Global fulfillment bridge instance
_fulfillment_bridge = None

def get_fulfillment_bridge(app_state) -> FulfillmentBridge:
    """Get or create fulfillment bridge instance."""
    global _fulfillment_bridge
    if _fulfillment_bridge is None:
        _fulfillment_bridge = FulfillmentBridge(app_state)
    return _fulfillment_bridge

# Convenience function for direct import in payment routes
async def fulfill_order(
    pool: asyncpg.Pool,
    app,
    order_id: str,
    amount_cents: int,
    provider: str,
    provider_tx_id: str
) -> bool:
    """
    Convenience function that matches the signature expected by payment routes.
    """
    try:
        # Get order details to extract user_id and product_code
        async with pool.acquire() as conn:
            order = await conn.fetchrow("""
                SELECT user_id, product_code 
                FROM payments_orders 
                WHERE id = $1
            """, order_id)
        
        if not order:
            logger.error(f"Order not found for fulfillment: {order_id}")
            return False
        
        # Use the fulfillment bridge
        bridge = get_fulfillment_bridge(app)
        return await bridge.fulfill_order(
            pool,
            order_id,
            order["user_id"],
            order["product_code"],
            amount_cents,
            provider,
            provider_tx_id
        )
        
    except Exception as e:
        logger.error(f"Fulfillment bridge error: {e}")
        return False