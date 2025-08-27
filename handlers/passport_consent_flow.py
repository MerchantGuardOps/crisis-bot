# handlers/passport_consent_flow.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.pool import PostgresPool
from utils.passport_generator import generate_tamper_evident_passport
from utils.human_review_queue import add_to_review_queue, get_review_status

router = Router()

class PassportConsentState(StatesGroup):
    awaiting_consent = State()
    awaiting_human_review = State()
    review_complete = State()

CONSENT_TEXT = """
🛡️ **Issue Your Compliance Passport**

Before we **issue your Compliance Passport**, please confirm:

**⚠️ IMPORTANT DISCLAIMERS:**

**What your Compliance Passport represents:**
• Educational assessment completion
• Self-reported compliance information
• Learning engagement verification
• Conversation starter for PSP discussions

**What your Compliance Passport does NOT represent:**
• Regulatory compliance certification
• PSP approval guarantee  
• Legal compliance audit
• Financial or legal advice
• Third-party verification

**Your Responsibilities:**
• Use Compliance Passport only for educational purposes
• Include disclaimers when sharing
• Seek independent professional advice
• Verify compliance with qualified experts

**Legal Protection:**
By accepting your Compliance Passport, you acknowledge that MerchantGuard™ provides educational tools only and is not liable for any business outcomes, regulatory actions, or compliance decisions based on Compliance Passport usage.

**Full Terms:** [merchantguard.ai/disclaimer]

Do you accept these terms and understand the educational nature of your Compliance Passport?
"""

