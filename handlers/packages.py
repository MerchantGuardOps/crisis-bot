# handlers/packages.py - Package Deep-Link System
"""
Universal Package Catalog with One-Click Deep Links
Supports 7-package system with market-aware recommendations
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from analytics.ltv_tracking import track_event, LTVTracker
from analytics.hardening_metrics import track_performance, log_security_event
from config.feature_config import get_config

router = Router()
logger = logging.getLogger(__name__)

# Package catalog configuration
PACKAGE_CATALOG = [
    {
        "id": "pkg_quick_97",
        "name": "⚡ Quick Hit",
        "price": 97,
        "description": "Risk Score Check + Basic Recommendations",
        "delivery": "Instant",
        "type": "digital",
        "stripe_price_id": "price_1QEQuickFix97"
    },
    {
        "id": "pkg_auto_199", 
        "name": "📦 PSP Readiness Pack",
        "price": 199,
        "description": "Market-specific PSP shortlist + templates",
        "delivery": "Instant",
        "type": "digital", 
        "stripe_price_id": "price_1QEReadinessPack199"
    },
    {
        "id": "pkg_review_297",
        "name": "🩺 Emergency Review",
        "price": 297,
        "description": "20-30 min Loom review within 24-48h",
        "delivery": "24-48 hours",
        "type": "service",
        "stripe_price_id": "price_1QEEmergencyReview297"
    },
    {
        "id": "kit_builder_499",
        "name": "🛠️ Builder's Kit", 
        "price": 499,
        "description": "Complete US fintech compliance foundation",
        "delivery": "Interactive workflow",
        "type": "premium_kit",
        "stripe_price_id": "price_1QEBuilderKit499"
    },
    {
        "id": "kit_global_499",
        "name": "🌍 Global Founder Kit",
        "price": 499, 
        "description": "International banking + multi-jurisdiction compliance",
        "delivery": "Interactive workflow",
        "type": "premium_kit",
        "stripe_price_id": "price_1QEGlobalFounder499"
    },
    {
        "id": "kit_crypto_499",
        "name": "🔐 Crypto Founder's Kit",
        "price": 499,
        "description": "Banking + tokenomics compliance workflow",
        "delivery": "Interactive workflow", 
        "type": "premium_kit",
        "stripe_price_id": "price_1QECryptoFounder499"
    },
    {
        "id": "kit_cbd_499",
        "name": "🌿 CBD / High-Risk Kit",
        "price": 499,
        "description": "High-risk navigation with SOPs and Earned Passport",
        "delivery": "Interactive workflow",
        "type": "premium_kit", 
        "stripe_price_id": "price_1QECBDHighRisk499"
    }
]

# Market-specific recommendations
MARKET_RECOMMENDATIONS = {
    "mkt_us_cards": {
        "name": "US Cards",
        "hint": "Recommended: US Cards (VAMP thresholds apply).",
        "primary_packages": ["pkg_auto_199", "kit_builder_499", "pkg_review_297"],
        "context": "VAMP dispute penalties assessed at acquirer-program level (commonly $4 per dispute for 'Above Standard' and $8 for 'Excessive'). LATAM merchant threshold 1.5% is stricter than 2.2% in NA/EU."
    },
    "mkt_br_pix": {
        "name": "Brazil PIX", 
        "hint": "Recommended: Brazil PIX focus (dispute <0.6% to avoid 150 bps penalty).",
        "primary_packages": ["pkg_auto_199", "kit_global_499", "pkg_review_297"],
        "context": "Target ≤0.3% green, alert at 0.45%, red at ≥0.55%. Penalty impact commonly expressed as reserve overlays and 150 bps cost drag when >0.6%."
    },
    "mkt_eu_sca": {
        "name": "EU SCA",
        "hint": "Recommended: EU SCA readiness (PSD2 compliance critical).", 
        "primary_packages": ["pkg_auto_199", "kit_crypto_499", "kit_global_499"],
        "context": "Strong Customer Authentication (SCA) requirements under PSD2. Auth rates impact approval ratios significantly."
    }
}

@router.message(Command("start"))
async def handle_package_start(message: Message, command: CommandObject, state: FSMContext):
    """Handle /start commands with package parameters - HARDENED"""
    
    with track_performance("package_start_handler", str(message.from_user.id)):
        start_param = command.args if command.args else ""
        user_id = message.from_user.id
        
        # Sanitize input: cap to 64 chars (Telegram limit), trim trackers safely
        if start_param:
            original_param = start_param
            start_param = start_param[:64].strip()
            # Remove any non-alphanumeric chars except underscores and hyphens
            start_param = ''.join(c for c in start_param if c.isalnum() or c in '_-')
            
            # Log potential security issues
            if original_param != start_param:
                log_security_event("input_sanitization", "low", str(user_id), 
                                 original=original_param, sanitized=start_param)
        
        # Parse UTM parameters if present (format: param_utm_source_utm_medium_utm_campaign)
        utm_data = {}
        if '_utm_' in start_param:
            parts = start_param.split('_utm_')
            if len(parts) > 1:
                start_param = parts[0]  # Keep the main parameter
                # Parse UTM data from remaining parts
                for i, utm_part in enumerate(parts[1:]):
                    if i == 0:
                        utm_data['source'] = utm_part
                    elif i == 1:
                        utm_data['medium'] = utm_part
                    elif i == 2:
                        utm_data['campaign'] = utm_part
        
        # Track entry with enhanced data
        await track_event("package_entry", {
            "user_id": user_id,
            "param": start_param,
            "utm_source": utm_data.get("source", "direct"),
            "utm_medium": utm_data.get("medium", "telegram"),
            "utm_campaign": utm_data.get("campaign", "organic"),
            "entry_type": "deep_link" if start_param else "direct",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Handle unknown deep-link slugs gracefully
        if start_param and start_param not in [pkg["id"] for pkg in PACKAGE_CATALOG] and start_param not in MARKET_RECOMMENDATIONS and start_param != "packages_catalog_v1":
            log_security_event("unknown_deep_link", "medium", str(user_id), param=start_param)
            await message.answer(
                "🤔 **Link seems outdated or invalid**\n\n"
                "No worries! Let me show you our current packages:",
                parse_mode="Markdown"
            )
            await show_package_catalog(message, state)
            return
        
        # Route based on parameter
        if start_param == "packages_catalog_v1":
            await show_package_catalog(message, state)
        elif start_param in [pkg["id"] for pkg in PACKAGE_CATALOG]:
            await handle_direct_package(message, start_param, state)
        elif start_param in MARKET_RECOMMENDATIONS:
            await show_market_catalog(message, start_param, state)
        else:
            # Default behavior - pass to main Golden Flow
            return  # Let other handlers process this

async def show_package_catalog(message: Message, state: FSMContext, market_context: str = None, tos_accepted: bool = False):
    """Show universal package catalog with all 7 packages - HARDENED WITH TOS GATE"""
    
    user_data = await state.get_data()
    
    # Check if ToS has been accepted for this session
    if not tos_accepted and not user_data.get("tos_accepted", False):
        await show_tos_gate(message, state, market_context)
        return
    
    catalog_text = """🛡️ **Choose your path — instant fix or deep dive**

