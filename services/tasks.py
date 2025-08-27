"""
Cloud Tasks integration for async heavy work
Keeps bot handlers fast by offloading CPU/IO intensive operations
"""
import os, json, hmac, hashlib, logging
from google.cloud import tasks_v2
from typing import Dict, Any

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("PROJECT_ID", "guardscore-fresh-new")
REGION = os.getenv("REGION", "us-central1")
QUEUE_NAME = os.getenv("TASKS_QUEUE", "merchantguard-async")
BASE_URL = os.getenv("BASE_URL", "https://guardscore-final-5wezdzk32a-uc.a.run.app")
TASKS_SECRET = os.getenv("TASKS_HMAC_SECRET", "mg_tasks_secret_2025")

class TaskScheduler:
    def __init__(self):
        self.client = tasks_v2.CloudTasksClient()
        self.queue_path = self.client.queue_path(PROJECT_ID, REGION, QUEUE_NAME)
        
    def _sign_payload(self, payload: dict) -> str:
        """Sign task payload with HMAC"""
        message = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(TASKS_SECRET.encode(), message, hashlib.sha256).hexdigest()
        return signature
        
    async def enqueue_task(self, endpoint: str, payload: dict, delay_seconds: int = 0):
        """Enqueue async task"""
        try:
            # Sign payload for verification
            signature = self._sign_payload(payload)
            
            # Create task
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{BASE_URL}{endpoint}",
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Tasks-Signature": signature
                    },
                    "body": json.dumps(payload).encode()
                }
            }
            
            if delay_seconds > 0:
                import datetime
                from google.protobuf import timestamp_pb2
                d = datetime.datetime.utcnow() + datetime.timedelta(seconds=delay_seconds)
                timestamp = timestamp_pb2.Timestamp()
                timestamp.FromDatetime(d)
                task["schedule_time"] = timestamp
            
            # Enqueue
            response = self.client.create_task(parent=self.queue_path, task=task)
            logger.info(f"Task enqueued: {endpoint} -> {response.name}")
            return response.name
            
        except Exception as e:
            logger.error(f"Failed to enqueue task {endpoint}: {e}")
            raise

# Global task scheduler instance
task_scheduler = TaskScheduler()

def verify_task_signature(signature: str, payload: dict) -> bool:
    """Verify task signature"""
    try:
        message = json.dumps(payload, sort_keys=True).encode()
        expected = hmac.new(TASKS_SECRET.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False

# Convenience functions for common async tasks
async def enqueue_evidence_generation(merchant_id: str, package_type: str):
    """Generate evidence pack asynchronously"""
    payload = {
        "merchant_id": merchant_id,
        "package_type": package_type,
        "timestamp": int(time.time())
    }
    return await task_scheduler.enqueue_task("/tasks/generate_evidence", payload)

async def enqueue_attestation_issuance(user_id: str, attestation_data: dict):
    """Issue EAS attestation asynchronously"""
    payload = {
        "user_id": user_id,
        "attestation_data": attestation_data,
        "timestamp": int(time.time())
    }
    return await task_scheduler.enqueue_task("/tasks/issue_attestation", payload)

async def enqueue_package_building(order_id: str, package_config: dict):
    """Build package contents asynchronously"""
    payload = {
        "order_id": order_id,
        "package_config": package_config,
        "timestamp": int(time.time())
    }
    return await task_scheduler.enqueue_task("/tasks/build_package", payload)
    
async def enqueue_webhook_processing(webhook_id: str, provider: str, payload_data: dict):
    """Process payment webhook data asynchronously"""
    payload = {
        "webhook_id": webhook_id,
        "provider": provider,
        "payload_data": payload_data,
        "timestamp": int(time.time())
    }
    return await task_scheduler.enqueue_task("/tasks/process_webhook", payload)

import time
