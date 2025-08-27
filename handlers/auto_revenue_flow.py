"""
Golden Flow v5.0 - Funnel C: $199 Auto Revenue Integration
========================================================

Extends our existing Golden Flow v5.0 with automated revenue funnel:
- Uses same ToS gate and market selection
- Quick 3-question assessment (QA_1-QA_3) 
- Instant scoring with offer logic ($199/$97/$499)
- Automated Stripe checkout + digital delivery
- Maintains ML feature mapping and analytics compatibility

This does NOT replace our comprehensive assessment - it extends it with a fast path.
"""

import asyncio
import json
import os
import yaml
from datetime import datetime
from typing import Dict, List, Optional
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Import our existing Golden Flow v5.0 system
from golden_flow_v5_integration import golden_flow_v5
from ml_training_pipeline import ml_pipeline

class AutoRevenueFlow:
    """$199 Auto Pack funnel integration with Golden Flow v5.0."""
    
    def __init__(self):
        # Load mini questions and offers configuration
        self._load_configs()
        
    def _load_configs(self):
        """Load auto revenue configurations."""
        
        with open('config/questions_mini.yaml', 'r') as f:
            self.mini_questions = yaml.safe_load(f)
            
        with open('config/offers.yaml', 'r') as f:
            self.offers_config = yaml.safe_load(f)
    
    async def check_auto_funnel_eligibility(self, user_id: int, context: str = 'default') -> bool:
        """Check if user should be routed to auto funnel."""
        
        # Auto funnel triggers:
        # 1. URL parameter: ?start=auto199
        # 2. User indicates urgency/time sensitivity  
        # 3. Specific market segments (can be configured)
        
        auto_triggers = [
            context == 'auto199',
            context == 'urgent',
            context == 'quick_check'
        ]
        
        return any(auto_triggers)
    
    async def start_mini_assessment(self, message: Message, user_id: int):
        """Start the 3-question mini assessment."""
        
        await message.answer(
            "🚀 **Fast Track Assessment** (3 minutes)\n\n"
            "Get your compliance readiness score and instant access to:\n"
            "• Industry-specific PSP recommendations\n" 
            "• Pre-filled application templates\n"
            "• Universal SOPs (Dispute, Refund, KYC)\n"
            "• Quick approval strategies\n\n"
            "⏱️ **Quick Questions (3 total)**\n\n"
            "Let's start with your markets..."
        )
        
        # Ask MKT_1 (reuse from Golden Flow v5.0)
        await self.ask_mini_question(message, user_id, 'MKT_1')
    
    async def ask_mini_question(self, message: Message, user_id: int, question_id: str):
        """Ask a mini assessment question."""
        
        # Find question in mini config
        question = None
        for item in self.mini_questions['items']:
            if item['id'] == question_id:
                question = item
                break
        
        if not question:
            await message.answer("❌ Question not found")
            return
            
        # Create keyboard from options
        keyboard_buttons = []
        for option in question['options']:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=option,
                    callback_data=f"mini_{question_id}_{option}"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Question number for progress
        question_numbers = {'MKT_1': '1', 'QA_1': '2', 'QA_2': '3', 'QA_3': '4'}
        q_num = question_numbers.get(question_id, '?')
        
        await message.answer(
            f"📋 **Question {q_num}/4** (Mini Assessment)\n\n"
            f"{question['prompt']['en']}\n\n"
            f"🎯 **ML Feature**: `{question['map_to']}`\n"
            "Choose your answer:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_mini_answer(self, callback: CallbackQuery, question_id: str, answer: str):
        """Handle mini assessment answer and progress flow."""
        
        user_id = callback.from_user.id
        
        # Save answer using Golden Flow v5.0 system (maintains ML compatibility)
        await golden_flow_v5.save_answer(
            user_id=user_id,
            question_id=question_id, 
            value=answer,
            market_scope='mini_assessment'
        )
        
        await callback.message.edit_text(
            f"✅ **Answer Recorded**\n\n"
            f"**Question:** {question_id}\n"
            f"**Answer:** {answer}\n\n"
            "💾 Saved to feature store (ML compatible with Golden Flow v5.0)\n\n"
            "Processing..."
        )
        
        # Determine next question or complete assessment
        await self.progress_mini_flow(callback.message, user_id, question_id)
    
    async def progress_mini_flow(self, message: Message, user_id: int, completed_question: str):
        """Progress through mini assessment flow."""
        
        # Question sequence: MKT_1 -> QA_1 -> QA_2 -> QA_3 -> Results
        flow_sequence = ['MKT_1', 'QA_1', 'QA_2', 'QA_3']
        
        try:
            current_index = flow_sequence.index(completed_question)
            next_index = current_index + 1
            
            if next_index < len(flow_sequence):
                # Ask next question
                next_question_id = flow_sequence[next_index]
                await asyncio.sleep(1)  # Brief pause
                await self.ask_mini_question(message, user_id, next_question_id)
            else:
                # All questions completed - compute score and offer
                await self.compute_mini_score_and_offer(message, user_id)
                
        except ValueError:
            await message.answer("❌ Flow sequence error")
    
    async def compute_mini_score_and_offer(self, message: Message, user_id: int):
        """Compute mini score and present appropriate offer."""
        
        await message.answer(
            "🧮 **Computing your Quick Score...**\n\n"
            "🤖 Analyzing your responses...\n"
            "📊 Applying risk heuristics...\n"
            "💰 Determining best offer...\n\n"
            "One moment..."
        )
        
        await asyncio.sleep(2)
        
        # Get user's answers from database
        import sqlite3
        conn = sqlite3.connect("guardscore_fallback.db")
        cursor = conn.cursor()
        
        try:
            cursor.execute('''SELECT question_id, value FROM answers 
                             WHERE user_id = ? AND market_scope = 'mini_assessment' 
                             ORDER BY created_at''', (user_id,))
            answers = dict(cursor.fetchall())
        except:
            answers = {}
        finally:
            cursor.close()
            conn.close()
        
        # Simple scoring heuristic for mini assessment
        score = self.calculate_mini_score(answers)
        
        # Determine offer based on score and config
        offer_type = self.determine_offer_type(score, answers)
        
        # Present the offer
        await self.present_offer(message, user_id, score, offer_type, answers)
    
    def calculate_mini_score(self, answers: Dict) -> int:
        """Calculate quick score from mini assessment answers."""
        
        score = 50  # Base score
        
        # QA_1: Dispute rate
        dispute_rate = answers.get('QA_1', 'Unknown')
        if '<0.5%' in dispute_rate:
            score += 25
        elif '0.5–1.0%' in dispute_rate:
            score += 10
        elif '>1.5%' in dispute_rate:
            score -= 20
        elif 'Unknown' in dispute_rate:
            score -= 5
        
        # QA_2: SOP level  
        sop_level = answers.get('QA_2', 'None')
        if sop_level == 'Comprehensive':
            score += 20
        elif sop_level == 'Basic':
            score += 5
        elif sop_level == 'None':
            score -= 15
        
        # QA_3: Platform (slight adjustment)
        platform = answers.get('QA_3', 'Custom/Other')
        if platform == 'Shopify':
            score += 5  # Generally more structured
        
        return max(0, min(100, score))
    
    def determine_offer_type(self, score: int, answers: Dict) -> str:
        """Determine offer type based on score and offer config."""
        
        config = self.offers_config['logic']
        
        # Check premium offer first (highest score)
        for condition in config.get('premium_offer_if', []):
            if 'score_gte' in condition and score >= condition['score_gte']:
                return 'premium'
        
        # Check quick fix offer  
        quick_conditions = config.get('quick_fix_if', [])
        if len(quick_conditions) >= 2:
            score_gte = quick_conditions[0].get('score_gte', 0)
            score_lt = quick_conditions[1].get('score_lt', 100)
            if score_gte <= score < score_lt:
                return 'quick_fix'
        
        # Default to auto pack
        return 'auto_pack'
    
    async def present_offer(self, message: Message, user_id: int, score: int, offer_type: str, answers: Dict):
        """Present the appropriate offer with Stripe checkout."""
        
        pricing = self.offers_config['pricing']
        
        # Offer details
        offers = {
            'auto_pack': {
                'title': '🚀 Auto Pack',
                'price': pricing['auto_pack_usd'],
                'description': 'Instant PSP list + templates + SOPs',
                'delivery': 'Immediate digital delivery',
                'recommended': True
            },
            'quick_fix': {
                'title': '⚡ Quick Fix',  
                'price': pricing['quick_fix_usd'],
                'description': 'Essential templates + mini checklist',
                'delivery': 'Digital package in 5 minutes',
                'recommended': False
            },
            'premium': {
                'title': '💎 Premium Setup',
                'price': pricing['premium_usd'], 
                'description': 'Full assessment + custom strategy call',
                'delivery': 'Comprehensive analysis + 30min call',
                'recommended': True
            }
        }
        
        current_offer = offers[offer_type]
        
        # Risk level for display
        if score >= 70:
            risk_emoji = "🟢"
            risk_level = "Low Risk"
        elif score >= 50:
            risk_emoji = "🟡" 
            risk_level = "Medium Risk"
        else:
            risk_emoji = "🔴"
            risk_level = "High Risk"
        
        # Create offer keyboard
        keyboard_buttons = []
        
        # Primary CTA
        cta_text = f"💳 Get {current_offer['title']} - ${current_offer['price']}"
        keyboard_buttons.append([
            InlineKeyboardButton(text=cta_text, callback_data=f"checkout_{offer_type}")
        ])
        
        # Alternative offers (if applicable)
        if offer_type == 'quick_fix':
            keyboard_buttons.append([
                InlineKeyboardButton(text=f"⬆️ Upgrade to Auto Pack - ${offers['auto_pack']['price']}", callback_data="checkout_auto_pack")
            ])
        
        # Additional options
        keyboard_buttons.append([
            InlineKeyboardButton(text="🔍 Full Assessment (Free)", callback_data="switch_to_full_assessment")
        ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="❓ Questions", callback_data="offer_questions")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Get market for context
        market = answers.get('MKT_1', 'GENERAL')
        market_names = {'US_CARDS': 'US Cards', 'BR_PIX': 'Brazil PIX', 'EU_CARDS_SCA': 'EU SCA', 'OTHER': 'Multi-Market'}
        market_display = market_names.get(market, 'General')
        
        await message.answer(
            f"📊 **Your Quick Assessment Results**\n\n"
            f"🎯 **Score: {score}/100** {risk_emoji}\n"
            f"⚠️ **Risk Level:** {risk_level}\n"
            f"🗺️ **Market:** {market_display}\n\n"
            
            f"💡 **Recommended for you:**\n\n"
            f"**{current_offer['title']}** - ${current_offer['price']}\n"
            f"✅ {current_offer['description']}\n"
            f"⚡ {current_offer['delivery']}\n\n"
            
            f"📦 **What you'll get:**\n"
            f"• PSP recommendations for {market_display}\n"
            f"• Pre-filled application templates\n" 
            f"• Universal compliance SOPs\n"
            f"• Quick approval strategies\n"
            f"• Instant digital delivery\n\n"
            
            f"🔒 **Payment via Stripe** (secure, 30-day refund)\n\n"
            f"⚠️ *Educational materials only. No approval guarantees.*",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Track analytics event
        await golden_flow_v5._track_event(user_id, 'offer_presented', {
            'offer_type': offer_type,
            'score': score,
            'price': current_offer['price'],
            'market': market
        })

# Global instance  
auto_revenue_flow = AutoRevenueFlow()