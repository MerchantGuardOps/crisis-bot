# handlers/conversion_optimization.py - Revenue Optimization System
"""
Conversion optimization features for maximum revenue generation:
- Urgency messaging
- Social proof
- Scarcity tactics
- Exit intent capture
- Upsell sequences
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import random
import logging

from analytics.ltv_tracking import track_event
from handlers.packages import PACKAGE_CATALOG

router = Router()
logger = logging.getLogger(__name__)

# Revenue optimization messages
URGENCY_MESSAGES = {
    "time_sensitive": [
        "⏰ **Limited Time:** This pricing expires in 24 hours!",
        "🔥 **Flash Deal:** 48-hour special pricing - don't miss out!",
        "⚡ **Act Fast:** Only available this week at this price!"
    ],
    "scarcity": [
        "🎯 **Only 50 spots left** for personalized review this month!",
        "📈 **High demand:** 200+ merchants served this week!",  
        "🏆 **Exclusive:** Limited access - secure your spot now!"
    ],
    "social_proof": [
        "✅ **Join 1,000+ merchants** who solved their compliance issues!",
        "🚀 **Success stories:** 89% get approved within 30 days!",
        "⭐ **Trusted by founders** at Stripe, PayPal, and 500+ startups!"
    ]
}

# Revenue-focused call-to-actions
MONEY_CTAS = {
    "desperate": {
        "pkg_auto_199": "🆘 **URGENT:** Get compliant in 24 hours - $199",
        "pkg_review_297": "🩺 **EMERGENCY:** Expert review in 48h - $297", 
        "kit_crypto_499": "🔐 **CRYPTO CRISIS?** Complete solution - $499"
    },
    "aspirational": {
        "kit_builder_499": "🏗️ **BUILD YOUR EMPIRE:** Complete toolkit - $499",
        "kit_global_499": "🌍 **GO GLOBAL:** International mastery - $499",
        "pkg_quick_97": "⚡ **QUICK WIN:** Score boost in 10 min - $97"
    }
}

@router.callback_query(F.data == "show_money_maker")
async def show_money_maker_options(callback: CallbackQuery):
    """Show revenue-optimized package selection"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Track revenue-focused entry
    await track_event("money_maker_entry", {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Random urgency message for variety
    urgency = random.choice(URGENCY_MESSAGES["time_sensitive"])
    social_proof = random.choice(URGENCY_MESSAGES["social_proof"])
    
    money_text = f"""💰 **REVENUE-FOCUSED SOLUTIONS**

{urgency}

{social_proof}

**💸 INSTANT MONEY-MAKERS:**
*For merchants losing revenue RIGHT NOW*

**🚀 GROWTH ACCELERATORS:**
*For founders ready to scale BIG*"""

    keyboard = []
    
    # Desperate solutions (high urgency)
    keyboard.append([InlineKeyboardButton(
        text="🆘 URGENT: Get Approved in 24h - $199", 
        callback_data="money_buy:pkg_auto_199"
    )])
    
    keyboard.append([InlineKeyboardButton(
        text="🩺 EMERGENCY: Expert Review - $297", 
        callback_data="money_buy:pkg_review_297"
    )])
    
    # Growth solutions (aspirational)
    keyboard.append([InlineKeyboardButton(
        text="🏗️ BUILD EMPIRE: Complete Toolkit - $499", 
        callback_data="money_buy:kit_builder_499"
    )])
    
    keyboard.append([InlineKeyboardButton(
        text="🔐 CRYPTO CRISIS: Total Solution - $499", 
        callback_data="money_buy:kit_crypto_499"
    )])
    
    # Quick win option
    keyboard.append([InlineKeyboardButton(
        text="⚡ QUICK WIN: 10-Min Score Boost - $97", 
        callback_data="money_buy:pkg_quick_97"
    )])
    
    # Exit options
    keyboard.append([
        InlineKeyboardButton(text="📋 See Details", callback_data="show_catalog"),
        InlineKeyboardButton(text="❓ Questions", url="mailto:support@merchantguard.ai")
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(money_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("money_buy:"))
async def handle_money_purchase(callback: CallbackQuery):
    """Handle revenue-optimized purchase flow"""
    await callback.answer()
    
    package_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    # Find package
    package = next((pkg for pkg in PACKAGE_CATALOG if pkg["id"] == package_id), None)
    if not package:
        await callback.message.edit_text("❌ Package not found.")
        return
    
    # Track money-focused purchase intent
    await track_event("money_purchase_intent", {
        "user_id": user_id,
        "package_id": package_id,
        "price": package["price"],
        "source": "revenue_optimized_flow",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Revenue-focused messaging
    if package["price"] >= 297:
        urgency_msg = "🔥 **HIGH-VALUE INVESTMENT** - Typically saves 10x the cost!"
        roi_msg = f"**ROI:** Most clients see ${package['price'] * 10}+ in avoided losses"
    else:
        urgency_msg = "⚡ **INSTANT RESULTS** - See improvements within hours!"
        roi_msg = f"**Value:** Prevents ${package['price'] * 50}+ in potential rejections"
    
    social_proof = random.choice(URGENCY_MESSAGES["social_proof"])
    
    money_purchase_text = f"""💰 **SMART INVESTMENT CHOICE!**

**Package:** {package['name']}
**Investment:** ${package['price']}
**Delivery:** {package['delivery']}

{urgency_msg}

{roi_msg}

{social_proof}

**⏰ Limited Time Pricing - Don't Wait!**

Ready to secure your spot?"""

    # Enhanced CTA with urgency
    cta_text = f"💳 SECURE YOUR SPOT - ${package['price']}"
    if package["price"] >= 499:
        cta_text = f"🚀 INVEST IN SUCCESS - ${package['price']}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cta_text, callback_data=f"buy:{package_id}")],
        [InlineKeyboardButton(text="💎 Add Premium Support (+$97)", callback_data=f"upsell:{package_id}:support")],
        [InlineKeyboardButton(text="🔙 Other Options", callback_data="show_money_maker")]
    ])
    
    await callback.message.edit_text(money_purchase_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("upsell:"))
async def handle_upsell_offer(callback: CallbackQuery):
    """Handle upsell opportunities during purchase"""
    await callback.answer()
    
    # Parse upsell data: upsell:package_id:upsell_type
    parts = callback.data.split(":")
    if len(parts) != 3:
        return
    
    package_id = parts[1]
    upsell_type = parts[2]
    user_id = callback.from_user.id
    
    package = next((pkg for pkg in PACKAGE_CATALOG if pkg["id"] == package_id), None)
    if not package:
        return
    
    # Track upsell engagement
    await track_event("upsell_viewed", {
        "user_id": user_id,
        "package_id": package_id,
        "upsell_type": upsell_type,
        "base_price": package["price"],
        "timestamp": datetime.utcnow().isoformat()
    })
    
    if upsell_type == "support":
        total_price = package["price"] + 97
        
        upsell_text = f"""💎 **PREMIUM SUPPORT UPGRADE**

**Base Package:** {package['name']} - ${package['price']}
**Premium Support:** +$97
**Total Investment:** ${total_price}

**🎯 Premium Support Includes:**
• 24/7 priority email response  
• Direct line to compliance experts
• Unlimited follow-up questions for 30 days
• Implementation troubleshooting
• Success guarantee or money back

**💰 Value:** Prevents $5,000+ in compliance mistakes!

Most successful merchants choose Premium Support."""

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🚀 YES! Add Premium Support - ${total_price}", callback_data=f"buy_bundle:{package_id}:support")],
            [InlineKeyboardButton(text=f"📦 Just the Package - ${package['price']}", callback_data=f"buy:{package_id}")],
            [InlineKeyboardButton(text="🔙 Back to Options", callback_data="show_money_maker")]
        ])
        
        await callback.message.edit_text(upsell_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "exit_intent")
async def handle_exit_intent(callback: CallbackQuery):
    """Handle exit intent with last-chance offer"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Track exit intent
    await track_event("exit_intent_triggered", {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    exit_text = f"""⚠️ **WAIT! Don't Leave Empty-Handed**

Before you go, here's an exclusive offer:

🎁 **LAST CHANCE: Quick Hit Package**
• Usually $97 → **Today only: $67**
• Instant risk score + recommendations
• 30-minute implementation guide
• Basic compliance checklist

**This offer expires in 15 minutes!**

Over 500 merchants used this to get approved on their next application.

Don't let compliance issues cost you thousands more."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Grab This Deal - $67", callback_data="exit_deal:pkg_quick_97")],
        [InlineKeyboardButton(text="📧 Email Me This Offer", callback_data="email_exit_offer")],
        [InlineKeyboardButton(text="🚪 No Thanks, I'll Leave", callback_data="final_exit")]
    ])
    
    await callback.message.edit_text(exit_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "show_testimonials")
