from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import os, aiohttp

router = Router()
BASE = os.environ.get("BASE_URL", "http://localhost:8000")
FEATURE = os.environ.get("FEATURE_PARTNERS_ENABLED", "true").lower() == "true"

async def _fetch_json(url: str, params: dict):
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params, timeout=10) as r:
            r.raise_for_status()
            return await r.json()

def _kbd_for_recs(user_id: str, recs: list, source: str):
    rows = []
    for r in recs:
        # ask API to generate a signed redirect URL
        # OR build using /partners/go then open URL from its "url" field
        # Here we use /partners/go to obtain signed /r link
        rows.append([InlineKeyboardButton(
            text=f"{r['name']}",
            url=f"{BASE}/partners/go/{r['id']}?user_id={user_id}&source={source}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text == "/partners")
async def partners_cmd(msg: Message):
    if not FEATURE:
        await msg.answer("Partner suggestions are currently disabled.")
        return

    params = {
        "user_id": str(msg.from_user.id),
        "match_listed": False,
        "violation_risk": 0.0,
        "needs_entity": False
    }
    data = await _fetch_json(f"{BASE}/partners/recommendations", params)
    recs = data.get("recommendations", [])
    disclosure = data.get("disclosure", "Independent recommendations.")

    if not recs:
        await msg.answer("No suggestions available right now.")
        return

    text = (
        "🤝 **Independent recommendations**\n\n"
        "These providers often help merchants in similar situations:\n\n" +
        "\n".join([f"• *{r['name']}* — {r['description']}" for r in recs]) +
        f"\n\n_{disclosure}_"
    )
    kb = _kbd_for_recs(str(msg.from_user.id), recs, source="/partners")
    await msg.answer(text, reply_markup=kb, parse_mode="Markdown")

# Contextual offers (call these from your existing flows)

async def send_psp_partner_offer(bot, user_id: int):
    if not FEATURE:
        return
    # Strong PSP suggestions after MATCH $499 purchase
    params = {
        "user_id": str(user_id),
        "match_listed": True,
        "violation_risk": 0.0,
        "needs_entity": False
    }
    data = await _fetch_json(f"{BASE}/partners/recommendations", params)
    recs = [r for r in data.get("recommendations", []) if r.get("category") == "psp"]
    if not recs:
        return
    txt = (
        "✅ **Your MATCH package is ready!**\n\n"
        "We can point you to processors that commonly approve MATCH recovery cases.\n"
        "No affiliate arrangement—just independent recommendations.\n\n"
        "Want to proceed?"
    )
    kb = _kbd_for_recs(str(user_id), recs, source="post_match_499")
    await bot.send_message(chat_id=user_id, text=txt, reply_markup=kb, parse_mode="Markdown")

async def send_legal_partner_offer(bot, user_id: int):
    if not FEATURE:
        return
    params = {
        "user_id": str(user_id),
        "match_listed": False,
        "violation_risk": 0.75,  # high risk threshold hit
        "needs_entity": False
    }
    data = await _fetch_json(f"{BASE}/partners/recommendations", params)
    recs = [r for r in data.get("recommendations", []) if r.get("category") == "legal"]
    if not recs:
        return
    txt = (
        "⚠️ **GuardScore flagged possible violations.**\n\n"
        "If you want, here's an independent legal review option. We don't have an affiliate relationship.\n"
        "They can review your case same‑day."
    )
    kb = _kbd_for_recs(str(user_id), recs, source="guardscore_violation")
    await bot.send_message(chat_id=user_id, text=txt, reply_markup=kb, parse_mode="Markdown")

async def send_llc_partner_offer(bot, user_id: int):
    if not FEATURE:
        return
    params = {
        "user_id": str(user_id),
        "match_listed": False,
        "violation_risk": 0.0,
        "needs_entity": True
    }
    data = await _fetch_json(f"{BASE}/partners/recommendations", params)
    recs = [r for r in data.get("recommendations", []) if r.get("category") == "formation"]
    if not recs:
        return
    txt = (
        "📝 **Need a clean entity for applications?**\n\n"
        "Here's a formation option we've seen merchants use.\n"
        "_Independent recommendation; no affiliate relationship._"
    )
    kb = _kbd_for_recs(str(user_id), recs, source="onboarding_llc")
    await bot.send_message(chat_id=user_id, text=txt, reply_markup=kb, parse_mode="Markdown")
