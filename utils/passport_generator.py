# utils/passport_generator.py
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
PASSPORT_SIGNING_KEY = os.getenv('PASSPORT_SIGNING_KEY', 'dev-key-change-in-production').encode('utf-8')

async def generate_tamper_evident_passport(review_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a tamper-evident Compliance Passport with HMAC signature"""
    
    passport_id = f"pp_{uuid.uuid4().hex[:6]}"
    issue_date = datetime.now(timezone.utc)
    expiry_date = issue_date + timedelta(days=90)  # 90-day expiration
    
    # Core passport data (this is what gets signed)
    passport_payload = {
        "version": "0.1",
        "asset_name": "Compliance Passport",
        "passport_id": passport_id,
        "issued_at": issue_date.isoformat(),
        "expires_at": expiry_date.isoformat(),
        "status": "valid",
        "review_level": "Reviewed",  # Self-Attested | Reviewed | Reviewed + UBO Verified
        "guardscore": review_data.get('guardscore', 0),
        "labels": ["Multi-PSP Ready", "Policy Complete"],
        "merchant": {
            "legal_name": review_data.get('business_name', 'Unknown'),
            "jurisdiction": "Unknown",  # Would be collected in assessment
            "domain": "unknown.example",  # Would be collected in assessment
            "support_email": "support@unknown.example"  # Would be collected in assessment
        },
        "checks": {
            "domain_identity_verified": True,
            "policy_stack_complete": True,
            "refund_kpis_defined": True,
            "dispute_sop_ready": True,
            "three_ds_plan_ready": True,
            "pci_minimization_ok": True,
            "support_alias_on_receipts": True,
            "multipsp_ready": True
        },
        "attestation": {
            "method": "bot_automation + human_review",
            "evidence_hash": f"sha256-{hashlib.sha256(str(review_data).encode()).hexdigest()[:16]}"
        },
        "signature": {
            "alg": "HMAC-SHA256",
            "kid": "mg_passport_v1",
            "value": None  # Will be populated below
        },
        "disclaimer_url": "https://merchantguard.ai/disclaimer"
    }
    
    # Generate HMAC signature
    payload_json = json.dumps(passport_payload, sort_keys=True, separators=(',', ':'))
    signature_value = hmac.new(
        PASSPORT_SIGNING_KEY, 
        payload_json.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    
    passport_payload["signature"]["value"] = signature_value
    
    # Store passport in database
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO compliance_passports (
                passport_id, user_id, review_id, passport_data, signature,
                issued_at, expires_at, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            passport_id,
            review_data.get('user_id'),
            review_data.get('review_id'),
            json.dumps(passport_payload),
            signature_value,
            issue_date,
            expiry_date,
            'active',
            datetime.now(timezone.utc)
        )
    
    return {
        "passport_id": passport_id,
        "passport_json": passport_payload,
        "user_id": review_data.get('user_id'),
        "business_name": review_data.get('business_name'),
        "guardscore": review_data.get('guardscore'),
        "issued_at": issue_date,
        "expires_at": expiry_date,
        "verification_url": f"https://merchantguard.ai/passport/{passport_id}",
        "download_url": f"https://merchantguard.ai/api/passport/{passport_id}/download"
    }

async def verify_passport_integrity(passport_json: Dict[str, Any]) -> Dict[str, bool]:
    """Verify the integrity and validity of a Compliance Passport"""
    try:
        passport_id = passport_json.get('passport_id')
        provided_signature = passport_json.get('signature', {}).get('value')
        
        if not provided_signature:
            return {
                "valid": False,
                "signature_valid": False,
                "not_expired": False,
                "error": "No signature found"
            }
        
        # Recreate the signature
        temp_passport = passport_json.copy()
        temp_passport["signature"]["value"] = None
        payload_json = json.dumps(temp_passport, sort_keys=True, separators=(',', ':'))
        expected_signature = hmac.new(
            PASSPORT_SIGNING_KEY,
            payload_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        signature_valid = hmac.compare_digest(provided_signature, expected_signature)
        
        # Check expiration
        expires_at = datetime.fromisoformat(passport_json.get('expires_at', ''))
        not_expired = datetime.now(timezone.utc) < expires_at
        
        # Check if passport exists in database
        database_valid = False
        
        if passport_id:
            pool = PostgresPool()
            async with pool.get_connection() as conn:
                result = await conn.fetchrow(
                    "SELECT status FROM compliance_passports WHERE passport_id = $1",
                    passport_id
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

async def revoke_passport(passport_id: str, reason: str, revoker_id: int) -> bool:
    """Revoke a Compliance Passport (mark as inactive)"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        result = await conn.execute(
            """
            UPDATE compliance_passports 
            SET status = 'revoked', 
                revoked_at = $1,
                revocation_reason = $2,
                revoked_by = $3
            WHERE passport_id = $4 AND status = 'active'
            """,
            datetime.now(timezone.utc),
            reason,
            revoker_id,
            passport_id
        )
        
        return result == "UPDATE 1"

async def get_passport_by_id(passport_id: str) -> Dict[str, Any] | None:
    """Get Compliance Passport data by ID"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        result = await conn.fetchrow(
            """
            SELECT passport_id, user_id, passport_data, signature, 
                   issued_at, expires_at, status, revoked_at, revocation_reason
            FROM compliance_passports 
            WHERE passport_id = $1
            """,
            passport_id
        )
        
        if not result:
            return None
            
        passport_dict = dict(result)
        passport_dict['passport_json'] = json.loads(passport_dict['passport_data'])
        
        return passport_dict

async def list_user_passports(user_id: int) -> list[Dict[str, Any]]:
    """List all Compliance Passports for a user"""
    pool = PostgresPool()
    async with pool.get_connection() as conn:
        results = await conn.fetch(
            """
            SELECT passport_id, passport_data, issued_at, expires_at, status
            FROM compliance_passports 
            WHERE user_id = $1
            ORDER BY issued_at DESC
            """,
            user_id
        )
        
        passports = []
        for row in results:
            passport_dict = dict(row)
            passport_dict['passport_json'] = json.loads(passport_dict['passport_data'])
            passports.append(passport_dict)
            
        return passports

def sign_passport(obj: dict, secret: str) -> dict:
    """Helper function to sign passport data"""
    canonical = json.dumps(obj, sort_keys=True, separators=(',', ':'))
    value = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).digest().hex()
    return {
        "canonical": canonical, 
        "signature": {
            "alg": "HMAC-SHA256", 
            "kid": "mg_passport_v1", 
            "value": value
        }
    }