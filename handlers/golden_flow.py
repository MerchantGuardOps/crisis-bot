# handlers/golden_flow.py - Golden Flow v4.0 Implementation
"""
The complete Golden Flow implementation with dual-funnel routing:
- Funnel A: Freemium-to-Premium (Broad Acquisition)  
- Funnel B: Premium-to-Proof (High-Intent Conversion)
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import logging
import asyncio
from typing import Dict, Any

from database.pool import PostgresPool
from config.feature_config import get_config
from analytics.ltv_tracking import track_event
from analytics.utm_enhanced_tracking import track_price_revealed_with_utm, track_offer_shown_with_utm
from utils.question_loader import question_loader
from analytics.question_analytics import analytics
from utils.guardscore_engine import guardscore_engine
from utils.alert_engine import alert_engine
from utils.hero_image_sender import send_guardscore_hero, send_merchantguard_hero, send_passport_visual
from utils.aha_moments_engine import aha_engine

router = Router()
logger = logging.getLogger(__name__)

class GoldenFlowStates(StatesGroup):
    # Market Selection
    market_selection = State()
    market_split = State()
    
    # Business Profile
    industry_selection = State()
    business_stage = State()
    entity_setup = State()
    monthly_volume = State()
    
    # VAMP Assessment
    dispute_ratio = State()
    chargeback_ratio = State()
    dispute_sop = State()
    compliance_experience = State()
    
    # Data-Verified Powerup
    platform_selection = State()
    csv_upload_consent = State()
    csv_processing = State()
    
    # Passport Issuance
    passport_generation = State()
    
    # Kit Upsell
    kit_recommendation = State()
    payment_processing = State()
    
    # Number input handling
    awaiting_number_input = State()
    
    # Terms of Service
    terms_acceptance = State()

# Market configuration
MARKETS = {
    "us_cards": {
        "name": "US Cards",
        "emoji": "🇺🇸",
        "risk_factors": ["VAMP", "Durbin Amendment"],
        "primary_concern": "chargeback_management"
    },
    "canada": {
        "name": "Canada",
        "emoji": "🇨🇦", 
        "risk_factors": ["Interac", "Provincial Regulations"],
        "primary_concern": "compliance_readiness"
    },
    "brazil_pix": {
        "name": "Brazil PIX", 
        "emoji": "🇧🇷",
        "risk_factors": ["PIX MED 2.0", "Reserve Requirements"],
        "primary_concern": "dispute_ratio"
    },
    "latinam": {
        "name": "LatinAM",
        "emoji": "🌎",
        "risk_factors": ["Regional Banking", "FX Compliance"],
        "primary_concern": "cross_border_readiness"
    },
    "eu_cards": {
        "name": "EU Cards (SCA)",
        "emoji": "🇪🇺", 
        "risk_factors": ["SCA", "PSD2", "Auth Rates"],
        "primary_concern": "regulatory_compliance"
    },
    "other": {
        "name": "Other Markets",
        "emoji": "🌍",
        "risk_factors": ["Multi-jurisdiction"],
        "primary_concern": "market_entry"
    }
}

@router.message(Command("start"))
async def handle_start_command(message: Message, command: CommandObject, state: FSMContext):
    """Main entry point - Terms of Service first, then funnel routing"""
    start_param = command.args if command.args else ""
    user_id = message.from_user.id
    
    # Track entry point
    await track_event("bot_started", {
        "user_id": user_id,
        "start_param": start_param,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Store start param for after ToS acceptance
    await state.update_data(start_param=start_param)
    
    # Show Terms of Service first
    await show_terms_of_service(message, state)

async def show_terms_of_service(message: Message, state: FSMContext):
    """Step 0: The Welcome & The Legal Gate (Golden Flow v5.0)"""
    await state.set_state(GoldenFlowStates.terms_acceptance)
    
    welcome_text = """🛡️ **Welcome to MerchantGuard**

We help founders issue a **Compliance Passport** so they can switch payment providers without starting over.

Before we begin, please review and accept our Terms of Service and Privacy Policy.

**🔒 What We Protect:**
• Your data is encrypted and never shared without consent
• Assessments are confidential and anonymized  
• You control who sees your GuardScore™ results

**⚖️ Legal Framework:**
• GuardScore™ is for informational purposes only
• Not financial, legal, or investment advice
• Results help demonstrate compliance readiness

**📊 Data Collection:**
• Business profile and compliance metrics
• Used solely for passport generation
• Stored with enterprise-grade security

