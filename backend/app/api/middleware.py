from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List
import asyncio
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using in-memory storage.
    Limits requests per IP address within a time window.
    """
    
    def __init__(self, app, requests_per_window: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.request_counts: Dict[str, List[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        async with self._lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=self.window_seconds)
            
            self.request_counts[client_ip] = [
                ts for ts in self.request_counts[client_ip]
                if ts > window_start
            ]
            
            if len(self.request_counts[client_ip]) >= self.requests_per_window:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"error": "Too many requests. Please try again later."},
                )
            
            self.request_counts[client_ip].append(now)
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests.
    """
    
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()
        
        response = await call_next(request)
        
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(
            f"{request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Duration: {duration:.2f}ms"
        )
        
        return response
