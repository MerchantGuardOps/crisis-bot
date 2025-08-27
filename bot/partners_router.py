import os
import yaml
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.affiliate_tracker import AffiliateTracker
from services.points_service import PointsService

router = Router()

# Load partner configuration
with open("config/partners.yaml", "r") as f:
    PARTNERS = yaml.safe_load(f)["partners"]

def _kb(rows):
    """Helper to create inline keyboards."""
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ========================================
# PSP PARTNER OFFER (Post-Purchase MATCH)
# ========================================

async def send_psp_partner_offer(
    bot,
    merchant_id: str,
    tracker: AffiliateTracker,
    points: PointsService,
    purchase_id: str = None
):
    """Send PSP partner offer after MATCH package purchase."""
    if not os.getenv("FEATURE_PARTNER_PSP", "true").lower() == "true":
        return
        
    p = PARTNERS["durango"]
    text = (
        "✅ **Your MATCH Liberation package is ready!**\n\n"
        f"**{p['name']}** — {p['value_prop']}\n\n"
        "Would you like a **warm intro**? We'll only share your details with your consent."
    )
    
    kb = _kb([
        [InlineKeyboardButton(text=p["cta_label"], callback_data="partner_psp_yes")],
        [InlineKeyboardButton(text=p["alt_label"], callback_data="partner_psp_self")]
    ])
    
    await bot.send_message(
        chat_id=int(merchant_id),
        text=text,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "partner_psp_yes")
