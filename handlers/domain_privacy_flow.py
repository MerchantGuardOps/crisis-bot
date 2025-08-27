"""
Domain Privacy Check & Fix Flow
Implements the 3-phase domain privacy compliance system for PSP readiness
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import yaml
import whois
import dns.resolver
import re
import uuid
from datetime import datetime
from typing import Dict, Optional

router = Router()

class DomainPrivacyStates(StatesGroup):
    """States for domain privacy fix flow"""
    VERIFYING_WHOIS = State()
    AWAITING_COMPLETION = State()
    DNS_VERIFICATION = State()

# Load task configuration
with open('content/bot_tasks.yaml', 'r') as f:
    config = yaml.safe_load(f)

domain_privacy_config = config['tasks']['domain_privacy']

@router.message(F.text == "kyb_website_collected")
async def ask_domain_identity(message: Message, state: FSMContext):
    """
    Non-blocking domain privacy check during KYB onboarding
    Phase 1: Ask but don't block flow
    """
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yes", callback_data="whois_yes"),
        InlineKeyboardButton(text="❓ No / Not sure", callback_data="whois_no")
    ]])
    
    await message.answer(
        "Quick check: is your domain's WHOIS contact public and showing your official business details?",
        reply_markup=kb
    )

@router.callback_query(F.data.in_({"whois_yes", "whois_no"}))
async def handle_whois_answer(call: CallbackQuery, state: FSMContext):
    """Handle domain privacy check response"""
    
    if call.data == "whois_yes":
        # Mark as verified, continue onboarding
        await state.update_data(domain_privacy_status="verified")
        await call.message.edit_text("Perfect — that's exactly what PSPs look for. Moving on.")
        # Continue to next KYB step
        await advance_kyb_flow(call, state)
        
    else:
        # Mark as needs fixing, add to persistent menu, continue onboarding
        await state.update_data(
            domain_privacy_status="needs_fix",
            needs_domain_privacy_fix=True
        )
        
        await call.message.edit_text(
            "Got it. This is common and quick to fix.\n\n"
            "I've added **Fix Domain Privacy** to your main menu — finish onboarding first, then tap it."
        )
        
        # Add persistent menu item
        await add_persistent_menu_item(call.from_user.id, "fix_domain_privacy")
        
        # Schedule nudge for 24 hours
        await schedule_domain_privacy_nudge(call.from_user.id)
        
        # Continue onboarding without blocking
        await advance_kyb_flow(call, state)

@router.message(F.text == "Fix Domain Privacy")
async def start_domain_privacy_flow(message: Message, state: FSMContext):
    """
    Phase 2: Self-serve domain privacy fix tool
    Always available in main menu
    """
    
    await message.answer(
        f"**{domain_privacy_config['label']}**\n\n"
        f"**Why it matters:**\n"
        f"• Faster underwriting & fewer back‑and‑forths\n"
        f"• Clear public identity matching your policies\n"
        f"• {domain_privacy_config['guardscore_points']} GuardScore™ points\n\n"
        f"**{domain_privacy_config['rationale']}**\n\n"
        "Ready to start?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Start Fix", callback_data="start_privacy_fix"),
        InlineKeyboardButton(text="📋 Alternative Methods", callback_data="privacy_alternatives")
    ]])
    
    await message.answer("Choose your approach:", reply_markup=kb)

@router.callback_query(F.data == "start_privacy_fix")
async def privacy_fix_steps(call: CallbackQuery, state: FSMContext):
    """Show domain privacy fix steps"""
    
    await call.message.edit_text(
        "**Domain Privacy Fix Steps:**\n\n"
        "**Step 1:** Open your domain registrar (GoDaddy, Namecheap, etc.)\n"
        "**Step 2:** Find 'Domain Privacy' or 'WHOIS Privacy' settings\n"
        "**Step 3:** Turn OFF privacy protection OR update registrant details to match your business\n"
        "**Step 4:** Set Admin/Tech contacts to your support email\n"
        "**Step 5:** Save changes (may take 24-48 hours to propagate)\n\n"
        "Reply with **DONE** when completed and I'll verify your domain."
    )
    
    await state.set_state(DomainPrivacyStates.AWAITING_COMPLETION)

@router.callback_query(F.data == "privacy_alternatives")
async def show_privacy_alternatives(call: CallbackQuery, state: FSMContext):
    """Show alternative verification methods for edge cases"""
    
    alternatives = config['verification_methods']['fallback']
    
    alt_text = "**Alternative Verification Methods:**\n\n"
    
    for i, method in enumerate(alternatives, 1):
        alt_text += f"**Option {i}:** {method['description']}\n"
    
    alt_text += "\n**Note:** These are for cases where registrar policies prevent public WHOIS.\n\n"
    alt_text += "Choose **Standard Fix** for most cases, or contact support for alternative verification."
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Standard Fix", callback_data="start_privacy_fix"),
        InlineKeyboardButton(text="💬 Need Help", callback_data="privacy_help")
    ]])
    
    await call.message.edit_text(alt_text, reply_markup=kb)

@router.message(DomainPrivacyStates.AWAITING_COMPLETION, F.text.regexp(r"(?i)^done$"))
async def verify_domain_privacy(message: Message, state: FSMContext):
    """Verify domain privacy fix completion"""
    
    user_data = await state.get_data()
    domain = user_data.get('business_website', '').replace('https://', '').replace('http://', '').split('/')[0]
    
    if not domain:
        await message.answer("I need your domain name to verify. Please provide your website URL first.")
        return
    
    await message.answer("🔍 Verifying your domain privacy settings... This may take a moment.")
    await state.set_state(DomainPrivacyStates.VERIFYING_WHOIS)
    
    try:
        # Check WHOIS data
        verification_result = await verify_whois_privacy(domain)
        
        if verification_result['is_public']:
            # Success!
            await state.update_data(domain_privacy_status="verified")
            await state.clear()
            
            await message.answer(
                "✅ **Domain Privacy Fixed!**\n\n"
                f"Your domain shows public business information as required by PSP underwriters.\n\n"
                f"**+{domain_privacy_config['guardscore_points']} GuardScore™ points earned!**\n\n"
                "This will improve your application review speed and reduce back-and-forth with underwriters."
            )
            
            # Award GuardScore points
            await add_guardscore_points(message.from_user.id, domain_privacy_config['guardscore_points'], 'domain_privacy_verified')
            
            # Remove from menu if no longer needed
            await remove_persistent_menu_item(message.from_user.id, "fix_domain_privacy")
            
        else:
            await message.answer(
                "⏳ **Changes Still Propagating**\n\n"
                f"WHOIS updates can take 24-48 hours to appear publicly. Current status:\n\n"
                f"• **Registrant:** {verification_result.get('registrant', 'Private')}\n"
                f"• **Admin Contact:** {verification_result.get('admin_contact', 'Private')}\n\n"
                "Try again in a few hours, or reply **DONE** once you see the changes live."
            )
            
    except Exception as e:
        await message.answer(
            "❌ **Verification Failed**\n\n"
            f"Unable to check domain privacy for {domain}. This could be temporary.\n\n"
            "Please try again in a few minutes, or contact support if the issue persists."
        )
        await state.clear()

async def verify_whois_privacy(domain: str) -> Dict:
    """
    Verify if domain WHOIS shows public business information
    Returns dict with verification status and details
    """
    try:
        w = whois.whois(domain)
        
        # Check if registrant information is public
        registrant = str(w.registrant or '').lower()
        admin_email = str(w.emails[0] if w.emails else '').lower()
        
        # Common privacy service indicators
        privacy_indicators = [
            'private', 'privacy', 'protected', 'proxy', 'masked',
            'whoisguard', 'domain privacy', 'contact privacy'
        ]
        
        is_private = any(indicator in registrant for indicator in privacy_indicators)
        is_generic_email = any(generic in admin_email for generic in ['privacy', 'proxy', 'protected'])
        
        return {
            'is_public': not is_private and not is_generic_email,
            'registrant': w.registrant or 'Not available',
            'admin_contact': admin_email or 'Not available',
            'raw_whois': w
        }
        
    except Exception as e:
        return {
            'is_public': False,
            'error': str(e),
            'registrant': 'Error retrieving',
            'admin_contact': 'Error retrieving'
        }

async def add_persistent_menu_item(user_id: int, item_id: str):
    """Add item to user's persistent menu"""
    # Implementation depends on your menu system
    pass

