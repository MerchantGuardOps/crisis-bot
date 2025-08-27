<<<<<<< Updated upstream
# infra/middleware.py
"""
Security and performance middleware for FastAPI
"""

import time
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers.update({
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "X-Content-Type-Options": "nosniff", 
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "interest-cohort=()",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "img-src 'self' data: https://*.telegram.org https://*.merchantguard.ai; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self' https://api.telegram.org; "
                "frame-ancestors 'none';"
            )
        })
        
        return response

class TimingMiddleware(BaseHTTPMiddleware):
    """Add request timing headers and logging"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            
            # Calculate timing
            process_time = (time.perf_counter() - start_time) * 1000
            response.headers["Server-Timing"] = f"app;dur={process_time:.1f}"
            
            # Log slow requests
            if process_time > 1000:  # > 1 second
                logger.warning(f"Slow request: {request.method} {request.url.path} took {process_time:.1f}ms")
            else:
                logger.info(f"Request: {request.method} {request.url.path} - {process_time:.1f}ms")
            
            return response
            
        except Exception as e:
            process_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Request failed: {request.method} {request.url.path} - {process_time:.1f}ms - {str(e)}")
            raise

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting by IP"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
        self.window_start = time.time()
        
    async def dispatch(self, request: Request, call_next):
        now = time.time()
        client_ip = request.client.host
        
        # Reset window every minute
        if now - self.window_start > 60:
            self.request_counts.clear()
            self.window_start = now
        
        # Check rate limit
        count = self.request_counts.get(client_ip, 0)
        if count >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(status_code=429, detail="Too Many Requests")
        
        # Increment count
        self.request_counts[client_ip] = count + 1
        
        return await call_next(request)
=======
from fastapi import Request
import time

class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

class TimingMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)

class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute=60):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
>>>>>>> Stashed changes