By continuing, you agree to our complete Terms of Service and Privacy Policy."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Accept & Continue", callback_data="accept_terms")],
        [InlineKeyboardButton(text="📋 Read Terms", url="https://merchantguard.ai/terms")],
        [InlineKeyboardButton(text="🔒 Privacy Policy", url="https://merchantguard.ai/privacy")]
    ])
    
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "accept_terms")
async def handle_terms_acceptance(callback: CallbackQuery, state: FSMContext):
    """Step 1: The Dynamic Router (Golden Flow v5.0 Brain)"""
    user_id = callback.from_user.id
    
    # Track ToS acceptance
    await track_event("terms_accepted", {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Get the original start parameter for routing
    data = await state.get_data()
    start_param = data.get('start_param', '')
    
    # Detect landing page traffic for price gating
    is_landing_page_traffic = (
        start_param.startswith("lp_") or 
        start_param.startswith("landing_") or
        "stripe-shut-down" in start_param or
        "high-chargebacks" in start_param or
        "us-first-psp" in start_param or
        "pix-med-brazil" in start_param or
        "crypto-banking" in start_param
    )
    
    # Store landing page traffic flag for price gating
    await state.update_data(is_landing_page_traffic=is_landing_page_traffic)
    
    # 🧠 DYNAMIC ROUTING LOGIC (Golden Flow v5.0 + Four-Persona System)
    from analytics.ltv_tracking import LTVTracker
    
    # Determine persona from our existing system
    persona = LTVTracker.PERSONA_MAPPING.get(start_param, "general")
    
    if start_param.startswith("kit_"):
        # 🎯 FUNNEL B: Premium-to-Proof Flow
        # High-intent users with existential problems who need specific kits
        await start_funnel_b_premium_to_proof(callback, start_param, state, persona)
        
    elif start_param.startswith("guide_"):
        # 🎯 FUNNEL A: Freemium-to-Premium (Guide Context)
        # Users from specific guide deep links, contextual to their problem
        await start_funnel_a_freemium_to_premium(callback, state, "guide", start_param, persona)
        
    elif start_param == "multipsp":
        # 🎯 FUNNEL A: Freemium-to-Premium (Multi-PSP Context)
        # Users specifically interested in switching PSPs → builders persona
        await start_funnel_a_freemium_to_premium(callback, state, "multipsp", "switching", "builders")
        
    else:
        # 🎯 FUNNEL A: Freemium-to-Premium (Generic)
        # Mass acquisition - generic entry point → general persona
        await start_funnel_a_freemium_to_premium(callback, state, "generic", "discovery", "general")
    
    await callback.answer("✅ Terms accepted!")

# 🎯 FUNNEL A: Freemium-to-Premium Flow (Golden Flow v5.0)
async def start_funnel_a_freemium_to_premium(callback: CallbackQuery, state: FSMContext, 
                                           entry_type: str, context: str, persona: str):
    """
    FUNNEL A: Mass user acquisition with tailored upsells
    Goal: Data collection + personalized $499 kit upsell
    """
    
    # Store funnel and persona data
    await state.update_data(
        funnel="freemium_to_premium",
        entry_type=entry_type,
        context=context,
        persona=persona
    )
    
    # Send hero image with personalized messaging
    if entry_type == "guide":
        hero_caption = (
            "🛡️ **Welcome to GuardScore™ Compliance Co-Pilot**\n\n"
            f"Since you're interested in {context.replace('guide_', '').replace('_', ' ')}, "
            "let's get your compliance passport ready!\n\n"
            "_Your personalized assessment takes under 3 minutes_ ⚡"
        )
    elif entry_type == "multipsp":
        hero_caption = (
            "🛡️ **Ready to Switch Payment Providers?**\n\n"
            "Get your **Multi-PSP Readiness Passport** to switch providers "
            "without starting compliance from zero.\n\n"
            "_Let's check your readiness in 60 seconds_ ⚡"
        )
    else:
        hero_caption = (
            "🛡️ **Welcome to GuardScore™ Compliance Co-Pilot**\n\n"
            "Your AI-powered payment compliance assessment.\n"
            "Get your personalized risk score and compliance passport!\n\n"
            "_Quick 3-minute assessment_ ⚡"
        )
    
    await send_guardscore_hero(callback.message, hero_caption)
    
    # Step A2: The "Market-First" Question
    await asyncio.sleep(1)
    await ask_market_first_question(callback.message, state)

# 🎯 FUNNEL B: Premium-to-Proof Flow (Golden Flow v5.0)  
async def start_funnel_b_premium_to_proof(callback: CallbackQuery, start_param: str, 
                                         state: FSMContext, persona: str):
    """
    FUNNEL B: High-intent conversion with paywall
    Goal: Immediate kit purchase → interactive workflow → earned passport
    """
    
    kit_type = start_param.replace("kit_", "")
    
    # Store funnel and persona data
    await state.update_data(
        funnel="premium_to_proof",
        kit_type=kit_type,
        persona=persona
    )
    
    # Kit-specific welcome messages
    kit_info = {
        "crypto": {
            "name": "Crypto Founder's Kit",
            "tagline": "Navigate U.S. regulations and secure stable banking",
            "problem": "crypto compliance and banking challenges"
        },
        "global": {
            "name": "Global Founder's Kit", 
            "tagline": "Master international payment rails and compliance",
            "problem": "global expansion and multi-market compliance"
        },
        "builders": {
            "name": "Builder's Standard Kit",
            "tagline": "Multi-PSP readiness and switching strategies", 
            "problem": "payment provider dependence and switching costs"
        },
        "genius": {
            "name": "Genius Snapshot Kit",
            "tagline": "Instant compliance assessment and optimization",
            "problem": "unknown compliance gaps and risk factors"
        }
    }
    
    info = kit_info.get(kit_type, kit_info["builders"])
    
    # Step B2: The Premium Welcome & Paywall
    paywall_text = f"""💎 **Welcome to the {info['name']}**

This is the definitive playbook for {info['problem']}.

**What You Get:**
• Interactive compliance workflow
• Step-by-step implementation guide  
• Personalized compliance strategies
• **Earned Compliance Passport** (higher status)
• Direct access to our PSP network

**Investment:** $499 (One-time)

To unlock the complete interactive workflow, secure your access below:"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔒 Secure Access - ${LTVTracker.REVENUE_VALUES['kit_purchase'].get(kit_type+'_standard', 499)}", 
                             url=f"https://merchantguard.ai/kits/{kit_type}?checkout=true")],
        [InlineKeyboardButton(text="📋 View Full Details", 
                             url=f"https://merchantguard.ai/kits/{kit_type}")],
        [InlineKeyboardButton(text="💬 Talk to Founder", callback_data="contact_founder")]
    ])
    
    await send_merchantguard_hero(callback.message, paywall_text)
    await callback.message.answer("👆 Choose your next step above", reply_markup=kb)
    
    # Also offer a "Check Payment Status" option for returning users
    payment_check_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Already Purchased - Continue", callback_data=f"verify_payment_{kit_type}")],
        [InlineKeyboardButton(text="🆓 Try Free Guide First", callback_data="suggest_free_guide")]
    ])
    
    await asyncio.sleep(2)  # Brief pause
    await callback.message.answer("💡 **Already purchased?** Continue your kit workflow:", reply_markup=payment_check_kb)

async def ask_market_first_question(message: Message, state: FSMContext):
    """Step A2: The Market-First Question (Funnel A)"""
    
    market_text = """🌍 **Step 1: Where are your customers?**

*Pick all markets that apply - this helps us tailor your compliance assessment.*

**Why this matters:** Each market has unique compliance requirements:
• 🇺🇸 **US Cards**: VAMP thresholds, dispute management  
• 🇨🇦 **Canada**: Interac compliance, provincial regulations
• 🇧🇷 **Brazil PIX**: MED 2.0 requirements, reserve management
• 🌎 **LatinAM**: Regional banking, FX compliance
• 🇪🇺 **EU Cards**: SCA requirements, PSD2 compliance  
• 🌍 **Other**: We'll cover the basics"""

    # Use our existing multi-select market system
    await message.answer(market_text, parse_mode="Markdown")
    await ask_question_by_id(message, "MKT_1", state)

@router.callback_query(F.data.startswith("market_toggle_"))
async def handle_market_toggle(callback: CallbackQuery, state: FSMContext):
    """Handle market selection toggle (multi-select)"""
    market = callback.data.replace("market_toggle_", "")
    
    # Get current selected markets
    data = await state.get_data()
    selected_markets = data.get('selected_markets', [])
    
    # Toggle market selection
    if market in selected_markets:
        selected_markets.remove(market)
        action = "removed"
    else:
        selected_markets.append(market)
        action = "added"
    
    # Update state
    await state.update_data(selected_markets=selected_markets)
    
    # Update the keyboard to show selections
    await update_market_selection_display(callback, selected_markets, state)
    
    market_name = {
        "US_CARDS": "US Cards",
        "CANADA": "Canada", 
        "BR_PIX": "Brazil PIX",
        "LATINAM": "LatinAM",
        "EU_CARDS_SCA": "EU Cards (SCA)",
        "OTHER": "Other Markets"
    }.get(market, market)
    
    await callback.answer(f"✅ {market_name} {action}")

@router.callback_query(F.data == "market_continue")
async def handle_market_continue(callback: CallbackQuery, state: FSMContext):
    """Continue after market selection"""
    data = await state.get_data()
    selected_markets = data.get('selected_markets', [])
    
    if not selected_markets:
        await callback.answer("⚠️ Please select at least one market first!", show_alert=True)
        return
    
    # Store the selection and continue
    await state.update_data(markets_selected=selected_markets)
    
    # Continue with business profile
    await callback.message.edit_text(
        f"✅ **Markets Selected**: {', '.join(selected_markets)}\n\n"
        "Now let's build your business profile...",
        parse_mode="Markdown"
    )
    
    # Start business profile questions
    await ask_question_by_id(callback.message, "BP_1", state)
    await callback.answer("✅ Market selection complete!")


async def handle_kit_entry(message: Message, kit_param: str, state: FSMContext):
    """Funnel B: Premium-to-Proof entry point"""
    kit_type = kit_param.replace("kit_", "")
    
    # Map kit types to descriptions
    kit_info = {
        "crypto": {
            "name": "Crypto Founder's Kit",
            "price": 499,
            "description": "Interactive workflow for compliant banking and tokenomics"
        },
        "global": {
            "name": "Global Founder Kit", 
            "price": 499,
            "description": "International banking and multi-jurisdiction compliance"
        },
        "builders": {
            "name": "Builder's Starter Kit",
            "price": 499, 
            "description": "Complete US fintech compliance foundation"
        },
        "genius": {
            "name": "GENIUS Act Readiness Snapshot",
            "price": 499,
            "description": "Comprehensive assessment and actionable roadmap"
        }
    }
    
    kit = kit_info.get(kit_type, kit_info["builders"])
    
    # Store kit context
    await state.update_data(
        funnel="premium_to_proof",
        kit_type=kit_type,
        kit_name=kit["name"],
        entry_type="kit_direct"
    )
    
    welcome_text = f"""🎯 <b>{kit['name']}</b>

Welcome! To unlock the interactive workflow and solve for {kit['description'].lower()}, please complete your purchase.

<b>What you get:</b>
• Interactive step-by-step guidance
• Custom compliance templates 
• Expert recommendations for your specific situation
• Earned Compliance Passport upon completion

<b>Price:</b> ${kit['price']} (one-time payment)"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Purchase ${kit['price']}", url=f"https://buy.stripe.com/merchantguard-{kit_type}")],
        [InlineKeyboardButton(text="❓ Questions?", callback_data="kit_questions")],
        [InlineKeyboardButton(text="← Try Free Version", callback_data="switch_to_freemium")]
    ])
    
    await message.answer(welcome_text, reply_markup=kb)
    await track_event("kit_entry_viewed", {"user_id": message.from_user.id, "kit_type": kit_type})

async def start_freemium_funnel(message: Message, state: FSMContext, entry_type: str, guide_param: str = None):
    """Funnel A: Freemium-to-Premium entry point"""
    await state.update_data(
        funnel="freemium_to_premium",
        entry_type=entry_type,
        guide_param=guide_param
    )
    
    # Market Selection using Golden Question Bank v4.0
    await ask_question_by_id(message, "MKT_1", state)

async def ask_question_by_id(message: Message, question_id: str, state: FSMContext, locale: str = 'en'):
    """Ask question using Golden Question Bank v4.0"""
    question = question_loader.get_question_by_id(question_id)
    if not question:
        await message.answer(f"❌ Question {question_id} not found")
        return
    
    # Track question shown
    await analytics.track_question_shown(message.from_user.id, question_id)
    
    # Get localized prompt
    prompt_text = question_loader.get_prompt(question_id, locale)
    
    if question_id == "MKT_1":
        # Market selection - special formatting
        message_text = f"""🛡️ <b>Ready to issue your Compliance Passport?</b>

I'll check your Multi-PSP readiness in ~60 seconds.

<i>We're an independent platform, not a PSP or underwriter.</i>

<b>{prompt_text}</b>"""
        
        # Build keyboard from options
        options = question_loader.get_options(question_id, locale)
        keyboard = []
        
        # Create market buttons
        row1 = []
        row2 = []
        
        # Enhanced emoji mapping for all markets
        emoji_map = {
            "US_CARDS": "🇺🇸", 
            "CANADA": "🇨🇦",
            "BR_PIX": "🇧🇷", 
            "LATINAM": "🌎",
            "EU_CARDS_SCA": "🇪🇺", 
            "OTHER": "🌍"
        }
        
        # Create multi-select buttons
        for i, option in enumerate(options):
            emoji = emoji_map.get(option['value'], "📍")
            button_text = f"{emoji} {option['label']}"
            callback_data = f"market_toggle_{option['value']}"
            
            if i < 3:
                row1.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
            else:
                row2.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
        
        keyboard = [row1]
        if row2:
            keyboard.append(row2)
        keyboard.append([InlineKeyboardButton(text="✅ Continue with Selection", callback_data="market_continue")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(message_text, reply_markup=kb)
        
    elif question['type'] == 'select':
        # Regular select question
        options = question_loader.get_options(question_id, locale)
        keyboard = []
        
        for option in options:
            callback_data = f"q_{question_id}_{option['value']}"
            keyboard.append([InlineKeyboardButton(text=option['label'], callback_data=callback_data)])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(prompt_text, reply_markup=kb)
    
    elif question['type'] == 'boolean':
        # Boolean question
        keyboard = [
            [
                InlineKeyboardButton(text="✅ Yes", callback_data=f"q_{question_id}_YES"),
                InlineKeyboardButton(text="❌ No", callback_data=f"q_{question_id}_NO")
            ]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(prompt_text, reply_markup=kb)
    
    elif question['type'] == 'multiselect':
        # Multi-select question (like policies)
        options = question_loader.get_options(question_id, locale)
        keyboard = []
        
        for option in options:
            callback_data = f"q_{question_id}_toggle_{option['value']}"
            keyboard.append([InlineKeyboardButton(text=f"☐ {option['label']}", callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton(text="✅ Continue", callback_data=f"q_{question_id}_continue")])
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await message.answer(prompt_text, reply_markup=kb)
    
    # Store current question context
    await state.update_data(current_question=question_id, question_type=question['type'])
    
    if question_id == "MKT_1":
        await state.set_state(GoldenFlowStates.market_selection)
        await state.update_data(selected_markets=[])

@router.callback_query(F.data.startswith("q_"))
async def handle_question_answer(call: CallbackQuery, state: FSMContext):
    """Handle answers for all questions using ID-based system"""
    await call.answer()
    
    # Parse callback data: q_QUESTIONID_VALUE or q_QUESTIONID_toggle_VALUE
    parts = call.data.split('_')
    if len(parts) < 3:
        return
    
    question_id = parts[1]
    action = parts[2] if len(parts) > 3 else None
    value = '_'.join(parts[3:]) if len(parts) > 3 else parts[2]
    
    data = await state.get_data()
    
    # Handle market selection specially
    if question_id == "MKT_1":
        await handle_market_selection_v4(call, state, question_id, value, action)
        return
    
    # Handle other question types
    question = question_loader.get_question_by_id(question_id)
    if not question:
        return
    
    if question['type'] == 'multiselect' and action == 'toggle':
        # Handle multiselect toggle
        current_values = data.get(f"{question_id}_selected", [])
        if value in current_values:
            current_values.remove(value)
        else:
            current_values.append(value)
        
        await state.update_data({f"{question_id}_selected": current_values})
        
        # Update button display
        await update_multiselect_display(call, question_id, current_values, state)
        
    elif action == 'continue' and question['type'] == 'multiselect':
        # Complete multiselect
        selected_values = data.get(f"{question_id}_selected", [])
        await analytics.track_question_answered(call.from_user.id, question_id, selected_values)
        
        # Store in feature format
        feature_mapping = question_loader.map_answer_to_feature(question_id, selected_values)
        await state.update_data(**feature_mapping)
        
        # Increment question count for price gating logic
        current_count = data.get('questions_answered_count', 0)
        await state.update_data(questions_answered_count=current_count + 1)
        
        # Move to next question
        await continue_question_flow(call.message, state)
        
    else:
        # Single value answer
        await analytics.track_question_answered(call.from_user.id, question_id, value)
        
        # Store in feature format
        feature_mapping = question_loader.map_answer_to_feature(question_id, value)
        await state.update_data(**feature_mapping)
        
        # Increment question count for price gating logic
        current_count = data.get('questions_answered_count', 0)
        await state.update_data(questions_answered_count=current_count + 1)
        
        # Check for aha moments on VAMP questions
        if question_id.startswith('VAMP_'):
            await handle_vamp_aha_moment(call.message, question_id, value, state)
        
        # Move to next question or continue flow
        await continue_question_flow(call.message, state)

async def handle_market_selection_v4(call: CallbackQuery, state: FSMContext, question_id: str, value: str, action: str):
    """Handle market selection with new ID system"""
    if call.data == "market_continue":
        # Complete market selection
        data = await state.get_data()
        selected_markets = data.get("MKT_1_selected", [])
        
        if not selected_markets:
            await call.message.edit_text("❌ Please select at least one market before continuing.")
            return
        
        # Track market selection
        await analytics.track_market_selection(call.from_user.id, selected_markets)
        
        # Store in feature format
        await state.update_data(**{"markets_served.selected": selected_markets})
        
        # Increment question count for price gating logic
        current_count = data.get('questions_answered_count', 0)
        await state.update_data(questions_answered_count=current_count + 1)
        
        # Move to business profile
        await ask_question_by_id(call.message, "BP_1", state)
        return
    
    # Handle market toggle
    data = await state.get_data()
    selected_markets = data.get("MKT_1_selected", [])
    
    if value in selected_markets:
        selected_markets.remove(value)
    else:
        selected_markets.append(value)
    
    await state.update_data(MKT_1_selected=selected_markets)
    
    # Update market selection display
    await update_market_selection_display(call, selected_markets, state)

async def update_market_selection_display(call: CallbackQuery, selected_markets: list, state: FSMContext):
    """Update market selection button display"""
    welcome_text = """🛡️ <b>Ready to issue your Compliance Passport?</b>

I'll check your Multi-PSP readiness in ~60 seconds.

<i>We're an independent platform, not a PSP or underwriter.</i>

<b>Where are your customers? (pick all that apply)</b>"""
    
    # Get options from question config
    options = question_loader.get_options("MKT_1", 'en')
    keyboard = []
    row1 = []
    row2 = []
    
    for i, option in enumerate(options):
        emoji = {"US_CARDS": "🇺🇸", "BR_PIX": "🇧🇷", "EU_CARDS_SCA": "🇪🇺", "OTHER": "🌍"}.get(option['value'], "📍")
        checkmark = "✅" if option['value'] in selected_markets else ""
        button_text = f"{emoji} {option['label']}{checkmark}"
        callback_data = f"q_MKT_1_{option['value']}"
        
        if i < 2:
            row1.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
        else:
            row2.append(InlineKeyboardButton(text=button_text, callback_data=callback_data))
    
    keyboard = [row1, row2]
    
    if selected_markets:
        keyboard.append([InlineKeyboardButton(text="✅ Continue with Selection", callback_data="market_continue")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text(welcome_text, reply_markup=kb)

async def update_multiselect_display(call: CallbackQuery, question_id: str, selected_values: list, state: FSMContext):
    """Update multiselect question display"""
    question = question_loader.get_question_by_id(question_id)
    prompt_text = question_loader.get_prompt(question_id, 'en')
    options = question_loader.get_options(question_id, 'en')
    
    keyboard = []
    for option in options:
        checkmark = "✅" if option['value'] in selected_values else "☐"
        button_text = f"{checkmark} {option['label']}"
        callback_data = f"q_{question_id}_toggle_{option['value']}"
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton(text="✅ Continue", callback_data=f"q_{question_id}_continue")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await call.message.edit_text(prompt_text, reply_markup=kb)

async def continue_question_flow(message: Message, state: FSMContext):
    """Continue to next question in the flow"""
    data = await state.get_data()
    
    # Determine what questions to ask next based on flow logic
    if 'profile.industry' not in data:
        await ask_question_by_id(message, "BP_1", state)
    elif 'profile.stage' not in data:
        await ask_question_by_id(message, "BP_2", state)
    elif 'risk.prior_suspensions' not in data:
        await ask_question_by_id(message, "BP_3", state)
    elif 'ops.policies' not in data:
        await ask_question_by_id(message, "BP_4", state)
    elif 'platform.primary' not in data:
        await ask_question_by_id(message, "BP_5", state)
    elif 'ops.multi_psp_intent' not in data:
        await ask_question_by_id(message, "BP_6", state)
    elif 'ops.stepup_3ds_plan' not in data:
        await ask_question_by_id(message, "BP_7", state)
    else:
        # Business profile complete, move to market-specific questions
        await start_market_specific_questions(message, state)

async def start_market_specific_questions(message: Message, state: FSMContext):
    """Start market-specific questions based on selected markets"""
    data = await state.get_data()
    selected_markets = data.get("markets_served.selected", [])
    
    # Determine which market-specific questions to ask
    if "US_CARDS" in selected_markets:
        # Ask VAMP questions
        await start_vamp_assessment_v4(message, state)
    elif "BR_PIX" in selected_markets:
        # Ask PIX questions
        await ask_question_by_id(message, "PIX_1", state)
    elif "EU_CARDS_SCA" in selected_markets:
        # Ask EU SCA questions
        await ask_question_by_id(message, "EU_1", state)
    else:
        # No specific market questions, move to powerup
        await check_powerup_eligibility(message, state)

async def start_vamp_assessment_v4(message: Message, state: FSMContext):
    """Start VAMP assessment using Golden Question Bank v4.0"""
    vamp_intro = """⚡ <b>Multi-PSP Readiness Check</b>

Now for the critical questions. These help us assess your readiness for multiple payment processors and identify any risk factors.

Let's start with the VAMP assessment for US Cards:"""
    
    await message.edit_text(vamp_intro)
    await asyncio.sleep(1)
    await ask_question_by_id(message, "VAMP_1", state)

async def check_powerup_eligibility(message: Message, state: FSMContext):
    """Check if user is eligible for Data-Verified powerup"""
    data = await state.get_data()
    
    if question_loader.should_offer_powerup(data):
        # Offer Data-Verified powerup
        await offer_data_verified_powerup_v4(message, state)
    else:
        # Move to passport generation
        await generate_passport_v4(message, state)

async def offer_data_verified_powerup_v4(message: Message, state: FSMContext):
    """Offer Data-Verified powerup using new system"""
    data = await state.get_data()
    platform = data.get('platform', {}).get('primary', 'Unknown')
    
    # Track powerup offered
    await analytics.track_powerup_offered(message.from_user.id, platform)
    
    powerup_text = f"""🔋 <b>Power-Up Your Passport</b>

<b>What platform do you use to run your store?</b>

Since you use {platform}, you can get a much more powerful <b>Data-Verified Passport</b> by providing your order history.

A Data-Verified Passport is significantly more valuable to PSPs because it shows real transaction data."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔋 Yes, Upgrade to Data-Verified", callback_data="accept_powerup")],
        [InlineKeyboardButton(text="⏭️ Skip this step", callback_data="skip_powerup")]
    ])
    
    await message.edit_text(powerup_text, reply_markup=kb)

async def generate_passport_v4(message: Message, state: FSMContext):
    """Generate passport using Golden Question Bank data"""
    processing_text = """⚙️ <b>Generating Your Compliance Passport...</b>

🔍 Analyzing your profile...
🧮 Calculating risk factors...
🎯 Determining market readiness...
🛡️ Generating tamper-evident passport...

<i>This will take just a few seconds...</i>"""
    
    processing_msg = await message.edit_text(processing_text)
    
    # Get user data
    data = await state.get_data()
    user_id = message.from_user.id
    
    try:
        # Determine passport tier based on completion method
        kit_paid = data.get('kit_paid', False)
        kit_type = data.get('kit_type')
        passport_tier = "earned" if kit_paid else "self_attested"
        
        # Get confidence data
        confidence_data = {
            'csv_uploaded': data.get('data_verified', False),
            'comprehensive_sop': data.get('ops.dispute_sop_level') == 'Comprehensive',
            'data_recency_days': 30  # Assume recent data for self-attested
        }
        
        # Enhanced confidence for paid kit workflow
        if kit_paid:
            confidence_data.update({
                'kit_completed': True,
                'interactive_workflow': True,
                'payment_verified': True,
                'data_recency_days': 7  # Fresher data assumption for paid workflow
            })
        
        # Generate passport using enhanced scoring engine
        passport_data = guardscore_engine.generate_passport_data(
            user_id=user_id,
            feature_data=data,
            market_shares=None,  # Use default equal shares
            confidence_data=confidence_data
        )
        
        # Check for alerts
        user_alerts = await alert_engine.check_user_alerts(
            user_id, data, confidence_data
        )
        
        # Send alert notifications if any
        if user_alerts:
            await alert_engine.send_alert_notifications(user_id, user_alerts)
        
        # Track passport issuance with enhanced data
        await analytics.track_passport_issued(user_id, passport_data)
        
        # Generate passport URL (implement your actual passport generation)
        passport_url = f"https://merchantguard.ai/passport/{user_id}_{datetime.utcnow().strftime('%Y%m%d')}"
        
        # Send passport visual first
        await send_passport_visual(
            message, 
            passport_data['guardscore'], 
            passport_data['risk_level'].title()
        )
        
        # Show success
        # Customize message based on passport tier
        if passport_tier == "earned":
            success_emoji = "🏆"
            tier_message = f"""**Congratulations!** 

As proof of your hard work completing the **{kit_type.title()} Kit**, we are now issuing your **Earned Compliance Passport**.

This is a respected credential that demonstrates your commitment to compliance excellence."""
            
            next_steps = """**What's Next:**
✅ Your passport carries higher credibility with PSPs
✅ Priority consideration for our PSP network  
✅ Eligible for advanced compliance modules"""
        else:
            success_emoji = "🎉"
            tier_message = "Your Self-Attested Compliance Passport is now ready! This demonstrates your commitment to compliance best practices."
            next_steps = """**What's Next:**
✅ Share with PSPs to prove compliance readiness
✅ Consider our premium kits for enhanced credentials
✅ Renew in 180 days to maintain validity"""
        
        success_text = f"""{success_emoji} <b>{tier_message}</b>

<b>GuardScore™:</b> {passport_data['guardscore']}/100
<b>Risk Level:</b> {passport_data['risk_level'].title()}  
<b>Type:</b> {passport_data['tier'].replace('_', ' ').title()} Passport
<b>Valid:</b> 180 days

🔗 <b>Your Passport Portal:</b>
{passport_url}

{next_steps}

🛡️ Passport is tamper-evident and cryptographically signed"""

        # Different button options based on tier
        if passport_tier == "earned":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 View Your Earned Passport", url=passport_url)],
                [InlineKeyboardButton(text="📋 Share Achievement", callback_data="share_earned_passport")],
                [InlineKeyboardButton(text="🔧 Access Kit Resources", callback_data=f"kit_resources_{kit_type}")]
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 View Passport", url=passport_url)],
                [InlineKeyboardButton(text="📋 Share Passport", callback_data="share_passport")], 
                [InlineKeyboardButton(text="📦 Browse All Packages", url="https://t.me/merchantguard_bot?start=packages_catalog_v1")]
            ])
        
        await processing_msg.edit_text(success_text, reply_markup=kb)
        
        # Different follow-up actions based on tier
        if passport_tier == "earned":
            # For earned passports, show kit resources and renewal options
            await asyncio.sleep(3)
            await show_kit_resources_access(message, kit_type, state)
        else:
            # For self-attested, show kit upsell
            await asyncio.sleep(3)
            await show_personalized_kit_upsell_v4(message, state)
        
    except Exception as e:
        logger.error(f"Passport generation failed: {e}")
        await processing_msg.edit_text(
            "❌ <b>Passport Generation Failed</b>\n\nPlease try again or contact support."
        )

# Removed calculate_guardscore_v4 - now using GuardScoreEngine

async def show_personalized_kit_upsell_v4(message: Message, state: FSMContext):
    """Show personalized kit using new data structure"""
    data = await state.get_data()
    markets = data.get('markets_served.selected', [])
    industry = data.get('profile.industry', '')
    guardscore = data.get('guardscore', 50)
    
    # Determine recommended kit
    recommended_kit = get_recommended_kit_v4(markets, industry, guardscore)
    
    # Price gating logic: Check if this is landing page traffic and questions answered
    is_landing_page_traffic = data.get('is_landing_page_traffic', False)
    questions_answered = data.get('questions_answered_count', 0)
    
    # Price gating: Hide prices for landing page traffic until after Q3
    show_prices = True
    if is_landing_page_traffic and questions_answered < 3:
        show_prices = False
        # Log analytics event for price gated
        await analytics.track_event("price_gated", {
            "user_id": message.from_user.id,
            "questions_answered": questions_answered,
            "landing_page_traffic": True
        })
    elif is_landing_page_traffic and questions_answered >= 3:
        # Log analytics event for price revealed with UTM context
        await track_price_revealed_with_utm(
            user_id=message.from_user.id,
            package_id=recommended_kit['id'],
            questions_answered=questions_answered,
            landing_page_traffic=True
        )
        
        # Legacy tracking for backward compatibility
        await analytics.track_event("price_revealed", {
            "user_id": message.from_user.id,
            "questions_answered": questions_answered,
            "kit_id": recommended_kit['id']
        })
    
    # Track kit offer with price visibility info
    await analytics.track_kit_offer_shown(message.from_user.id, recommended_kit['id'], {
        'persona': industry,
        'markets': markets,
        'score': guardscore,
        'price_shown': show_prices,
        'landing_page_traffic': is_landing_page_traffic
    })
    
    # Build upsell text with conditional price display
    if show_prices:
        upsell_text = f"""🎯 <b>Recommended for You</b>

Based on your profile as a <b>{industry}</b> founder with <b>GuardScore™ {guardscore}</b>, you have specific compliance needs.

{get_personalized_message_v4(recommended_kit, markets, industry)}

<b>🎁 Special Offer: {recommended_kit['name']} ($499)</b>

{recommended_kit['description']}

<b>Perfect for:</b> {recommended_kit['audience']}"""
        button_text = f"🚀 Get {recommended_kit['name']} ($499)"
    else:
        upsell_text = f"""🎯 <b>Recommended for You</b>

Based on your profile as a <b>{industry}</b> founder with <b>GuardScore™ {guardscore}</b>, you have specific compliance needs.

{get_personalized_message_v4(recommended_kit, markets, industry)}

<b>🎁 Special Offer: {recommended_kit['name']}</b>

{recommended_kit['description']}

<b>Perfect for:</b> {recommended_kit['audience']}

<i>💡 Complete a few more questions to see pricing and unlock your personalized solution</i>"""
        button_text = f"🚀 Get {recommended_kit['name']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, url=f"https://t.me/merchantguard_bot?start={recommended_kit['id']}&utm_source=upsell")],
        [InlineKeyboardButton(text="📦 Browse All Packages", url="https://t.me/merchantguard_bot?start=packages_catalog_v1&utm_source=upsell")],
        [InlineKeyboardButton(text="⏭️ Maybe Later", callback_data="upsell_decline")]
    ])
    
    await message.answer(upsell_text, reply_markup=kb)

def get_recommended_kit_v4(markets: list, industry: str, guardscore: int) -> dict:
    """Determine recommended kit using v4.0 data"""
    kits = {
        "builders_standard": {
            "id": "kit_builder_499",
            "name": "Builder's Starter Kit", 
            "description": "Complete US fintech compliance foundation with Multi-PSP readiness",
            "audience": "First-time fintech founders, US market focus",
            "priority_score": 0
        },
        "global_founder": {
            "id": "kit_global_499", 
            "name": "Global Founder Kit",
            "description": "International banking and multi-jurisdiction compliance strategies", 
            "audience": "Global founders, international businesses",
            "priority_score": 0
        },
        "crypto_founder": {
            "id": "kit_crypto_499",
            "name": "Crypto Founder's Kit",
            "description": "Token economics, compliant messaging, and crypto banking strategies",
            "audience": "Crypto startups, Web3 builders, DeFi protocols", 
            "priority_score": 0
        }
    }
    
    # Scoring logic
    if industry == "CRYPTO":
        kits["crypto_founder"]["priority_score"] += 30
    
    if len(markets) > 1 or "OTHER" in markets:
        kits["global_founder"]["priority_score"] += 20
        
    if "BR_PIX" in markets:
        kits["global_founder"]["priority_score"] += 15
        
    if industry in ["SAAS", "ECOM"]:
        kits["builders_standard"]["priority_score"] += 15
    
    return max(kits.values(), key=lambda k: k["priority_score"])

def get_personalized_message_v4(kit: dict, markets: list, industry: str) -> str:
    """Generate personalized message using v4.0 data"""
    messages = {
        "crypto_founder": "🚨 <b>High Crypto Compliance Risk Detected</b>\n\nCrypto businesses face unique challenges with banking and tokenomics compliance.",
        "global_founder": "🌍 <b>Multi-Market Complexity Detected</b>\n\nOperating across multiple markets requires specialized compliance strategies.",
        "builders_standard": "🇺🇸 <b>US Market Foundation Needed</b>\n\nYou need a solid US compliance foundation for sustainable growth."
    }
    
    return messages.get(kit["id"], "💡 <b>Custom Recommendation</b>\n\nBased on your unique profile, this kit will address your specific needs.")

# Handle Data-Verified powerup responses
@router.callback_query(F.data == "accept_powerup")
async def handle_powerup_accept(call: CallbackQuery, state: FSMContext):
    """User accepted Data-Verified powerup"""
    await call.answer()
    
    data = await state.get_data()
    platform = data.get('platform', {}).get('primary', 'Unknown')
    
    await analytics.track_powerup_accepted(call.from_user.id, platform)
    
    # Redirect to Data-Verified flow
    await call.message.edit_text("🔋 <b>Starting Data-Verified Upgrade...</b>\n\nRedirecting to upload flow...")
    
    # Trigger Data-Verified handler
    from handlers.data_verified_powerup import offer_data_verified_powerup
    await offer_data_verified_powerup(call, state)

@router.callback_query(F.data == "skip_powerup")
async def handle_powerup_skip(call: CallbackQuery, state: FSMContext):
    """User skipped powerup"""
    await call.answer()
    await generate_passport_v4(call.message, state)

# Remove old VAMP assessment - now handled by start_vamp_assessment_v4
# async def start_vamp_assessment(message: Message, state: FSMContext):

# Handler for number input (VAMP rates, etc.)
@router.message(GoldenFlowStates.awaiting_number_input)
async def handle_number_input(message: Message, state: FSMContext):
    """Handle numeric input for VAMP questions"""
    data = await state.get_data()
    question_id = data.get('awaiting_question_id')
    
    if not question_id:
        await message.answer("❌ Error: No question context found. Please restart the assessment.")
        return
    
    try:
        # Parse the numeric input
        value = float(message.text.replace('%', '').replace(',', '.'))
        
        # Validate range (rates should be between 0 and 1)
        if question_id.startswith('VAMP_') or question_id.startswith('PIX_') or question_id.startswith('EU_'):
            if value > 1.0:  # Assume they meant percentage, convert to decimal
                value = value / 100
            
            if value < 0 or value > 1:
                await message.answer("❌ Please enter a rate between 0 and 1 (or 0% and 100%)")
                return
        
        # Track the answer
        await analytics.track_question_answered(message.from_user.id, question_id, value)
        
        # Store in feature format
        feature_mapping = question_loader.map_answer_to_feature(question_id, value)
        await state.update_data(**feature_mapping)
        
        # Increment question count for price gating logic
        current_count = data.get('questions_answered_count', 0)
        await state.update_data(questions_answered_count=current_count + 1)
        
        # Clear the awaiting state
        await state.update_data(awaiting_question_id=None)
        
        # Provide feedback
        percentage = f"{value:.3%}"
        await message.answer(f"✅ Recorded: {percentage}\\n\\nContinuing with next question...")
        
        # Continue to next question
        await continue_question_flow(message, state)
        
    except ValueError:
        await message.answer("❌ Please enter a valid number. Example formats:\\n• 0.0065 (for 0.65%)\\n• 0.65% (will be converted)\\n• 0.9 (for 90%)")

# ========================================
# FUNNEL B: Payment Verification & Earned Passport System
# ========================================

@router.callback_query(F.data.startswith("verify_payment_"))
async def verify_kit_payment(callback: CallbackQuery, state: FSMContext):
    """Verify kit payment and start interactive workflow (Step B3)"""
    await callback.answer()
    
    kit_type = callback.data.replace("verify_payment_", "")
    
    # In production, verify payment via Stripe webhook or API
    payment_verified = await check_payment_status(callback.from_user.id, kit_type)
    
    if payment_verified:
        await start_interactive_kit_workflow(callback, kit_type, state)
    else:
        await show_payment_verification_options(callback, kit_type, state)

async def check_payment_status(user_id: int, kit_type: str) -> bool:
    """Check if user has paid for the kit"""
    # Demo mode - allow all payments for testing
    if os.getenv('DEMO_MODE', 'true').lower() == 'true':
        logger.info(f"Demo mode: Assuming payment verified for user {user_id}, kit {kit_type}")
        return True
    
    # In production, check database/Stripe for payment record
    # return await db.check_kit_purchase(user_id, kit_type)
    return False

async def show_payment_verification_options(callback: CallbackQuery, kit_type: str, state: FSMContext):
    """Show options when payment is not verified"""
    
    verification_text = """🔍 **Payment Verification**

We couldn't find a payment record for this kit. Here are your options:"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Complete Purchase Now", 
                             url=f"https://merchantguard.ai/kits/{kit_type}?checkout=true")],
        [InlineKeyboardButton(text="📧 Email Proof of Payment", callback_data="email_payment_proof")],
        [InlineKeyboardButton(text="🔄 Check Again", callback_data=f"verify_payment_{kit_type}")],
        [InlineKeyboardButton(text="💬 Contact Support", callback_data="contact_support")]
    ])
    
    await callback.message.edit_text(verification_text, reply_markup=kb)

