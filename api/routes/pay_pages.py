"""
Hosted payment pages for providers that need client-side collection.
Currently supports NMI Collect.js integration.
"""

import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
import asyncpg

from services.payments.adapter_base import ProductCodes
from services.payments.nmi_adapter import generate_nmi_payment_page

router = APIRouter(tags=["payment-pages"])

@router.get("/pay/nmi/{order_id}", response_class=HTMLResponse)
async def nmi_payment_page(order_id: str, request: Request):
    """Serve NMI Collect.js payment page for a specific order."""
    
    try:
        # Get database pool
        if not hasattr(request.app.state, 'pg_pool'):
            raise HTTPException(status_code=500, detail="Database not available")
        
        pool = request.app.state.pg_pool
        
        # Get order details
        async with pool.acquire() as conn:
            order = await conn.fetchrow("""
                SELECT user_id, product_code, amount_cents, currency, status, provider
                FROM payments_orders 
                WHERE id = $1
            """, order_id)
        
        if not order:
            return HTMLResponse("""
<!DOCTYPE html>
<html>
<head><title>Order Not Found</title></head>
<body>
    <h1>Order Not Found</h1>
    <p>The payment link you followed is invalid or expired.</p>
    <a href="https://t.me/guardscorebot">Return to GuardScore Bot</a>
</body>
</html>
            """, status_code=404)
        
        # Check if order is already paid
        if order["status"] == "paid":
            success_url = os.environ.get("NMI_HOSTED_SUCCESS", "/payments/success")
            return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url={success_url}">
    <title>Redirecting...</title>
</head>
<body>
    <p>This order has already been paid. <a href="{success_url}">Continue</a></p>
</body>
</html>
            """)
        
        # Verify this is an NMI order
        if order["provider"] != "nmi":
            raise HTTPException(status_code=400, detail="Invalid payment provider for this page")
        
        # Get NMI configuration
        public_key = os.environ.get("NMI_PUBLIC_KEY")
        base_url = os.environ.get("BASE_URL")
        
        if not public_key or not base_url:
            raise HTTPException(status_code=500, detail="Payment configuration incomplete")
        
        # Get product description
        product_description = ProductCodes.get_description(order["product_code"])
        
        # Generate the payment page HTML
        payment_html = generate_nmi_payment_page(
            order_id=order_id,
            amount_cents=order["amount_cents"],
            product_description=product_description,
            public_key=public_key,
            base_url=base_url
        )
        
        return HTMLResponse(content=payment_html)
        
    except Exception as e:
        # Return error page
        return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Payment Error</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: system-ui;
            background: #1e293b;
            color: white;
            padding: 40px 20px;
            text-align: center;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            max-width: 500px;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
        }}
        a {{ color: #22d3ee; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Payment Error</h1>
        <p>Unable to load payment page. Please try again or contact support.</p>
        <p><a href="https://t.me/guardscorebot">Return to GuardScore Bot</a></p>
        <details style="margin-top: 20px; text-align: left;">
            <summary>Error Details</summary>
            <code>{str(e)}</code>
        </details>
    </div>
</body>
</html>
        """, status_code=500)

