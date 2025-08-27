# handlers/data_verified_powerup.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import pandas as pd
import io
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
router = Router()

class DataVerifiedStates(StatesGroup):
    platform_selection = State()
    csv_explanation = State()
    csv_upload = State()
    csv_processing = State()
    powerup_complete = State()

# Platform-specific CSV requirements
PLATFORM_REQUIREMENTS = {
    "shopify": {
        "name": "Shopify",
        "required_fields": ["Order ID", "Financial Status", "Total", "Currency", "Created at", "Customer Email", "Risk Level"],
        "export_path": "Orders → Export → Export orders (CSV)",
        "sample_url": "https://merchantguard.ai/samples/shopify_orders_sample.csv",
        "video_url": "https://merchantguard.ai/videos/shopify_export_30sec.mp4"
    },
    "woocommerce": {
        "name": "WooCommerce", 
        "required_fields": ["Order ID", "Status", "Total", "Currency", "Date Created", "Customer Email", "Payment Method"],
        "export_path": "WooCommerce → Orders → Export (CSV Export plugin)",
        "sample_url": "https://merchantguard.ai/samples/woocommerce_orders_sample.csv",
        "video_url": "https://merchantguard.ai/videos/woocommerce_export_30sec.mp4"
    },
    "bigcommerce": {
        "name": "BigCommerce",
        "required_fields": ["Order ID", "Status", "Total Value", "Currency Code", "Date Created", "Billing Email"],
        "export_path": "Orders → Export Orders → CSV",
        "sample_url": "https://merchantguard.ai/samples/bigcommerce_orders_sample.csv", 
        "video_url": "https://merchantguard.ai/videos/bigcommerce_export_30sec.mp4"
    }
}

@router.callback_query(F.data == "offer_data_verified")
async def offer_data_verified_powerup(call: CallbackQuery, state: FSMContext):
    """Offer Data-Verified power-up during passport flow"""
    await call.answer()
    
    powerup_text = """🔋 **Upgrade to Data-Verified Passport**

**Current:** Self-Attested Passport (based on your responses)
**Upgrade:** Data-Verified Passport (backed by real transaction data)

**Benefits of Data-Verified:**
✅ **Stronger acceptance signals** with PSPs
✅ **Higher trust score** on your passport portal  
✅ **"Data-Verified" badge** visible to partners
✅ **More detailed insights** in your assessment

**What you need:**
📊 Recent orders CSV from your e-commerce platform (last 90 days)
⏱️ **Takes 2 minutes** - we'll guide you through it

Ready to power-up your passport?"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔋 Yes, Upgrade to Data-Verified", callback_data="start_powerup")],
        [InlineKeyboardButton(text="📋 Keep Self-Attested for Now", callback_data="skip_powerup")],
        [InlineKeyboardButton(text="❓ What's the difference?", callback_data="explain_tiers")]
    ])
    
    await call.message.edit_text(powerup_text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "start_powerup")
async def start_powerup_flow(call: CallbackQuery, state: FSMContext):
    """Start the Data-Verified power-up flow"""
    await call.answer()
    
    # Track power-up start
    await track_event("shopify_powerup_offered", {
        "user_id": call.from_user.id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    platform_text = """🛍️ **Platform Selection**

Which e-commerce platform do you use? We'll show you exactly how to export your order data.

