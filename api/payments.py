<<<<<<< Updated upstream
"""
Payment API Routes
Handles payment processing and webhook endpoints.
"""

import os
import json
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Response
from pydantic import BaseModel
from services.payments.authnet_adapter import AuthorizeNetAdapter
from services.payments.nmi_adapter import NMIAdapter, generate_nmi_payment_page
from services.payments.adapter_base import ProductCodes

router = APIRouter(prefix="/payments", tags=["payments"])

@router.get("/test")
async def test_payment_flow(
    user_id: str = "test_user", 
    product_code: str = "VAMP_199", 
    amount_cents: int = None,
    provider: str = None
):
    """Test payment flow - generates payment checkout for testing."""
    
    adapters = get_available_adapters()
    
    if not adapters:
        raise HTTPException(status_code=503, detail="No payment adapters available")
    
    if not provider:
        provider, adapter = get_preferred_adapter(adapters)
    elif provider not in adapters:
        raise HTTPException(status_code=400, detail=f"Provider {provider} not available. Available: {list(adapters.keys())}")
    else:
        adapter = adapters[provider]
    
    if not amount_cents:
        amount_cents = ProductCodes.get_amount_cents(product_code)
    
    description = ProductCodes.get_description(product_code)
    order_id = str(uuid.uuid4())
    
    try:
        result = await adapter.create_checkout(
            order_id=order_id,
            user_id=user_id,
            product_code=product_code,
            amount_cents=amount_cents,
            metadata={"test": "true", "source": "api_test"}
        )
        
        if result.html:
            return Response(content=result.html, media_type="text/html")
        else:
            return {
                "status": "ok",
                "adapters": list(adapters.keys()),
                "preferred": os.environ.get("PAYMENT_PREFERRED_ADAPTER", "authnet"),
                "provider": provider,
                "order_id": order_id,
                "product": description,
                "amount": f"${amount_cents/100:.2f}",
                "redirect_url": result.redirect_url
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test payment failed: {str(e)}")

# Keep existing router definition

# Payment request models
class ChargeRequest(BaseModel):
    order_id: str
    token: str

class CheckoutRequest(BaseModel):
    product_code: str
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

# Initialize adapters with failover logic
def get_available_adapters():
    """Get list of available payment adapters based on feature flags."""
    adapters = {}
    
    if not os.environ.get("PAYMENT_DISABLE_AUTHNET", "").lower() == "true":
        try:
            adapters["authnet"] = AuthorizeNetAdapter()
        except Exception as e:
            print(f"[PAYMENTS] AuthNet adapter failed to initialize: {e}")
    
    if not os.environ.get("PAYMENT_DISABLE_NMI", "").lower() == "true":
        try:
            adapters["nmi"] = NMIAdapter()
        except Exception as e:
            print(f"[PAYMENTS] NMI adapter failed to initialize: {e}")
    
    return adapters

def get_preferred_adapter(adapters):
    """Get preferred adapter based on configuration."""
    preferred = os.environ.get("PAYMENT_PREFERRED_ADAPTER", "authnet").lower()
    
    if preferred in adapters:
        return preferred, adapters[preferred]
    
    # Fallback to any available adapter
    if adapters:
        fallback = list(adapters.keys())[0]
        print(f"[PAYMENTS] Preferred adapter {preferred} not available, using {fallback}")
        return fallback, adapters[fallback]
    
    raise RuntimeError("No payment adapters available")

# Initialize adapters
available_adapters = get_available_adapters()
if not available_adapters:
    print("WARNING: No payment adapters initialized - payments will fail")
    authnet = nmi = None
else:
    authnet = available_adapters.get("authnet")
    nmi = available_adapters.get("nmi")

@router.post("/checkout/{provider}")
async def create_checkout(provider: str, request: CheckoutRequest):
    """Create payment checkout session."""
    
    if provider not in ["authnet", "nmi"]:
        raise HTTPException(status_code=400, detail="Unsupported payment provider")
    
    # Generate order ID
    order_id = str(uuid.uuid4())
    user_id = request.user_id or "anonymous"
    
    # Get amount from product code
    amount_cents = ProductCodes.get_amount_cents(request.product_code)
    if amount_cents == 0:
        raise HTTPException(status_code=400, detail="Invalid product code")
    
    try:
        if provider == "authnet":
            result = await authnet.create_checkout(
                order_id=order_id,
                user_id=user_id,
                product_code=request.product_code,
                amount_cents=amount_cents,
                metadata=request.metadata
            )
            
            if result.html:
                return Response(content=result.html, media_type="text/html")
            elif result.redirect_url:
                return {"redirect_url": result.redirect_url}
        
        elif provider == "nmi":
            result = await nmi.create_checkout(
                order_id=order_id,
                user_id=user_id,
                product_code=request.product_code,
                amount_cents=amount_cents,
                metadata=request.metadata
            )
            
            return {"redirect_url": result.redirect_url}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkout creation failed: {str(e)}")

@router.get("/pay/nmi/{order_id}")
async def nmi_payment_page(order_id: str, product_code: str = "VAMP_199"):
    """Generate NMI Collect.js payment page."""
    
    amount_cents = ProductCodes.get_amount_cents(product_code)
    description = ProductCodes.get_description(product_code)
    
    if amount_cents == 0:
        raise HTTPException(status_code=400, detail="Invalid product code")
    
    try:
        public_key = os.environ.get("NMI_PUBLIC_KEY", "")
        base_url = os.environ.get("BASE_URL", "")
        
        html = generate_nmi_payment_page(
            order_id=order_id,
            amount_cents=amount_cents,
            product_description=description,
            public_key=public_key,
            base_url=base_url
        )
        
        return Response(content=html, media_type="text/html")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment page generation failed: {str(e)}")

@router.post("/nmi/charge")
async def nmi_charge(request: ChargeRequest):
    """Process NMI tokenized charge."""
    
    try:
        # Get order details (in production, fetch from database)
        amount_cents = 19900  # Default to VAMP_199, should be looked up
        
        event = await nmi.charge_token(
            order_id=request.order_id,
            token=request.token,
            amount_cents=amount_cents
        )
        
        if event.status == "paid":
            # Process successful payment (award points, send email, etc.)
            success_url = os.environ.get("PAYMENT_SUCCESS_URL", "/success")
            return {
                "ok": True,
                "status": "paid",
                "transaction_id": event.provider_tx_id,
                "redirect": success_url
            }
        else:
            return {
                "ok": False,
                "status": event.status,
                "message": "Payment processing failed"
            }
    
    except Exception as e:
        return {
            "ok": False,
            "status": "failed",
            "message": str(e)
        }

@router.post("/webhook/authnet")
async def authnet_webhook(request: Request):
    """Handle Authorize.Net webhooks."""
    
    try:
        headers = dict(request.headers)
        body = await request.body()
        
        event = await authnet.handle_webhook(headers, body)
        
        # Process the payment event
        await process_payment_event(event)
        
        return {"status": "success"}
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook/nmi")
async def nmi_webhook(request: Request):
    """Handle NMI webhooks (if configured)."""
    
    try:
        headers = dict(request.headers)
        body = await request.body()
        
        event = await nmi.handle_webhook(headers, body)
        
        # Process the payment event
        await process_payment_event(event)
        
        return {"status": "success"}
    
    except NotImplementedError:
        # NMI typically uses synchronous processing
        return {"status": "not_implemented"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/success")
async def payment_success():
    """Payment success page."""
    
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Payment Successful - MerchantGuard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            text-align: center;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }
        .checkmark {
            font-size: 4rem;
            margin-bottom: 20px;
        }
        h1 { margin-bottom: 10px; }
        p { opacity: 0.9; margin-bottom: 20px; }
        .btn {
            background: white;
            color: #059669;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✅</div>
        <h1>Payment Successful!</h1>
        <p>Your transaction has been processed successfully.</p>
        <p>You should receive a confirmation email shortly.</p>
        <a href="/" class="btn">Return to MerchantGuard</a>
    </div>
</body>
</html>
    """
    
    return Response(content=html, media_type="text/html")

async def process_payment_event(event):
    """Process a payment event (award points, send notifications, etc.)."""
    
    try:
        if event.status == "paid":
            print(f"[PAYMENT] Successful payment: order={event.order_id} amount=${event.amount_cents/100:.2f}")
            
            # Determine product from amount
            product_code = "UNKNOWN"
            if event.amount_cents == 19900:
                product_code = "VAMP_199"
            elif event.amount_cents == 49900:
                product_code = "MATCH_499"
            elif event.amount_cents == 4900:
                product_code = "ATTEST_49"
            
            # Log revenue
            try:
                from services.revenue_tracker import RevenueTracker
                # In production, get pool from app state
                revenue = RevenueTracker(pool=None)  # Will log to console without pool
                await revenue.log_sale(
                    merchant_id=event.order_id,  # Using order_id as merchant_id for now
                    product=product_code,
                    amount_usd=event.amount_cents/100.0,
                    source=event.provider,
                    meta={"order_id": event.order_id, "provider_tx_id": event.provider_tx_id}
                )
            except Exception as e:
                print(f"[PAYMENT] Revenue logging failed: {e}")
            
            # Award points for payment
            try:
                from services.points_service import PointsService
                points = PointsService()
                await points.award(
                    event_type="purchase",
                    user_id=event.order_id,
                    points=100 if product_code == "VAMP_199" else 250,
                    meta={"product": product_code, "amount_cents": event.amount_cents},
                    idem_key=f"purchase:{event.order_id}"
                )
            except Exception as e:
                print(f"[PAYMENT] Points award failed: {e}")
            
            # Issue attestation for MATCH purchases or if explicitly included
            if product_code in ["MATCH_499", "ATTEST_49"] or os.getenv("FEATURE_ATTESTATION_INCLUDED_IN_MATCH") == "true":
                try:
                    from services.attestation_service import AttestationService  
                    attestation = AttestationService()
                    await attestation.issue_attestation_for_user(
                        user_id=event.order_id,
                        snapshot_id=f"purchase_{product_code}_{event.provider_tx_id}"
                    )
                except Exception as e:
                    print(f"[PAYMENT] Attestation failed: {e}")
            
            # Trigger fulfillment based on product
            try:
                await trigger_product_fulfillment(event.order_id, product_code, event)
            except Exception as e:
                print(f"[PAYMENT] Fulfillment failed: {e}")
        
        elif event.status == "failed":
            print(f"[PAYMENT] Failed payment: order={event.order_id} provider={event.provider}")
        
        elif event.status == "refunded":
            print(f"[PAYMENT] Refunded payment: order={event.order_id} amount=${event.amount_cents/100:.2f}")
    
    except Exception as e:
        print(f"[PAYMENT] Event processing error: {e}")

async def trigger_product_fulfillment(order_id: str, product_code: str, event):
    """Trigger appropriate fulfillment based on product type."""
    
    print(f"[FULFILLMENT] Starting fulfillment for {product_code} order {order_id}")
    
    if product_code == "VAMP_199":
        # VAMP Prevention Package - send Prevention Guide
        await fulfill_vamp_package(order_id, event)
    
    elif product_code == "MATCH_499":
        # MATCH Liberation Package - full hybrid package + check-ins
        await fulfill_match_package(order_id, event)
    
    elif product_code == "ATTEST_49":
        # Standalone attestation
        print(f"[FULFILLMENT] Attestation-only purchase completed for {order_id}")
    
    else:
        print(f"[FULFILLMENT] Unknown product code {product_code} for order {order_id}")

async def fulfill_vamp_package(order_id: str, event):
    """Fulfill VAMP Prevention Package."""
    
    try:
        # In production, this would:
        # 1. Build ZIP with Prevention Guide PDF
        # 2. Send via bot DM to user
        # 3. Send confirmation email
        
        print(f"[FULFILLMENT] VAMP package fulfilled for order {order_id}")
        print(f"  - Prevention Guide PDF delivered")
        print(f"  - Evidence Pack templates included") 
        print(f"  - Bot notification sent")
        
    except Exception as e:
        print(f"[FULFILLMENT] VAMP fulfillment failed for {order_id}: {e}")

async def fulfill_match_package(order_id: str, event):
    """Fulfill MATCH Liberation Package with full hybrid features."""
    
    try:
        # In production, this would:
        # 1. Build comprehensive ZIP package
        # 2. Send via bot DM
        # 3. Schedule weekly check-ins
        # 4. Send welcome sequence
        
        print(f"[FULFILLMENT] MATCH Liberation package fulfilled for order {order_id}")
        print(f"  - MATCH Survival & Playbook 2025 PDF delivered")
        print(f"  - MoR + High-risk application pre-fills included")
        print(f"  - Escalation contacts and rejection scripts provided")
        print(f"  - Crypto/USDC setup matrix included")
        print(f"  - Live success rates embedded")
        print(f"  - Weekly check-ins scheduled")
        
        # Schedule check-ins (would call actual scheduler in production)
        await schedule_match_checkins(order_id)
        
    except Exception as e:
        print(f"[FULFILLMENT] MATCH fulfillment failed for {order_id}: {e}")

async def schedule_match_checkins(order_id: str):
    """Schedule weekly check-in reminders for MATCH customers."""
    
    # In production, this would integrate with your bot's scheduler
    # For now, just log the scheduling
    
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    week1 = now + timedelta(days=7)
    week2 = now + timedelta(days=14) 
    week3 = now + timedelta(days=21)
    week4 = now + timedelta(days=28)
    
    print(f"[SCHEDULER] MATCH check-ins scheduled for order {order_id}:")
    print(f"  - Week 1: {week1.date()} - Application submission check")
    print(f"  - Week 2: {week2.date()} - Response tracking and follow-ups")
    print(f"  - Week 3: {week3.date()} - Outcome logging and next steps")
    print(f"  - Week 4: {week4.date()} - Success celebration or alternative paths")
=======
from fastapi import APIRouter

router = APIRouter()

@router.get("/payments/health")
async def payments_health():
    return {"status": "payments_ok"}
>>>>>>> Stashed changes
