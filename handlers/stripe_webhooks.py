# handlers/stripe_webhooks.py - HARDENED WEBHOOK HANDLER
"""
Stripe Webhook Handler with Production Hardening
- Idempotency protection
- Signature verification
- Duplicate event handling
- Error recovery
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from aiogram import Bot
from config.feature_config import get_config

logger = logging.getLogger(__name__)

# In-memory deduplication cache (in production, use Redis)
processed_events: Dict[str, datetime] = {}
CACHE_EXPIRY_HOURS = 24

class StripeWebhookHandler:
    """Production-hardened Stripe webhook handler"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.webhook_secret = get_config("STRIPE_WEBHOOK_SECRET")
        
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature"""
        if not self.webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET not configured")
            return False
            
        try:
            # Parse signature header
            elements = signature.split(',')
            timestamp = None
            signature_value = None
            
            for element in elements:
                if element.startswith('t='):
                    timestamp = element[2:]
                elif element.startswith('v1='):
                    signature_value = element[3:]
            
            if not timestamp or not signature_value:
                logger.error("Invalid signature format")
                return False
            
            # Check timestamp (reject events older than 5 minutes)
            try:
                event_timestamp = int(timestamp)
                current_timestamp = int(datetime.utcnow().timestamp())
                if abs(current_timestamp - event_timestamp) > 300:
                    logger.error("Event timestamp too old")
                    return False
            except ValueError:
                logger.error("Invalid timestamp in signature")
                return False
            
            # Verify signature
            signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                signed_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature_value)
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def is_duplicate_event(self, event_id: str) -> bool:
        """Check if event has already been processed (idempotency)"""
        # Clean up old entries
        cutoff = datetime.utcnow() - timedelta(hours=CACHE_EXPIRY_HOURS)
        expired_keys = [k for k, v in processed_events.items() if v < cutoff]
        for key in expired_keys:
            del processed_events[key]
        
        # Check if this event was already processed
        if event_id in processed_events:
            logger.info(f"Duplicate event ignored: {event_id}")
            return True
        
        # Mark as processed
        processed_events[event_id] = datetime.utcnow()
        return False
    
    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Main webhook handler with full hardening"""
        
        # 1. Verify signature
        if not self.verify_signature(payload, signature):
            logger.error("Webhook signature verification failed")
            return {"status": "error", "message": "Invalid signature"}
        
        try:
            # 2. Parse event
            event = json.loads(payload.decode('utf-8'))
            event_id = event.get('id')
            event_type = event.get('type')
            
            if not event_id or not event_type:
                logger.error("Invalid event format")
                return {"status": "error", "message": "Invalid event format"}
            
            # 3. Check for duplicates (idempotency)
            if self.is_duplicate_event(event_id):
                return {"status": "success", "message": "Duplicate event ignored"}
            
            logger.info(f"Processing Stripe event: {event_type} ({event_id})")
            
            # 4. Route to appropriate handler
            if event_type == 'checkout.session.completed':
                await self._handle_checkout_completed(event)
            elif event_type == 'invoice.payment_succeeded':
                await self._handle_payment_succeeded(event)
            elif event_type == 'invoice.payment_failed':
                await self._handle_payment_failed(event)
            elif event_type == 'customer.subscription.deleted':
                await self._handle_subscription_cancelled(event)
            else:
                logger.info(f"Unhandled event type: {event_type}")
            
            return {"status": "success", "event_id": event_id}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return {"status": "error", "message": "Invalid JSON"}
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _handle_checkout_completed(self, event: Dict[str, Any]):
        """Handle successful checkout completion"""
        try:
            session = event['data']['object']
            customer_email = session.get('customer_email')
            client_reference_id = session.get('client_reference_id')  # User ID
            amount_total = session.get('amount_total', 0)
            
            # Extract metadata
            metadata = session.get('metadata', {})
            package_id = metadata.get('package_id')
            sku = metadata.get('sku')
            
            logger.info(f"Checkout completed: {package_id} (SKU: {sku}) for user {client_reference_id}")
            
            # Handle Quick-Hit Kit specifically
            if sku == 'MG-QH-097' or package_id == 'quick_hit_97':
                await self._handle_quick_hit_purchase(session, client_reference_id, customer_email)
            
            if client_reference_id:
                # Send confirmation to user via Telegram
                await self._send_purchase_confirmation(
                    user_id=int(client_reference_id),
                    package_id=package_id,
                    amount=amount_total,
                    sku=sku
                )
                
                # Trigger package delivery
                await self._deliver_package(client_reference_id, package_id)
                
        except Exception as e:
            logger.error(f"Error handling checkout completion: {e}")
    
    async def _handle_quick_hit_purchase(self, session: Dict[str, Any], user_id: str, email: str):
        """Handle Quick-Hit Kit purchase - start email course and bot delivery"""
        try:
            logger.info(f"Processing Quick-Hit Kit purchase for user {user_id}, email {email}")
            
            # 1. Queue 30-day email course
            await self._queue_email_course(email, 'quick_hit')
            
            # 2. Notify Telegram bot for instant delivery
            if user_id:
                await self._notify_telegram_bot_delivery(user_id, f"deliver_quick_hit_{session.get('id')}")
            
            # 3. Track analytics event
            await self._track_analytics_event('kit_purchase_success', {
                'sku': 'MG-QH-097',
                'value': 97,
                'currency': 'USD',
                'user_id': user_id,
                'email': email
            })
            
            logger.info(f"Quick-Hit Kit processing completed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error processing Quick-Hit Kit purchase: {e}")
    
    async def _queue_email_course(self, email: str, course_key: str):
        """Queue email course for user"""
        try:
            # Import email service
            from services.email_service import EmailService
            
            email_service = EmailService()
            await email_service.start_course_sequence(email, course_key)
            
            logger.info(f"Email course '{course_key}' queued for {email}")
            
        except Exception as e:
            logger.error(f"Error queueing email course: {e}")
    
    async def _notify_telegram_bot_delivery(self, user_id: str, start_param: str):
        """Notify Telegram bot to deliver content"""
        try:
            await self.bot.send_message(
                chat_id=int(user_id),
                text=f"🎯 Your Quick-Hit Kit is ready! Click to start: /start {start_param}",
                parse_mode="Markdown"
            )
            
            logger.info(f"Bot delivery notification sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error notifying bot delivery: {e}")
    
    async def _track_analytics_event(self, event_name: str, properties: Dict[str, Any]):
        """Track analytics event"""
        try:
            # Log for now - in production would send to analytics service
            logger.info(f"Analytics event: {event_name} with properties: {properties}")
            
        except Exception as e:
            logger.error(f"Error tracking analytics event: {e}")
    
    async def _handle_payment_succeeded(self, event: Dict[str, Any]):
        """Handle successful payment"""
        logger.info("Payment succeeded - additional processing if needed")
    
    async def _handle_payment_failed(self, event: Dict[str, Any]):
        """Handle failed payment"""
        try:
            invoice = event['data']['object']
            customer = invoice.get('customer')
            logger.warning(f"Payment failed for customer {customer}")
            
            # Could implement retry logic or notification here
            
        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")
    
    async def _handle_subscription_cancelled(self, event: Dict[str, Any]):
        """Handle subscription cancellation"""
        logger.info("Subscription cancelled")
    
    async def _send_purchase_confirmation(self, user_id: int, package_id: str, amount: int, sku: str = None):
        """Send purchase confirmation to user"""
        try:
            if sku == 'MG-QH-097':
                confirmation_text = f"""🎯 **Quick-Hit Kit Activated!**

Your emergency triage system is ready.

**Amount:** ${amount // 100}
**Status:** Instant delivery starting
**Email Course:** Starting in 5 minutes

🚀 Click below to start your 60-minute triage:
/start deliver_quick_hit

Questions? Contact support@merchantguard.ai"""
            else:
                confirmation_text = f"""✅ **Purchase Confirmed!**

Your {package_id} package is ready for delivery.

**Amount:** ${amount // 100}
**Status:** Processing delivery

You'll receive your package contents within the next few minutes.

Questions? Contact support@merchantguard.ai"""

            await self.bot.send_message(
                chat_id=user_id,
                text=confirmation_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Error sending confirmation to {user_id}: {e}")
    
    async def _deliver_package(self, user_id: str, package_id: str):
        """Trigger package delivery workflow"""
        try:
            # Import here to avoid circular imports
            from modules.package_delivery import deliver_package_to_user
            
            await deliver_package_to_user(user_id, package_id)
            logger.info(f"Package {package_id} delivered to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error delivering package: {e}")

# FastAPI endpoint for webhook
async def stripe_webhook_endpoint(request_body: bytes, stripe_signature: str, bot: Bot):
    """FastAPI/Flask endpoint wrapper"""
    handler = StripeWebhookHandler(bot)
    return await handler.handle_webhook(request_body, stripe_signature)