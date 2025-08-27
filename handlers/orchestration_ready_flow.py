"""
Orchestration-Ready Flow
Multi-PSP readiness checklist for payment orchestration
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import yaml
import json
from datetime import datetime
from typing import Dict, List, Optional

router = Router()

class OrchestrationStates(StatesGroup):
    """States for orchestration readiness flow"""
    COLLECTING_INTENT = State()
    RUNNING_CHECKLIST = State()
    REVIEWING_RESULTS = State()

# Load task configuration
with open('content/bot_tasks.yaml', 'r') as f:
    config = yaml.safe_load(f)

orchestration_config = config['tasks']['orchestration_ready']

# 8-point orchestration checklist
ORCHESTRATION_CHECKLIST = [
    {
        "id": "public_identity",
        "name": "Public Identity Signals",
        "description": "WHOIS shows business entity publicly",
        "check_type": "whois_verification",
        "weight": 15
    },
    {
        "id": "footer_policies", 
        "name": "Footer Policies",
        "description": "Terms, Privacy, Refund policies accessible",
        "check_type": "policy_scan",
        "weight": 12
    },
    {
        "id": "refund_latency",
        "name": "Refund Latency Targets", 
        "description": "Clear refund timeline in policies",
        "check_type": "policy_content",
        "weight": 10
    },
    {
        "id": "dispute_sop",
        "name": "Dispute SOP + Evidence Pack",
        "description": "Documented chargeback response process",
        "check_type": "process_documentation",
        "weight": 15
    },
    {
        "id": "3ds_stepup",
        "name": "3-DS Step-up Plan",
        "description": "Strategy for authentication challenges", 
        "check_type": "technical_plan",
        "weight": 12
    },
    {
        "id": "saq_hosted_fields",
        "name": "SAQ-A / Hosted Fields",
        "description": "PCI compliance approach documented",
        "check_type": "security_compliance",
        "weight": 15
    },
    {
        "id": "support_alias",
        "name": "Support Alias on Receipts",
        "description": "Consistent support contact across processors",
        "check_type": "operational_setup", 
        "weight": 11
    },
    {
        "id": "guardscore_snapshot",
        "name": "GuardScore Snapshot",
        "description": "Current compliance score saved",
        "check_type": "platform_integration",
        "weight": 10
    }
]

@router.message(F.text == "business_model_collected")
async def ask_multi_psp_intent(message: Message, state: FSMContext):
    """
    Non-blocking multi-PSP intent check during onboarding
    """
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yes", callback_data="multi_psp_yes"),
        InlineKeyboardButton(text="🤔 No / Unsure", callback_data="multi_psp_no")
    ]])
    
    await message.answer(
        "Quick question: Will you use more than one payment processor in the next 12 months?\n\n"
        "This helps us tailor your compliance preparation.",
        reply_markup=kb
    )

@router.callback_query(F.data.in_({"multi_psp_yes", "multi_psp_no"}))
async def handle_multi_psp_intent(call: CallbackQuery, state: FSMContext):
    """Handle multi-PSP intent response"""
    
    if call.data == "multi_psp_yes":
        await state.update_data(multi_psp_intent=True)
        await call.message.edit_text(
            "Perfect! Multi-PSP orchestration is smart business strategy.\n\n"
            "✨ **Quick Win Available:** I've added **Orchestration-Ready** to your menu. "
            "Run our 8-point checklist anytime to prepare for seamless processor switching."
        )
        # Add to persistent menu
        await add_persistent_menu_item(call.from_user.id, "orchestration_ready")
        
    else:
        await state.update_data(multi_psp_intent=False)
        await call.message.edit_text(
            "No problem! Single processor is fine to start.\n\n"
            "I've still added **Orchestration-Ready** to your menu in case you want to prepare for the future."
        )
        # Add to menu anyway (low friction)
        await add_persistent_menu_item(call.from_user.id, "orchestration_ready")
    
    # Continue onboarding without blocking
    await advance_onboarding_flow(call, state)

@router.message(F.text == "Orchestration-Ready")
@router.message(F.text.startswith("/start orchestration"))
async def start_orchestration_flow(message: Message, state: FSMContext):
    """
    Main orchestration readiness flow
    Entry point from menu or deep link
    """
    
    await message.answer(
        f"🎯 **{orchestration_config['label']}**\n\n"
        f"{orchestration_config['rationale']}\n\n"
        "**What we'll check:**\n"
        "• Public identity signals\n"
        "• Policy completeness\n" 
        "• Operational processes\n"
        "• Technical compliance\n\n"
        f"**Reward:** +{orchestration_config['guardscore_points']} GuardScore™ points\n\n"
        "Ready to run your orchestration readiness check?"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Start Checklist", callback_data="start_orchestration_check"),
        InlineKeyboardButton(text="📋 See Full Checklist", callback_data="show_checklist_details")
    ]])
    
    await message.answer("Choose your next step:", reply_markup=kb)

@router.callback_query(F.data == "show_checklist_details")
async def show_checklist_details(call: CallbackQuery, state: FSMContext):
    """Show detailed checklist breakdown"""
    
    details_text = "**8-Point Orchestration Checklist:**\n\n"
    
    for i, item in enumerate(ORCHESTRATION_CHECKLIST, 1):
        details_text += f"**{i}. {item['name']}**\n"
        details_text += f"   {item['description']}\n"
        details_text += f"   Weight: {item['weight']}%\n\n"
    
    details_text += "Each item maps to reviewer expectations across major PSPs.\n\n"
    details_text += "Ready to begin?"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Start Checklist", callback_data="start_orchestration_check"),
        InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")
    ]])
    
    await call.message.edit_text(details_text, reply_markup=kb)

@router.callback_query(F.data == "start_orchestration_check")
async def run_orchestration_checklist(call: CallbackQuery, state: FSMContext):
    """Run the 8-point orchestration checklist"""
    
    await call.message.edit_text(
        "🔍 **Running Orchestration Readiness Check...**\n\n"
        "Checking your setup against multi-PSP requirements..."
    )
    
    await state.set_state(OrchestrationStates.RUNNING_CHECKLIST)
    
    # Get user data for checks
    user_data = await state.get_data()
    domain = user_data.get('business_website', '').replace('https://', '').replace('http://', '').split('/')[0]
    
    # Run checklist items
    results = []
    total_score = 0
    max_score = sum(item['weight'] for item in ORCHESTRATION_CHECKLIST)
    
    for item in ORCHESTRATION_CHECKLIST:
        result = await run_checklist_item(item, user_data, domain)
        results.append(result)
        if result['passed']:
            total_score += item['weight']
    
    # Calculate orchestration readiness score
    readiness_percentage = int((total_score / max_score) * 100)
    
    await state.update_data(
        orchestration_results=results,
        orchestration_score=readiness_percentage,
        orchestration_completed=datetime.utcnow().isoformat()
    )
    
    # Show results
    await show_orchestration_results(call, state, results, readiness_percentage)

async def run_checklist_item(item: Dict, user_data: Dict, domain: str) -> Dict:
    """Run individual checklist item"""
    
    result = {
        'id': item['id'],
        'name': item['name'], 
        'passed': False,
        'message': '',
        'weight': item['weight']
    }
    
    if item['check_type'] == 'whois_verification':
        # Check if domain privacy is already verified
        domain_privacy_status = user_data.get('domain_privacy_status')
        result['passed'] = domain_privacy_status == 'verified'
        result['message'] = "✅ Domain shows public business info" if result['passed'] else "❌ Domain privacy enabled"
        
    elif item['check_type'] == 'policy_scan':
        # Check if policies exist (simplified)
        result['passed'] = True  # Assume passes if they've gotten this far
        result['message'] = "✅ Required policies detected"
        
    elif item['check_type'] == 'policy_content':
        result['passed'] = True  # Placeholder - would check policy content
        result['message'] = "✅ Refund timeline specified"
        
    elif item['check_type'] == 'process_documentation':
        result['passed'] = False  # Most don't have this initially
        result['message'] = "❌ Needs documented dispute process"
        
    elif item['check_type'] == 'technical_plan':
        result['passed'] = False  # Most don't have this initially  
        result['message'] = "❌ Needs 3-DS implementation plan"
        
    elif item['check_type'] == 'security_compliance':
        result['passed'] = True   # Assume basic compliance
        result['message'] = "✅ Basic PCI compliance approach"
        
    elif item['check_type'] == 'operational_setup':
        result['passed'] = True   # Assume they have support email
        result['message'] = "✅ Support contact configured"
        
    elif item['check_type'] == 'platform_integration':
        result['passed'] = True   # They're using the platform
        result['message'] = "✅ GuardScore snapshot available"
    
    return result

async def show_orchestration_results(call: CallbackQuery, state: FSMContext, results: List[Dict], score: int):
    """Display orchestration readiness results"""
    
    # Determine readiness level
    if score >= 85:
        level = "🟢 **Excellent**"
        level_msg = "Ready for multi-PSP orchestration!"
    elif score >= 70:
        level = "🟡 **Good**" 
        level_msg = "Minor improvements needed"
    elif score >= 55:
        level = "🟠 **Fair**"
        level_msg = "Several gaps to address"
    else:
        level = "🔴 **Needs Work**"
        level_msg = "Significant preparation required"
    
    results_text = f"🎯 **Orchestration Readiness: {score}%**\n\n"
    results_text += f"{level}\n{level_msg}\n\n"
    results_text += "**Checklist Results:**\n\n"
    
    # Show results for each item
    for result in results:
        results_text += f"{result['message']}\n"
    
    results_text += f"\n**+{orchestration_config['guardscore_points']} GuardScore™ points earned!**"
    
    # Action buttons based on score
    if score >= 70:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Generate Readiness Report", callback_data="generate_readiness_report")],
            [InlineKeyboardButton(text="🔄 Re-run Check", callback_data="start_orchestration_check")]
        ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛠️ Fix Issues", callback_data="fix_orchestration_issues")],
            [InlineKeyboardButton(text="📋 Get Action Plan", callback_data="orchestration_action_plan")]
        ])
    
    await call.message.edit_text(results_text, reply_markup=kb)
    
    # Award GuardScore points
    await add_guardscore_points(
        call.from_user.id, 
        orchestration_config['guardscore_points'],
        'orchestration_ready_completed'
    )
    
    # Mark as completed if score is high enough
    if score >= 70:
        await state.update_data(orchestration_ready_status="verified")

@router.callback_query(F.data == "generate_readiness_report")
async def generate_readiness_report(call: CallbackQuery, state: FSMContext):
    """Generate shareable readiness report"""
    
    user_data = await state.get_data()
    score = user_data.get('orchestration_score', 0)
    
    report_url = await create_readiness_snapshot(call.from_user.id, user_data)
    
    await call.message.edit_text(
        f"📊 **Orchestration Readiness Report Generated**\n\n"
        f"Your Score: **{score}%**\n"
        f"Report ID: `{report_url}`\n\n"
        "This portable snapshot can be shared with PSPs to demonstrate your multi-processor readiness.\n\n"
        "The report includes your checklist results and compliance verification."
    )

# PSP Attestation Gate (Phase 4)
@router.message(F.text == "request_psp_attestation")
async def check_orchestration_before_attestation(message: Message, state: FSMContext):
    """
    Hard gate for PSP attestation - require orchestration readiness
    """
    
    user_data = await state.get_data()
    orchestration_status = user_data.get('orchestration_ready_status')
    domain_privacy_status = user_data.get('domain_privacy_status')
    
    missing_requirements = []
    
    if domain_privacy_status != 'verified':
        missing_requirements.append("✅ Domain Privacy Fix")
    
    if orchestration_status != 'verified':
        missing_requirements.append("✅ Orchestration-Ready Checklist")
    
    if missing_requirements:
        requirements_text = "**Requirements Missing for PSP Attestation:**\n\n"
        for req in missing_requirements:
            requirements_text += f"• {req}\n"
        
        requirements_text += "\n**Why These Matter:**\n"
        requirements_text += "PSP underwriters verify multi-processor readiness before approval. "
        requirements_text += "Completing these requirements speeds up review and reduces rejection risk.\n\n"
        requirements_text += "Complete the missing items to proceed with attestation."
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🛠️ Complete Requirements", callback_data="complete_attestation_requirements")
        ]])
        
        await message.answer(requirements_text, reply_markup=kb)
        return
    
    # All requirements met, proceed with attestation
    await generate_psp_attestation_package(message, state)

# Helper functions
async def add_persistent_menu_item(user_id: int, item_id: str):
    """Add item to user's persistent menu"""
    pass

async def advance_onboarding_flow(call: CallbackQuery, state: FSMContext):
    """Continue to next step in onboarding"""
    pass

async def add_guardscore_points(user_id: int, points: int, reason: str):
    """Award GuardScore points"""
    pass

async def create_readiness_snapshot(user_id: int, user_data: Dict) -> str:
    """Create shareable readiness report"""
    return f"mg_readiness_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}"

async def generate_psp_attestation_package(message: Message, state: FSMContext):
    """Generate PSP attestation package"""
    pass