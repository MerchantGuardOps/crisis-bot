# handlers/promo_codes.py - Promo Code System for Revenue Boost
"""
Promo code system for package discounts and urgency creation
Perfect for revenue optimization and conversion boosts
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import logging

from analytics.ltv_tracking import track_event
from handlers.packages import PACKAGE_CATALOG, get_package_by_id

router = Router()
logger = logging.getLogger(__name__)

# Active promo codes configuration
PROMO_CODES = {
    "FIRST20": {
        "discount_percent": 20,
        "description": "Early adopter discount",
        "valid_until": "2025-12-31",
        "min_purchase": 97,
        "max_uses": 1000,
        "current_uses": 0,
        "active": True
    },
    "CRYPTO50": {
        "discount_percent": 10, 
        "description": "Crypto founder special",
        "valid_until": "2025-09-30",
        "min_purchase": 297,
        "applicable_packages": ["kit_crypto_499"],
        "current_uses": 0,
        "active": True
    },
    "URGENT297": {
        "discount_percent": 15,
        "description": "Emergency review rush discount",
        "valid_until": "2025-09-01", 
        "applicable_packages": ["pkg_review_297"],
        "current_uses": 0,
        "active": True
    }
}

@router.callback_query(F.data.startswith("apply_promo:"))
async def handle_promo_application(callback: CallbackQuery):
    """Handle promo code application during purchase flow"""
    await callback.answer()
    
    # Extract package ID from callback
    package_id = callback.data.split(":", 1)[1]
    package = get_package_by_id(package_id)
    
    if not package:
        await callback.message.edit_text("❌ Package not found.")
        return
    
    promo_text = f"""🎯 **Apply Promo Code**

**Package:** {package['name']} (${package['price']})

Enter a promo code to get a discount on your purchase:

**Available Codes:**
• `FIRST20` - 20% off any package (early adopter special)
• `CRYPTO50` - 10% off crypto kit
• `URGENT297` - 15% off emergency review

Type your promo code or click below to continue without discount:"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Continue Without Discount", callback_data=f"buy:{package_id}")],
        [InlineKeyboardButton(text="🔙 Back to Package", callback_data=f"show_package:{package_id}")],
        [InlineKeyboardButton(text="📦 Browse All Packages", callback_data="show_catalog")]
    ])
    
    await callback.message.edit_text(promo_text, reply_markup=kb, parse_mode="Markdown")

