"""
Payment processing API routes for multi-provider support.
Handles checkout creation, webhooks, and NMI direct charging.
"""

import os
import uuid
import json
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
import asyncpg

from services.payments.adapter_base import (
    PaymentAdapter, 
    CheckoutResult, 
    PaymentEvent,
    PaymentError,
    WebhookVerificationError,
    ProductCodes,
    PaymentStatus
)
from services.payments.authnet_adapter import AuthorizeNetAdapter
from services.payments.nmi_adapter import NMIAdapter

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

# Get the default payment provider from environment
DEFAULT_PROVIDER = os.environ.get("PAYMENTS_PROVIDER", "authnet")

def get_payment_adapter(provider: str = None) -> PaymentAdapter:
    """Get payment adapter instance based on provider."""
    provider = provider or DEFAULT_PROVIDER
    
    if provider == "authnet":
        return AuthorizeNetAdapter()
    elif provider == "nmi":
        return NMIAdapter()
    elif provider == "stripe":
        # Import Stripe adapter if available
        try:
            from services.payments.stripe_adapter import StripeAdapter
            return StripeAdapter()
        except ImportError:
            raise HTTPException(
                status_code=500, 
                detail="Stripe adapter not available"
            )
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported payment provider: {provider}"
        )

async def get_db_pool(request: Request) -> asyncpg.Pool:
    """Get database pool from app state."""
    if not hasattr(request.app.state, 'pg_pool'):
        raise HTTPException(
            status_code=500,
            detail="Database pool not initialized"
        )
    return request.app.state.pg_pool

async def create_order(
    pool: asyncpg.Pool,
    user_id: str,
    product_code: str,
    amount_cents: int,
    currency: str = "USD",
    provider: str = None
) -> str:
    """Create a new payment order in the database."""
    order_id = str(uuid.uuid4())
    provider = provider or DEFAULT_PROVIDER
    
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO payments_orders 
            (id, user_id, product_code, amount_cents, currency, provider, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, order_id, user_id, product_code, amount_cents, currency, provider, PaymentStatus.CREATED)
    
    return order_id

async def update_order_status(
    pool: asyncpg.Pool,
    order_id: str,
    status: str,
    provider_session_id: str = None,
    provider_tx_id: str = None
) -> bool:
    """Update order status and provider details."""
    async with pool.acquire() as conn:
        query = """
            UPDATE payments_orders 
            SET status = $2, updated_at = NOW()
        """
        params = [order_id, status]
        
        if provider_session_id is not None:
            query += ", provider_session_id = $" + str(len(params) + 1)
            params.append(provider_session_id)
        
        if provider_tx_id is not None:
            query += ", provider_tx_id = $" + str(len(params) + 1)
            params.append(provider_tx_id)
        
        query += " WHERE id = $1 AND status != $3 RETURNING id"
        params.append(PaymentStatus.PAID)  # Don't update already paid orders
        
        result = await conn.fetchrow(query, *params)
        return result is not None

