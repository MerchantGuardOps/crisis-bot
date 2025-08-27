"""
AI Headers Middleware - Optimized caching and CORS for AI crawlers
"""
import hashlib
from typing import Dict, List, Tuple
from starlette.types import ASGIApp, Receive, Scope, Send


class AIHeadersMiddleware:
    """
    Middleware to add optimal headers for AI crawler ingestion:
    - Cache-Control for facts and sitemaps
    - CORS for cross-origin AI access
    - ETag for efficient caching
    - AI-specific headers for attribution
    """
    
    def __init__(self, app: ASGIApp):
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        async def _send(event):
            if event["type"] == "http.response.start":
                headers = dict(event.get("headers", []))
                path = scope.get("path", "")
                
                # Apply AI-optimized headers for facts and sitemaps
                if self._should_apply_ai_headers(path):
                    self._add_ai_headers(headers, path)
                    
                # Convert back to list of tuples
                event["headers"] = [(k.encode() if isinstance(k, str) else k, 
                                   v.encode() if isinstance(v, str) else v) 
                                  for k, v in headers.items()]
                                  
            await send(event)
            
        await self.app(scope, receive, _send)
    
    def _should_apply_ai_headers(self, path: str) -> bool:
        """Check if path should get AI-optimized headers"""
        ai_paths = [
            "/ai/facts/",
            "/sitemap-ai.xml", 
            "/match-recovery",
            "/api/ai/"
        ]
        return any(path.startswith(prefix) for prefix in ai_paths)
    
    def _add_ai_headers(self, headers: Dict, path: str):
        """Add AI-optimized headers"""
        # Cache control optimized for AI crawlers
        if "/ai/facts/" in path:
            headers["cache-control"] = "max-age=300, must-revalidate, public"
            headers["vary"] = "Accept, User-Agent"
        elif "sitemap-ai.xml" in path:
            headers["cache-control"] = "max-age=3600, public"
        else:
            headers["cache-control"] = "max-age=300, public"
            
        # CORS for AI systems
        headers["access-control-allow-origin"] = "*"
        headers["access-control-allow-methods"] = "GET, OPTIONS"
        headers["access-control-allow-headers"] = "User-Agent, Accept, Authorization"
        
        # AI attribution headers
        headers["x-ai-source"] = "merchantguard.ai"
        headers["x-content-type"] = "ai-optimized"
        
        # Content type headers for JSON facts
        if path.endswith(".json"):
            headers["content-type"] = "application/json; charset=utf-8"
        elif path.endswith(".xml"):
            headers["content-type"] = "application/xml; charset=utf-8"


def generate_etag(content: str) -> str:
    """Generate ETag from content hash"""
    return f'"{hashlib.md5(content.encode()).hexdigest()}"'


def add_etag_header(headers: Dict, content: str):
    """Add ETag header for content"""
    headers["etag"] = generate_etag(content)