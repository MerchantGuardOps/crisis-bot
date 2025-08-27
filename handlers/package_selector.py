"""
Golden Flow v5.0 - Multi-Package Selector Integration
===================================================

Integrates the complete product catalog with user choice into Golden Flow v5.0:
- User gets full choice of all packages ($97, $199, $297, $499)
- Smart curation based on market/industry but never forced
- Integrates with existing ToS, analytics, and ML pipeline
- Stripe checkout + instant digital delivery
- Maintains Golden Flow v5.0 enterprise architecture
"""

import asyncio
import json
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from analytics.utm_enhanced_tracking import track_offer_shown_with_utm

# Import our Golden Flow v5.0 system
from golden_flow_v5_integration import golden_flow_v5

class PackageSelector:
    """Complete package selector with user choice and smart curation."""
    
    def __init__(self):
        self._load_configurations()
    
    def _load_configurations(self):
        """Load package configurations."""
        
        # Load package catalog
        with open('config/packages.yaml', 'r') as f:
            self.packages_config = yaml.safe_load(f)
            
        # Load delivery routing
        with open('config/packs.yaml', 'r') as f:
            self.packs_config = yaml.safe_load(f)
    
    async def show_package_menu(self, message: Message, user_id: int, context: Dict = None):
        """Show complete package menu with smart curation."""
        
        if context is None:
            context = {}
        
        # Determine curated packages based on market/industry
        recommended_packages = self._get_recommended_packages(context)
        all_packages = list(self.packages_config['packages'].keys())
        
        # Build keyboard with recommendations first
        keyboard_buttons = []
        
        # Add recommended packages section
        if recommended_packages:
            keyboard_buttons.append([InlineKeyboardButton(text="🎯 Recommended for You", callback_data="info_recommended")])
            
            for pkg_id in recommended_packages[:3]:  # Top 3 recommendations
                pkg = self.packages_config['packages'][pkg_id]
                price = pkg['price_usd']
                
                keyboard_buttons.append([
                    InlineKeyboardButton(text=f"ℹ️ {pkg['name']}", callback_data=f"pkg_view_{pkg_id}"),
                    InlineKeyboardButton(text=f"💳 ${price}", callback_data=f"pkg_buy_{pkg_id}")
                ])
        
        # Add "View All Packages" option
        keyboard_buttons.append([InlineKeyboardButton(text="📋 View All Packages", callback_data="show_all_packages")])
        
        # Navigation options
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔍 Full Assessment (Free)", callback_data="switch_to_full_assessment"),
            InlineKeyboardButton(text="❓ Help", callback_data="package_help")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Context-aware message
        market_name = self._get_market_display_name(context.get('market'))
        industry_name = context.get('industry', 'General')
        
        await message.answer(
            f"💼 **Choose Your Package**\n\n"
            f"📍 **Market**: {market_name}\n"
            f"🏢 **Industry**: {industry_name}\n\n"
            f"We've curated the best options for your profile, but you can choose any package:\n\n"
            f"🚀 **Fast & Automated** → Digital delivery in minutes\n"
            f"💎 **Premium & Expert** → Custom strategy + calls\n"
            f"📚 **Educational Only** → No guarantees, you submit applications\n\n"
            f"Select a package to see details:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Track analytics
        await golden_flow_v5._track_event(user_id, 'package_menu_shown', {
            'recommended_packages': recommended_packages,
            'market': context.get('market'),
            'industry': context.get('industry'),
            'user_choice': True
        })
    
    def _get_recommended_packages(self, context: Dict) -> List[str]:
        """Get recommended packages based on context."""
        
        market = context.get('market')
        industry = context.get('industry') 
        
        offer_logic = self.packages_config.get('offer_logic', {})
        
        # Try market-specific recommendations first
        if market and market in offer_logic.get('by_market', {}):
            return offer_logic['by_market'][market]['show']
        
        # Try industry-specific recommendations
        if industry and industry in offer_logic.get('by_industry', {}):
            return offer_logic['by_industry'][industry]['show']
        
        # Fall back to default menu
        return offer_logic.get('default_menu', {}).get('show', ['readiness_pack_199', 'kit_builder_499', 'quick_fix_97'])
    
    def _get_market_display_name(self, market_code: str) -> str:
        """Get user-friendly market name."""
        
        market_names = {
            'US_CARDS': 'US Cards (VAMP)',
            'BR_PIX': 'Brazil PIX',
            'EU_CARDS_SCA': 'EU Cards (SCA)',
            'OTHER': 'Multi-Market'
        }
        return market_names.get(market_code, 'Global')
    
    async def show_all_packages(self, message: Message, user_id: int):
        """Show complete package catalog."""
        
        keyboard_buttons = []
        
        # Group packages by tier
        tiers = {
            'digital': '📦 Digital Packages',
            'service_async': '🎥 Service Packages', 
            'premium_kit': '💎 Premium Kits'
        }
        
        for tier, tier_name in tiers.items():
            # Add tier header
            keyboard_buttons.append([InlineKeyboardButton(text=tier_name, callback_data=f"info_tier_{tier}")])
            
            # Add packages in this tier
            for pkg_id, pkg in self.packages_config['packages'].items():
                if pkg.get('tier') == tier:
                    price = pkg['price_usd']
                    keyboard_buttons.append([
                        InlineKeyboardButton(text=f"ℹ️ {pkg['name']}", callback_data=f"pkg_view_{pkg_id}"),
                        InlineKeyboardButton(text=f"💳 ${price}", callback_data=f"pkg_buy_{pkg_id}")
                    ])
        
        # Navigation
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔙 Back to Recommendations", callback_data="back_to_recommendations"),
            InlineKeyboardButton(text="❓ Compare Packages", callback_data="compare_packages")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(
            f"📋 **Complete Package Catalog**\n\n"
            f"Choose any package that fits your needs. All packages include:\n"
            f"• Educational materials and templates\n"
            f"• No approval guarantees (you submit applications)\n"
            f"• 7-day refund if not accessed\n\n"
            f"**Select a package:**",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        await golden_flow_v5._track_event(user_id, 'all_packages_viewed', {})
    
    async def show_package_details(self, callback: CallbackQuery, package_id: str):
        """Show detailed package information."""
        
        pkg = self.packages_config['packages'].get(package_id)
        if not pkg:
            await callback.answer("❌ Package not found", show_alert=True)
            return
        
        # Format package details
        tier_names = {
            'digital': 'Digital Package',
            'service_async': 'Async Service',
            'premium_kit': 'Premium Kit'
        }
        
        tier_name = tier_names.get(pkg.get('tier'), 'Package')
        
        # Build contents preview
        contents = self._get_package_contents(package_id)
        contents_text = '\n'.join([f"• {item}" for item in contents])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Buy ${pkg['price_usd']}", callback_data=f"pkg_buy_{package_id}")],
            [InlineKeyboardButton(text="📋 View All Packages", callback_data="show_all_packages")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_recommendations")]
        ])
        
        await callback.message.edit_text(
            f"📦 **{pkg['name']}** - ${pkg['price_usd']}\n"
            f"🏷️ *{tier_name}*\n\n"
            f"**Description:**\n"
            f"{pkg['description']}\n\n"
            f"**What's Included:**\n"
            f"{contents_text}\n\n"
            f"⚠️ **Important:** Educational materials only. No approval guarantees. You submit your own applications. Not ISO/broker services.\n\n"
            f"💳 **Secure Payment:** Stripe checkout with 30-day support",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Track offer shown with UTM context
        await track_offer_shown_with_utm(
            user_id=callback.from_user.id,
            package_id=package_id,
            price=pkg['price_usd'],
            display_context="package_details_view"
        )
        
        # Legacy tracking
        await golden_flow_v5._track_event(callback.from_user.id, 'package_details_viewed', {
            'package_id': package_id,
            'price': pkg['price_usd']
        })
    
    def _get_package_contents(self, package_id: str) -> List[str]:
        """Get package contents preview."""
        
        # Package-specific contents (can be enhanced)
        contents_map = {
            'readiness_pack_199': [
                'Market-specific PSP shortlist (8-12 providers)',
                'Pre-filled application templates',
                'SOPs for disputes, refunds, KYC',
                'Quick approval checklist',
                'Email outreach scripts'
            ],
            'quick_fix_97': [
                'One-page PSP shortlist',
                'Essential approval checklist',
                'Quick orientation guide'
            ],
            'loom_review_297': [
                'Upload your materials for review',
                '20-30 min Loom video analysis',
                'Prioritized action items',
                '24-48h turnaround'
            ],
            'kit_builder_499': [
                'Complete interactive workflow',
                'Advanced templates and SOPs',
                'Earned Passport on completion',
                'Email support included'
            ],
            'kit_brazil_499': [
                'PIX MED 2.0 compliance playbook',
                'Brazil-specific dispute SOPs',
                'Earned Passport certification',
                'Portuguese language support'
            ],
            'kit_crypto_499': [
                'Banking compliance workflow',
                'Tokenomics compliance guide',
                'Earned Passport certification',
                'Crypto-specific templates'
            ],
            'kit_cbd_499': [
                'High-risk navigation guide',
                'CBD-specific SOPs',
                'Earned Passport certification',
                'Specialized compliance templates'
            ]
        }
        
        return contents_map.get(package_id, ['Package contents', 'Digital delivery', 'Educational materials'])
    
    async def initiate_purchase(self, callback: CallbackQuery, package_id: str):
        """Initiate Stripe checkout for package."""
        
        user_id = callback.from_user.id
        pkg = self.packages_config['packages'].get(package_id)
        
        if not pkg:
            await callback.answer("❌ Package not found", show_alert=True)
            return
        
        # Check if Stripe is configured
        stripe_price_id = pkg.get('stripe_price_id')
        if not stripe_price_id or stripe_price_id.startswith('price_xxx'):
            await callback.message.edit_text(
                f"💳 **Payment Setup Required**\n\n"
                f"The payment system for **{pkg['name']}** is being configured.\n\n"
                f"**Package Details:**\n"
                f"• Price: ${pkg['price_usd']}\n"
                f"• Type: {pkg.get('tier', 'package').title()}\n"
                f"• Instant delivery after payment\n\n"
                f"Please contact @MerchantGuard_Support to complete your purchase.\n\n"
                f"⚠️ *Educational materials only. No approval guarantees.*",
                parse_mode='Markdown'
            )
            return
        
        # TODO: Integrate with real Stripe checkout
        # For now, simulate the purchase flow
        await callback.message.edit_text(
            f"💳 **Secure Checkout - {pkg['name']}**\n\n"
            f"🔄 Creating Stripe checkout session...\n"
            f"💰 Amount: ${pkg['price_usd']} USD\n"
            f"🔒 256-bit SSL encryption\n"
            f"📱 Instant digital delivery\n"
            f"💯 7-day refund if not accessed\n\n"
            f"**Next Steps:**\n"
            f"1. Complete secure payment via Stripe\n"
            f"2. Receive instant delivery confirmation\n"
            f"3. Access your package immediately\n\n"
            f"⚠️ By purchasing, you agree to our Terms. Educational materials only.",
            parse_mode='Markdown'
        )
        
        # Track purchase intent
        await golden_flow_v5._track_event(user_id, 'purchase_initiated', {
            'package_id': package_id,
            'price': pkg['price_usd'],
            'stripe_price_id': stripe_price_id
        })
        
        # Simulate successful purchase after delay
        await asyncio.sleep(3)
        await self._simulate_successful_purchase(callback.message, user_id, package_id, pkg)
    
    async def _simulate_successful_purchase(self, message: Message, user_id: int, package_id: str, pkg: Dict):
        """Simulate successful purchase and delivery."""
        
        # Generate order ID
        order_id = f"MG-{user_id}-{package_id[:8].upper()}-{int(datetime.utcnow().timestamp())}"
        
        await message.edit_text(
            f"✅ **Purchase Successful!**\n\n"
            f"🎉 **{pkg['name']}** purchased successfully!\n"
            f"💰 Amount: ${pkg['price_usd']} USD\n"
            f"📄 Order ID: `{order_id}`\n\n"
            f"📦 **Instant Delivery:**\n"
            f"Your package is being prepared for delivery...\n\n"
            f"📧 You'll receive your materials within 5 minutes\n"
            f"💬 Support: @MerchantGuard_Support\n\n"
            f"Thank you for choosing MerchantGuard™!",
            parse_mode='Markdown'
        )
        
        # Track successful purchase
        await golden_flow_v5._track_event(user_id, 'purchase_completed', {
            'package_id': package_id,
            'price': pkg['price_usd'],
            'order_id': order_id,
            'delivery_method': 'telegram'
        })
        
        # Simulate package delivery
        await asyncio.sleep(2)
        await self._deliver_package(message, user_id, package_id, order_id)
    
    async def _deliver_package(self, message: Message, user_id: int, package_id: str, order_id: str):
        """Simulate package delivery."""
        
        await message.bot.send_message(
            chat_id=user_id,
            text=f"📦 **Package Delivered!**\n\n"
                 f"Your **{self.packages_config['packages'][package_id]['name']}** is ready!\n\n"
                 f"📄 Order: `{order_id}`\n"
                 f"🗂️ **Package Contents:**\n"
                 + '\n'.join([f"• {item}" for item in self._get_package_contents(package_id)]) + "\n\n"
                 f"📥 **Download your files:**\n"
                 f"[📁 Main Package] (Simulated - Replace with real delivery)\n"
                 f"[📋 Quick Start Guide] (Simulated - Replace with real delivery)\n\n"
                 f"💡 **Next Steps:**\n"
                 f"1. Download and review all materials\n"
                 f"2. Follow the included guides\n"
                 f"3. Contact support if you need help\n\n"
                 f"⭐ **Upgrade Available:**\n"
                 + self._get_upsell_message(package_id),
            parse_mode='Markdown'
        )
        
        # Track delivery
        await golden_flow_v5._track_event(user_id, 'package_delivered', {
            'package_id': package_id,
            'order_id': order_id,
            'delivery_time_seconds': 300  # 5 minutes
        })
    
    def _get_upsell_message(self, package_id: str) -> str:
        """Get appropriate upsell message."""
        
        upsells = self.packages_config.get('upsell', {})
        
        if package_id in upsells:
            suggested = upsells[package_id].get('suggest', [])
            if suggested:
                return f"Consider upgrading to {suggested[0]} for advanced features!"
        
        return "Explore our premium kits for advanced workflows!"

# Global instance
package_selector = PackageSelector()