async def start_interactive_kit_workflow(callback: CallbackQuery, kit_type: str, state: FSMContext):
    """Start the interactive kit workflow (Step B3)"""
    
    # Store payment verification
    await state.update_data(
        kit_paid=True,
        kit_type=kit_type,
        workflow_started=datetime.utcnow().isoformat()
    )
    
    # Track kit workflow start
    await track_event("kit_workflow_started", {
        "user_id": callback.from_user.id,
        "kit_type": kit_type,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    kit_workflows = {
        "crypto": {
            "name": "Crypto Founder's Kit",
            "welcome": """🚀 **Your Crypto Founder's Kit Workflow**

Welcome to the definitive crypto compliance system. We'll guide you through:

**Phase 1:** Banking Foundation
• Compliant entity structure
• Banking readiness assessment  
• Bank-friendly positioning

**Phase 2:** Regulatory Compliance
• Token classification framework
• AML/KYC requirements
• FINCEN obligations

**Phase 3:** Operational Excellence
• Multi-PSP crypto-friendly setup
• Risk management protocols
• Ongoing compliance monitoring

Let's build your **Earned Compliance Passport** together.""",
            "first_question": "BP_1"  # Start with business profile
        },
        
        "global": {
            "name": "Global Founder's Kit", 
            "welcome": """🌍 **Your Global Founder's Kit Workflow**

Welcome to international payments mastery. We'll guide you through:

**Phase 1:** Market Analysis
• Target market selection
• Local compliance requirements
• Currency handling strategies

**Phase 2:** Banking Infrastructure
• Multi-jurisdiction banking
• International wire protocols
• FX risk management

**Phase 3:** Compliance Framework
• Cross-border regulations
• Tax optimization strategies
• Operational excellence

Your **Earned Compliance Passport** awaits.""",
            "first_question": "MKT_1"  # Start with market selection
        },
        
        "builders": {
            "name": "Builder's Standard Kit",
            "welcome": """🛠️ **Your Builder's Standard Kit Workflow**

Welcome to multi-PSP mastery. We'll guide you through:

**Phase 1:** Foundation Assessment
• Current PSP analysis
• Risk profile optimization
• Switching cost calculation

**Phase 2:** Multi-PSP Strategy
• Provider diversification plan
• Routing logic design
• Backup system setup

**Phase 3:** Implementation
• Technical integration guides
• Compliance documentation
• Ongoing monitoring systems

Ready to earn your **Multi-PSP Compliance Passport**?""",
            "first_question": "VAMP_1"  # Start with VAMP assessment
        }
    }
    
    workflow = kit_workflows.get(kit_type, kit_workflows["builders"])
    
    # Send hero image with workflow welcome
    await send_guardscore_hero(callback.message, workflow["welcome"])
    
    # Start the assessment flow
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Begin Assessment", callback_data=f"start_kit_assessment_{kit_type}")],
        [InlineKeyboardButton(text="📋 View Kit Modules", callback_data=f"view_modules_{kit_type}")]
    ])
    
    await asyncio.sleep(1)
    await callback.message.answer("👆 Ready to begin your personalized workflow?", reply_markup=kb)