@router.message(F.text.regexp(r"^[A-Z0-9]{4,15}$"))
async def handle_promo_code_entry(message: Message):
    """Handle promo code text entry"""
    promo_code = message.text.upper().strip()
    user_id = message.from_user.id
    
    # Check if it's a valid promo code
    if promo_code not in PROMO_CODES:
        await message.answer(
            f"❌ **Invalid Promo Code**\n\n"
            f"'{promo_code}' is not a valid promo code.\n\n"
            f"**Valid codes:**\n"
            f"• `FIRST20` - 20% off any package\n"
            f"• `CRYPTO50` - 10% off crypto kit\n" 
            f"• `URGENT297` - 15% off emergency review\n\n"
            f"Try again or browse packages: /start",
            parse_mode="Markdown"
        )
        return
    
    promo = PROMO_CODES[promo_code]
    
    # Validate promo code
    if not promo["active"]:
        await message.answer("❌ This promo code is no longer active.")
        return
    
    # Check expiry
    if datetime.now() > datetime.strptime(promo["valid_until"], "%Y-%m-%d"):
        await message.answer("❌ This promo code has expired.")
        return
    
    # Track promo code usage
    await track_event("promo_code_applied", {
        "user_id": user_id,
        "promo_code": promo_code,
        "discount_percent": promo["discount_percent"],
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Show applicable packages with discount
    await show_discounted_packages(message, promo_code, promo)

async def show_discounted_packages(message: Message, promo_code: str, promo: dict):
    """Show packages with promo discount applied"""
    
    applicable_packages = promo.get("applicable_packages", [pkg["id"] for pkg in PACKAGE_CATALOG])
    min_purchase = promo.get("min_purchase", 0)
    
    discount_text = f"""🎉 **Promo Code Applied: {promo_code}**

✅ **{promo['discount_percent']}% discount** - {promo['description']}
⏰ **Valid until:** {promo['valid_until']}

**Choose your discounted package:**"""

    keyboard = []
    
    for package in PACKAGE_CATALOG:
        if package["id"] in applicable_packages and package["price"] >= min_purchase:
            original_price = package["price"]
            discounted_price = int(original_price * (1 - promo["discount_percent"] / 100))
            savings = original_price - discounted_price
            
            button_text = f"{package['name']} - ${discounted_price} (Save ${savings}!)"
            callback_data = f"buy_promo:{package['id']}:{promo_code}"
            
            keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    if not keyboard:
        await message.answer(f"❌ No packages qualify for the {promo_code} discount.")
        return
    
    # Add utility buttons
    keyboard.append([InlineKeyboardButton(text="📦 See All Packages", callback_data="show_catalog")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(discount_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("buy_promo:"))
async def handle_promo_purchase(callback: CallbackQuery):
    """Handle purchase with promo code applied"""
    await callback.answer()
    
    # Parse callback data: buy_promo:package_id:promo_code
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.message.edit_text("❌ Invalid promo purchase data.")
        return
    
    package_id = parts[1]
    promo_code = parts[2]
    
    package = get_package_by_id(package_id)
    promo = PROMO_CODES.get(promo_code)
    
    if not package or not promo:
        await callback.message.edit_text("❌ Package or promo code not found.")
        return
    
    # Calculate discounted price
    original_price = package["price"]
    discounted_price = int(original_price * (1 - promo["discount_percent"] / 100))
    savings = original_price - discounted_price
    
    user_id = callback.from_user.id
    
    # Track promo purchase intent
    await track_event("promo_purchase_intent", {
        "user_id": user_id,
        "package_id": package_id,
        "promo_code": promo_code,
        "original_price": original_price,
        "discounted_price": discounted_price,
        "savings": savings,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Show purchase confirmation with discount
    purchase_text = f"""🎯 **Discounted Purchase Ready!**

**Package:** {package['name']}
**Original Price:** ~~${original_price}~~
**Your Price:** ${discounted_price} 
**You Save:** ${savings} ({promo['discount_percent']}% off)

**Promo Code:** {promo_code} - {promo['description']}

Ready to complete your discounted purchase?"""

    # Generate discounted Stripe checkout URL
    stripe_url = await generate_discounted_stripe_url(package, discounted_price, promo_code, user_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Pay ${discounted_price} (Save ${savings}!)", url=stripe_url)],
        [InlineKeyboardButton(text="🔙 Back to Packages", callback_data="show_catalog")],
        [InlineKeyboardButton(text="💬 Questions?", url="mailto:support@merchantguard.ai")]
    ])
    
    await callback.message.edit_text(purchase_text, reply_markup=kb, parse_mode="Markdown")

async def generate_discounted_stripe_url(package: dict, discounted_price: int, promo_code: str, user_id: int) -> str:
    """Generate Stripe checkout URL with promo discount applied"""
    
    # In production, this would create a Stripe checkout session with the discounted amount
    # For now, we'll use a special price ID or coupon system
    
    base_url = "https://checkout.stripe.com/pay"
    price_id = package["stripe_price_id"]
    
    # Add promo metadata for webhook processing
    checkout_url = f"{base_url}/{price_id}?prefilled_email=&client_reference_id={user_id}"
    checkout_url += f"&promo_code={promo_code}&discount_price={discounted_price}"
    
    return checkout_url

# Add promo code hints to regular purchase flow
def get_promo_hint_for_package(package_id: str) -> str:
    """Get promo code hint for specific package"""
    
    hints = {
        "kit_crypto_499": "💡 **Tip:** Use code `CRYPTO50` for 10% off!",
        "pkg_review_297": "⏰ **Limited time:** Code `URGENT297` saves 15%!",
    }
    
    return hints.get(package_id, "💡 **Tip:** Use code `FIRST20` for 20% off your first purchase!")

# Utility function to check if promo applies to package
def promo_applies_to_package(promo_code: str, package_id: str) -> bool:
    """Check if promo code applies to specific package"""
    
    promo = PROMO_CODES.get(promo_code)
    if not promo or not promo["active"]:
        return False
    
    package = get_package_by_id(package_id)
    if not package:
        return False
    
    # Check minimum purchase
    if package["price"] < promo.get("min_purchase", 0):
        return False
    
    # Check package restrictions
    applicable_packages = promo.get("applicable_packages")
    if applicable_packages and package_id not in applicable_packages:
        return False
    
    return True

# Export for use in other modules
__all__ = ['router', 'PROMO_CODES', 'get_promo_hint_for_package', 'promo_applies_to_package']