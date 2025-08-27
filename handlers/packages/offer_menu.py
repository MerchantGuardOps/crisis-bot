from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from typing import List, Dict, Any
import os

from bot.utils.config_loader import load_packages_config
from bot.payments.stripe_client import create_checkout_session

router = Router()
PKG_CFG = load_packages_config()

def _build_menu_buttons(package_codes: List[str], locale: str = "en"):
    rows = []
    for code in package_codes:
        p = PKG_CFG["packages"].get(code)
        if not p: 
            continue
        cta = p["locales"].get(locale, p["locales"]["en"])["cta"]
        rows.append([
            InlineKeyboardButton(text=f"ℹ️ {p['name']}", callback_data=f"view_pkg:{code}"),
            InlineKeyboardButton(text=f"💳 {cta}", callback_data=f"buy_pkg:{code}")
        ])
    rows.append([InlineKeyboardButton(text="🔙 Back", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _pick_menu(context: Dict[str, Any]) -> List[str]:
    market = context.get("market")
    industry = context.get("industry")
    if market and market in PKG_CFG.get("offer_logic", {}).get("by_market", {}):
        return PKG_CFG["offer_logic"]["by_market"][market]["show"]
    if industry and industry in PKG_CFG.get("offer_logic", {}).get("by_industry", {}):
        return PKG_CFG["offer_logic"]["by_industry"][industry]["show"]
    return PKG_CFG["offer_logic"]["default_menu"]["show"]

@router.message(F.text == "/offers")
async def show_offers(message: Message):
    ctx = getattr(message, "merchantguard_ctx", {}) or {}
    menu_codes = _pick_menu(ctx)
    kb = _build_menu_buttons(menu_codes, locale=ctx.get("locale", "en"))
    await message.answer(
        "Choose the package that fits you best. You can always upgrade later.",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("view_pkg:"))
async def on_view_package(cb: CallbackQuery):
    code = cb.data.split(":")[1]
    p = PKG_CFG["packages"].get(code)
    if not p:
        await cb.answer("Unavailable", show_alert=True); return

    await cb.message.edit_text(
        f"**{p['name']}** — ${p['price_usd']}

{p['description']}

"
        f"_Educational readiness tools. No guarantees. You submit your own applications._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💳 Buy Now", callback_data=f"buy_pkg:{code}")
        ],[
            InlineKeyboardButton(text="🔙 Back", callback_data="back_to_menu")
        ]])
    )

@router.callback_query(F.data.startswith("buy_pkg:"))
async def on_buy_package(cb: CallbackQuery):
    user_id = cb.from_user.id
    code = cb.data.split(":")[1]
    p = PKG_CFG["packages"].get(code)
    if not p:
        await cb.answer("Unavailable", show_alert=True); return

    price_id = p.get("stripe_price_id")
    if not price_id or price_id.startswith("price_xxx"):
        await cb.answer("Payment not configured yet. Ask support.", show_alert=True); return

    checkout_url = create_checkout_session(user_id, code, price_id)
    await cb.message.answer(
        f"Secure checkout for **{p['name']} (${p['price_usd']})**:
{checkout_url}

"
        "By paying, you agree to our Terms (educational only, no guarantees).",
        parse_mode="Markdown"
    )
    await cb.answer()

@router.callback_query(F.data == "back_to_menu")
async def on_back(cb: CallbackQuery):
    ctx = getattr(cb.message, "merchantguard_ctx", {}) or {}
    menu_codes = _pick_menu(ctx)
    kb = _build_menu_buttons(menu_codes, locale=ctx.get("locale", "en"))
    await cb.message.edit_text(
        "Choose the package that fits you best. You can always upgrade later.",
        reply_markup=kb
    )