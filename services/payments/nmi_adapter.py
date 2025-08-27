"""
NMI (Network Merchants) payment adapter using Collect.js for tokenization.
Commonly used by high-risk processors like Durango, EMB, PaymentCloud.
"""

import os
import aiohttp
import urllib.parse
import uuid
from typing import Dict, Any, Optional
from .adapter_base import PaymentAdapter, CheckoutResult, PaymentEvent, ProductCodes

class NMIAdapter(PaymentAdapter):
    """NMI payment processing using Collect.js tokenization."""
    
    def __init__(self):
        self.security_key = os.environ["NMI_SECURITY_KEY"]
        self.public_key = os.environ["NMI_PUBLIC_KEY"]
        self.api_base = os.environ.get(
            "NMI_API_BASE", 
            "https://secure.networkmerchants.com/api/transact.php"
        )
        self.success_url = os.environ.get("NMI_HOSTED_SUCCESS")
        self.fail_url = os.environ.get("NMI_HOSTED_FAIL")
        
        # Base URL for our hosted payment pages
        self.base_url = os.environ["BASE_URL"]
    
    @property
    def provider(self) -> str:
        return "nmi"
    
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
        """Create NMI checkout by redirecting to our hosted Collect.js page."""
        
        # Redirect to our hosted payment page which will use Collect.js
        redirect_url = f"{self.base_url}/pay/nmi/{order_id}"
        
        return CheckoutResult(
            provider="nmi",
            order_id=order_id,
            redirect_url=redirect_url
        )
    
    async def charge_token(
        self, 
        *, 
        order_id: str, 
        token: str, 
        amount_cents: int, 
        currency: str = "USD",
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentEvent:
        """Charge a tokenized payment via NMI API."""
        
        amount = f"{amount_cents/100:.2f}"
        
        # Build form data for NMI API
        form_data = {
            "security_key": self.security_key,
            "type": "sale",
            "payment_token": token,
            "amount": amount,
            "orderid": order_id,
            "currency": currency
        }
        
        # Add metadata as custom fields if provided
        if metadata:
            for i, (key, value) in enumerate(metadata.items(), 1):
                if i <= 10:  # NMI supports up to 10 custom fields
                    form_data[f"custom{i}"] = f"{key}:{value}"
        
        try:
            # Make API request to NMI
            encoded_data = urllib.parse.urlencode(form_data)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_base,
                    data=encoded_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30
                ) as response:
                    response_text = await response.text()
            
            # Parse NMI response (name=value pairs)
            parsed_response = {}
            for pair in response_text.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    parsed_response[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
            
            # Determine transaction status
            result_code = parsed_response.get("response") or parsed_response.get("result")
            
            if str(result_code) in ("1", "Approved"):
                status = "paid"
            elif str(result_code) in ("2", "Declined"):
                status = "failed"
            else:
                status = "processing"
            
            # Extract transaction ID
            tx_id = (
                parsed_response.get("transactionid") or 
                parsed_response.get("transid") or 
                parsed_response.get("transaction_id") or
                ""
            )
            
            # Get response text/reason
            response_text_msg = parsed_response.get("responsetext", "")
            
            # If transaction failed, include error details
            if status == "failed":
                error_msg = f"Transaction declined: {response_text_msg}"
                if "cvv" in response_text_msg.lower():
                    error_msg += " (CVV mismatch)"
                elif "avs" in response_text_msg.lower():
                    error_msg += " (Address verification failed)"
                raise RuntimeError(f"NMI payment failed: {error_msg}")
            
            return PaymentEvent(
                provider="nmi",
                order_id=order_id,
                provider_tx_id=tx_id,
                amount_cents=amount_cents,
                currency=currency,
                status=status,
                raw=parsed_response
            )
            
        except aiohttp.ClientError as e:
            raise RuntimeError(f"NMI API connection error: {str(e)}")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"NMI charge processing error: {str(e)}")
    
    async def handle_webhook(self, headers: Dict[str, str], body: bytes) -> PaymentEvent:
        """
        Handle NMI webhook (if configured).
        Many NMI setups use synchronous processing, so this might not be used.
        """
        # NMI webhooks are less standardized than Stripe/AuthNet
        # Implementation depends on specific NMI configuration
        raise NotImplementedError(
            "NMI webhook handling not implemented. "
            "NMI typically processes synchronously via charge_token()."
        )
    
    async def refund_payment(self, provider_tx_id: str, amount_cents: int) -> Dict[str, Any]:
        """Refund a payment via NMI API."""
        
        amount = f"{amount_cents/100:.2f}"
        
        form_data = {
            "security_key": self.security_key,
            "type": "refund",
            "transactionid": provider_tx_id,
            "amount": amount
        }
        
        try:
            encoded_data = urllib.parse.urlencode(form_data)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_base,
                    data=encoded_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30
                ) as response:
                    response_text = await response.text()
            
            # Parse response
            parsed_response = {}
            for pair in response_text.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    parsed_response[urllib.parse.unquote(key)] = urllib.parse.unquote(value)
            
            result_code = parsed_response.get("response") or parsed_response.get("result")
            
            if str(result_code) in ("1", "Approved"):
                return {
                    "success": True,
                    "refund_tx_id": parsed_response.get("transactionid", ""),
                    "amount_cents": amount_cents
                }
            else:
                error_msg = parsed_response.get("responsetext", "Refund failed")
                raise RuntimeError(f"NMI refund failed: {error_msg}")
                
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"NMI refund error: {str(e)}")