@router.message(F.text == "Issue My Compliance Passport")
async def initiate_passport_consent(message: Message, state: FSMContext):
    """Start the Compliance Passport consent flow"""
    user_id = message.from_user.id
    
    # Check if user has completed GuardScore assessment
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM user_profiles WHERE user_id = $1 AND guardscore IS NOT NULL",
            user_id
        )
        
        if not result:
            await message.answer(
                "❌ **Compliance Passport Not Available**\n\n"
                "You need to complete your GuardScore™ assessment first.\n\n"
                "Use /guardscore to get started!"
            )
            return
    
    # Present consent form
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ I Accept Terms", callback_data="passport_consent_accept"),
            InlineKeyboardButton(text="❌ Decline", callback_data="passport_consent_decline")
        ],
        [
            InlineKeyboardButton(text="📄 Full Disclaimer", url="https://merchantguard.ai/disclaimer")
        ]
    ])
    
    await message.answer(
        text=CONSENT_TEXT,
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    
    await state.set_state(PassportConsentState.awaiting_consent)

@router.callback_query(F.data == "passport_consent_accept")
async def handle_consent_accept(callback: CallbackQuery, state: FSMContext):
    """Handle user accepting Compliance Passport consent"""
    user_id = callback.from_user.id
    
    # Log consent acceptance
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO passport_consent_log (user_id, consent_given, consent_timestamp, disclaimer_acknowledged)
            VALUES ($1, TRUE, $2, TRUE)
            ON CONFLICT (user_id) DO UPDATE SET
                consent_given = TRUE,
                consent_timestamp = $2,
                disclaimer_acknowledged = TRUE
            """,
            user_id, 
            datetime.now(timezone.utc)
        )
        
        # Get user profile for review
        user_profile = await conn.fetchrow(
            """
            SELECT user_id, business_name, industry, monthly_volume, 
                   guardscore, risk_level, created_at
            FROM user_profiles 
            WHERE user_id = $1
            """,
            user_id
        )
    
    # Add to human review queue
    review_id = await add_to_review_queue(user_profile, callback.from_user)
    
    await callback.message.edit_text(
        "✅ **Consent Recorded**\n\n"
        "Thanks. Your **Compliance Passport** is queued for quick review.\n\n"
        "**What happens next:**\n"
        "• Our compliance team reviews your assessment\n"
        "• We verify information for accuracy and consistency\n"
        "• Compliance Passport is generated with tamper-evident signature\n"
        "• You receive your Passport Portal URL within 24-48 hours\n\n"
        f"**Review ID:** `{review_id}`\n\n"
        "You'll get a link once verified.",
        parse_mode="Markdown"
    )
    
    await state.set_state(PassportConsentState.awaiting_human_review)

@router.callback_query(F.data == "passport_consent_decline")
async def handle_consent_decline(callback: CallbackQuery, state: FSMContext):
    """Handle user declining Compliance Passport consent"""
    await callback.message.edit_text(
        "❌ **Compliance Passport Request Cancelled**\n\n"
        "You have declined the Compliance Passport terms. No Compliance Passport will be generated.\n\n"
        "You can still:\n"
        "• Access your GuardScore™ assessment\n"
        "• Use our educational resources\n"
        "• Request a Compliance Passport later by using the button again\n\n"
        "If you have questions about our Compliance Passports, contact support@merchantguard.ai"
    )
    
    await state.clear()

@router.message(F.text.startswith("/passport_status"))
async def check_passport_status(message: Message):
    """Check the status of Compliance Passport review"""
    user_id = message.from_user.id
    
    status = await get_review_status(user_id)
    
    if not status:
        await message.answer(
            "❓ **No Review Found**\n\n"
            "You don't have any pending Compliance Passport reviews.\n\n"
            "Use the **Issue My Compliance Passport** button to request one."
        )
        return
    
    status_emoji = {
        "pending": "⏳",
        "in_review": "🔍", 
        "approved": "✅",
        "rejected": "❌",
        "requires_info": "❓"
    }
    
    status_text = {
        "pending": "Pending Review",
        "in_review": "Under Review",
        "approved": "Approved",
        "rejected": "Rejected", 
        "requires_info": "Additional Information Required"
    }
    
    await message.answer(
        f"{status_emoji.get(status['status'], '❓')} **Compliance Passport Status**\n\n"
        f"**Status:** {status_text.get(status['status'], 'Unknown')}\n"
        f"**Submitted:** {status['created_at'].strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"**Review ID:** `{status['review_id']}`\n\n"
        f"{status.get('reviewer_notes', 'No additional notes.')}\n\n"
        "We'll notify you when there are updates to your review.",
        parse_mode="Markdown"
    )

# Success notification when Compliance Passport is ready
async def notify_passport_ready(user_id: int, passport_data: dict):
    """Notify user that their Compliance Passport is ready"""
    from main import bot  # Import your bot instance
    
    passport_url = f"https://merchantguard.ai/passport/{passport_data['passport_id']}"
    
    message_text = (
        "🎉 **Your GuardScore™ Compliance Passport is live!**\n\n"
        f"**Business:** {passport_data['business_name']}\n"
        f"**GuardScore™:** {passport_data['guardscore']}\n"
        f"**Passport ID:** `{passport_data['passport_id']}`\n"
        f"**Expires:** {passport_data['expires_at'].strftime('%Y-%m-%d')}\n\n"
        "**Present your Compliance Passport to any PSP:**\n"
        f"🔗 {passport_url}\n\n"
        "**Remember:**\n"
        "• This Compliance Passport is for educational purposes only\n"
        "• Include disclaimers when sharing\n"
        "• Verify independently for compliance decisions\n\n"
        "**Questions?** Contact support@merchantguard.ai"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛡️ View Passport", url=passport_url),
            InlineKeyboardButton(text="📄 Disclaimer", url="https://merchantguard.ai/disclaimer")
        ]
    ])
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to notify user {user_id}: {e}")

# Admin handlers for human review process
@router.message(F.text.startswith("/admin_passport"))
async def admin_passport_interface(message: Message):
    """Admin interface for reviewing Compliance Passport requests"""
    user_id = message.from_user.id
    
    # Check if user is admin (implement your admin verification)
    if not await is_admin(user_id):
        await message.answer("❌ Access denied. Admin privileges required.")
        return
    
    # Get pending reviews
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        pending_reviews = await conn.fetch(
            """
            SELECT review_id, user_id, business_name, industry, 
                   guardscore, created_at
            FROM passport_review_queue 
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 5
            """
        )
    
    if not pending_reviews:
        await message.answer("✅ No pending Compliance Passport reviews!")
        return
    
    review_text = "🔍 **Pending Compliance Passport Reviews**\n\n"
    keyboard_buttons = []
    
    for review in pending_reviews:
        review_text += (
            f"**{review['business_name']}**\n"
            f"Industry: {review['industry']}\n"
            f"GuardScore: {review['guardscore']}\n"
            f"Submitted: {review['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        )
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"Review {review['business_name'][:20]}...",
                callback_data=f"admin_passport_{review['review_id']}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        text=review_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def is_admin(user_id: int) -> bool:
    """Check if user has admin privileges"""
    # Implement your admin verification logic
    admin_users = [123456789]  # Replace with actual admin user IDs
    return user_id in admin_users