async def partner_psp_yes(cb: CallbackQuery, tracker: AffiliateTracker, points: PointsService):
    """User wants warm PSP intro - create offer and show consent."""
    p = PARTNERS["durango"]
    aff_link = os.getenv(p["affiliate_env"])
    
    # Create tracking record
    rid = await tracker.create_offer(
        merchant_id=str(cb.from_user.id),
        offer_type="psp",
        partner_key=p["key"],
        affiliate_link=aff_link,
        payout_estimated=p["affiliate_payout"],
        source=p["offer_source"]
    )
    
    await tracker.update_status(rid, "accepted")
    
    # Award points for engagement
    await points.award(
        user_id=str(cb.from_user.id),
        action="partner_intro_accepted",
        meta={"partner": p["key"], "offer_type": "psp"},
        idempotency_key=f"psp_intro:{cb.from_user.id}"
    )

    # Show consent prompt
    text = (
        "📝 **Consent to Share (Warm Intro)**\n\n"
        "We will share ONLY your intake summary:\n"
        "• Legal name, country, website\n"
        "• Business model and volume\n"
        "• Current dispute metrics\n\n"
        "❌ No personal IDs, bank details, or sensitive data.\n\n"
        "Proceed with warm intro?"
    )
    
    kb = _kb([
        [InlineKeyboardButton(text="✅ Yes, send my summary", callback_data=f"partner_psp_consent_{rid}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="partner_psp_cancel")]
    ])
    
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("partner_psp_consent_"))
async def partner_psp_consent(cb: CallbackQuery, tracker: AffiliateTracker):
    """User consents to warm intro - generate intro email."""
    rid = int(cb.data.split("_")[-1])

    # Get merchant intake summary (you'll need to implement this based on your data)
    merchant_summary = await _load_intake_summary(str(cb.from_user.id))
    
    # Build intro email
    email_data = await tracker.build_intro_email(rid, merchant_summary)
    
    # Mark as intro sent (manual sending for now)
    await tracker.update_status(rid, "intro_sent")
    
    # Log intro for manual processing
    # TODO: Integrate with your email service for automated sending
    
    text = (
        "📨 **Warm intro queued!**\n\n"
        f"We'll introduce you to **{PARTNERS['durango']['name']}** using your consented business summary.\n\n"
        "✉️ Watch your inbox over the next **1–3 business days**.\n\n"
        "They'll prioritize your application as a MerchantGuard referral."
    )
    
    await cb.message.edit_text(text, parse_mode="Markdown")
    await cb.answer("Intro queued")

@router.callback_query(F.data == "partner_psp_cancel")
async def partner_psp_cancel(cb: CallbackQuery):
    """User cancels warm intro."""
    await cb.message.edit_text(
        "No problem! You can always request a warm intro later with /partners.",
        parse_mode="Markdown"
    )
    await cb.answer()

@router.callback_query(F.data == "partner_psp_self")
async def partner_psp_self(cb: CallbackQuery, tracker: AffiliateTracker):
    """User wants to apply themselves - provide tracked affiliate link."""
    p = PARTNERS["durango"]
    aff_link = os.getenv(p["affiliate_env"])
    
    # Create tracking record
    rid = await tracker.create_offer(
        merchant_id=str(cb.from_user.id),
        offer_type="psp",
        partner_key=p["key"],
        affiliate_link=aff_link,
        payout_estimated=p["affiliate_payout"],
        source=p["offer_source"]
    )
    
    # Generate secure redirect link
    tracked_url = tracker.signed_redirect(
        referral_id=rid,
        partner_key=p["key"],
        dest_url=aff_link,
        merchant_id=str(cb.from_user.id)
    )
    
    kb = _kb([[InlineKeyboardButton(text=f"🔗 Open {p['name']}", url=tracked_url)]])
    
    await cb.message.edit_text(
        f"Perfect! Click below to apply directly with **{p['name']}**.\n\n"
        "✅ We'll track your progress for follow-up support.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await cb.answer()

# ========================================
# LEGAL PARTNER OFFER (GuardScore Violations)
# ========================================

async def maybe_send_legal_offer(
    bot,
    merchant_id: str,
    tracker: AffiliateTracker,
    points: PointsService,
    violation_risk: float
):
    """Send legal review offer if GuardScore shows high violation risk."""
    if (violation_risk < 0.70 or 
        not os.getenv("FEATURE_PARTNER_LEGAL", "true").lower() == "true"):
        return
        
    p = PARTNERS["complianceguard"]
    aff_link = os.getenv(p["affiliate_env"])
    
    # Create tracking record
    rid = await tracker.create_offer(
        merchant_id=merchant_id,
        offer_type="legal",
        partner_key=p["key"],
        affiliate_link=aff_link,
        payout_estimated=p["affiliate_payout"],
        source=p["offer_source"]
    )
    
    # Generate tracked link
    tracked_url = tracker.signed_redirect(rid, p["key"], aff_link, merchant_id)
    
    text = (
        f"⚠️ **Your GuardScore shows active VAMP violations**\n\n"
        f"**{p['name']}** — {p['value_prop']}\n\n"
        f"💰 Use code **{os.getenv('PARTNER_LEGAL_CODE', 'MG25')}** for 25% off"
    )
    
    kb = _kb([
        [InlineKeyboardButton(text=p["cta_label"], url=tracked_url)],
        [InlineKeyboardButton(text=p["alt_label"], callback_data="partner_legal_skip")]
    ])
    
    await bot.send_message(
        chat_id=int(merchant_id),
        text=text,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "partner_legal_skip")
async def partner_legal_skip(cb: CallbackQuery):
    """User skips legal offer."""
    await cb.answer("Skipping legal help for now")

# ========================================
# LLC PARTNER OFFER (Entity Formation)
# ========================================

async def maybe_send_llc_offer(
    bot,
    merchant_id: str,
    tracker: AffiliateTracker,
    needs_new_entity: bool
):
    """Send LLC formation offer if user needs new entity."""
    if (not needs_new_entity or 
        not os.getenv("FEATURE_PARTNER_LLC", "true").lower() == "true"):
        return
        
    p = PARTNERS["firstbase"]
    aff_link = os.getenv(p["affiliate_env"])
    
    # Create tracking record
    rid = await tracker.create_offer(
        merchant_id=merchant_id,
        offer_type="llc",
        partner_key=p["key"],
        affiliate_link=aff_link,
        payout_estimated=p["affiliate_payout"],
        source=p["offer_source"]
    )
    
    # Generate tracked link
    tracked_url = tracker.signed_redirect(rid, p["key"], aff_link, merchant_id)
    
    text = (
        f"📝 **You'll likely need a clean entity for new PSP applications**\n\n"
        f"**{p['name']}** — {p['value_prop']}"
    )
    
    kb = _kb([
        [InlineKeyboardButton(text=p["cta_label"], url=tracked_url)],
        [InlineKeyboardButton(text=p["alt_label"], callback_data="partner_llc_skip")]
    ])
    
    await bot.send_message(
        chat_id=int(merchant_id),
        text=text,
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "partner_llc_skip")
async def partner_llc_skip(cb: CallbackQuery):
    """User skips LLC formation offer."""
    await cb.answer("Skipping LLC formation for now")

# ========================================
# MANUAL PARTNER ACCESS COMMAND
# ========================================

@router.message(F.text == "/partners")
async def cmd_partners(message: Message, tracker: AffiliateTracker):
    """Manual command to access partner offers."""
    text = (
        "🤝 **MerchantGuard Partner Network**\n\n"
        "Available partner services:\n\n"
        "🏦 **Payment Processing** - MATCH-friendly processors\n"
        "⚖️ **Legal Compliance** - Same-day reviews\n"
        "🏢 **LLC Formation** - Clean entity in 24h\n\n"
        "Partner offers are shown automatically at relevant moments in your journey."
    )
    
    await message.reply(text, parse_mode="Markdown")

# ========================================
# HELPER FUNCTIONS
# ========================================

async def _load_intake_summary(merchant_id: str) -> dict:
    """
    Load merchant intake summary for warm intros.
    TODO: Implement based on your existing user data structure.
    """
    # This is a stub - implement based on your user data model
    return {
        "legal_name": "Example Business LLC",
        "country": "United States",
        "website": "https://example.com",
        "business_model": "E-commerce",
        "volume_monthly": "50,000",
        "avg_ticket": "75",
        "dispute_rate_30d": "0.8%",
        "notes": "Implementing MerchantGuard compliance recommendations"
    }