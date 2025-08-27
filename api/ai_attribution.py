<<<<<<< Updated upstream
"""
AI Attribution & SEO ROI Tracking
Logs AI crawler hits and measures AI-driven traffic
"""

from fastapi import APIRouter, Request, Response
from datetime import datetime
from typing import Optional
import json
import os
import re

router = APIRouter(prefix="/api/ai", tags=["ai-attribution"])

# Known AI crawler patterns
AI_CRAWLERS = {
    'openai': r'(GPTBot|OpenAI)',
    'anthropic': r'(Claude-Web)',
    'perplexity': r'(PerplexityBot)',
    'google': r'(Google-Extended|Bard)',
    'microsoft': r'(BingBot|Copilot)',
    'meta': r'(FacebookBot|Meta)',
    'cohere': r'(Cohere)',
    'character': r'(Character\.AI)',
    'you': r'(YouBot)',
    'phind': r'(PhindBot)'
}

def classify_user_agent(ua: str) -> tuple[str, bool]:
    """Classify user agent as AI crawler or regular traffic."""
    if not ua:
        return "unknown", False
    
    ua_lower = ua.lower()
    
    for crawler_name, pattern in AI_CRAWLERS.items():
        if re.search(pattern, ua, re.IGNORECASE):
            return crawler_name, True
    
    # Check for common crawler indicators
    crawler_indicators = ['bot', 'crawler', 'spider', 'scraper', 'agent']
    for indicator in crawler_indicators:
        if indicator in ua_lower:
            return "generic_crawler", True
    
    return "human", False

@router.get("/hit")
async def log_ai_hit(request: Request, url: str, source: Optional[str] = None):
    """Log AI crawler or referral hit."""
    
    ua = request.headers.get("user-agent", "")
    crawler_type, is_ai = classify_user_agent(ua)
    ip = request.client.host if request.client else "unknown"
    
    hit_data = {
        "url": url,
        "user_agent": ua,
        "crawler_type": crawler_type,
        "is_ai_crawler": is_ai,
        "source": source,
        "ip": ip,
        "timestamp": datetime.utcnow().isoformat(),
        "headers": dict(request.headers)
    }
    
    # In production, this would log to database
    # For now, log to file for analysis
    log_ai_hit_to_file(hit_data)
    
    return {
        "ok": True,
        "url": url,
        "crawler_type": crawler_type,
        "is_ai": is_ai,
        "timestamp": hit_data["timestamp"]
    }

@router.post("/attribution")
async def log_ai_attribution(request: Request):
    """Log AI-driven conversion attribution."""
    
    try:
        data = await request.json()
        
        attribution_data = {
            "event_type": data.get("event_type"),  # "page_view", "conversion", "click"
            "source": data.get("source"),  # "ai_search", "direct", "organic"
            "ai_engine": data.get("ai_engine"),  # "chatgpt", "perplexity", etc.
            "query": data.get("query"),  # Original search query if known
            "page": data.get("page"),
            "user_id": data.get("user_id"),
            "session_id": data.get("session_id"),
            "timestamp": datetime.utcnow().isoformat(),
            "user_agent": request.headers.get("user-agent", "")
        }
        
        # Log attribution event
        log_attribution_to_file(attribution_data)
        
        return {"ok": True, "logged": True}
    
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/stats")
async def get_ai_stats(days: int = 7):
    """Get AI traffic and attribution stats."""
    
    # In production, this would query database
    # For now, return sample data structure
    
    stats = {
        "period": f"last_{days}_days",
        "ai_crawlers": {
            "total_hits": 0,
            "unique_crawlers": 0,
            "top_crawlers": []
        },
        "ai_referrals": {
            "total_visits": 0,
            "conversions": 0,
            "conversion_rate": 0.0,
            "top_engines": []
        },
        "content_performance": {
            "most_accessed_facts": [],
            "top_performing_pages": []
        },
        "generated_at": datetime.utcnow().isoformat()
    }
    
    # Try to read from log files if they exist
    try:
        stats.update(analyze_log_files(days))
    except Exception as e:
        print(f"Error analyzing logs: {e}")
    
    return stats

@router.get("/facts/{entity}")
async def serve_ai_fact(entity: str, request: Request):
    """Serve AI facts with hit tracking."""
    
    # Log the hit
    await log_ai_hit(request, f"/ai/facts/{entity}.json", "api_request")
    
    # Serve the actual fact file
    fact_path = f"public/ai/facts/{entity}.json"
    
    if os.path.exists(fact_path):
        with open(fact_path, 'r', encoding='utf-8') as f:
            fact_data = json.load(f)
        
        return Response(
            content=json.dumps(fact_data, indent=2),
            media_type="application/json",
            headers={
                "Cache-Control": "max-age=300, must-revalidate",
                "ETag": f'"{hash(str(fact_data))}"'
            }
        )
    else:
        return {"error": "Fact not found", "entity": entity}, 404

def log_ai_hit_to_file(hit_data: dict):
    """Log AI hit to file for analysis."""
    
    try:
        os.makedirs("logs/ai", exist_ok=True)
        
        log_file = f"logs/ai/hits_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(hit_data) + '\n')
    
    except Exception as e:
        print(f"Error logging AI hit: {e}")

def log_attribution_to_file(attribution_data: dict):
    """Log attribution event to file."""
    
    try:
        os.makedirs("logs/ai", exist_ok=True)
        
        log_file = f"logs/ai/attribution_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(attribution_data) + '\n')
    
    except Exception as e:
        print(f"Error logging attribution: {e}")

def analyze_log_files(days: int) -> dict:
    """Analyze log files for stats (basic implementation)."""
    
    stats = {
        "ai_crawlers": {"total_hits": 0, "unique_crawlers": set()},
        "ai_referrals": {"total_visits": 0, "conversions": 0}
    }
    
    # This is a simplified implementation
    # In production, use proper log analysis tools
    
    return {
        "ai_crawlers": {
            "total_hits": len(stats["ai_crawlers"]["unique_crawlers"]),
            "unique_crawlers": len(stats["ai_crawlers"]["unique_crawlers"]),
            "top_crawlers": list(stats["ai_crawlers"]["unique_crawlers"])[:5]
        },
        "ai_referrals": {
            "total_visits": stats["ai_referrals"]["total_visits"],
            "conversions": stats["ai_referrals"]["conversions"],
            "conversion_rate": stats["ai_referrals"]["conversions"] / max(stats["ai_referrals"]["total_visits"], 1) * 100
        }
    }
=======
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/ai/health") 
async def ai_health():
    return {"status": "ai_attribution_ok"}
>>>>>>> Stashed changes