@router.post("/checkout")
async def create_checkout(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Create a new checkout session."""
    try:
        body = await request.json()
        
        # Extract and validate request data
        user_id = str(body["user_id"])
        product_code = body["product_code"]
        amount_cents = int(body["amount_cents"])
        currency = body.get("currency", "USD")
        provider = body.get("provider", DEFAULT_PROVIDER)
        metadata = body.get("metadata", {})
        
        # Validate product code
        if product_code not in [ProductCodes.VAMP_199, ProductCodes.MATCH_499, ProductCodes.ATTEST_49]:
            raise HTTPException(status_code=400, detail="Invalid product code")
        
        # Validate amount matches product
        expected_amount = ProductCodes.get_amount_cents(product_code)
        if expected_amount > 0 and amount_cents != expected_amount:
            raise HTTPException(
                status_code=400, 
                detail=f"Amount mismatch: expected {expected_amount}, got {amount_cents}"
            )
        
        # Create order in database
        order_id = await create_order(pool, user_id, product_code, amount_cents, currency, provider)
        
        # Get payment adapter and create checkout
        adapter = get_payment_adapter(provider)
        checkout_result: CheckoutResult = await adapter.create_checkout(
            order_id=order_id,
            user_id=user_id,
            product_code=product_code,
            amount_cents=amount_cents,
            currency=currency,
            metadata=metadata
        )
        
        # Update order with session ID
        await update_order_status(
            pool,
            order_id,
            PaymentStatus.PROCESSING,
            provider_session_id=checkout_result.provider_session_id
        )
        
        logger.info(f"Created checkout for order {order_id}, user {user_id}, product {product_code}")
        
        # Return appropriate response
        if checkout_result.html:
            return HTMLResponse(content=checkout_result.html)
        else:
            return JSONResponse({
                "success": True,
                "order_id": order_id,
                "redirect_url": checkout_result.redirect_url,
                "provider": provider
            })
            
    except PaymentError as e:
        logger.error(f"Payment error in checkout: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in checkout: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/webhook/authnet")
async def webhook_authorize_net(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Handle Authorize.Net webhooks."""
    try:
        body = await request.body()
        headers = dict(request.headers)
        
        adapter = AuthorizeNetAdapter()
        payment_event: PaymentEvent = await adapter.handle_webhook(headers, body)
        
        # Update order status
        updated = await update_order_status(
            pool,
            payment_event.order_id,
            payment_event.status,
            provider_tx_id=payment_event.provider_tx_id
        )
        
        if updated and payment_event.status == PaymentStatus.PAID:
            # Trigger fulfillment
            await fulfill_order(
                pool, 
                request.app,
                payment_event.order_id,
                payment_event.amount_cents,
                payment_event.provider,
                payment_event.provider_tx_id
            )
        
        logger.info(f"Processed AuthNet webhook for order {payment_event.order_id}")
        return {"success": True, "processed": updated}
        
    except WebhookVerificationError as e:
        logger.warning(f"AuthNet webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    except PaymentError as e:
        logger.error(f"AuthNet webhook processing error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in AuthNet webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/nmi/charge")
async def charge_nmi_token(
    request: Request,
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Process NMI payment token and charge the card."""
    try:
        body = await request.json()
        
        order_id = body["order_id"]
        token = body["token"]
        
        # Get order details from database
        async with pool.acquire() as conn:
            order = await conn.fetchrow("""
                SELECT user_id, product_code, amount_cents, currency, status
                FROM payments_orders 
                WHERE id = $1
            """, order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        if order["status"] == PaymentStatus.PAID:
            # Order already paid, return success
            success_url = os.environ.get("NMI_HOSTED_SUCCESS", "/payments/success")
            return JSONResponse({
                "ok": True,
                "status": "paid",
                "redirect": success_url,
                "message": "Order already paid"
            })
        
        # Charge the token via NMI
        adapter = NMIAdapter()
        payment_event: PaymentEvent = await adapter.charge_token(
            order_id=order_id,
            token=token,
            amount_cents=order["amount_cents"],
            currency=order["currency"]
        )
        
        # Update order status
        updated = await update_order_status(
            pool,
            order_id,
            payment_event.status,
            provider_tx_id=payment_event.provider_tx_id
        )
        
        if updated and payment_event.status == PaymentStatus.PAID:
            # Trigger fulfillment
            await fulfill_order(
                pool,
                request.app,
                order_id,
                payment_event.amount_cents,
                payment_event.provider,
                payment_event.provider_tx_id
            )
        
        # Determine redirect URL
        if payment_event.status == PaymentStatus.PAID:
            redirect_url = os.environ.get("NMI_HOSTED_SUCCESS", "/payments/success")
            message = "Payment successful"
        else:
            redirect_url = os.environ.get("NMI_HOSTED_FAIL", "/payments/failed")
            message = "Payment failed"
        
        logger.info(f"Processed NMI charge for order {order_id}: {payment_event.status}")
        
        return JSONResponse({
            "ok": True,
            "status": payment_event.status,
            "redirect": redirect_url,
            "message": message
        })
        
    except PaymentError as e:
        logger.error(f"NMI charge error: {e}")
        fail_url = os.environ.get("NMI_HOSTED_FAIL", "/payments/failed")
        return JSONResponse({
            "ok": False,
            "status": "failed",
            "redirect": fail_url,
            "message": str(e)
        })
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in NMI charge: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/test")
async def create_test_payment(
    request: Request,
    user_id: str = "test_user",
    amount_cents: int = 50,  # $0.50 test
    pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Create a test payment for debugging/verification."""
    try:
        # Create test order
        order_id = await create_order(
            pool, 
            user_id, 
            ProductCodes.ATTEST_49, 
            amount_cents,
            "USD"
        )
        
        # Get checkout URL
        adapter = get_payment_adapter()
        checkout_result = await adapter.create_checkout(
            order_id=order_id,
            user_id=user_id,
            product_code=ProductCodes.ATTEST_49,
            amount_cents=amount_cents,
            currency="USD",
            metadata={"test": True}
        )
        
        await update_order_status(
            pool,
            order_id,
            PaymentStatus.PROCESSING,
            provider_session_id=checkout_result.provider_session_id
        )
        
        if checkout_result.html:
            return HTMLResponse(content=checkout_result.html)
        else:
            return JSONResponse({
                "test_order_id": order_id,
                "checkout_url": checkout_result.redirect_url,
                "amount": f"${amount_cents/100:.2f}",
                "provider": DEFAULT_PROVIDER
            })
            
    except Exception as e:
        logger.error(f"Test payment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Success/failure pages
@router.get("/success")
async def payment_success():
    """Payment success page."""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Payment Successful - MerchantGuard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: system-ui;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            margin: 0;
            padding: 40px 20px;
            text-align: center;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 500px;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }
        h1 { color: #22d3ee; margin-bottom: 20px; }
        .checkmark { font-size: 4rem; margin-bottom: 20px; }
        a { color: #22d3ee; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✅</div>
        <h1>Payment Successful!</h1>
        <p>Your order has been processed successfully. You should receive your purchase shortly.</p>
        <p><a href="https://t.me/guardscorebot">Return to GuardScore Bot →</a></p>
    </div>
</body>
</html>
    """)

@router.get("/failed")
async def payment_failed():
    """Payment failed page."""
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
    <title>Payment Failed - MerchantGuard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: system-ui;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            margin: 0;
            padding: 40px 20px;
            text-align: center;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            max-width: 500px;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }
        h1 { color: #fcd34d; margin-bottom: 20px; }
        .cross { font-size: 4rem; margin-bottom: 20px; }
        a { color: #fcd34d; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="cross">❌</div>
        <h1>Payment Failed</h1>
        <p>Your payment could not be processed. Please check your payment details and try again.</p>
        <p><a href="https://t.me/guardscorebot">Return to GuardScore Bot →</a></p>
    </div>
</body>
</html>
    """)

async def fulfill_order(
    pool: asyncpg.Pool,
    app,
    order_id: str,
    amount_cents: int,
    provider: str,
    provider_tx_id: str
):
    """
    Fulfill an order by triggering the appropriate business logic.
    This function integrates with existing fulfillment systems.
    """
    try:
        # Get order details
        async with pool.acquire() as conn:
            order = await conn.fetchrow("""
                SELECT user_id, product_code, amount_cents 
                FROM payments_orders 
                WHERE id = $1
            """, order_id)
        
        if not order:
            logger.error(f"Order not found for fulfillment: {order_id}")
            return
        
        user_id = order["user_id"]
        product_code = order["product_code"]
        
        # Log revenue event
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO revenue_events 
                (merchant_id, product_code, amount_cents, provider, provider_tx_id, order_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, user_id, product_code, amount_cents, provider, provider_tx_id, order_id)
        
        # Trigger product-specific fulfillment
        # These functions should already exist in your system
        
        if product_code == ProductCodes.MATCH_499:
            logger.info(f"Fulfilling MATCH package for user {user_id}")
            # Import and call existing fulfillment functions
            try:
                from services.package_builder_match import deliver_match_zip
                from bot.match_fulfillment import schedule_match_checkins
                
                await deliver_match_zip(app, user_id, order_id)
                await schedule_match_checkins(app, user_id)
                
                # Award points if system available
                if hasattr(app.state, 'points_service'):
                    points_service = app.state.points_service
                    if hasattr(points_service, 'award'):
                        await points_service.award("match_purchase", user_id)
                
                # Include attestation if enabled
                attestation_enabled = os.environ.get("FEATURE_ATTESTATION_INCLUDED_IN_MATCH", "false").lower() == "true"
                if attestation_enabled:
                    try:
                        from services.attestation_service import issue_included_attestation
                        await issue_included_attestation(app, user_id)
                    except ImportError:
                        logger.warning("Attestation service not available")
                        
            except ImportError as e:
                logger.warning(f"MATCH fulfillment functions not available: {e}")
        
        elif product_code == ProductCodes.VAMP_199:
            logger.info(f"Fulfilling VAMP package for user {user_id}")
            try:
                from services.vamp_fulfillment import deliver_vamp_pack, attach_prevention_guide_pdf
                
                await deliver_vamp_pack(app, user_id)
                await attach_prevention_guide_pdf(app, user_id)
                
            except ImportError as e:
                logger.warning(f"VAMP fulfillment functions not available: {e}")
        
        elif product_code == ProductCodes.ATTEST_49:
            logger.info(f"Fulfilling attestation for user {user_id}")
            try:
                from services.attestation_service import issue_attestation_for_user
                
                await issue_attestation_for_user(app, user_id)
                
            except ImportError as e:
                logger.warning(f"Attestation service not available: {e}")
        
        logger.info(f"Successfully fulfilled order {order_id} for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error fulfilling order {order_id}: {e}")
        # Don't raise exception - payment was successful, fulfillment can be retried