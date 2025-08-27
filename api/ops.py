"""
Operations endpoints for MATCH AI Pack v1.1
Automated maintenance tasks for AI content freshness
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
import asyncio
import asyncpg
import httpx
import json
import os
from typing import Dict, Any

router = APIRouter(prefix="/ops", tags=["operations"])

# IndexNow configuration
INDEXNOW_ENDPOINTS = {
    "bing": "https://www.bing.com/indexnow",
    "yandex": "https://yandex.com/indexnow"
}

@router.post("/refresh_provider_mv")
async def refresh_provider_mv():
    """Refresh materialized view for provider success rates"""
    try:
        # Connect to database (use your existing connection)
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise HTTPException(500, "DATABASE_URL not configured")
            
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Refresh the materialized view concurrently
            start_time = datetime.utcnow()
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY provider_success_mv;")
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Log success
            print(f"✅ Provider MV refreshed in {duration:.2f}s at {end_time}")
            
            return {
                "ok": True,
                "refreshed_at": end_time.isoformat(),
                "duration_seconds": duration,
                "message": "provider_success_mv refreshed successfully"
            }
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"❌ Failed to refresh provider MV: {e}")
        raise HTTPException(500, f"Failed to refresh materialized view: {str(e)}")

@router.post("/rebuild_ai_index_match")
async def rebuild_ai_index_match():
    """Rebuild AI search index for MATCH content"""
    try:
        from scripts.ai_build_match_index import main as rebuild_index
        
        start_time = datetime.utcnow()
        
        # Run the index rebuild
        result = await asyncio.get_event_loop().run_in_executor(None, rebuild_index)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ AI index rebuilt in {duration:.2f}s at {end_time}")
        
        return {
            "ok": True,
            "rebuilt_at": end_time.isoformat(),
            "duration_seconds": duration,
            "result": result,
            "message": "AI index rebuilt successfully"
        }
        
    except Exception as e:
        print(f"❌ Failed to rebuild AI index: {e}")
        raise HTTPException(500, f"Failed to rebuild AI index: {str(e)}")

@router.post("/indexnow_ping")
async def indexnow_ping():
    """Ping IndexNow services with updated content"""
    try:
        base_url = os.getenv("BASE_URL", "https://merchantguard.ai")
        indexnow_key = os.getenv("INDEXNOW_KEY", "your-indexnow-key")
        
        # URLs to notify
        updated_urls = [
            f"{base_url}/ai/facts/match.providers.json",
            f"{base_url}/ai/facts/match.core.json", 
            f"{base_url}/sitemap-ai.xml",
            f"{base_url}/match-recovery"
        ]
        
        results = {}
        
        async with httpx.AsyncClient() as client:
            for service, endpoint in INDEXNOW_ENDPOINTS.items():
                try:
                    payload = {
                        "host": base_url.replace("https://", "").replace("http://", ""),
                        "key": indexnow_key,
                        "urlList": updated_urls
                    }
                    
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                    
                    results[service] = {
                        "status_code": response.status_code,
                        "success": response.status_code == 200,
                        "urls_submitted": len(updated_urls)
                    }
                    
                except Exception as e:
                    results[service] = {
                        "success": False,
                        "error": str(e)
                    }
        
        success_count = sum(1 for r in results.values() if r.get("success"))
        
        print(f"✅ IndexNow ping: {success_count}/{len(INDEXNOW_ENDPOINTS)} services succeeded")
        
        return {
            "ok": True,
            "pinged_at": datetime.utcnow().isoformat(),
            "results": results,
            "urls_submitted": updated_urls,
            "success_count": success_count,
            "total_services": len(INDEXNOW_ENDPOINTS)
        }
        
    except Exception as e:
        print(f"❌ Failed to ping IndexNow: {e}")
        raise HTTPException(500, f"Failed to ping IndexNow: {str(e)}")

@router.get("/health")
async def ops_health():
    """Health check for ops endpoints"""
    return {
        "ok": True,
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "ready" if os.getenv("DATABASE_URL") else "not_configured",
            "indexnow": "ready" if os.getenv("INDEXNOW_KEY") else "not_configured"
        }
    }

@router.post("/validate_facts")
async def validate_facts():
    """Validate all AI facts files against schemas"""
    try:
        import glob
        import jsonschema
        
        schema_base = "schemas/ai_facts/base.schema.json"
        schema_providers = "schemas/ai_facts/match.providers.schema.json"
        
        # Load schemas
        with open(schema_base) as f:
            base_schema = json.load(f)
        with open(schema_providers) as f:
            providers_schema = json.load(f)
            
        results = {}
        errors = []
        
        # Validate all fact files
        for fact_file in glob.glob("public/ai/facts/*.json"):
            if "schema.json" in fact_file:
                continue
                
            try:
                with open(fact_file) as f:
                    fact_data = json.load(f)
                
                # Choose appropriate schema
                if "providers" in fact_file:
                    jsonschema.validate(fact_data, providers_schema)
                else:
                    jsonschema.validate(fact_data, base_schema)
                    
                results[fact_file] = {"valid": True}
                
            except Exception as e:
                results[fact_file] = {"valid": False, "error": str(e)}
                errors.append(f"{fact_file}: {str(e)}")
        
        validation_passed = len(errors) == 0
        
        return {
            "ok": validation_passed,
            "validated_at": datetime.utcnow().isoformat(),
            "total_files": len(results),
            "valid_files": len([r for r in results.values() if r["valid"]]),
            "invalid_files": len(errors),
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(500, f"Failed to validate facts: {str(e)}")

# Background task helpers
async def log_operation(operation: str, success: bool, details: Dict[str, Any] = None):
    """Log operation result for monitoring"""
    log_entry = {
        "operation": operation,
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {}
    }
    print(f"[OPS] {json.dumps(log_entry)}")