@router.get("/pay/test")
async def test_payment_page():
    """Test payment page for development/debugging."""
    
    test_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Payment System Test</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: system-ui;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            padding: 40px 20px;
            margin: 0;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }}
        .test-section {{
            margin: 20px 0;
            padding: 20px;
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
        }}
        .test-button {{
            background: #22d3ee;
            color: #1e293b;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            margin: 5px;
            text-decoration: none;
            display: inline-block;
        }}
        .test-button:hover {{
            background: #0891b2;
        }}
        .provider-badge {{
            background: #059669;
            color: white;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status {{
            margin: 20px 0;
            padding: 15px;
            border-radius: 8px;
            font-family: monospace;
        }}
        .status.success {{ background: rgba(16, 185, 129, 0.2); color: #10b981; }}
        .status.error {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
        .status.info {{ background: rgba(59, 130, 246, 0.2); color: #3b82f6; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MerchantGuard Payment System Test</h1>
        
        <div class="status info">
            <strong>Current Provider:</strong> <span class="provider-badge">{os.environ.get('PAYMENTS_PROVIDER', 'authnet')}</span><br>
            <strong>Environment:</strong> {os.environ.get('APP_ENV', 'development')}<br>
            <strong>Base URL:</strong> {os.environ.get('BASE_URL', 'not configured')}
        </div>
        
        <div class="test-section">
            <h3>Test Payments ($0.50)</h3>
            <p>Create small test transactions to verify payment processing:</p>
            
            <a href="/payments/test?user_id=test_user_1&amount_cents=50" class="test-button">
                Test Payment #1
            </a>
            <a href="/payments/test?user_id=test_user_2&amount_cents=100" class="test-button">
                Test Payment #2 ($1.00)
            </a>
            <a href="/payments/test?user_id=test_user_3&amount_cents=500" class="test-button">
                Test Payment #3 ($5.00)
            </a>
        </div>
        
        <div class="test-section">
            <h3>Product Tests</h3>
            <p>Test actual product purchases:</p>
            
            <button class="test-button" onclick="testProduct('ATTEST_49', 4900)">
                Attestation ($49)
            </button>
            <button class="test-button" onclick="testProduct('VAMP_199', 19900)">
                VAMP Protection ($199)
            </button>
            <button class="test-button" onclick="testProduct('MATCH_499', 49900)">
                MATCH Liberation ($499)
            </button>
        </div>
        
        <div class="test-section">
            <h3>Environment Check</h3>
            <div id="env-check">
                <button class="test-button" onclick="checkEnvironment()">
                    Check Configuration
                </button>
            </div>
            <div id="env-results"></div>
        </div>
        
        <div class="test-section">
            <h3>Recent Orders</h3>
            <button class="test-button" onclick="loadRecentOrders()">
                Load Recent Test Orders
            </button>
            <div id="recent-orders"></div>
        </div>
    </div>
    
    <script>
        async function testProduct(productCode, amountCents) {{
            try {{
                const response = await fetch('/payments/checkout', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{
                        user_id: `test_${{Date.now()}}`,
                        product_code: productCode,
                        amount_cents: amountCents,
                        metadata: {{ test: true, timestamp: new Date().toISOString() }}
                    }})
                }});
                
                if (response.headers.get('content-type')?.includes('text/html')) {{
                    // HTML response (auto-submit form)
                    const html = await response.text();
                    const newWindow = window.open();
                    newWindow.document.write(html);
                }} else {{
                    // JSON response (redirect URL)
                    const data = await response.json();
                    if (data.redirect_url) {{
                        window.open(data.redirect_url, '_blank');
                    }} else {{
                        alert(`Order created: ${{data.order_id}}`);
                    }}
                }}
            }} catch (error) {{
                alert(`Error: ${{error.message}}`);
            }}
        }}
        
        async function checkEnvironment() {{
            const results = document.getElementById('env-results');
            results.innerHTML = '<p>Checking configuration...</p>';
            
            const checks = [
                {{ name: 'Database', endpoint: '/payments/test?user_id=config_test&amount_cents=1' }},
                // Add more checks as needed
            ];
            
            let html = '<h4>Configuration Status:</h4>';
            
            for (const check of checks) {{
                try {{
                    const response = await fetch(check.endpoint);
                    const status = response.ok ? '✅' : '❌';
                    html += `<p>${{status}} ${{check.name}}</p>`;
                }} catch (error) {{
                    html += `<p>❌ ${{check.name}} (Error: ${{error.message}})</p>`;
                }}
            }}
            
            results.innerHTML = html;
        }}
        
        async function loadRecentOrders() {{
            // This would require an admin endpoint to view recent orders
            document.getElementById('recent-orders').innerHTML = 
                '<p>Recent orders endpoint not implemented. Check database directly.</p>';
        }}
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=test_html)