Get a **quick turnaround** ($97–$199) or the **full solution** ($499). Instant delivery. Educational guidance — not brokerage.

Issuing your **Compliance Passport**? You'll get it **Self-Attested** now, **Data-Verified/Earned** after tasks or kit completion.

📦 **Available Packages:**"""

    # Add market-specific hint if provided
    if market_context and market_context in MARKET_RECOMMENDATIONS:
        market_info = MARKET_RECOMMENDATIONS[market_context]
        catalog_text += f"\n\n💡 {market_info['hint']}"
    
    # Add legal disclaimer
    catalog_text += "\n\n⚖️ *All packages are educational resources. Not financial, legal, or investment advice.*"

    # Build keyboard with packages
    keyboard = []
    
    # Row 1: Quick options ($97-$297)
    row1 = []
    for pkg in PACKAGE_CATALOG[:3]:  # First 3 packages
        button_text = f"{pkg['name']} — ${pkg['price']}"
        row1.append(InlineKeyboardButton(text=button_text, callback_data=f"buy:{pkg['id']}"))
    keyboard.append(row1)
    
    # Row 2: Premium kits ($499) 
    row2 = []
    for pkg in PACKAGE_CATALOG[3:6]:  # Next 3 packages  
        button_text = f"{pkg['name']} — ${pkg['price']}"
        row2.append(InlineKeyboardButton(text=button_text, callback_data=f"buy:{pkg['id']}"))
    keyboard.append(row2)
    
    # Row 3: Last kit + utility buttons
    row3 = []
    last_pkg = PACKAGE_CATALOG[6]  # CBD kit
    row3.append(InlineKeyboardButton(text=f"{last_pkg['name']} — ${last_pkg['price']}", callback_data=f"buy:{last_pkg['id']}"))
    row3.append(InlineKeyboardButton(text="❓ Help", callback_data="pkg_help"))
    row3.append(InlineKeyboardButton(text="🔙 Back", callback_data="main_menu"))
    keyboard.append(row3)
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(catalog_text, reply_markup=kb, parse_mode="Markdown")

async def show_tos_gate(message: Message, state: FSMContext, market_context: str = None):
    """Show Terms of Service gate before package access"""
    
    tos_text = """📋 **Terms of Service & Disclaimer**