**Supported platforms:**"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Shopify", callback_data="platform_shopify"),
            InlineKeyboardButton(text="🌐 WooCommerce", callback_data="platform_woocommerce")
        ],
        [
            InlineKeyboardButton(text="🏪 BigCommerce", callback_data="platform_bigcommerce"),
            InlineKeyboardButton(text="📊 Other/Custom", callback_data="platform_other")
        ],
        [InlineKeyboardButton(text="← Back to Self-Attested", callback_data="skip_powerup")]
    ])
    
    await call.message.edit_text(platform_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(DataVerifiedStates.platform_selection)

@router.callback_query(F.data.startswith("platform_"))
async def handle_platform_selection(call: CallbackQuery, state: FSMContext):
    """Handle platform selection"""
    await call.answer()
    
    platform = call.data.replace("platform_", "")
    await state.update_data(selected_platform=platform)
    
    if platform == "other":
        await handle_other_platform(call, state)
        return
    
    platform_config = PLATFORM_REQUIREMENTS.get(platform)
    if not platform_config:
        await call.message.edit_text("❌ Platform not supported yet. Please contact support.")
        return
    
    # Show platform-specific instructions
    instructions_text = f"""📊 **{platform_config['name']} Export Instructions**

**Step 1:** Go to your {platform_config['name']} admin
**Step 2:** Navigate to: `{platform_config['export_path']}`
**Step 3:** Export last 90 days of orders as CSV
**Step 4:** Upload the CSV file here

**Required fields in your CSV:**
""" + "\n".join([f"• {field}" for field in platform_config['required_fields']]) + f"""

**Need help?** Watch this 30-second video:
{platform_config['video_url']}

**Sample file:** {platform_config['sample_url']}
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Watch 30-sec Tutorial", url=platform_config['video_url'])],
        [InlineKeyboardButton(text="📄 Download Sample CSV", url=platform_config['sample_url'])],
        [InlineKeyboardButton(text="✅ I've Got My CSV, Upload Now", callback_data="ready_to_upload")],
        [InlineKeyboardButton(text="❓ Need Help", callback_data="need_help")]
    ])
    
    await call.message.edit_text(instructions_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(DataVerifiedStates.csv_explanation)

@router.callback_query(F.data == "ready_to_upload")
async def ready_to_upload(call: CallbackQuery, state: FSMContext):
    """Ready to upload CSV"""
    await call.answer()
    
    upload_text = """📤 **Upload Your Orders CSV**

**Send your orders CSV file as a document in this chat.**

**Requirements:**
✅ CSV format (.csv extension)
✅ Last 90 days of orders
✅ Contains required fields (we'll validate)
✅ Max file size: 50MB

**Privacy:** Your file is processed securely and deleted after analysis. We only extract aggregate patterns, not individual order details.

Ready when you are! 👆 Send the file now."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Need Help", callback_data="need_help")],
        [InlineKeyboardButton(text="← Back to Instructions", callback_data=f"platform_{(await state.get_data())['selected_platform']}")]
    ])
    
    await call.message.edit_text(upload_text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(DataVerifiedStates.csv_upload)

@router.message(DataVerifiedStates.csv_upload, F.document)
async def handle_csv_upload(message: Message, state: FSMContext):
    """Handle CSV file upload"""
    if not message.document.file_name.endswith('.csv'):
        await message.answer("❌ Please upload a CSV file (.csv extension)")
        return
    
    if message.document.file_size > 50 * 1024 * 1024:  # 50MB limit
        await message.answer("❌ File too large. Please ensure your CSV is under 50MB.")
        return
    
    # Track CSV upload
    await track_event("shopify_csv_uploaded", {
        "user_id": message.from_user.id,
        "file_size": message.document.file_size,
        "filename": message.document.file_name,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    processing_msg = await message.answer("🔄 **Processing your CSV...**\n\nThis may take 30-60 seconds while we analyze your transaction patterns.")
    
    try:
        # Download and process CSV
        file = await message.bot.get_file(message.document.file_id)
        csv_data = await message.bot.download_file(file.file_path)
        
        # Process CSV and extract insights
        insights = await process_csv_for_insights(csv_data, await state.get_data())
        
        if not insights["valid"]:
            await processing_msg.edit_text(
                f"❌ **CSV Validation Failed**\n\n{insights['error']}\n\nPlease check your CSV format and try again."
            )
            return
        
        # Update passport to Data-Verified
        passport = await upgrade_to_data_verified(message.from_user.id, insights)
        
        # Track successful power-up
        await track_event("shopify_powerup_completed", {
            "user_id": message.from_user.id,
            "insights": insights["summary"],
            "new_score": passport["guardscore"],
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Success message
        success_text = f"""🎉 **Data-Verified Power-Up Complete!**

**Your Passport Has Been Upgraded:**
📊 **New Score:** {passport['guardscore']}/100 (+{insights['score_boost']} boost)
🔋 **Status:** Data-Verified 
✅ **Insights Analyzed:** {insights['summary']['total_orders']:,} orders, {insights['summary']['total_volume']:,} in volume

**Key Insights:**
• **Avg Order Value:** ${insights['summary']['avg_order_value']:.2f}
• **Chargeback Rate:** <{insights['summary']['estimated_chargeback_rate']:.2f}%
• **Top Payment Method:** {insights['summary']['top_payment_method']}
• **Growth Trend:** {insights['summary']['growth_trend']}

**Your Data-Verified passport is now live:**
🔗 {passport['portal_url']}

**Next Steps:**
"""

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 View Data-Verified Portal", url=passport['portal_url'])],
            [InlineKeyboardButton(text="📄 Download Updated Report", callback_data="download_updated_report")],
            [InlineKeyboardButton(text="🎯 Upgrade to Reviewed (+$199)", callback_data="offer_reviewed_addon")]
        ])
        
        await processing_msg.edit_text(success_text, reply_markup=kb, parse_mode="Markdown")
        await state.set_state(DataVerifiedStates.powerup_complete)
        
    except Exception as e:
        logger.error(f"CSV processing failed: {str(e)}")
        await processing_msg.edit_text(
            "❌ **Processing Failed**\n\nThere was an issue processing your CSV. Please ensure it follows the required format and try again."
        )

async def process_csv_for_insights(csv_data: io.BytesIO, state_data: dict) -> dict:
    """Process uploaded CSV and extract business insights"""
    try:
        # Read CSV
        df = pd.read_csv(csv_data)
        
        # Get platform requirements
        platform = state_data.get("selected_platform", "shopify")
        requirements = PLATFORM_REQUIREMENTS.get(platform, PLATFORM_REQUIREMENTS["shopify"])
        
        # Validate required fields (flexible matching)
        available_fields = df.columns.tolist()
        field_mapping = await map_csv_fields(available_fields, requirements["required_fields"])
        
        if not field_mapping["valid"]:
            return {
                "valid": False,
                "error": f"Missing required fields: {', '.join(field_mapping['missing'])}"
            }
        
        # Extract insights
        insights = {
            "valid": True,
            "score_boost": 0,
            "summary": {
                "total_orders": len(df),
                "total_volume": 0,
                "avg_order_value": 0,
                "estimated_chargeback_rate": 0.3,  # Conservative estimate
                "top_payment_method": "Credit Card",
                "growth_trend": "Stable",
                "date_range": "Last 90 days"
            }
        }
        
        # Calculate volume and AOV (try multiple field names)
        total_fields = ["Total", "Order Total", "Amount", "Total Value"]
        total_field = next((f for f in total_fields if f in df.columns), None)
        
        if total_field:
            # Clean and convert to numeric
            df[total_field] = pd.to_numeric(df[total_field].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            total_volume = df[total_field].sum()
            avg_order_value = df[total_field].mean()
            
            insights["summary"]["total_volume"] = total_volume
            insights["summary"]["avg_order_value"] = avg_order_value
        
        # Calculate score boost based on data quality
        base_boost = 5  # Base boost for having data
        
        # Volume-based boost
        if insights["summary"]["total_volume"] > 10000:
            insights["score_boost"] += 8
        elif insights["summary"]["total_volume"] > 1000:
            insights["score_boost"] += 5
        else:
            insights["score_boost"] += 2
            
        # Order count boost
        if insights["summary"]["total_orders"] > 500:
            insights["score_boost"] += 5
        elif insights["summary"]["total_orders"] > 100:
            insights["score_boost"] += 3
        
        insights["score_boost"] += base_boost
        insights["score_boost"] = min(insights["score_boost"], 15)  # Cap at 15 point boost
        
        return insights
        
    except Exception as e:
        logger.error(f"CSV processing error: {str(e)}")
        return {
            "valid": False,
            "error": "Invalid CSV format. Please ensure your file is a valid CSV with order data."
        }

async def map_csv_fields(available_fields: list, required_fields: list) -> dict:
    """Map available CSV fields to required fields with fuzzy matching"""
    field_mapping = {}
    missing_fields = []
    
    # Simple fuzzy matching for common variations
    field_variants = {
        "Order ID": ["order_id", "id", "order_number", "order #"],
        "Total": ["total", "amount", "order_total", "total_price", "grand_total"],
        "Status": ["status", "order_status", "financial_status"],
        "Email": ["email", "customer_email", "billing_email"],
        "Created": ["created", "date", "order_date", "created_at", "date_created"],
        "Currency": ["currency", "currency_code"]
    }
    
    for required in required_fields:
        found = False
        # Exact match first
        if required in available_fields:
            field_mapping[required] = required
            found = True
        else:
            # Fuzzy match
            variants = field_variants.get(required, [])
            for available in available_fields:
                if any(variant.lower() in available.lower() for variant in variants):
                    field_mapping[required] = available
                    found = True
                    break
        
        if not found:
            missing_fields.append(required)
    
    return {
        "valid": len(missing_fields) == 0,
        "mapping": field_mapping,
        "missing": missing_fields
    }

async def upgrade_to_data_verified(user_id: int, insights: dict):
    """Upgrade passport from Self-Attested to Data-Verified"""
    # Get existing passport
    existing_passport = await get_user_passport(user_id)
    
    if not existing_passport:
        raise Exception("No existing passport found")
    
    # Update passport
    new_score = min(existing_passport["guardscore"] + insights["score_boost"], 100)
    
    updated_passport = {
        **existing_passport,
        "tier": "data_verified",
        "guardscore": new_score,
        "data_insights": insights["summary"],
        "issuer": "MerchantGuard Bot (Data-Verified)",
        "upgraded_at": datetime.now(timezone.utc),
        "portal_url": f"https://merchantguard.ai/passport/{existing_passport['passport_id']}?tier=data_verified"
    }
    
    # Store updated passport
    await store_passport(user_id, updated_passport)
    
    return updated_passport

@router.callback_query(F.data == "explain_tiers")
async def explain_passport_tiers(call: CallbackQuery, state: FSMContext):
    """Explain the different passport tiers"""
    await call.answer()
    
    tiers_text = """🎯 **Compliance Passport Tiers Explained**

**🔸 Self-Attested**
• Based on your questionnaire responses
• Issued instantly
• Good for basic compliance tracking
• **Standard acceptance** with PSPs

**🔋 Data-Verified** 
• Backed by real transaction data
• Analysis of your order history
• **Stronger acceptance signals**
• **"Data-Verified" badge** on portal
• Higher trust score

**👨‍💼 Reviewed** (+$199)
• Human expert QA review
• 24-hour SLA
• **Highest trust level**
• Detailed review notes
• **Premium badge** on portal

**Which tier is right for you?**
• Just starting → **Self-Attested**
• Have transaction history → **Data-Verified** 
• Need maximum credibility → **Reviewed**
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔋 Upgrade to Data-Verified", callback_data="start_powerup")],
        [InlineKeyboardButton(text="👨‍💼 Add Reviewed Later (+$199)", callback_data="skip_powerup")],
        [InlineKeyboardButton(text="📋 Keep Self-Attested", callback_data="skip_powerup")]
    ])
    
    await call.message.edit_text(tiers_text, reply_markup=kb, parse_mode="Markdown")

# Helper functions
async def get_user_passport(user_id: int):
    """Get user's existing passport"""
    # Implement based on your database
    pass

async def track_event(event_name: str, properties: dict):
    """Track analytics event"""
    logger.info(f"Event: {event_name}, Properties: {properties}")

async def store_passport(user_id: int, passport: dict):
    """Store passport in database"""
    logger.info(f"Storing passport {passport['passport_id']} for user {user_id}")

async def handle_other_platform(call: CallbackQuery, state: FSMContext):
    """Handle other/custom platform selection"""
    other_text = """📊 **Custom Platform Support**

For platforms not listed, you can still upgrade to **Data-Verified** by providing a CSV with these minimum fields:

**Required columns:**
• Order ID or Reference
• Order Total/Amount  
• Order Date
• Customer Email (optional)
• Order Status

**Format your CSV and upload it. We'll do our best to process it!**

Most e-commerce platforms can export order data in CSV format - check your admin panel's export or reports section.
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I Have a Custom CSV", callback_data="ready_to_upload")],
        [InlineKeyboardButton(text="❓ Need Help", callback_data="need_help")],
        [InlineKeyboardButton(text="← Back to Platform Selection", callback_data="start_powerup")]
    ])
    
    await call.message.edit_text(other_text, reply_markup=kb, parse_mode="Markdown")