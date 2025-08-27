# utils/human_review_queue.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from database.pool import PostgresPool

async def add_to_review_queue(user_profile: Dict[str, Any], telegram_user: Any) -> str:
    """Add a badge request to the human review queue"""
    review_id = str(uuid.uuid4())
    
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO badge_review_queue (
                review_id, user_id, telegram_username, business_name, 
                industry, monthly_volume, guardscore, risk_level,
                status, created_at, user_data
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            review_id,
            user_profile['user_id'],
            telegram_user.username or telegram_user.first_name,
            user_profile.get('business_name', 'Unknown'),
            user_profile.get('industry', 'Unknown'),
            user_profile.get('monthly_volume', 0),
            user_profile.get('guardscore', 0),
            user_profile.get('risk_level', 'Unknown'),
            'pending',
            datetime.now(timezone.utc),
            {
                'telegram_id': telegram_user.id,
                'first_name': telegram_user.first_name,
                'last_name': telegram_user.last_name,
                'username': telegram_user.username,
                'original_assessment_date': user_profile.get('created_at', datetime.now()).isoformat() if user_profile.get('created_at') else None
            }
        )
    
    return review_id

async def get_review_status(user_id: int) -> Optional[Dict[str, Any]]:
    """Get the review status for a user's badge request"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        result = await conn.fetchrow(
            """
            SELECT review_id, status, created_at, reviewed_at, 
                   reviewer_notes, reviewer_id
            FROM badge_review_queue 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            user_id
        )
        
        if not result:
            return None
            
        return dict(result)

async def get_pending_reviews(limit: int = 10) -> list[Dict[str, Any]]:
    """Get pending badge reviews for admin interface"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        results = await conn.fetch(
            """
            SELECT review_id, user_id, telegram_username, business_name,
                   industry, monthly_volume, guardscore, risk_level,
                   created_at, user_data
            FROM badge_review_queue 
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            limit
        )
        
        return [dict(row) for row in results]

async def approve_badge_review(review_id: str, reviewer_id: int, notes: str = "") -> Dict[str, Any]:
    """Approve a badge review and generate the badge"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        # Update review status
        await conn.execute(
            """
            UPDATE badge_review_queue 
            SET status = 'approved', 
                reviewed_at = $1, 
                reviewer_id = $2,
                reviewer_notes = $3
            WHERE review_id = $4
            """,
            datetime.now(timezone.utc),
            reviewer_id,
            notes,
            review_id
        )
        
        # Get the review data
        review_data = await conn.fetchrow(
            """
            SELECT * FROM badge_review_queue 
            WHERE review_id = $1
            """,
            review_id
        )
        
        if not review_data:
            raise ValueError("Review not found")
        
        # Generate badge
        from utils.badge_generator import generate_tamper_evident_badge
        badge_data = await generate_tamper_evident_badge(dict(review_data))
        
        return badge_data

async def reject_badge_review(review_id: str, reviewer_id: int, reason: str) -> None:
    """Reject a badge review"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        await conn.execute(
            """
            UPDATE badge_review_queue 
            SET status = 'rejected', 
                reviewed_at = $1, 
                reviewer_id = $2,
                reviewer_notes = $3
            WHERE review_id = $4
            """,
            datetime.now(timezone.utc),
            reviewer_id,
            reason,
            review_id
        )

async def request_additional_info(review_id: str, reviewer_id: int, info_needed: str) -> None:
    """Request additional information from the user"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        await conn.execute(
            """
            UPDATE badge_review_queue 
            SET status = 'requires_info', 
                reviewed_at = $1, 
                reviewer_id = $2,
                reviewer_notes = $3
            WHERE review_id = $4
            """,
            datetime.now(timezone.utc),
            reviewer_id,
            f"Additional information required: {info_needed}",
            review_id
        )

async def get_review_analytics() -> Dict[str, Any]:
    """Get analytics about the review process"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        # Get counts by status
        status_counts = await conn.fetch(
            """
            SELECT status, COUNT(*) as count
            FROM badge_review_queue
            GROUP BY status
            """
        )
        
        # Get average processing time
        avg_processing_time = await conn.fetchrow(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (reviewed_at - created_at))/3600) as avg_hours
            FROM badge_review_queue
            WHERE reviewed_at IS NOT NULL
            """
        )
        
        # Get reviews by date (last 30 days)
        daily_reviews = await conn.fetch(
            """
            SELECT DATE(created_at) as review_date, 
                   COUNT(*) as reviews_submitted,
                   COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved,
                   COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected
            FROM badge_review_queue 
            WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY review_date DESC
            """
        )
        
        return {
            'status_counts': {row['status']: row['count'] for row in status_counts},
            'avg_processing_hours': float(avg_processing_time['avg_hours']) if avg_processing_time['avg_hours'] else 0,
            'daily_reviews': [dict(row) for row in daily_reviews]
        }