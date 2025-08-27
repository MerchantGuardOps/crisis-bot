# handlers/guide_entry_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = Router()

class GuideFlowStates(StatesGroup):
    mini_check_q1 = State()
    mini_check_q2 = State() 
    mini_check_q3 = State()
    passport_issued = State()
    kit_upsell = State()

# Guide entry point mapping
GUIDE_CONFIG = {
    "guide_fintech_1day": {
        "title": "1-Day Fintech Compliance Guide",
        "persona": "builders",
        "kit_upsell": "builders_standard",
        "pdf_name": "fintech_compliance_1day.pdf"
    },
    "guide_learning_modules": {
        "title": "GuardScore™ Learning Modules", 
        "persona": "education",
        "kit_upsell": "builders_standard",
        "pdf_name": "guardscore_learning_modules.pdf"
    },
    "guide_pix_med_brazil": {
        "title": "Brazil Pix MED 2.0 Playbook",
        "persona": "igaming",
        "kit_upsell": "global_founder",
        "pdf_name": "brazil_pix_med_playbook.pdf"
    },
    "guide_cbd_processing": {
        "title": "High-Risk CBD Processing Guide",
        "persona": "high_risk", 
        "kit_upsell": "builders_standard",
        "pdf_name": "cbd_processing_guide.pdf"
    },
    "guide_global_payment_rails": {
        "title": "Global Payment Rails Guide",
        "persona": "global",
        "kit_upsell": "global_founder",
        "pdf_name": "global_payment_rails.pdf"
    }
}