@router.callback_query(F.data.startswith("start_kit_assessment_"))
async def start_kit_assessment(callback: CallbackQuery, state: FSMContext):
    """Start the kit-specific assessment"""
    await callback.answer()
    
    kit_type = callback.data.replace("start_kit_assessment_", "")
    
    # Route to appropriate assessment based on kit type
    if kit_type == "crypto":
        # Start with business profile for crypto
        await ask_question_by_id(callback.message, "BP_1", state)
    elif kit_type == "global":
        # Start with market selection for global
        await ask_question_by_id(callback.message, "MKT_1", state)
    elif kit_type == "builders":
        # Start with VAMP assessment for builders
        await ask_question_by_id(callback.message, "VAMP_1", state)
    else:
        # Default to business profile
        await ask_question_by_id(callback.message, "BP_1", state)

async def issue_earned_passport(user_id: int, kit_type: str, assessment_data: dict, state_data: dict):
    """Issue Earned Compliance Passport (Step B4)"""
    from datetime import timedelta
    import uuid
    from analytics.ltv_tracking import LTVTracker
    
    # Calculate enhanced score for paid kit
    base_score = assessment_data.get('guardscore', 75)
    earned_bonus = 15  # Bonus for completing paid kit
    final_score = min(base_score + earned_bonus, 100)
    
    passport_id = f"mgp_earned_{uuid.uuid4().hex[:8]}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=180)
    
    # Track kit completion and passport issuance
    tracker = LTVTracker()
    await tracker.track_kit_conversion(user_id, kit_type, {
        "payment_method": "verified",
        "checkout_method": "telegram_bot_premium",
        "workflow_completed": True
    })
    
    passport = {
        "passport_id": passport_id,
        "tier": "earned",  # Higher tier than self_attested
        "guardscore": final_score,
        "valid_until": expires_at,
        "issued_at": datetime.now(timezone.utc),
        "issuer": f"MerchantGuard Bot (Earned via {kit_type.title()} Kit)",
        "kit_completed": kit_type,
        "workflow_data": assessment_data,
        "portal_url": f"https://merchantguard.ai/passport/{passport_id}",
        "verification_signature": f"earned_{kit_type}_{user_id}_{int(datetime.now().timestamp())}"
    }
    
    # Store in database
    await store_passport(user_id, passport)
    
    return passport

