# api/stripe_webhook.py - Instant Package Delivery System
"""
Stripe Webhook Handler for Instant Package Delivery
Processes checkout.session.completed events and delivers digital products
"""

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import stripe
import json
import logging
import os
import asyncio
from typing import Optional
from datetime import datetime

from services.email_service import EmailService
from analytics.ltv_tracking import track_event
from analytics.utm_enhanced_tracking import track_payment_success_with_utm, track_offer_shown_with_utm
from handlers.packages import PACKAGE_CATALOG, get_package_by_id
from database.pool import get_db_connection

router = APIRouter()
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

async def is_event_already_processed(event_id: str, event_type: str) -> bool:
    """Check if webhook event has already been processed (idempotency check)"""
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchrow(
                "SELECT id FROM processed_webhook_events WHERE event_id = $1",
                event_id
            )
            return result is not None
    except Exception as e:
        logger.error(f"Error checking event processing status: {e}")
        # Fail safe - allow processing if we can't check
        return False

async def mark_event_as_processed(event_id: str, event_type: str, user_id: str = None, metadata: dict = None):
    """Mark webhook event as processed"""
    try:
        async with get_db_connection() as conn:
            await conn.execute("""
                INSERT INTO processed_webhook_events 
                (event_id, event_type, user_id, metadata) 
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (event_id) DO NOTHING
            """, event_id, event_type, int(user_id) if user_id else None, json.dumps(metadata or {}))
    except Exception as e:
        logger.error(f"Error marking event as processed: {e}")

async def is_package_already_delivered(user_id: str, package_id: str, session_id: str) -> bool:
    """Check if package has already been delivered to prevent duplicates"""
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchrow("""
                SELECT id FROM package_deliveries 
                WHERE user_id = $1 AND package_id = $2 AND stripe_session_id = $3
            """, int(user_id), package_id, session_id)
            return result is not None
    except Exception as e:
        logger.error(f"Error checking package delivery status: {e}")
        return False

async def record_package_delivery(user_id: str, package: dict, session: dict):
    """Record successful package delivery"""
    try:
        async with get_db_connection() as conn:
            await conn.execute("""
                INSERT INTO package_deliveries 
                (user_id, package_id, stripe_session_id, stripe_payment_intent_id, 
                 customer_email, amount_paid_cents, delivery_details) 
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id, package_id, stripe_session_id) DO NOTHING
            """, 
                int(user_id),
                package["id"], 
                session["id"],
                session.get("payment_intent"),
                session.get("customer_details", {}).get("email"),
                session.get("amount_total", 0),
                json.dumps({
                    "package_name": package["name"],
                    "delivery_method": "email",
                    "delivered_at": datetime.utcnow().isoformat()
                })
            )
    except Exception as e:
        logger.error(f"Error recording package delivery: {e}")

@router.post("/stripe/webhook")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature")
):
    """Handle Stripe webhook events for package delivery with idempotency protection"""
    
    try:
        # Get raw body
        body = await request.body()
        
        # Verify webhook signature
        if not webhook_secret:
            logger.warning("STRIPE_WEBHOOK_SECRET not configured - skipping verification")
            event = json.loads(body)
        else:
            try:
                event = stripe.Webhook.construct_event(
                    body, stripe_signature, webhook_secret
                )
            except ValueError:
                logger.error("Invalid payload in Stripe webhook")
                raise HTTPException(status_code=400, detail="Invalid payload")
            except stripe.error.SignatureVerificationError:
                logger.error("Invalid signature in Stripe webhook")
                raise HTTPException(status_code=400, detail="Invalid signature")
        
        event_id = event.get("id")
        event_type = event.get("type")
        
        # Idempotency check - skip if already processed
        if await is_event_already_processed(event_id, event_type):
            logger.info(f"Webhook event {event_id} already processed, skipping")
            return JSONResponse({"status": "success", "message": "Event already processed"})
        
        # Extract user ID for tracking
        user_id = None
        if event_type == 'checkout.session.completed':
            user_id = event['data']['object'].get('client_reference_id')
        
        # Mark event as being processed
        await mark_event_as_processed(event_id, event_type, user_id, {"processed_at": datetime.utcnow().isoformat()})
        
        # Handle the event
        if event_type == 'checkout.session.completed':
            await handle_checkout_completed(event['data']['object'])
        elif event_type == 'invoice.payment_succeeded':
            await handle_payment_succeeded(event['data']['object'])
        else:
            logger.info(f"Unhandled event type: {event_type}")
        
        return JSONResponse({"status": "success", "event_id": event_id})
        
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

