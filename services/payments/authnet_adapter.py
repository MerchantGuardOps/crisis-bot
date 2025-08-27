"""
Authorize.Net payment adapter using Accept Hosted (SAQ-A compliant).
Handles payment page creation and webhook processing.
"""

import os
import json
import hmac
import hashlib
import uuid
from typing import Dict, Any, Optional
from .adapter_base import PaymentAdapter, CheckoutResult, PaymentEvent, ProductCodes

class AuthorizeNetAdapter(PaymentAdapter):
    """Authorize.Net payment processing using Accept Hosted."""
    
    def __init__(self):
        self.login_id = os.environ.get("AUTHNET_API_LOGIN_ID", "")
        self.txn_key = os.environ.get("AUTHNET_TRANSACTION_KEY", "")
        self.sig_hex = os.environ.get("AUTHNET_SIGNATURE_KEY_HEX", "")
        self.env = os.environ.get("AUTHNET_ENV", "production")
        self.return_url = os.environ.get("AUTHNET_RETURN_URL", "")
        self.cancel_url = os.environ.get("AUTHNET_CANCEL_URL", "")
        
        # API endpoints
        if self.env == "production":
            self.api_endpoint = "https://api2.authorize.net/xml/v1/request.api"
            self.hosted_endpoint = "https://accept.authorize.net/payment/payment"
        else:
            self.api_endpoint = "https://apitest.authorize.net/xml/v1/request.api"
            self.hosted_endpoint = "https://test.authorize.net/payment/payment"
    
    @property
    def provider(self) -> str:
        return "authnet"
    
    async def _post_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request to Authorize.Net."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.api_endpoint, 
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise RuntimeError(f"Authorize.Net API error: {str(e)}")
    
    async def create_checkout(
        self, 
        *, 
        order_id: str, 
        user_id: str, 
        product_code: str,
        amount_cents: int, 
        currency: str = "USD", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> CheckoutResult:
        """Create Accept Hosted payment page."""
        
        amount = f"{amount_cents/100:.2f}"
        description = ProductCodes.get_description(product_code)
        
        # Build the hosted payment page request
        request_payload = {
            "getHostedPaymentPageRequest": {
                "merchantAuthentication": {
                    "name": self.login_id,
                    "transactionKey": self.txn_key
                },
                "transactionRequest": {
                    "transactionType": "authCaptureTransaction",
                    "amount": amount,
                    "order": {
                        "invoiceNumber": order_id,
                        "description": description
                    },
                    "customer": {
                        "id": user_id
                    }
                },
                "hostedPaymentSettings": {
                    "setting": [
                        {
                            "settingName": "hostedPaymentReturnOptions",
                            "settingValue": json.dumps({
                                "showReceipt": True,
                                "url": self.return_url,
                                "urlText": "Return to MerchantGuard",
                                "cancelUrl": self.cancel_url,
                                "cancelUrlText": "Cancel"
                            })
                        },
                        {
                            "settingName": "hostedPaymentButtonOptions",
                            "settingValue": json.dumps({
                                "text": f"Pay ${amount_cents/100:.2f}"
                            })
                        },
                        {
                            "settingName": "hostedPaymentStyleOptions",
                            "settingValue": json.dumps({
                                "bgColor": "#1e293b"
                            })
                        }
                    ]
                }
            }
        }
        
        # Add metadata if provided
        if metadata:
            request_payload["getHostedPaymentPageRequest"]["transactionRequest"]["userFields"] = {
                "userField": [
                    {"name": k, "value": str(v)} for k, v in metadata.items()
                ]
            }
        
        try:
            response_data = await self._post_api(request_payload)
            
            # Extract token from response
            token = response_data.get("token")
            if not token:
                error_msgs = response_data.get("messages", {}).get("message", [])
                error_text = "; ".join([msg.get("text", "") for msg in error_msgs])
                raise RuntimeError(f"No token received: {error_text}")
            
            # Generate auto-submit HTML form
            html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Secure Checkout - MerchantGuard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            margin: 0;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }}
        .container {{
            text-align: center;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }}
        .spinner {{
            border: 3px solid rgba(255,255,255,0.3);
            border-top: 3px solid #22d3ee;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body onload="document.forms[0].submit()">
    <div class="container">
        <div class="spinner"></div>
        <h3>Redirecting to Secure Checkout...</h3>
        <p>You will be redirected to Authorize.Net's secure payment page.</p>
        <form method="post" action="{self.hosted_endpoint}" style="display:none;">
            <input type="hidden" name="token" value="{token}"/>
            <noscript>
                <input type="submit" value="Continue to Payment" 
                       style="background:#22d3ee;color:white;padding:12px 24px;border:none;border-radius:8px;font-size:16px;cursor:pointer;">
            </noscript>
        </form>
    </div>
</body>
</html>
"""
            
            return CheckoutResult(
                provider="authnet",
                order_id=order_id,
                html=html
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to create checkout: {str(e)}")
    
    def _verify_webhook_signature(self, headers: Dict[str, str], body: bytes) -> bool:
        """Verify Authorize.Net webhook signature."""
        # Get signature from headers (case-insensitive)
        sig_header = None
        for key, value in headers.items():
            if key.lower() == "x-anet-signature":
                sig_header = value
                break
        
        if not sig_header or not sig_header.lower().startswith("sha512="):
            return False
        
        try:
            # Extract hex digest from signature header
            their_hex = sig_header.split("=", 1)[1]
            
            # Convert hex signature key to bytes
            key = bytes.fromhex(self.sig_hex)
            
            # Calculate expected signature
            expected_digest = hmac.new(key, body, hashlib.sha512).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(expected_digest, their_hex)
            
        except Exception:
            return False
    
    async def handle_webhook(self, headers: Dict[str, str], body: bytes) -> PaymentEvent:
        """Handle Authorize.Net webhook and return normalized payment event."""
        
        # Verify webhook signature
        if not self._verify_webhook_signature(headers, body):
            raise ValueError("Invalid Authorize.Net webhook signature")
        
        try:
            # Parse webhook payload
            payload = json.loads(body.decode("utf-8"))
            
            # Extract event details
            event_type = payload.get("eventType", "")
            event_data = payload.get("payload", {})
            
            # Determine payment status based on event type
            if event_type == "net.authorize.payment.authcapture.created":
                status = "paid"
            elif event_type in [
                "net.authorize.payment.void.created",
                "net.authorize.payment.refund.created"
            ]:
                status = "refunded"
            elif event_type in [
                "net.authorize.payment.fraud.held",
                "net.authorize.payment.fraud.declined"
            ]:
                status = "failed"
            else:
                status = "processing"
            
            # Extract transaction details
            order_data = event_data.get("order", {}) or {}
            order_id = order_data.get("invoiceNumber") or event_data.get("id", str(uuid.uuid4()))
            
            # Get transaction ID
            tx_id = event_data.get("id") or event_data.get("transId") or ""
            
            # Extract amount (try different fields)
            amount_str = (
                event_data.get("authAmount") or 
                event_data.get("settleAmount") or 
                event_data.get("amount") or 
                "0.00"
            )
            amount_cents = int(round(float(amount_str) * 100))
            
            # Extract customer info if available
            customer_data = event_data.get("customer", {}) or {}
            customer_id = customer_data.get("id")
            email = customer_data.get("email")
            
            return PaymentEvent(
                provider="authnet",
                order_id=order_id,
                provider_tx_id=tx_id,
                amount_cents=amount_cents,
                currency="USD",  # Authorize.Net typically uses USD
                status=status,
                raw=payload
            )
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid webhook JSON: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Webhook processing error: {str(e)}")
    