async def show_social_proof(callback: CallbackQuery):
    """Show social proof and testimonials"""
    await callback.answer()
    
    testimonials_text = f"""⭐ **SUCCESS STORIES FROM REAL MERCHANTS**

**🏆 "Approved in 3 days after 6 months of rejections!"**
*- Sarah K., E-commerce Founder*

**💰 "Saved us $50K in processing fees with better PSP match"**
*- Mike R., SaaS Startup*

**🚀 "From 0 to $2M monthly volume in 90 days"**
*- Alex T., Crypto Exchange*

**📈 "Dispute rate dropped from 2.1% to 0.3%"**
*- Jennifer L., Subscription Business*

**🌟 "Compliance passport opened doors to premium PSPs"**
*- David M., High-Risk Merchant*

**📊 PROVEN RESULTS:**
• 89% approval rate within 30 days
• Average 0.3% processing fee reduction
• 95% customer satisfaction
• 1,000+ merchants served

**Ready to join the success stories?**"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Start My Success Story", callback_data="show_money_maker")],
        [InlineKeyboardButton(text="📦 Browse Packages", callback_data="show_catalog")],
        [InlineKeyboardButton(text="💬 Talk to Success Team", url="mailto:success@merchantguard.ai")]
    ])
    
    await callback.message.edit_text(testimonials_text, reply_markup=kb, parse_mode="Markdown")

# Utility functions for revenue optimization
def get_urgency_message(package_id: str) -> str:
    """Get urgency message for specific package"""
    
    urgency_map = {
        "pkg_auto_199": "⏰ **URGENT:** Prevent more rejections - Get approved in 24h!",
        "pkg_review_297": "🩺 **CRITICAL:** Expert review prevents $10K+ in losses!",
        "kit_crypto_499": "🔐 **CRISIS MODE:** Banking issues killing your launch?",
        "pkg_quick_97": "⚡ **INSTANT FIX:** 10-minute score boost - Don't wait!"
    }
    
    return urgency_map.get(package_id, "🔥 **Limited time:** Secure your compliance now!")

def get_roi_message(package_price: int) -> str:
    """Get ROI message based on package price"""
    
    if package_price >= 499:
        return f"**ROI:** Typically prevents ${package_price * 20}+ in business losses"
    elif package_price >= 297:
        return f"**Value:** Saves ${package_price * 15}+ in avoided mistakes"
    else:
        return f"**Impact:** Prevents ${package_price * 50}+ in potential rejections"

# Export the router
__all__ = ['router', 'get_urgency_message', 'get_roi_message']