@router.message(Command("start"))
async def handle_start_command(message: Message, command: CommandObject, state: FSMContext):
    """Handle /start command with deep link parameters"""
    if not command.args:
        # Default start flow - send to main menu
        await handle_default_start(message, state)
        return
        
    start_param = command.args
    logger.info(f"Start command with param: {start_param} from user {message.from_user.id}")
    
    # Track entry point
    await track_event("bot_start", {
        "user_id": message.from_user.id,
        "start_param": start_param,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    if start_param.startswith("guide_"):
        await handle_guide_entry(message, start_param, state)
    elif start_param.startswith("kit_"):
        await handle_kit_entry(message, start_param, state)
    elif start_param == "multipsp":
        await handle_multipsp_entry(message, state)
    else:
        await handle_default_start(message, state)

async def handle_guide_entry(message: Message, guide_param: str, state: FSMContext):
    """Handle guide entry points - free mini-check flow"""
    config = GUIDE_CONFIG.get(guide_param)
    if not config:
        await message.answer("❌ Guide not found. Let me show you our available resources.")
        await handle_default_start(message, state)
        return
    
    # Store guide context
    await state.update_data(
        guide_param=guide_param,
        guide_config=config,
        entry_type="guide",
        persona=config["persona"]
    )
    
    # Welcome message for guide entry
    welcome_text = f"""🎯 **{config['title']}**

Welcome! I'll help you get started with a quick 3-question assessment to issue your **GuardScore™ Compliance Passport**.

This takes ~60 seconds and gives you:
✅ Your personalized compliance passport
✅ The complete guide (PDF)
✅ Custom recommendations for your business

Ready to begin?"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Start 3-Question Check", callback_data="start_mini_check")]
    ])
    
    await message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "start_mini_check")
async def start_mini_check(call: CallbackQuery, state: FSMContext):
    """Start the 3-question mini-check"""
    await call.answer()
    
    # Track mini-check start
    await track_event("mini_check_started", {
        "user_id": call.from_user.id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Question 1: Website/Business
    q1_text = """**Question 1 of 3: Business Foundation**

Do you have a live website with proper business policies?"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes, live with policies", callback_data="q1_yes_policies"),
            InlineKeyboardButton(text="🔄 Yes, but missing policies", callback_data="q1_yes_no_policies")
        ],
        [InlineKeyboardButton(text="🚧 Still building website", callback_data="q1_building")]
    ])
    
    await call.message.edit_text(q1_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(GuideFlowStates.mini_check_q1)

@router.callback_query(F.data.startswith("q1_"))
async def handle_q1_response(call: CallbackQuery, state: FSMContext):
    """Handle question 1 response"""
    await call.answer()
    
    q1_answer = call.data.replace("q1_", "")
    await state.update_data(q1_answer=q1_answer)
    
    # Question 2: Payment Processing
    q2_text = """**Question 2 of 3: Payment Processing**

What's your current payment processing status?"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Already processing", callback_data="q2_processing"),
            InlineKeyboardButton(text="📝 Applied, waiting approval", callback_data="q2_applied")
        ],
        [
            InlineKeyboardButton(text="🎯 Ready to apply", callback_data="q2_ready"),
            InlineKeyboardButton(text="📋 Still researching", callback_data="q2_researching")
        ]
    ])
    
    await call.message.edit_text(q2_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(GuideFlowStates.mini_check_q2)

@router.callback_query(F.data.startswith("q2_"))
async def handle_q2_response(call: CallbackQuery, state: FSMContext):
    """Handle question 2 response"""
    await call.answer()
    
    q2_answer = call.data.replace("q2_", "")
    await state.update_data(q2_answer=q2_answer)
    
    # Question 3: Multi-PSP Strategy
    q3_text = """**Question 3 of 3: Multi-PSP Strategy**

How important is provider flexibility for your business?"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Critical - need backup options", callback_data="q3_critical"),
            InlineKeyboardButton(text="📈 Important for growth", callback_data="q3_important")
        ],
        [
            InlineKeyboardButton(text="🤔 Exploring options", callback_data="q3_exploring"),
            InlineKeyboardButton(text="➡️ Single provider is fine", callback_data="q3_single")
        ]
    ])
    
    await call.message.edit_text(q3_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(GuideFlowStates.mini_check_q3)

@router.callback_query(F.data.startswith("q3_"))
async def handle_q3_response(call: CallbackQuery, state: FSMContext):
    """Handle question 3 response and issue Self-Attested Passport"""
    await call.answer()
    
    q3_answer = call.data.replace("q3_", "")
    data = await state.get_data()
    
    # Store final answer
    await state.update_data(q3_answer=q3_answer)
    
    # Calculate basic score
    score = await calculate_mini_check_score(data["q1_answer"], data["q2_answer"], q3_answer)
    
    # Issue Self-Attested Passport
    passport = await issue_self_attested_passport(
        user_id=call.from_user.id,
        guide_context=data.get("guide_config", {}),
        mini_check_responses={
            "q1": data["q1_answer"],
            "q2": data["q2_answer"], 
            "q3": q3_answer
        },
        score=score
    )
    
    # Track passport issuance
    await track_event("passport_self_attested", {
        "user_id": call.from_user.id,
        "passport_id": passport["passport_id"],
        "score": score,
        "guide_context": data.get("guide_param"),
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Success message with passport details
    success_text = f"""🎉 **Your GuardScore™ Compliance Passport is Ready!**

**Score:** {score}/100
**Status:** Multi-PSP Ready
**Valid Until:** {passport['expires_at'].strftime('%B %d, %Y')}

✅ **What you get:**
• Your personalized compliance passport
• The complete {data['guide_config']['title']} (PDF)
• Custom recommendations for your business

**Passport Portal:** {passport['portal_url']}
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Download Your Guide (PDF)", callback_data="download_pdf")],
        [InlineKeyboardButton(text="🎯 Upgrade to Full Kit ($499)", callback_data="upsell_kit")],
        [InlineKeyboardButton(text="🔍 View Passport Portal", url=passport['portal_url'])]
    ])
    
    await call.message.edit_text(success_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(GuideFlowStates.passport_issued)

@router.callback_query(F.data == "download_pdf")
async def handle_pdf_download(call: CallbackQuery, state: FSMContext):
    """Handle PDF download request"""
    await call.answer()
    
    data = await state.get_data()
    guide_config = data.get("guide_config", {})
    
    # Track PDF download
    await track_event("guide_pdf_downloaded", {
        "user_id": call.from_user.id,
        "guide": data.get("guide_param"),
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Generate personalized PDF (implementation depends on your PDF system)
    pdf_url = await generate_personalized_pdf(
        user_id=call.from_user.id,
        guide_config=guide_config,
        mini_check_data=data
    )
    
    await call.message.answer(
        f"📄 **Your personalized {guide_config['title']} is ready!**\n\n"
        f"Download: {pdf_url}\n\n"
        f"This guide is customized based on your mini-check responses."
    )
    
    # Show kit upsell after PDF
    await show_kit_upsell(call.message, data)

@router.callback_query(F.data == "upsell_kit")
async def handle_kit_upsell(call: CallbackQuery, state: FSMContext):
    """Handle kit upsell"""
    await call.answer()
    
    data = await state.get_data()
    await show_kit_upsell(call.message, data)

async def show_kit_upsell(message, data):
    """Show appropriate kit upsell based on guide context"""
    guide_config = data.get("guide_config", {})
    kit_type = guide_config.get("kit_upsell", "builders_standard")
    
    # Kit messaging based on type
    kit_info = {
        "builders_standard": {
            "name": "Builder's Starter Kit",
            "desc": "Complete compliance foundation for US fintech builders",
            "highlights": ["Multi-PSP readiness checklist", "Legal entity setup guide", "Policy templates", "PCI compliance roadmap"]
        },
        "global_founder": {
            "name": "Global Founder Kit", 
            "desc": "International banking & compliance for global builders",
            "highlights": ["International banking module", "Multi-jurisdiction compliance", "Currency handling guides", "Global KYC/AML requirements"]
        }
    }
    
    kit = kit_info.get(kit_type, kit_info["builders_standard"])
    
    upsell_text = f"""🚀 **Ready to Go Deeper?**

**{kit['name']} - $499**

{kit['desc']}

**What you get:**
""" + "\n".join([f"✅ {highlight}" for highlight in kit['highlights']]) + f"""

**Plus:**
✅ **Earned Passport** (stronger than Self-Attested)
✅ Interactive completion tracking
✅ 180-day validity with renewal reminders

**Special Add-ons:**
• **Reviewed Passport** (+$199) - Human QA, 24-hr SLA
• **Application Pack** (+$99) - PSP-ready ZIP file
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎯 Get {kit['name']} ($499)", url=f"https://merchantguard.ai/kits/{kit_type}")],
        [InlineKeyboardButton(text="📋 Compare All Kits", url="https://merchantguard.ai/kits")],
        [InlineKeyboardButton(text="💬 Continue in Bot", callback_data="main_menu")]
    ])
    
    await message.answer(upsell_text, reply_markup=kb, parse_mode="Markdown")

# Kit entry handlers
async def handle_kit_entry(message: Message, kit_param: str, state: FSMContext):
    """Handle kit entry points - paid flow"""
    kit_type = kit_param.replace("kit_", "")
    
    # Store kit context
    await state.update_data(
        kit_param=kit_param,
        kit_type=kit_type,
        entry_type="kit"
    )
    
    # Track kit entry
    await track_event("kit_viewed", {
        "user_id": message.from_user.id,
        "kit_type": kit_type,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    kit_welcome_text = f"""🎯 **{get_kit_name(kit_type)} - $499**

You're about to unlock:
✅ Interactive step-by-step modules
✅ **Earned Passport** upon completion
✅ Downloadable resources & templates
✅ 180-day validity with renewal tracking

**Payment required to continue.**
This unlocks the full kit experience and issues your **Earned Passport**.
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Purchase Kit ($499)", url=f"https://merchantguard.ai/kits/{kit_type}?checkout=true")],
        [InlineKeyboardButton(text="📋 Compare All Kits", url="https://merchantguard.ai/kits")],
        [InlineKeyboardButton(text="🆓 Try Free Guide First", callback_data="suggest_free_guide")]
    ])
    
    await message.answer(kit_welcome_text, reply_markup=kb, parse_mode="Markdown")

# Multi-PSP readiness flow
async def handle_multipsp_entry(message: Message, state: FSMContext):
    """Handle multi-PSP readiness assessment"""
    await state.update_data(entry_type="multipsp")
    
    await track_event("multipsp_assessment_started", {
        "user_id": message.from_user.id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    multipsp_text = """🔄 **Multi-PSP Readiness Assessment**

Check if your business is ready to switch providers without starting over.

**8-Point Readiness Check:**
• Business documentation
• Policy compliance  
• Technical integration readiness
• Risk profile optimization
• Financial documentation
• Operational procedures
• Compliance monitoring
• Provider-agnostic setup

This assessment takes ~3 minutes and results in a **readiness score** + recommendations.
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Start 8-Point Check", callback_data="start_8point_check")],
        [InlineKeyboardButton(text="📋 Learn About Multi-PSP", callback_data="learn_multipsp")]
    ])
    
    await message.answer(multipsp_text, reply_markup=kb, parse_mode="Markdown")

# Helper functions
async def calculate_mini_check_score(q1: str, q2: str, q3: str) -> int:
    """Calculate score based on mini-check responses"""
    base_score = 60
    
    # Q1 scoring
    if q1 == "yes_policies":
        base_score += 15
    elif q1 == "yes_no_policies":
        base_score += 8
    elif q1 == "building":
        base_score += 3
    
    # Q2 scoring  
    if q2 == "processing":
        base_score += 15
    elif q2 == "applied":
        base_score += 12
    elif q2 == "ready":
        base_score += 8
    elif q2 == "researching":
        base_score += 5
    
    # Q3 scoring
    if q3 == "critical":
        base_score += 10
    elif q3 == "important":
        base_score += 8
    elif q3 == "exploring":
        base_score += 5
    elif q3 == "single":
        base_score += 2
    
    return min(base_score, 100)

async def issue_self_attested_passport(user_id: int, guide_context: dict, mini_check_responses: dict, score: int):
    """Issue Self-Attested Compliance Passport"""
    from datetime import datetime, timezone, timedelta
    import uuid
    
    passport_id = f"mgp_sa_{uuid.uuid4().hex[:8]}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=180)
    
    passport = {
        "passport_id": passport_id,
        "tier": "self_attested",
        "guardscore": score,
        "valid_until": expires_at,
        "issued_at": datetime.now(timezone.utc),
        "issuer": "MerchantGuard Bot (Self-Attested)",
        "guide_context": guide_context.get("title", ""),
        "mini_check_responses": mini_check_responses,
        "portal_url": f"https://merchantguard.ai/passport/{passport_id}"
    }
    
    # Store in database (implement based on your DB setup)
    await store_passport(user_id, passport)
    
    return passport

async def generate_personalized_pdf(user_id: int, guide_config: dict, mini_check_data: dict) -> str:
    """Generate personalized PDF based on user responses"""
    # Implementation depends on your PDF generation system
    # Return URL to generated PDF
    pdf_filename = f"{guide_config['pdf_name'].replace('.pdf', '')}_{user_id}.pdf"
    return f"https://merchantguard.ai/guides/personalized/{pdf_filename}"

def get_kit_name(kit_type: str) -> str:
    """Get display name for kit type"""
    names = {
        "builders_standard": "Builder's Starter Kit",
        "global_founder": "Global Founder Kit",
        "crypto_founder": "Crypto Founder's Kit", 
        "genius_snapshot": "GENIUS Act Readiness Snapshot"
    }
    return names.get(kit_type, "Builder's Starter Kit")

async def track_event(event_name: str, properties: dict):
    """Track analytics event"""
    # Implement based on your analytics system
    logger.info(f"Event: {event_name}, Properties: {properties}")

async def store_passport(user_id: int, passport: dict):
    """Store passport in database"""
    # Implement based on your database setup
    logger.info(f"Storing passport {passport['passport_id']} for user {user_id}")

async def handle_default_start(message: Message, state: FSMContext):
    """Handle default start command without parameters"""
    await message.answer(
        "👋 Welcome to MerchantGuard! Choose what you'd like to do:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Issue My Compliance Passport", callback_data="start_assessment")],
            [InlineKeyboardButton(text="📚 Browse Guides", callback_data="browse_guides")],
            [InlineKeyboardButton(text="🛒 View Kits", url="https://merchantguard.ai/kits")]
        ])
    )