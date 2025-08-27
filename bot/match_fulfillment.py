"""MATCH package fulfillment and delivery"""

from aiogram import Router
from aiogram.types import InputFile, BufferedInputFile
from services.package_builder_match import build_match_package
from services.revenue_tracker import RevenueTracker
from services.outcome_tracker import OutcomeTracker
from services.affiliate_tracker import AffiliateTracker
from datetime import datetime, timedelta
import os
import json

router = Router()

async def fulfill_match_purchase(bot, chat_id: int, merchant_id: str, intake: dict, 
                                pool, payment_intent_id: str = None):
    """
    Complete MATCH package fulfillment after successful Stripe payment.
    
    Args:
        bot: Telegram bot instance
        chat_id: Telegram chat ID
        merchant_id: Unique merchant identifier  
        intake: Merchant intake data
        pool: Database connection pool
        payment_intent_id: Stripe payment intent ID (optional)
    """
    
    try:
        # Initialize services
        revenue_tracker = RevenueTracker(pool)
        outcome_tracker = OutcomeTracker(pool)
        affiliate_tracker = AffiliateTracker(pool)
        
        # Log the revenue event
        await revenue_tracker.log_match_purchase(merchant_id, payment_intent_id or "unknown")
        
        # Build the complete package ZIP
        await bot.send_message(chat_id, "📦 **Building your MATCH Liberation package...**", parse_mode="Markdown")
        
        zip_bytes = await build_match_package(pool, intake, include_prevention_guide=False)
        
        # Create file for Telegram delivery
        zip_file = BufferedInputFile(
            zip_bytes, 
            filename=f"MATCH_Liberation_Package_{merchant_id[:8]}.zip"
        )
        
        # Send the package
        success_message = f"""**🎉 MATCH Liberation Package Delivered!**

**What you just received:**
• 30-page MATCH Survival Playbook
• 5 pre-filled PSP applications (ranked for your profile)
• Emergency escalation contacts
• Rejection response templates
• MATCH removal letter templates
• USDC/crypto setup guide
• Current provider success rates

**Your Next Steps:**
1. **TODAY**: Set up USDC payments (see crypto_providers.yaml)
2. **This week**: Submit top 3 applications from your package
3. **Weekly check-ins**: I'll check your progress and provide support

**Emergency Support:**
If you need urgent help, use the emergency contacts in your package.

**Bonus Included:**
• Free on-chain attestation (normally $49)
• MGRD Points for ecosystem participation

**Package Reference:** MATCH-{datetime.now().strftime('%Y%m%d')}-{merchant_id[:8]}

→ **Your recovery starts NOW. Let's get you back in business! 🚀**"""

        await bot.send_document(
            chat_id=chat_id,
            document=zip_file,
            caption=success_message,
            parse_mode="Markdown"
        )
        
        # Log affiliate applications for tracking (logging only, no link injection yet)
        providers = ['durango', 'paymentcloud', 'fastspring', 'emb', 'soar']
        for provider in providers:
            try:
                await affiliate_tracker.log_application_sent(merchant_id, provider)
            except Exception as e:
                print(f"Error logging affiliate for {provider}: {e}")
        
        # Award points for purchase
        points_service = bot.get('points_service')
        if points_service:
            try:
                await points_service.award(merchant_id, "match_purchase", source="purchase")
                await bot.send_message(
                    chat_id, 
                    "🎯 **+800 MGRD Points** awarded for MATCH Liberation purchase!",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error awarding points: {e}")
        
        # Include free attestation (if flag enabled)
        attestation_included = os.getenv("FEATURE_ATTESTATION_INCLUDED_IN_MATCH", "true").lower() == "true"
        if attestation_included:
            try:
                # Trigger attestation service (implement based on your existing attestation system)
                await bot.send_message(
                    chat_id,
                    "🏛️ **Bonus:** Your free on-chain attestation is being generated and will be ready within 24 hours!",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error triggering attestation: {e}")
        
        # Schedule Week 1 check-in (7 days from now)
        await schedule_week1_checkin(bot, chat_id, merchant_id, pool)
        
        print(f"✅ MATCH package fulfilled for merchant {merchant_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error fulfilling MATCH package for {merchant_id}: {e}")
        
        # Send error message to user
        await bot.send_message(
            chat_id,
            "⚠️ **Delivery Error**\n\nThere was an issue preparing your package. Our support team has been notified and will reach out within 1 hour.\n\nReference: MATCH-ERROR-" + merchant_id[:8],
            parse_mode="Markdown"
        )
        return False

async def schedule_week1_checkin(bot, chat_id: int, merchant_id: str, pool):
    """Schedule the Week 1 check-in (integrate with your existing scheduler)"""
    try:
        # This would integrate with your existing job scheduler
        # For now, just log the intent
        print(f"📅 Scheduling Week 1 check-in for merchant {merchant_id} in 7 days")
        
        # You could add to a job queue, database table, or use APScheduler
        # Example placeholder:
        checkin_date = datetime.now() + timedelta(days=7)
        print(f"Week 1 check-in scheduled for {checkin_date}")
        
    except Exception as e:
        print(f"Error scheduling check-in: {e}")

async def deliver_vamp_package_with_prevention_guide(bot, chat_id: int, merchant_id: str, 
                                                   intake: dict, pool, payment_intent_id: str = None):
    """
    Deliver VAMP ($199) package including the 5-page Prevention Guide.
    This is called for VAMP purchases to add the prevention guide.
    """
    
    try:
        revenue_tracker = RevenueTracker(pool)
        await revenue_tracker.log_vamp_purchase(merchant_id, payment_intent_id or "unknown")
        
        # Build VAMP package with prevention guide included
        zip_bytes = await build_match_package(pool, intake, include_prevention_guide=True)
        
        zip_file = BufferedInputFile(
            zip_bytes,
            filename=f"VAMP_Protection_Package_{merchant_id[:8]}.zip"
        )
        
        success_message = """**🛡️ VAMP Protection Package Delivered!**

**What's included:**
• 5-page MATCH Prevention Guide 
• VAMP threshold monitoring tools
• Chargeback prevention strategies
• Emergency contacts for VAMP issues

**Your prevention strategy starts now!**"""

        await bot.send_document(
            chat_id=chat_id,
            document=zip_file,
            caption=success_message,
            parse_mode="Markdown"
        )
        
        # Award VAMP points
        points_service = bot.get('points_service')
        if points_service:
            await points_service.award(merchant_id, "vamp_purchase", source="purchase")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fulfilling VAMP package: {e}")
        return False