@router.callback_query(F.data == "email_payment_proof")
async def handle_email_proof(callback: CallbackQuery, state: FSMContext):
    """Handle email proof of payment"""
    await callback.answer()
    
    proof_text = """📧 **Email Proof of Payment**

Please forward your payment confirmation to:
**support@merchantguard.ai**

Include:
• Your Telegram username (@username)  
• Transaction ID or receipt
• Kit name you purchased

We'll verify and activate your kit within 2 hours."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Email Sent - Check Status", callback_data="check_manual_verification")],
        [InlineKeyboardButton(text="💳 Purchase Now Instead", url="https://merchantguard.ai/kits")]
    ])
    
    await callback.message.edit_text(proof_text, reply_markup=kb)

@router.callback_query(F.data == "suggest_free_guide")
async def suggest_free_guide(callback: CallbackQuery, state: FSMContext):
    """Suggest free guide alternative"""
    await callback.answer()
    
    free_guide_text = """🆓 **Try Our Free Guides First**

Not ready for the full kit? Start with our free compliance guides:

• **Fintech 1-Day Guide** - Quick compliance foundation
• **Multi-PSP Readiness** - Switching strategies  
• **Brazil PIX MED** - International expansion guide

Each includes a free Self-Attested Compliance Passport!"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Get Free Fintech Guide", url="https://t.me/MerchantGuardPilotBot?start=guide_fintech_1day")],
        [InlineKeyboardButton(text="🔄 Multi-PSP Guide", url="https://t.me/MerchantGuardPilotBot?start=multipsp")], 
        [InlineKeyboardButton(text="🌎 Brazil PIX Guide", url="https://t.me/MerchantGuardPilotBot?start=guide_pix_med_brazil")]
    ])
    
    await callback.message.edit_text(free_guide_text, reply_markup=kb)

