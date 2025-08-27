"""MATCH Recovery offer presentation for Telegram bot"""

from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

def match_hybrid_message(vamp_summary: str, ui: dict) -> str:
    """Format the MATCH Recovery hybrid offer message"""
    body = ui.get("hybrid_body", "")
    disc = ui.get("disclaimer","")
    return f"🚨 **{ui.get('hybrid_headline','MATCH Recovery — Hybrid')}**\n\n{body}\n\n{vamp_summary}\n\n_{disc}_"

def match_hybrid_keyboard(checkout_url: str, ui: dict) -> InlineKeyboardMarkup:
    """Generate keyboard for MATCH Recovery offer"""
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text=ui.get("cta_buy","Get Package — $499"), url=checkout_url)],
      [InlineKeyboardButton(text=ui.get("cta_details","See what's included"), callback_data="match_hybrid_details")]
    ])

def format_provider_stats(stats: dict) -> str:
    """Format observed provider statistics for display"""
    if not stats:
        return "📊 **Success rates will show here as users report outcomes**"
    
    lines = ["📊 **Observed Success Rates (Last 90 Days)**\n"]
    for provider, data in stats.items():
        success_rate = data.get('success', 0) * 100
        avg_days = data.get('days', 0)
        lines.append(f"• {provider.title()}: {success_rate:.0f}% ({avg_days:.0f} days avg)")
    
    return "\n".join(lines)