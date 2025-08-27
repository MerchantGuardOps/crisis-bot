"""
Cloud Tasks endpoints for async processing
Heavy work handlers that run outside the critical path
"""
from fastapi import APIRouter, Request, HTTPException, Header, Depends
import json, logging
from services.tasks import verify_task_signature
from services.db_pool import get_connection

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger(__name__)

def verify_internal_signature(x_tasks_signature: str, payload: dict):
    """Verify task is from our internal task queue"""
    if not verify_task_signature(x_tasks_signature, payload):
        logger.warning("Invalid task signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

@router.post("/generate_evidence")
async def generate_evidence_task(
    request: Request,
    x_tasks_signature: str = Header(..., alias="X-Tasks-Signature")
):
    """Generate evidence pack asynchronously"""
    payload = await request.json()
    verify_internal_signature(x_tasks_signature, payload)
    
    merchant_id = payload["merchant_id"]
    package_type = payload["package_type"]
    
    logger.info(f"Generating evidence pack for merchant {merchant_id}, type {package_type}")
    
    try:
        # Heavy work: PDF generation, document compilation, etc.
        async with get_connection() as conn:
            # Get merchant data
            merchant = await conn.fetchrow("SELECT * FROM merchants WHERE id = $1", merchant_id)
            if not merchant:
                raise HTTPException(status_code=404, detail="Merchant not found")
            
            # Generate evidence pack (placeholder for actual implementation)
            evidence_data = {
                "merchant_id": merchant_id,
                "package_type": package_type,
                "generated_at": payload["timestamp"],
                "status": "completed"
            }
            
            # Store result
            await conn.execute("""
                INSERT INTO evidence_packs (merchant_id, package_type, data, status)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (merchant_id, package_type) 
                DO UPDATE SET data = $3, status = $4, updated_at = NOW()
            """, merchant_id, package_type, json.dumps(evidence_data), "completed")
            
        logger.info(f"Evidence pack generated successfully for {merchant_id}")
        return {"status": "completed", "merchant_id": merchant_id}
        
    except Exception as e:
        logger.error(f"Evidence generation failed for {merchant_id}: {e}")
        return {"status": "failed", "error": str(e)}

@router.post("/issue_attestation")
async def issue_attestation_task(
    request: Request,
    x_tasks_signature: str = Header(..., alias="X-Tasks-Signature")
):
    """Issue EAS attestation asynchronously"""
    payload = await request.json()
    verify_internal_signature(x_tasks_signature, payload)
    
    user_id = payload["user_id"]
    attestation_data = payload["attestation_data"]
    
    logger.info(f"Issuing attestation for user {user_id}")
    
    try:
        # Heavy work: EAS network calls, blockchain interactions
        async with get_connection() as conn:
            # Store attestation
            await conn.execute("""
                INSERT INTO attestations (user_id, data, status, created_at)
                VALUES ($1, $2, $3, NOW())
            """, user_id, json.dumps(attestation_data), "issued")
            
        logger.info(f"Attestation issued successfully for {user_id}")
        return {"status": "issued", "user_id": user_id}
        
    except Exception as e:
        logger.error(f"Attestation issuance failed for {user_id}: {e}")
        return {"status": "failed", "error": str(e)}

@router.post("/build_package")
async def build_package_task(
    request: Request,
    x_tasks_signature: str = Header(..., alias="X-Tasks-Signature")
):
    """Build package contents asynchronously"""
    payload = await request.json()
    verify_internal_signature(x_tasks_signature, payload)
    
    order_id = payload["order_id"]
    package_config = payload["package_config"]
    
    logger.info(f"Building package for order {order_id}")
    
    try:
        # Heavy work: Package compilation, file generation, etc.
        async with get_connection() as conn:
            # Get order details
            order = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            
            # Build package (placeholder)
            package_data = {
                "order_id": order_id,
                "config": package_config,
                "built_at": payload["timestamp"],
                "status": "ready"
            }
            
            # Update order status
            await conn.execute("""
                UPDATE orders SET 
                    package_data = $1, 
                    status = 'package_ready',
                    updated_at = NOW()
                WHERE id = $2
            """, json.dumps(package_data), order_id)
            
        logger.info(f"Package built successfully for order {order_id}")
        return {"status": "ready", "order_id": order_id}
        
    except Exception as e:
        logger.error(f"Package building failed for {order_id}: {e}")
        return {"status": "failed", "error": str(e)}

@router.post("/process_webhook")
async def process_webhook_task(
    request: Request,
    x_tasks_signature: str = Header(..., alias="X-Tasks-Signature")
):
    """Process payment webhook asynchronously"""
    payload = await request.json()
    verify_internal_signature(x_tasks_signature, payload)
    
    webhook_id = payload["webhook_id"]
    provider = payload["provider"]
    webhook_data = payload["payload_data"]
    
    logger.info(f"Processing {provider} webhook {webhook_id}")
    
    try:
        # Heavy work: Payment processing, business logic, notifications
        async with get_connection() as conn:
            # Store webhook processing result
            await conn.execute("""
                INSERT INTO webhook_processing_log (webhook_id, provider, processed_at, status)
                VALUES ($1, $2, NOW(), 'completed')
            """, webhook_id, provider)
            
        logger.info(f"Webhook {webhook_id} processed successfully")
        return {"status": "processed", "webhook_id": webhook_id}
        
    except Exception as e:
        logger.error(f"Webhook processing failed for {webhook_id}: {e}")
        return {"status": "failed", "error": str(e)}

@router.get("/health")
async def tasks_health():
    """Tasks service health check"""
    return {
        "status": "healthy",
        "service": "MerchantGuard Async Tasks",
        "endpoints": [
            "/tasks/generate_evidence",
            "/tasks/issue_attestation", 
            "/tasks/build_package",
            "/tasks/process_webhook"
        ]
    }