async def show_kit_resources_access(message: Message, kit_type: str, state: FSMContext):
    """Show kit resources access for earned passport holders"""
    
    kit_resources = {
        "crypto": {
            "name": "Crypto Founder's Kit Resources",
            "resources": [
                "🏦 Bank-Approved Entity Structures",
                "📋 Crypto-Friendly PSP Directory", 
                "⚖️ Token Classification Framework",
                "🔒 AML/KYC Template Library",
                "📊 FINCEN Compliance Tracker"
            ],
            "bonus": "Bonus: Direct line to our crypto compliance attorney"
        },
        "global": {
            "name": "Global Founder's Kit Resources", 
            "resources": [
                "🌍 Multi-Jurisdiction Banking Guide",
                "💱 FX Risk Management Toolkit",
                "📋 International PSP Network Access",
                "⚖️ Cross-Border Compliance Calendar",
                "🏛️ Tax Optimization Strategies"
            ],
            "bonus": "Bonus: Monthly global regulatory updates"
        },
        "builders": {
            "name": "Builder's Standard Kit Resources",
            "resources": [
                "🔄 Multi-PSP Integration Templates",
                "📊 Risk Profile Optimization Tools", 
                "🏦 PSP Switching Playbooks",
                "⚙️ Technical Implementation Guides",
                "📈 Performance Monitoring Dashboards"
            ],
            "bonus": "Bonus: Priority PSP introduction service"
        }
    }
    
    kit_info = kit_resources.get(kit_type, kit_resources["builders"])
    
    resources_text = f"""🎁 **{kit_info['name']}**

Congratulations on earning your passport! You now have access to:

""" + "\n".join(kit_info['resources']) + f"""

🎯 **{kit_info['bonus']}**

**Your Kit Dashboard:** All resources are available in your personal portal."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎛️ Access Kit Dashboard", url=f"https://merchantguard.ai/dashboard/kits/{kit_type}")],
        [InlineKeyboardButton(text="📞 Schedule Compliance Review", callback_data="schedule_review")],
        [InlineKeyboardButton(text="🔄 Renewal Options", callback_data="passport_renewal")],
        [InlineKeyboardButton(text="🎯 Main Menu", callback_data="main_menu")]
    ])
    
    await message.answer(resources_text, reply_markup=kb)

# New handlers for earned passport actions
@router.callback_query(F.data == "share_earned_passport")
async def handle_share_earned_passport(callback: CallbackQuery, state: FSMContext):
    """Handle sharing of earned passport"""
    await callback.answer()
    
    share_text = """🏆 **Share Your Achievement**

