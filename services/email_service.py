# services/email_service.py - Email Delivery Service
"""
Email service for package delivery and notifications
Supports instant digital delivery and purchase confirmations
"""

import os
import logging
from typing import Dict, List, Optional
import aiohttp
import json
from datetime import datetime
from database.pool import get_db_connection

logger = logging.getLogger(__name__)

class EmailService:
    """Email service for package delivery and notifications"""
    
    def __init__(self):
        self.postmark_token = os.getenv('POSTMARK_TOKEN')
        self.from_email = "noreply@merchantguard.ai" 
        self.postmark_url = "https://api.postmarkapp.com/email"
    
    async def _was_email_already_sent(self, email_address: str, email_type: str, reference_id: str) -> bool:
        """Check if email was already sent to prevent duplicates"""
        try:
            async with get_db_connection() as conn:
                result = await conn.fetchrow("""
                    SELECT id FROM email_deliveries 
                    WHERE email_address = $1 AND email_type = $2 AND reference_id = $3
                """, email_address, email_type, reference_id)
                return result is not None
        except Exception as e:
            logger.error(f"Error checking email delivery status: {e}")
            return False
    
    async def _record_email_sent(self, user_id: str, email_address: str, email_type: str, 
                                reference_id: str, subject: str, provider_message_id: str = None):
        """Record successful email delivery"""
        try:
            async with get_db_connection() as conn:
                await conn.execute("""
                    INSERT INTO email_deliveries 
                    (user_id, email_address, email_type, reference_id, subject_line, provider_message_id, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (email_address, email_type, reference_id) DO NOTHING
                """, 
                    int(user_id) if user_id else None,
                    email_address,
                    email_type,
                    reference_id,
                    subject,
                    provider_message_id,
                    json.dumps({"sent_at": datetime.utcnow().isoformat()})
                )
        except Exception as e:
            logger.error(f"Error recording email delivery: {e}")
    
    async def _send_email_with_idempotency(self, user_id: str, to_email: str, subject: str, 
                                          content: str, email_type: str, reference_id: str) -> bool:
        """Send email with idempotency protection"""
        
        # Check if email was already sent
        if await self._was_email_already_sent(to_email, email_type, reference_id):
            logger.info(f"Email {email_type} already sent to {to_email} for {reference_id}, skipping")
            return True
        
        # Send the email
        result = await self._send_email(to_email, subject, content)
        
        # Record successful delivery
        if result:
            await self._record_email_sent(user_id, to_email, email_type, reference_id, subject)
        
        return result
    
    async def _send_email(self, to_email: str, subject: str, content: str) -> bool:
        """Send email via Postmark API"""
        
        if not self.postmark_token:
            logger.warning("POSTMARK_TOKEN not configured - email not sent")
            return False
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": self.postmark_token
        }
        
        email_data = {
            "From": self.from_email,
            "To": to_email,
            "Subject": subject,
            "TextBody": content,
            "MessageStream": "outbound"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.postmark_url,
                    headers=headers,
                    json=email_data
                ) as response:
                    if response.status == 200:
                        logger.info(f"Email sent successfully to {to_email}")
                        return True
                    else:
                        logger.error(f"Failed to send email: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
    
    async def send_digital_package_delivery(self, recipient_email: str, package: dict, content_files: dict, user_id: str):
        """Send digital package content delivery email"""
        
        subject = f"🚀 Your {package['name']} is Ready - Instant Access"
        
        # Build content sections
        content_sections = []
        for filename, content in content_files.items():
            content_sections.append(f"""
## 📄 {filename.replace('_', ' ').replace('.txt', '').title()}

{content}

---
""")
        
        email_content = f"""
# 🎉 Package Delivered Successfully!

Thank you for your purchase! Your **{package['name']}** (${package['price']}) is ready for immediate use.

{''.join(content_sections)}

## 📞 Support & Questions

- **Email:** support@merchantguard.ai
- **Response Time:** Within 24 hours
- **Order ID:** MG-{user_id}-{package['id'][:8].upper()}

## ⚖️ Important Notes

This package contains educational materials and is not financial, legal, or investment advice. 
Results may vary based on your specific situation and implementation.

---

**MerchantGuard™** - Your Payment Compliance Partner  
https://merchantguard.ai
        """
        
        return await self._send_email_with_idempotency(
            user_id, recipient_email, subject, email_content, 
            "package_delivery", package['id']
        )
    
    async def send_service_package_instructions(self, recipient_email: str, package: dict, user_id: str):
        """Send service package delivery instructions"""
        
        subject = f"📋 {package['name']} - Next Steps & Instructions"
        
        email_content = f"""
# 🩺 Your {package['name']} is Confirmed!

Thank you for your purchase! We've received your payment and will begin your review process.

## 📋 What Happens Next

**Within 24-48 Hours:**
1. Our compliance expert will review your materials
2. Create a personalized 20-30 minute Loom video
3. Deliver actionable recommendations via email
4. Provide prioritized fixes and implementation guidance

## 📤 How to Submit Your Materials

Reply to this email with:
- Current PSP application (if available)
- Website URL and key pages
- Business registration documents
- Any specific compliance questions
- Previous rejection notices (if applicable)

## 📞 Questions or Urgent Needs

- **Email:** support@merchantguard.ai
- **Order ID:** MG-{user_id}-{package['id'][:8].upper()}
- **Expected Delivery:** 24-48 hours from material submission

---

**MerchantGuard™** - Your Payment Compliance Partner  
https://merchantguard.ai
        """
        
        return await self._send_email(recipient_email, subject, email_content)
    
    async def send_premium_kit_welcome(self, recipient_email: str, package: dict, user_id: str):
        """Send premium kit welcome and bot continuation instructions"""
        
        subject = f"🎯 {package['name']} - Continue Your Interactive Workflow"
        
        email_content = f"""
# 🚀 Welcome to Your {package['name']}!

Thank you for your investment in compliance excellence! Your interactive workflow is now ready.

## 🎯 Continue in the Bot

Your personalized workflow continues in the MerchantGuard bot:

👉 **Return to bot:** https://t.me/guardscorebot

**What to do:**
1. Type /continue in the bot
2. Follow your personalized assessment workflow
3. Complete all modules to earn your **Earned Compliance Passport**

## 🎁 What You Get

- **Interactive Workflow:** Step-by-step personalized guidance
- **Expert Templates:** Industry-specific compliance materials
- **Earned Passport:** Higher credibility credential after completion
- **Priority Support:** Direct access to our compliance team
- **Kit Resources:** Comprehensive toolkit access

## 📞 Support & Questions

- **Email:** support@merchantguard.ai
- **Bot Support:** Type /help in the bot
- **Order ID:** MG-{user_id}-{package['id'][:8].upper()}

## 🔒 Your Investment Protection

30-day money-back guarantee. If you're not completely satisfied with your kit, 
contact support for a full refund within 30 days.

---

**Ready to become compliance-ready?** Continue in the bot to start your workflow!

**MerchantGuard™** - Your Payment Compliance Partner  
https://merchantguard.ai
        """
        
        return await self._send_email(recipient_email, subject, email_content)
    
    async def send_course_email(self, to_email: str, subject: str, content: str, day: int) -> bool:
        """Send course email with special formatting"""
        try:
            # Convert text content to HTML for better email rendering
            html_content = content.replace('\n\n', '</p><p>').replace('\n', '<br>')
            html_content = f"<p>{html_content}</p>"
            
            # Basic markdown-like formatting
            html_content = html_content.replace('**', '<strong>').replace('**', '</strong>')
            html_content = html_content.replace('*', '<em>').replace('*', '</em>')
            
            # Create email data for Postmark
            email_data = {
                "From": self.from_email,
                "To": to_email,
                "Subject": subject,
                "HtmlBody": html_content,
                "TextBody": content,
                "MessageStream": "outbound",
                "Tag": "quick-hit-course"
            }
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": self.postmark_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.postmark_url,
                    headers=headers,
                    json=email_data
                ) as response:
                    if response.status == 200:
                        logger.info(f"Course email day {day} sent to {to_email}")
                        return True
                    else:
                        logger.error(f"Failed to send course email: {response.status}")
                        return False
            
        except Exception as e:
            logger.error(f"Error sending course email: {e}")
            return False
    
    async def start_course_sequence(self, email: str, course_key: str):
        """Start email course sequence for a user"""
        try:
            from services.email_course_sender import course_sender
            await course_sender.start_course_sequence(email, course_key)
            
        except Exception as e:
            logger.error(f"Error starting course sequence: {e}")
    
    async def send_purchase_confirmation(self, recipient_email: str, confirmation_data: dict):
        """Send purchase confirmation receipt"""
        
        subject = f"✅ Payment Confirmed - Order {confirmation_data['order_id']}"
        
        email_content = f"""
# ✅ Payment Confirmation

Thank you for your purchase! Your order has been confirmed and processed.

## 📋 Order Details

- **Package:** {confirmation_data['package_name']}
- **Price:** ${confirmation_data['price']}
- **Order ID:** {confirmation_data['order_id']}
- **Purchase Date:** {confirmation_data['purchase_date']}
- **Delivery:** {confirmation_data['delivery_info']}

## 📧 What's Next

- **Digital Products:** Content delivered immediately to this email
- **Service Products:** Instructions sent separately, delivery within timeframe
- **Premium Kits:** Continue workflow in the MerchantGuard bot

## 💳 Payment Information

- **Session ID:** {confirmation_data['session_id']}
- **Billing Email:** {confirmation_data['customer_email']}
- **Payment Processor:** Stripe (secure payment processing)

## 📞 Support

Questions about your order? Contact support@merchantguard.ai with your Order ID.

## 🔒 Refund Policy

- **Digital Products:** 7-day money-back guarantee
- **Service Products:** Satisfaction guaranteed
- **Premium Kits:** 30-day money-back guarantee

---

**MerchantGuard™** - Your Payment Compliance Partner  
https://merchantguard.ai
        """
        
        return await self._send_email(recipient_email, subject, email_content)