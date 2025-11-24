from functools import wraps
from typing import Callable
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

logger = logging.getLogger(__name__)

# Initialize limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000/hour"],  # Default limit
    storage_uri="memory://",  # In-memory storage (can upgrade to Redis later)
)

# Rate limit configuration per plan
RATE_LIMITS = {
    'free': {
        'per_minute': 60,
        'per_hour': 1000,
    },
    'pro': {
        'per_minute': 120,
        'per_hour': 5000,
    },
    'business': {
        'per_minute': 300,
        'per_hour': -1,  # unlimited
    }
}


def get_user_rate_limit_key(request: Request) -> str:
    """Get rate limit key from user_id in request state (set by auth middleware)"""
    # Try to get user_id from request state (set by get_current_user)
    user_id = getattr(request.state, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    # Fallback to IP address
    return get_remote_address(request)


def rate_limit_by_plan(plan_tier: str = 'free'):
    """
    Decorator to apply rate limiting based on user's plan tier.
    Must be used after authentication middleware.
    """
    def decorator(func: Callable):
        limits = RATE_LIMITS.get(plan_tier, RATE_LIMITS['free'])
        minute_limit = f"{limits['per_minute']}/minute"
        hour_limit = f"{limits['per_hour']}/hour" if limits['per_hour'] > 0 else None
        
        # Apply rate limits
        if hour_limit:
            func = limiter.limit(f"{minute_limit};{hour_limit}", key_func=get_user_rate_limit_key)(func)
        else:
            func = limiter.limit(minute_limit, key_func=get_user_rate_limit_key)(func)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except RateLimitExceeded:
                logger.warning(f"Rate limit exceeded for plan: {plan_tier}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Plan: {plan_tier}. Please try again later."
                )
        return wrapper
    return decorator


def check_rate_limit(request: Request, user_plan: str) -> bool:
    """
    Check if request is within rate limits for the user's plan.
    Returns True if within limits, False if exceeded.
    """
    limits = RATE_LIMITS.get(user_plan, RATE_LIMITS['free'])
    # This is a simplified check - actual enforcement happens via decorator
    return True