You've earned a prestigious **Earned Compliance Passport**! This demonstrates your commitment to compliance excellence.

**Share options:**
• LinkedIn achievement post  
• Twitter compliance badge
• Email signature certificate
• PSP introduction package

Which would you like to share?"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 LinkedIn Post", callback_data="share_linkedin")],
        [InlineKeyboardButton(text="🐦 Twitter Badge", callback_data="share_twitter")],
        [InlineKeyboardButton(text="📧 Email Certificate", callback_data="share_email")],
        [InlineKeyboardButton(text="🏦 PSP Package", callback_data="share_psp_package")]
    ])
    
    await callback.message.edit_text(share_text, reply_markup=kb)

@router.callback_query(F.data.startswith("kit_resources_"))
async def handle_kit_resources_access(callback: CallbackQuery, state: FSMContext):
    """Handle kit resources access"""
    await callback.answer()
    
    kit_type = callback.data.replace("kit_resources_", "")
    await show_kit_resources_access(callback.message, kit_type, state)

@router.callback_query(F.data == "upgrade_to_earned")
async def handle_upgrade_to_earned(callback: CallbackQuery, state: FSMContext):
    """Handle upgrade to earned passport"""
    await callback.answer()
    
    upgrade_text = """⬆️ **Upgrade to Earned Passport**

Transform your Self-Attested Passport into an **Earned Passport** with higher credibility.

**How to upgrade:**
• Complete any $499 kit workflow
• Interactive compliance assessment
• Personalized implementation guidance  
• Higher PSP credibility rating

**Available kits:**"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠️ Builder's Standard Kit ($499)", url="https://merchantguard.ai/kits/builders")],
        [InlineKeyboardButton(text="🌍 Global Founder Kit ($499)", url="https://merchantguard.ai/kits/global")],
        [InlineKeyboardButton(text="🚀 Crypto Founder Kit ($499)", url="https://merchantguard.ai/kits/crypto")],
        [InlineKeyboardButton(text="📋 Compare All Kits", url="https://merchantguard.ai/kits")]
    ])
    
    await callback.message.edit_text(upgrade_text, reply_markup=kb)

async def handle_vamp_aha_moment(message: Message, question_id: str, answer: str, state: FSMContext):
    """Handle VAMP aha moments - real-time contextual insights"""
    try:
        # Get current user data for context
        user_data = await state.get_data()
        
        # Convert string answers to appropriate types for numeric questions
        if question_id in ['VAMP_1', 'VAMP_2']:  # Numeric ratio questions
            try:
                answer = float(answer)
            except ValueError:
                logger.warning(f"Could not convert VAMP answer to float: {answer}")
                return
        
        # Get instant insight for this answer
        insight = aha_engine.get_instant_insight(question_id, answer, user_data)
        
        if insight:
            # Format aha moment message
            aha_message = await format_aha_moment_message(insight, question_id)
            
            # Send aha moment with appropriate styling
            await asyncio.sleep(0.8)  # Brief pause for dramatic effect
            await message.answer(aha_message, parse_mode="HTML")
            
            # Track aha moment shown
            await analytics.track_event("aha_moment_shown", {
                "user_id": message.from_user.id,
                "question_id": question_id, 
                "insight_severity": insight['severity'],
                "answer": str(answer)
            })
        
        # Check for combined insights after VAMP_4 (last VAMP question)
        if question_id == 'VAMP_4':
            await handle_combined_vamp_insights(message, state)
            
    except Exception as e:
        logger.error(f"Error handling VAMP aha moment for {question_id}: {e}")

async def format_aha_moment_message(insight: Dict[str, Any], question_id: str) -> str:
    """Format aha moment message with appropriate styling"""
    severity = insight.get('severity', 'info')
    
    # Severity-based styling
    severity_styles = {
        'critical': {
            'icon': '🚨',
            'color_indicator': '🔴',
            'header_style': '<b>CRITICAL INSIGHT</b>'
        },
        'warning': {
            'icon': '⚠️', 
            'color_indicator': '🟡',
            'header_style': '<b>IMPORTANT INSIGHT</b>'
        },
        'positive': {
            'icon': '✅',
            'color_indicator': '🟢', 
            'header_style': '<b>POSITIVE INSIGHT</b>'
        }
    }
    
    style = severity_styles.get(severity, severity_styles['warning'])
    
    # Build message
    lines = [
        f"{style['color_indicator']} {style['header_style']}",
        "",
        f"{style['icon']} <b>{insight.get('title', 'Insight')}</b>",
        "",
        f"<i>{insight.get('message', '')}</i>",
        "",
        f"📊 <b>Impact:</b> {insight.get('impact', '')}"
    ]
    
    # Add action if present
    if insight.get('action'):
        lines.extend([
            "",
            f"🎯 <b>Action:</b> {insight.get('action', '')}"
        ])
    
    lines.extend([
        "",
        f"<i>💡 This insight is based on your {question_id.replace('_', ' ')} answer and industry benchmarks.</i>"
    ])
    
    return "\n".join(lines)

async def handle_combined_vamp_insights(message: Message, state: FSMContext):
    """Handle combined insights after all VAMP questions"""
    try:
        user_data = await state.get_data()
        
        # Get combined insights
        combined_insights = aha_engine.get_combined_insights(user_data)
        
        if combined_insights:
            await asyncio.sleep(1.2)  # Pause before combined insight
            
            for insight in combined_insights:
                combined_message = await format_combined_insight_message(insight)
                await message.answer(combined_message, parse_mode="HTML")
                
                # Track combined insight shown
                await analytics.track_event("combined_insight_shown", {
                    "user_id": message.from_user.id,
                    "insight_key": insight.get('insight_key'),
                    "severity": insight['severity']
                })
        
        # Get contextual recommendation
        recommendation = aha_engine.get_contextual_recommendation(user_data)
        if recommendation:
            rec_message = f"💼 <b>Contextual Recommendation</b>\n\n<i>{recommendation}</i>"
            await message.answer(rec_message, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Error handling combined VAMP insights: {e}")

async def format_combined_insight_message(insight: Dict[str, Any]) -> str:
    """Format combined insight message"""
    severity = insight.get('severity', 'info')
    
    severity_headers = {
        'critical': '🚨 <b>CRITICAL RISK PROFILE</b>',
        'warning': '⚠️ <b>ELEVATED RISK INDICATORS</b>',
        'positive': '✅ <b>PREMIUM RISK PROFILE</b>'
    }
    
    header = severity_headers.get(severity, '💡 <b>ASSESSMENT COMPLETE</b>')
    
    lines = [
        header,
        "",
        f"📋 <b>{insight.get('title', 'Combined Assessment')}</b>",
        "",
        f"<i>{insight.get('message', '')}</i>",
        "",
        f"📊 <b>Impact:</b> {insight.get('impact', '')}", 
        "",
        f"🎯 <b>Next Steps:</b> {insight.get('action', '')}"
    ]
    
    return "\n".join(lines)

# Import required modules
import os
from datetime import datetime, timezone