**Before accessing MerchantGuard™ packages:**

🔹 All packages are **educational resources** designed to inform and guide.
🔹 Content is **not financial, legal, or investment advice**.
🔹 Recommendations are general guidance - not specific to your situation.
🔹 PSP approval decisions are made solely by payment processors.
🔹 Results may vary based on your specific business circumstances.

**By continuing, you acknowledge:**
✅ You understand this is educational content only
✅ You will not rely solely on this information for business decisions
✅ You may seek professional advice for your specific situation
✅ You accept our full Terms of Service at merchantguard.ai/terms

**Ready to continue with these terms?**"""

    # Store market context for after ToS acceptance
    if market_context:
        await state.update_data(pending_market_context=market_context)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Accept - Show Packages", callback_data="tos_accept")],
        [InlineKeyboardButton(text="📄 Read Full Terms", url="https://merchantguard.ai/terms/")],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="main_menu")]
    ])
    
    await message.answer(tos_text, reply_markup=kb, parse_mode="Markdown")

async def show_market_catalog(message: Message, market_param: str, state: FSMContext):
    """Show market-aware package catalog with recommendations"""
    market_info = MARKET_RECOMMENDATIONS[market_param]
    
    # Store market context
    await state.update_data(market_context=market_param)
    
    market_text = f"""🎯 **{market_info['name']} Merchant Packages**

{market_info['hint']}

**Market Context:** {market_info['context']}

**Recommended packages for your market:**"""

    # Show catalog with market recommendations highlighted
    await show_package_catalog(message, state, market_param)

async def handle_direct_package(message: Message, package_id: str, state: FSMContext):
    """Handle direct package deep links"""
    # Find the package
    package = next((pkg for pkg in PACKAGE_CATALOG if pkg["id"] == package_id), None)
    if not package:
        await message.answer("❌ Package not found. Use /start to see available packages.")
        return
    
    user_id = message.from_user.id
    
    # Track direct package view
    await track_event("direct_package_view", {
        "user_id": user_id,
        "package_id": package_id,
        "package_price": package["price"],
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Show package details with immediate purchase option
    package_text = f"""🎯 **{package['name']}**

**Price:** ${package['price']}
**Delivery:** {package['delivery']}

{package['description']}

Ready to get started?"""

    # Different CTAs based on package type
    if package["type"] == "premium_kit":
        cta_text = f"🚀 Get {package['name']} — ${package['price']}"
        description_extra = "\n\n**What you get:**\n• Interactive step-by-step workflow\n• Personalized compliance templates\n• **Earned Compliance Passport** upon completion\n• Priority PSP network access"
    else:
        cta_text = f"💳 Purchase ${package['price']} — Instant Delivery"
        description_extra = "\n\n**Instant delivery** after payment confirmation."
    
    package_text += description_extra

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cta_text, callback_data=f"buy:{package_id}")],
        [InlineKeyboardButton(text="📋 View All Packages", callback_data="show_catalog")],
        [InlineKeyboardButton(text="❓ Questions", callback_data="pkg_help")]
    ])
    
    await message.answer(package_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("buy:"))
async def handle_package_purchase(callback: CallbackQuery, state: FSMContext):
    """Handle package purchase callbacks"""
    await callback.answer()
    
    package_id = callback.data.split(":", 1)[1]
    package = next((pkg for pkg in PACKAGE_CATALOG if pkg["id"] == package_id), None)
    
    if not package:
        await callback.message.edit_text("❌ Package not found.")
        return
    
    user_id = callback.from_user.id
    
    # Track purchase intent
    await track_event("purchase_intent", {
        "user_id": user_id, 
        "package_id": package_id,
        "package_price": package["price"],
        "source": "catalog_callback",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Generate Stripe checkout URL
    stripe_url = await generate_stripe_checkout_url(package, user_id)
    
    purchase_text = f"""🎯 **Great choice!**

