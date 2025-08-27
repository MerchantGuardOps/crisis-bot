# utils/badge_generator.py
from __future__ import annotations

import os
import json
import hmac
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from database.pool import PostgresPool

# Get signing key from environment (in production, use a secure key management system)
BADGE_SIGNING_KEY = os.getenv('BADGE_SIGNING_KEY', 'dev-key-change-in-production').encode('utf-8')

async def generate_tamper_evident_badge(review_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a tamper-evident compliance badge with HMAC signature"""
    
    badge_id = str(uuid.uuid4())
    issue_date = datetime.now(timezone.utc)
    expiry_date = issue_date + timedelta(days=90)  # 90-day expiration
    
    # Core badge data (this is what gets signed)
    badge_payload = {
        "badge_id": badge_id,
        "version": "1.0",
        "issued_at": issue_date.isoformat(),
        "expires_at": expiry_date.isoformat(),
        "issuer": {
            "name": "MerchantGuard™",
            "entity": "DuneCrest Ventures Inc.",
            "contact": "compliance@merchantguard.ai",
            "verification_url": "https://merchantguard.ai/api/verify-badge"
        },
        "subject": {
            "business_name": review_data.get('business_name', 'Unknown'),
            "industry": review_data.get('industry', 'Unknown'),
            "assessment_completion_date": review_data.get('created_at', issue_date).isoformat()
        },
        "assessment": {
            "guardscore": review_data.get('guardscore', 0),
            "risk_level": review_data.get('risk_level', 'Unknown'),
            "assessment_type": "GuardScore™ Educational Assessment",
            "methodology_version": "v2.0"
        },
        "compliance_framework": {
            "frameworks_assessed": [
                "PCI DSS Awareness",
                "GDPR Basic Understanding", 
                "Payment Processing Best Practices",
                "Risk Management Fundamentals"
            ],
            "assessment_scope": "Self-reported educational questionnaire",
            "verification_level": "Basic compliance awareness"
        },
        "disclaimers": {
            "educational_only": True,
            "not_certification": True,
            "not_legal_advice": True,
            "not_psp_approval": True,
            "full_disclaimer_url": "https://merchantguard.ai/disclaimer"
        },
        "review_process": {
            "human_reviewed": True,
            "review_date": datetime.now(timezone.utc).isoformat(),
            "review_id": review_data.get('review_id'),
            "reviewer_verified": True
        }
    }
    
    # Create the complete badge structure
    badge_json = {
        "badge": badge_payload,
        "integrity": {
            "algorithm": "HMAC-SHA256",
            "signature": None,  # Will be populated below
            "signed_fields": [
                "badge_id", "version", "issued_at", "expires_at", 
                "issuer", "subject", "assessment", "compliance_framework",
                "disclaimers", "review_process"
            ],
            "verification_instructions": {
                "steps": [
                    "1. Extract the 'badge' object from this JSON",
                    "2. Serialize it using compact JSON (no spaces)",
                    "3. Compute HMAC-SHA256 using MerchantGuard's public verification endpoint",
                    "4. Compare with the signature field",
                    "5. Check expiration date"
                ],
                "api_endpoint": "https://merchantguard.ai/api/verify-badge",
                "public_verification": True
            }
        },
        "metadata": {
            "format_version": "1.0",
            "schema": "https://merchantguard.ai/schema/compliance-badge-v1.json",
            "rendering_hints": {
                "display_name": f"MerchantGuard™ Compliance Badge",
                "primary_color": "#0EA5E9",
                "badge_type": "Educational Assessment",
                "show_expiry_warning_days": 7
            }
        }
    }
    
    # Generate HMAC signature
    payload_json = json.dumps(badge_payload, sort_keys=True, separators=(',', ':'))
    signature = hmac.new(
        BADGE_SIGNING_KEY, 
        payload_json.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    
    badge_json["integrity"]["signature"] = signature
    
    # Store badge in database
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO compliance_badges (
                badge_id, user_id, review_id, badge_data, signature,
                issued_at, expires_at, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            badge_id,
            review_data.get('user_id'),
            review_data.get('review_id'),
            json.dumps(badge_json),
            signature,
            issue_date,
            expiry_date,
            'active',
            datetime.now(timezone.utc)
        )
    
    return {
        "badge_id": badge_id,
        "badge_json": badge_json,
        "user_id": review_data.get('user_id'),
        "business_name": review_data.get('business_name'),
        "guardscore": review_data.get('guardscore'),
        "issued_at": issue_date,
        "expires_at": expiry_date,
        "verification_url": f"https://merchantguard.ai/badge/{badge_id}",
        "download_url": f"https://merchantguard.ai/api/badge/{badge_id}/download"
    }

async def verify_badge_integrity(badge_json: Dict[str, Any]) -> Dict[str, bool]:
    """Verify the integrity and validity of a badge"""
    try:
        # Extract components
        badge_data = badge_json.get('badge', {})
        integrity = badge_json.get('integrity', {})
        provided_signature = integrity.get('signature')
        
        if not provided_signature:
            return {
                "valid": False,
                "signature_valid": False,
                "not_expired": False,
                "error": "No signature found"
            }
        
        # Recreate the signature
        payload_json = json.dumps(badge_data, sort_keys=True, separators=(',', ':'))
        expected_signature = hmac.new(
            BADGE_SIGNING_KEY,
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        signature_valid = hmac.compare_digest(provided_signature, expected_signature)
        
        # Check expiration
        expires_at = datetime.fromisoformat(badge_data.get('expires_at', ''))
        not_expired = datetime.now(timezone.utc) < expires_at
        
        # Check if badge exists in database
        badge_id = badge_data.get('badge_id')
        database_valid = False
        
        if badge_id:
            pool = PostgresPool()
            async with pool.get_connection() as conn:
                result = await conn.fetchrow(
                    "SELECT status FROM compliance_badges WHERE badge_id = $1",
                    badge_id
                )
                database_valid = result is not None and result['status'] == 'active'
        
        return {
            "valid": signature_valid and not_expired and database_valid,
            "signature_valid": signature_valid,
            "not_expired": not_expired,
            "database_valid": database_valid,
            "expires_at": expires_at.isoformat(),
            "days_until_expiry": (expires_at - datetime.now(timezone.utc)).days
        }
        
    except Exception as e:
        return {
            "valid": False,
            "signature_valid": False,
            "not_expired": False,
            "database_valid": False,
            "error": f"Verification failed: {str(e)}"
        }

async def revoke_badge(badge_id: str, reason: str, revoker_id: int) -> bool:
    """Revoke a badge (mark as inactive)"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE compliance_badges 
            SET status = 'revoked', 
                revoked_at = $1,
                revocation_reason = $2,
                revoked_by = $3
            WHERE badge_id = $4 AND status = 'active'
            """,
            datetime.now(timezone.utc),
            reason,
            revoker_id,
            badge_id
        )
        
        return result == "UPDATE 1"

async def get_badge_by_id(badge_id: str) -> Dict[str, Any] | None:
    """Get badge data by ID"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        result = await conn.fetchrow(
            """
            SELECT badge_id, user_id, badge_data, signature, 
                   issued_at, expires_at, status, revoked_at, revocation_reason
            FROM compliance_badges 
            WHERE badge_id = $1
            """,
            badge_id
        )
        
        if not result:
            return None
            
        badge_dict = dict(result)
        badge_dict['badge_json'] = json.loads(badge_dict['badge_data'])
        
        return badge_dict

async def list_user_badges(user_id: int) -> list[Dict[str, Any]]:
    """List all badges for a user"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        results = await conn.fetch(
            """
            SELECT badge_id, badge_data, issued_at, expires_at, status
            FROM compliance_badges 
            WHERE user_id = $1
            ORDER BY issued_at DESC
            """,
            user_id
        )
        
        badges = []
        for row in results:
            badge_dict = dict(row)
            badge_dict['badge_json'] = json.loads(badge_dict['badge_data'])
            badges.append(badge_dict)
            
        return badges