async def handle_checkout_completed(session):
    """Handle successful checkout completion"""
    
    try:
        # Extract key information
        customer_email = session.get('customer_details', {}).get('email')
        client_reference_id = session.get('client_reference_id')  # user_id
        payment_intent_id = session.get('payment_intent')
        amount_total = session.get('amount_total', 0) / 100  # Convert from cents
        
        # Get line items to identify the package
        line_items = stripe.checkout.Session.list_line_items(session['id'])
        
        if not line_items.data:
            logger.error("No line items found in checkout session")
            return
        
        # Identify the package from price ID
        price_id = line_items.data[0].price.id
        package = get_package_by_price_id(price_id)
        
        if not package:
            logger.error(f"Unknown price ID: {price_id}")
            return
        
        # Track successful purchase with UTM attribution
        await track_payment_success_with_utm(
            user_id=int(client_reference_id) if client_reference_id else None,
            package_id=package["id"],
            amount=int(amount_total * 100),  # Convert to cents
            stripe_session_id=session["id"],
            package_name=package["name"],
            payment_intent=payment_intent_id,
            customer_email=customer_email
        )
        
        # Also track the legacy event for backward compatibility
        await track_event("package_purchase_completed", {
            "user_id": client_reference_id,
            "package_id": package["id"],
            "package_name": package["name"],
            "price": package["price"],
            "payment_intent": payment_intent_id,
            "customer_email": customer_email,
            "amount_paid": amount_total,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Check if package was already delivered to prevent duplicates
        if await is_package_already_delivered(client_reference_id, package["id"], session["id"]):
            logger.info(f"Package {package['id']} already delivered to user {client_reference_id}, skipping")
        else:
            # Deliver the package
            await deliver_package(package, client_reference_id, customer_email, session)
            # Record successful delivery
            await record_package_delivery(client_reference_id, package, session)
        
        # Update user's passport status if applicable
        if package["type"] == "premium_kit":
            await update_passport_status(client_reference_id, package["id"], "earned")
        else:
            await update_passport_status(client_reference_id, package["id"], "data_verified")
        
        logger.info(f"Successfully delivered package {package['id']} to user {client_reference_id}")
        
    except Exception as e:
        logger.error(f"Failed to handle checkout completion: {e}")

async def deliver_package(package: dict, user_id: str, customer_email: str, session: dict):
    """Deliver digital package content to customer"""
    
    package_type = package["type"]
    package_id = package["id"]
    
    if package_type == "digital":
        await deliver_digital_package(package, user_id, customer_email)
    elif package_type == "service":
        await deliver_service_package(package, user_id, customer_email)
    elif package_type == "premium_kit":
        await deliver_premium_kit(package, user_id, customer_email)
    
    # Send purchase confirmation email
    await send_purchase_confirmation(package, user_id, customer_email, session)

async def deliver_digital_package(package: dict, user_id: str, customer_email: str):
    """Deliver instant digital package"""
    
    package_id = package["id"]
    
    # Map package IDs to content files
    content_mapping = {
        "pkg_quick_97": {
            "files": ["QUICK_HIT_UNLOCK.txt"],
            "path": "packs/US_CARDS/GENERAL/"
        },
        "pkg_auto_199": {
            "files": ["READINESS_PACK_UNLOCK.txt"],
            "path": "packs/US_CARDS/GENERAL/"
        }
    }
    
    content_info = content_mapping.get(package_id)
    if not content_info:
        logger.error(f"No content mapping for package {package_id}")
        return
    
    # Read content files
    content_files = {}
    for filename in content_info["files"]:
        file_path = f"/Users/soccer/Downloads/merchantguard-nextjs/{content_info['path']}{filename}"
        try:
            with open(file_path, 'r') as f:
                content_files[filename] = f.read()
        except Exception as e:
            logger.error(f"Failed to read content file {file_path}: {e}")
    
    # Send via email using EmailService
    email_service = EmailService()
    await email_service.send_digital_package_delivery(
        customer_email, 
        package,
        content_files,
        user_id
    )

async def deliver_service_package(package: dict, user_id: str, customer_email: str):
    """Handle service package delivery (Emergency Review)"""
    
    # For service packages, send instructions rather than content
    email_service = EmailService()
    await email_service.send_service_package_instructions(
        customer_email,
        package,
        user_id
    )
    
    # Create internal task/notification for service delivery
    logger.info(f"Service package {package['id']} purchased by user {user_id} - manual delivery required")

async def deliver_premium_kit(package: dict, user_id: str, customer_email: str):
    """Handle premium kit delivery (Interactive Workflow)"""
    
    # Premium kits are delivered via bot workflow, not email
    # Send welcome email with instructions to continue in bot
    email_service = EmailService()
    await email_service.send_premium_kit_welcome(
        customer_email,
        package,
        user_id
    )

async def send_purchase_confirmation(package: dict, user_id: str, customer_email: str, session: dict):
    """Send purchase confirmation email"""
    
    email_service = EmailService()
    
    confirmation_data = {
        "package_name": package["name"],
        "price": package["price"],
        "delivery_info": package["delivery"],
        "order_id": f"MG-{user_id}-{package['id'][:8].upper()}",
        "session_id": session["id"],
        "customer_email": customer_email,
        "purchase_date": datetime.utcnow().strftime("%B %d, %Y")
    }
    
    await email_service.send_purchase_confirmation(
        customer_email,
        confirmation_data
    )

async def update_passport_status(user_id: str, package_id: str, new_status: str):
    """Update user's compliance passport status after purchase"""
    
    try:
        # In production, update database record
        await track_event("passport_status_updated", {
            "user_id": user_id,
            "package_id": package_id,
            "new_status": new_status,
            "upgrade_reason": "package_purchase",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Updated passport status for user {user_id} to {new_status}")
        
    except Exception as e:
        logger.error(f"Failed to update passport status: {e}")

def get_package_by_price_id(price_id: str) -> dict:
    """Get package configuration by Stripe price ID"""
    for package in PACKAGE_CATALOG:
        if package["stripe_price_id"] == price_id:
            return package
    return None

# Health check endpoint
@router.get("/stripe/webhook/health")
async def webhook_health():
    """Webhook health check"""
    return {
        "status": "healthy",
        "webhook_secret_configured": bool(webhook_secret),
        "stripe_key_configured": bool(stripe.api_key),
        "timestamp": datetime.utcnow().isoformat()
    }