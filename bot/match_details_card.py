"""MATCH Recovery package details handler"""

from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

DETAILS = (
"**MATCH Liberation Package ($499)**\n\n"
"🚀 **IMMEDIATE (24–72h):**\n"
"• MoR applications (FastSpring, Paddle)\n"
"• USDC payment setup guide\n"
"• Keep selling while apps process\n\n"
"💼 **TRADITIONAL RECOVERY (2-12 weeks):**\n"
"• 5 pre‑filled high‑risk applications\n"
"• Emergency underwriter contacts\n"
"• Rejection recovery scripts\n"
"• MATCH removal letter templates\n\n"
"🎯 **ONGOING SUPPORT:**\n"
"• Weekly interactive check‑ins\n"
"• Outcome tracking & optimization\n"
"• FREE on‑chain attestation ($49 value)\n\n"
"**This is a DIY package** — we provide all materials, you handle submissions.\n\n"
"*One payment. Two paths. Maximum survival odds.*"
)

@router.callback_query(F.data == "match_hybrid_details")
async def show_details(cb: CallbackQuery):
    """Show detailed package contents"""
    await cb.message.answer(DETAILS, parse_mode="Markdown")
    await cb.answer("Package details sent!")