**Package:** {package['name']}
**Price:** ${package['price']}
**Delivery:** {package['delivery']}

💳 **Pay securely with Stripe:**
{stripe_url}

After payment you'll receive:
• Instant delivery (digital products)
• Email confirmation with access details  
• Your Compliance Passport status will update
• 24/7 access to your purchase content

**Questions?** Contact support@merchantguard.ai"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Complete Payment", url=stripe_url)],
        [InlineKeyboardButton(text="🔙 Back to Catalog", callback_data="show_catalog")],
        [InlineKeyboardButton(text="💬 Contact Support", url="mailto:support@merchantguard.ai")]
    ])
    
    await callback.message.edit_text(purchase_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "show_catalog")
async def handle_show_catalog(callback: CallbackQuery, state: FSMContext):
    """Show package catalog from callback"""
    await callback.answer()
    await show_package_catalog(callback.message, state)

@router.callback_query(F.data == "pkg_help")
async def handle_package_help(callback: CallbackQuery, state: FSMContext):
    """Show package help and FAQ"""
    await callback.answer()
    
    help_text = """❓ **Package Help & FAQ**

**What's included?**
• Digital products: instant download after payment
• Service products: delivered within timeframe specified
• Premium kits: interactive workflow + earned passport

**Refund Policy:**
• Digital products: 7-day money-back guarantee
• Services: Satisfaction guaranteed or full refund
• Kits: 30-day money-back guarantee

**Important Notes:**
• All packages are educational artifacts, not financial advice
• Not brokerage or underwriting services
• PSP decisions are made by individual processors
• Results may vary based on your specific situation

**Support:**
• Email: support@merchantguard.ai
• Response time: Within 24 hours
• Live chat: Available during business hours

**Payment Security:**
• All payments processed via Stripe
• Your payment information is never stored
• 256-bit SSL encryption for all transactions"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Back to Packages", callback_data="show_catalog")],
        [InlineKeyboardButton(text="💬 Contact Support", url="mailto:support@merchantguard.ai")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(help_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "tos_accept")
async def handle_tos_acceptance(callback: CallbackQuery, state: FSMContext):
    """Handle ToS acceptance and show packages"""
    await callback.answer()
    
    # Mark ToS as accepted in session
    await state.update_data(tos_accepted=True)
    
    # Get any pending market context
    user_data = await state.get_data()
    market_context = user_data.get("pending_market_context")
    
    # Track ToS acceptance
    await track_event("tos_accepted", {
        "user_id": callback.from_user.id,
        "market_context": market_context,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await show_package_catalog(callback.message, state, market_context, tos_accepted=True)

async def generate_stripe_checkout_url(package: dict, user_id: int) -> str:
    """Generate Stripe checkout URL for package"""
    # In production, this would create a proper Stripe checkout session
    # For now, return the direct Stripe payment link
    
    base_url = "https://checkout.stripe.com/pay"
    price_id = package["stripe_price_id"]
    
    # Add UTM tracking for analytics
    checkout_url = f"{base_url}/{price_id}?prefilled_email=&client_reference_id={user_id}"
    
    # Add success/cancel URLs when available
    if get_config("STRIPE_SUCCESS_URL"):
        checkout_url += f"&success_url={get_config('STRIPE_SUCCESS_URL')}"
    if get_config("STRIPE_CANCEL_URL"):  
        checkout_url += f"&cancel_url={get_config('STRIPE_CANCEL_URL')}"
    
    return checkout_url

# Utility function to get package by ID
def get_package_by_id(package_id: str) -> dict:
    """Get package configuration by ID"""
    return next((pkg for pkg in PACKAGE_CATALOG if pkg["id"] == package_id), None)

# Export the router for main bot registration
__all__ = ['router', 'PACKAGE_CATALOG', 'MARKET_RECOMMENDATIONS']