def generate_nmi_payment_page(
    order_id: str, 
    amount_cents: int, 
    product_description: str,
    public_key: str,
    base_url: str
) -> str:
    """Generate the Collect.js payment page HTML."""
    
    amount_display = f"${amount_cents/100:.2f}"
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Secure Checkout - {product_description}</title>
    <script src="https://secure.networkmerchants.com/token/Collect.js" 
            data-tokenization-key="{public_key}"
            data-variant="inline"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 500px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .amount {{
            font-size: 2rem;
            font-weight: 800;
            color: #22d3ee;
            margin-bottom: 8px;
        }}
        .description {{
            color: rgba(255,255,255,0.8);
            margin-bottom: 30px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: rgba(255,255,255,0.9);
        }}
        .collectjs-cc-number,
        .collectjs-cc-exp,
        .collectjs-cc-cvv {{
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 8px;
            padding: 12px;
            color: white;
            font-size: 16px;
            width: 100%;
        }}
        .form-row {{
            display: flex;
            gap: 15px;
        }}
        .form-row .form-group {{
            flex: 1;
        }}
        .pay-button {{
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            border: none;
            padding: 16px 32px;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
            transition: all 0.3s ease;
            box-shadow: 0 8px 24px rgba(239, 68, 68, 0.3);
        }}
        .pay-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 32px rgba(239, 68, 68, 0.4);
        }}
        .pay-button:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}
        .error {{
            color: #ff6b6b;
            margin-top: 10px;
            padding: 12px;
            background: rgba(255,107,107,0.1);
            border-radius: 8px;
            display: none;
        }}
        .loading {{
            display: none;
            text-align: center;
            margin-top: 20px;
        }}
        .spinner {{
            border: 3px solid rgba(255,255,255,0.3);
            border-top: 3px solid #22d3ee;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .secure-badge {{
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.2);
        }}
        .secure-badge small {{
            color: rgba(255,255,255,0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="amount">{amount_display}</div>
            <div class="description">{product_description}</div>
        </div>
        
        <form id="payment-form">
            <div class="form-group">
                <label class="form-label">Card Number</label>
                <div class="collectjs-cc-number" id="ccnumber"></div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Expiry Date</label>
                    <div class="collectjs-cc-exp" id="ccexp"></div>
                </div>
                <div class="form-group">
                    <label class="form-label">CVV</label>
                    <div class="collectjs-cc-cvv" id="cvv"></div>
                </div>
            </div>
            
            <button type="submit" class="pay-button" id="pay-btn">
                Pay {amount_display}
            </button>
            
            <div class="error" id="error-message"></div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Processing payment...</div>
            </div>
        </form>
        
        <div class="secure-badge">
            <small>
                🔒 Your payment is secured with 256-bit SSL encryption
            </small>
        </div>
    </div>

    <script>
        const form = document.getElementById('payment-form');
        const payBtn = document.getElementById('pay-btn');
        const errorDiv = document.getElementById('error-message');
        const loadingDiv = document.getElementById('loading');
        
        function showError(message) {{
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            payBtn.disabled = false;
            payBtn.textContent = 'Pay {amount_display}';
            loadingDiv.style.display = 'none';
        }}
        
        function showLoading() {{
            payBtn.disabled = true;
            payBtn.textContent = 'Processing...';
            errorDiv.style.display = 'none';
            loadingDiv.style.display = 'block';
        }}
        
        form.addEventListener('submit', function(e) {{
            e.preventDefault();
            showLoading();
            
            // Start payment request with Collect.js
            CollectJS.startPaymentRequest({{
                callback: function(response) {{
                    if (response.token) {{
                        // Send token to our server for processing
                        fetch('{base_url}/payments/nmi/charge', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Accept': 'application/json'
                            }},
                            body: JSON.stringify({{
                                order_id: '{order_id}',
                                token: response.token
                            }})
                        }})
                        .then(response => response.json())
                        .then(data => {{
                            if (data.ok && data.status === 'paid') {{
                                // Redirect to success page
                                window.location.href = data.redirect || '{base_url}/payments/success';
                            }} else {{
                                showError(data.message || 'Payment failed. Please try again.');
                            }}
                        }})
                        .catch(error => {{
                            console.error('Payment error:', error);
                            showError('Payment processing error. Please try again.');
                        }});
                    }} else {{
                        showError('Failed to tokenize payment information. Please check your card details.');
                    }}
                }},
                fieldsAvailableCallback: function() {{
                    console.log('Collect.js payment fields are available');
                }},
                fieldsNotAvailableCallback: function() {{
                    showError('Payment form failed to load. Please refresh the page.');
                }}
            }});
        }});
        
        // Handle Collect.js validation errors
        document.addEventListener('DOMContentLoaded', function() {{
            // Add any additional initialization here
            console.log('NMI payment page loaded for order: {order_id}');
        }});
    </script>
</body>
</html>
"""