import time
from typing import Callable, Optional
from collections import defaultdict, deque
import asyncio

from fastapi import Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from redis import Redis
from app.core.logging import security_logger


# In-memory rate limiter for development (fallback)
class InMemoryRateLimiter:
    def __init__(self):
        self.clients = defaultdict(deque)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        async with self.lock:
            now = time.time()
            client_requests = self.clients[key]
            
            # Remove old requests outside the window
            while client_requests and client_requests[0] < now - window:
                client_requests.popleft()
            
            # Check if limit is exceeded
            if len(client_requests) >= limit:
                return False
            
            # Add current request
            client_requests.append(now)
            return True


# Redis-based rate limiter for production
class RedisRateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
    
    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        try:
            pipe = self.redis.pipeline()
            now = time.time()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, now - window)
            
            # Count current entries
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiration
            pipe.expire(key, window)
            
            results = pipe.execute()
            current_count = results[1]
            
            return current_count < limit
            
        except Exception as e:
            security_logger.error("Redis rate limiter error", error=str(e))
            # Fallback to allowing the request if Redis fails
            return True


# Global rate limiter instance
_rate_limiter_instance: Optional[InMemoryRateLimiter] = None
_redis_rate_limiter: Optional[RedisRateLimiter] = None

def get_rate_limiter() -> InMemoryRateLimiter:
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = InMemoryRateLimiter()
    return _rate_limiter_instance

def setup_redis_rate_limiter(redis_url: str = "redis://localhost:6379") -> None:
    global _redis_rate_limiter
    try:
        redis_client = Redis.from_url(redis_url, decode_responses=True)
        _redis_rate_limiter = RedisRateLimiter(redis_client)
        security_logger.info("Redis rate limiter configured")
    except Exception as e:
        security_logger.warning("Failed to setup Redis rate limiter, using in-memory fallback", error=str(e))

def get_active_rate_limiter():
    return _redis_rate_limiter if _redis_rate_limiter else get_rate_limiter()


# SlowAPI configuration for FastAPI
def rate_limit_key_func(request: Request) -> str:
    """Generate rate limit key from request"""
    # Try to get user ID from token if authenticated
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Fallback to IP address
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(key_func=rate_limit_key_func)


async def rate_limit_middleware(request: Request, call_next: Callable):
    """Custom rate limiting middleware"""
    
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/", "/docs", "/redoc"]:
        return await call_next(request)
    
    rate_limiter = get_active_rate_limiter()
    client_key = rate_limit_key_func(request)
    
    # Different limits for different endpoints
    if request.url.path.startswith("/auth"):
        # Stricter limits for auth endpoints
        limit, window = 5, 60  # 5 requests per minute
    elif request.url.path.startswith("/chats") and request.method == "POST":
        # Moderate limits for chat creation and messaging
        limit, window = 30, 60  # 30 requests per minute
    else:
        # General API limits
        limit, window = 100, 60  # 100 requests per minute
    
    is_allowed = await rate_limiter.is_allowed(client_key, limit, window)
    
    if not is_allowed:
        security_logger.warning(
            "Rate limit exceeded",
            client=client_key,
            path=request.url.path,
            method=request.method
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {limit} requests per {window} seconds."
        )
    
    return await call_next(request)


# Rate limit error handler
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    security_logger.warning(
        "SlowAPI rate limit exceeded",
        client=rate_limit_key_func(request),
        path=request.url.path
    )
    return _rate_limit_exceeded_handler(request, exc) 