async def remove_persistent_menu_item(user_id: int, item_id: str):
    """Remove item from user's persistent menu"""
    # Implementation depends on your menu system
    pass

async def schedule_domain_privacy_nudge(user_id: int):
    """Schedule 24h nudge for domain privacy fix"""
    nudge_config = config['nudges']['domain_privacy_incomplete']
    # Implementation depends on your scheduling system
    pass

async def advance_kyb_flow(call: CallbackQuery, state: FSMContext):
    """Continue to next step in KYB onboarding"""
    # Implementation depends on your KYB flow
    pass

async def add_guardscore_points(user_id: int, points: int, reason: str):
    """Award GuardScore points for completing domain privacy verification"""
    # Implementation depends on your scoring system
    pass

# PSP Attestation Gate (Phase 4)
@router.message(F.text == "request_psp_attestation")
async def check_domain_privacy_before_attestation(message: Message, state: FSMContext):
    """
    Phase 4: Hard gate for PSP attestation
    Only required when requesting official attestation
    """
    
    user_data = await state.get_data()
    domain_privacy_status = user_data.get('domain_privacy_status')
    
    if domain_privacy_status != 'verified':
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔧 Fix Domain Privacy", callback_data="start_privacy_fix"),
            InlineKeyboardButton(text="❓ Need Help", callback_data="privacy_help")
        ]])
        
        await message.answer(
            "**Domain Verification Required**\n\n"
            "Before I can generate your PSP attestation package, we need to verify your domain shows public business information.\n\n"
            "This is required by underwriters to confirm your business identity matches your policies.\n\n"
            "**Current Status:** ❌ Not Verified\n\n"
            "Fix this now to proceed:",
            reply_markup=kb
        )
        return
    
    # Domain verified, proceed with attestation
    await generate_psp_attestation_package(message, state)