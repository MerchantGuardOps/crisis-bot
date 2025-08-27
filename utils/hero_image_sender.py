# utils/hero_image_sender.py
"""
GuardScore™ Hero Image Integration
Sends branded hero images in bot responses
"""
import logging
from pathlib import Path
from aiogram.types import FSInputFile, Message
from aiogram import Bot
from typing import Optional

logger = logging.getLogger(__name__)

class HeroImageSender:
    """Send GuardScore hero images in bot responses"""
    
    def __init__(self):
        self.images_dir = Path("public")
        self.guardscore_hero = self.images_dir / "guardscore_hero.png"
        self.merchantguard_hero = self.images_dir / "Hero-image-merchantguard.jpg"
    
    async def send_guardscore_hero(self, message: Message, caption: str = None) -> bool:
        """
        Send the GuardScore ecosystem hero image
        Shows the 87/100 score with connected platforms
        """
        try:
            if not self.guardscore_hero.exists():
                logger.error(f"GuardScore hero image not found: {self.guardscore_hero}")
                return False
            
            photo = FSInputFile(self.guardscore_hero)
            
            default_caption = (
                "🛡️ **GuardScore™ Ecosystem**\n\n"
                "Your comprehensive payment compliance score connecting:\n"
                "• Stripe, PayPal, Shopify platforms\n"
                "• Predictive AI alerts\n" 
                "• Chargeback prevention\n"
                "• Real-time risk monitoring\n\n"
                "_Start your assessment with /start_"
            )
            
            await message.answer_photo(
                photo=photo,
                caption=caption or default_caption,
                parse_mode="Markdown"
            )
            
            logger.info("✅ Sent GuardScore hero image")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send GuardScore hero: {e}")
            return False
    
    async def send_merchantguard_hero(self, message: Message, caption: str = None) -> bool:
        """
        Send the MerchantGuard shield hero image
        Shows the AI shield with $MGRD token
        """
        try:
            if not self.merchantguard_hero.exists():
                logger.error(f"MerchantGuard hero image not found: {self.merchantguard_hero}")
                return False
            
            photo = FSInputFile(self.merchantguard_hero)
            
            default_caption = (
                "🛡️ **MerchantGuard™ AI Shield**\n\n"
                "Advanced payment risk protection powered by:\n"
                "• AI-driven threat detection\n"
                "• Blockchain reputation scoring\n" 
                "• $MGRD token rewards\n"
                "• Enterprise-grade security\n\n"
                "_Secure your payments with /start_"
            )
            
            await message.answer_photo(
                photo=photo,
                caption=caption or default_caption,
                parse_mode="Markdown"
            )
            
            logger.info("✅ Sent MerchantGuard hero image")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send MerchantGuard hero: {e}")
            return False
    
    async def send_passport_visual(self, message: Message, score: int, status: str) -> bool:
        """
        Send GuardScore hero with personalized passport info
        """
        
        # Choose image based on score
        if score >= 70:
            image_path = self.guardscore_hero
            status_emoji = "✅"
        else:
            image_path = self.merchantguard_hero
            status_emoji = "⚠️"
        
        try:
            photo = FSInputFile(image_path)
            
            caption = (
                f"🛡️ **Your GuardScore™ Passport**\n\n"
                f"**Score**: {score}/100 {status_emoji}\n"
                f"**Status**: {status}\n"
                f"**Market Coverage**: Multi-region compliance\n\n"
                f"_Your AI-powered payment risk profile_"
            )
            
            await message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Sent passport visual for score {score}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send passport visual: {e}")
            return False

# Global instance
hero_sender = HeroImageSender()

# Convenience functions for bot handlers
async def send_guardscore_hero(message: Message, caption: str = None) -> bool:
    """Send GuardScore ecosystem hero image"""
    return await hero_sender.send_guardscore_hero(message, caption)

async def send_merchantguard_hero(message: Message, caption: str = None) -> bool:
    """Send MerchantGuard AI shield hero image"""
    return await hero_sender.send_merchantguard_hero(message, caption)

async def send_passport_visual(message: Message, score: int, status: str) -> bool:
    """Send personalized passport visual"""
    return await hero_sender.send_passport_visual(message, score, status)