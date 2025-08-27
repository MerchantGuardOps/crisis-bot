"""Interactive MATCH Recovery check-ins via Telegram"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.match_outcome_service import MatchOutcomeService
import json

router = Router()

# Week 1 Check-in Flow
def week1_message():
    text = (
"📊 **Week 1 Check‑in**\n\n"
"Quick check — did you submit your applications?\n\n"
"**Recommended order:**\n"
"1️⃣ FastSpring (digital, 3-5 days)\n"
"2️⃣ Durango (MATCH recovery, 7-14 days)\n"
"3️⃣ PaymentCloud (mixed, 7-21 days)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="✅ All submitted", callback_data="m1_all")],
      [InlineKeyboardButton(text="📤 Some submitted", callback_data="m1_some")],
      [InlineKeyboardButton(text="⏳ Not yet", callback_data="m1_none")],
      [InlineKeyboardButton(text="🆘 Need help", callback_data="m1_help")]
    ])
    return text, kb

@router.callback_query(F.data.in_({"m1_all","m1_some","m1_none","m1_help"}))
async def week1_capture(cb: CallbackQuery):
    """Handle Week 1 check-in responses"""
    outcome_service: MatchOutcomeService = cb.message.bot.get('outcome_service')
    points_service = cb.message.bot.get('points_service')

    resp = cb.data
    merchant_id = str(cb.from_user.id)
    
    if outcome_service:
        await outcome_service.log_interaction(merchant_id, 1, resp)

    if resp == "m1_all":
        await cb.message.edit_text(
"✅ **Excellent!** You're ahead of 70% of users.\n\n"
"**Typical timelines:**\n"
"• FastSpring: 3–5 days\n"
"• Durango: 7–14 days\n"
"• PaymentCloud: 7–21 days\n\n"
"📧 **Check spam folders daily** — approvals often land there.\n\n"
"🎯 **+200 MGRD points** for taking action!", parse_mode="Markdown")
        
        if points_service:
            try:
                await points_service.award(merchant_id, "match_progress", 200,
                                         meta={"stage":"week1_submitted"},
                                         idempotency_key=f"match:w1:{merchant_id}")
            except:
                pass  # Points are nice-to-have, don't break flow
                
    elif resp == "m1_some":
        kb = InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="FastSpring ✅", callback_data="m1_did_fs"),
           InlineKeyboardButton(text="Paddle ✅", callback_data="m1_did_paddle")],
          [InlineKeyboardButton(text="Durango ✅", callback_data="m1_did_durango"),
           InlineKeyboardButton(text="PaymentCloud ✅", callback_data="m1_did_pc")],
          [InlineKeyboardButton(text="EMB ✅", callback_data="m1_did_emb")],
          [InlineKeyboardButton(text="📝 Submit remaining now", callback_data="m1_finish")]
        ])
        await cb.message.edit_text(
"📤 **Good progress!** Tap the ones you've submitted:", 
reply_markup=kb, parse_mode="Markdown")
        
    elif resp == "m1_none":
        kb = InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="USDC live ✅", callback_data="m1_usdc_yes")],
          [InlineKeyboardButton(text="USDC not setup", callback_data="m1_usdc_no")],
          [InlineKeyboardButton(text="Need USDC help", callback_data="m1_usdc_help")]
        ])
        await cb.message.edit_text(
"⏰ **Time is critical.** Submit today for best results.\n\n"
"**Start with:**\n"
"1️⃣ FastSpring (digital products)\n"
"2️⃣ Durango (MATCH specialists)\n\n"
"**Meanwhile** — is USDC payment setup?", 
reply_markup=kb, parse_mode="Markdown")
        
    else:  # m1_help
        kb = InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="Missing documents", callback_data="m1_docs")],
          [InlineKeyboardButton(text="Fields unclear", callback_data="m1_fields")],
          [InlineKeyboardButton(text="Technical issue", callback_data="m1_tech")]
        ])
        await cb.message.edit_text("🆘 **What's blocking you?**", reply_markup=kb, parse_mode="Markdown")
    
    await cb.answer()

# Week 2 Check-in Flow
def week2_message():
    text = (
"🎯 **Week 2 Update**\n\n"
"Any responses from processors yet?\n\n"
"Don't panic if still waiting — underwriting takes time."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🎉 Got approved!", callback_data="m2_approved")],
      [InlineKeyboardButton(text="😞 Got rejected", callback_data="m2_rejected")],
      [InlineKeyboardButton(text="⏳ Still waiting", callback_data="m2_waiting")]
    ])
    return text, kb

@router.callback_query(F.data.in_({"m2_approved","m2_rejected","m2_waiting"}))
async def week2_capture(cb: CallbackQuery):
    """Handle Week 2 check-in responses"""
    outcome_service: MatchOutcomeService = cb.message.bot.get('outcome_service')
    points_service = cb.message.bot.get('points_service')

    resp = cb.data
    merchant_id = str(cb.from_user.id)
    
    if outcome_service:
        await outcome_service.log_interaction(merchant_id, 2, resp)

    if resp == "m2_approved":
        kb = InlineKeyboardMarkup(inline_keyboard=[
          [InlineKeyboardButton(text="FastSpring", callback_data="m2_app_fastspring")],
          [InlineKeyboardButton(text="Durango", callback_data="m2_app_durango")],
          [InlineKeyboardButton(text="PaymentCloud", callback_data="m2_app_paymentcloud")],
          [InlineKeyboardButton(text="Other", callback_data="m2_app_other")]
        ])
        await cb.message.edit_text(
"🎉 **FANTASTIC!** Which processor approved you?", 
reply_markup=kb, parse_mode="Markdown")
        
        if points_service:
            try:
                await points_service.award(merchant_id, "match_success", 500,
                                         meta={"stage":"week2_approved"},
                                         idempotency_key=f"match:w2:{merchant_id}")
            except:
                pass
                
    elif resp == "m2_rejected":
        await cb.message.edit_text(
"😞 **Rejection isn't the end.**\n\n"
"**Next steps:**\n"
"1️⃣ Use rejection recovery scripts in your package\n"
"2️⃣ Offer higher reserve (10-20%)\n"
"3️⃣ Propose volume caps for 90 days\n"
"4️⃣ Apply to next processor on list\n\n"
"Many merchants get approved on 2nd or 3rd try.", parse_mode="Markdown")
        
    else:  # m2_waiting
        await cb.message.edit_text(
"⏰ **Send follow-ups now.**\n\n"
"**Template:**\n"
"```\nSubject: Application Status — [Your Company]\n\nHi Team,\nFollowing up on my application submitted [date].\nApp ID: [reference number]\nHappy to provide additional info.\nThanks!\n```\n\n"
"**Contacts:**\n"
"• FastSpring: merchants@fastspring.com\n"
"• Durango: highrisk@durangomerchantservices.com\n"
"• PaymentCloud: support@paymentcloudinc.com", parse_mode="Markdown")
    
    await cb.answer()

@router.callback_query(F.data.startswith("m2_app_"))
async def week2_provider_detail(cb: CallbackQuery):
    """Record which provider approved the merchant"""
    provider = cb.data.split("_")[2]
    outcome_service: MatchOutcomeService = cb.message.bot.get('outcome_service')
    merchant_id = str(cb.from_user.id)
    
    if outcome_service and provider != "other":
        await outcome_service.record_outcome(merchant_id, provider, approved=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="No reserve", callback_data=f"m2_res_{provider}_0")],
      [InlineKeyboardButton(text="5% reserve", callback_data=f"m2_res_{provider}_5")],
      [InlineKeyboardButton(text="10% reserve", callback_data=f"m2_res_{provider}_10")],
      [InlineKeyboardButton(text="15%+ reserve", callback_data=f"m2_res_{provider}_15")]
    ])
    await cb.message.edit_text(
f"✅ **Logged approval with {provider.title()}!**\n\nWhat reserve did they require?", 
reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("m2_res_"))
async def week2_reserve_capture(cb: CallbackQuery):
    """Record reserve percentage required"""
    _, _, provider, val = cb.data.split("_")
    outcome_service: MatchOutcomeService = cb.message.bot.get('outcome_service')
    merchant_id = str(cb.from_user.id)
    
    reserve_map = {"0": 0.0, "5": 5.0, "10": 10.0, "15": 15.0}
    reserve = reserve_map.get(val)
    
    if outcome_service and provider != "other":
        await outcome_service.record_outcome(merchant_id, provider, approved=True, reserve_percent=reserve)
    
    reserve_text = "No reserve required! 🎉" if reserve == 0 else f"{reserve}% rolling reserve"
    
    await cb.message.edit_text(
f"📈 **{reserve_text}**\n\n"
"**Optimization tips:**\n"
"• Start with smaller test volumes\n"
"• Keep disputes under 0.5%\n"
"• Request step-down review at day 90\n"
"• Enable all fraud tools (3DS, AVS/CVV)\n\n"
"**You survived MATCH! 🎯**", parse_mode="Markdown")
    await cb.answer()

# Demo command for testing
@router.message(F.text == "/match_demo")
async def demo_checkins(message: Message):
    """Demo the check-in flow"""
    text1, kb1 = week1_message()
    await message.answer(text1, reply_markup=kb1, parse_mode="Markdown")
    
    text2, kb2 = week2_message()
    await message.answer(text2, reply_markup=kb2, parse_mode="Markdown")