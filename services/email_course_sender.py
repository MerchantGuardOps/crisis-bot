# services/email_course_sender.py
"""
Email Course Automation System
Sends daily email course lessons based on user enrollment
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from services.email_service import EmailService

logger = logging.getLogger(__name__)

class EmailCourseSender:
    """Manages automated email course delivery"""
    
    def __init__(self):
        self.email_service = EmailService()
        self.courses_dir = Path("emails")
        self.active_courses = {}  # In production: use database
        
    async def start_course_sequence(self, email: str, course_key: str, start_date: Optional[datetime] = None):
        """Start an email course for a user"""
        try:
            if start_date is None:
                start_date = datetime.utcnow()
                
            # Store course enrollment (in production: save to database)
            self.active_courses[f"{email}_{course_key}"] = {
                'email': email,
                'course_key': course_key,
                'start_date': start_date,
                'current_day': 1,
                'status': 'active'
            }
            
            logger.info(f"Started course '{course_key}' for {email}")
            
            # Send day 1 immediately (with 5-minute delay as mentioned in webhook)
            await asyncio.sleep(300)  # 5 minutes delay
            await self.send_course_email(email, course_key, 1)
            
        except Exception as e:
            logger.error(f"Error starting course sequence: {e}")
    
    async def send_course_email(self, email: str, course_key: str, day: int):
        """Send a specific day's email from a course"""
        try:
            # Load email content
            email_file = self.courses_dir / course_key / f"day-{day:02d}.md"
            
            if not email_file.exists():
                logger.error(f"Email file not found: {email_file}")
                return False
                
            with open(email_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse content (extract subject and body)
            lines = content.split('\n')
            subject = "Quick-Hit Course Day " + str(day)
            body_lines = []
            
            for line in lines:
                if line.startswith('Subject:'):
                    subject = line.replace('Subject:', '').strip()
                elif line.startswith('#'):
                    continue  # Skip markdown headers
                else:
                    body_lines.append(line)
            
            body = '\n'.join(body_lines).strip()
            
            # Replace template variables
            body = body.replace('{{firstName}}', email.split('@')[0].title())
            
            # Send email using existing email service
            success = await self.email_service.send_course_email(
                to_email=email,
                subject=subject,
                content=body,
                day=day
            )
            
            if success:
                logger.info(f"Sent day {day} of {course_key} to {email}")
            else:
                logger.error(f"Failed to send day {day} of {course_key} to {email}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error sending course email: {e}")
            return False
    
    async def process_daily_sends(self):
        """Process all scheduled course emails (run daily via cron)"""
        try:
            current_date = datetime.utcnow()
            
            for course_id, course_data in self.active_courses.items():
                if course_data['status'] != 'active':
                    continue
                    
                # Calculate which day should be sent
                days_since_start = (current_date - course_data['start_date']).days
                next_day = days_since_start + 1
                
                # Skip if already sent today or course complete
                if next_day <= course_data['current_day'] or next_day > 30:
                    continue
                
                # Send next day's email
                success = await self.send_course_email(
                    course_data['email'],
                    course_data['course_key'],
                    next_day
                )
                
                if success:
                    course_data['current_day'] = next_day
                    
                    # Mark course as complete if day 30
                    if next_day >= 30:
                        course_data['status'] = 'completed'
                        logger.info(f"Course {course_data['course_key']} completed for {course_data['email']}")
                        
        except Exception as e:
            logger.error(f"Error processing daily sends: {e}")
    
    def get_available_courses(self) -> List[str]:
        """Get list of available email courses"""
        courses = []
        for course_dir in self.courses_dir.iterdir():
            if course_dir.is_dir():
                courses.append(course_dir.name)
        return courses
    
    async def pause_course(self, email: str, course_key: str):
        """Pause a course for a user"""
        course_id = f"{email}_{course_key}"
        if course_id in self.active_courses:
            self.active_courses[course_id]['status'] = 'paused'
            logger.info(f"Paused course {course_key} for {email}")
    
    async def resume_course(self, email: str, course_key: str):
        """Resume a paused course"""
        course_id = f"{email}_{course_key}"
        if course_id in self.active_courses:
            self.active_courses[course_id]['status'] = 'active'
            logger.info(f"Resumed course {course_key} for {email}")

# Global instance
course_sender = EmailCourseSender()

async def main():
    """CLI runner for testing"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python email_course_sender.py <command>")
        print("Commands: daily_send, test_course <email> <course_key>")
        return
    
    command = sys.argv[1]
    
    if command == "daily_send":
        await course_sender.process_daily_sends()
        print("Daily sends processed")
        
    elif command == "test_course" and len(sys.argv) >= 4:
        email = sys.argv[2]
        course_key = sys.argv[3]
        await course_sender.start_course_sequence(email, course_key)
        print(f"Started test course {course_key} for {email}")
        
    else:
        print("Invalid command")

if __name__ == "__main__":
    asyncio.run(main())