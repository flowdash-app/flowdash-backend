from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.firebase import verify_firebase_token
from app.core.database import get_db
from app.models.user import User
from app.core.cache import get_cache
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Rate limit configuration per plan
RATE_LIMITS = {
    'free': {
        'per_minute': 60,
        'per_hour': 1000,
    },
    'pro': {
        'per_minute': 120,
        'per_hour': 5000,
    }
}

# Default rate limits for unauthenticated requests (IP-based)
DEFAULT_IP_LIMITS = {
    'per_minute': 30,
    'per_hour': 500,
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting based on user plan or IP address.
    Prevents code duplication by automatically applying limits to all requests.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.cache = get_cache()
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check and other public endpoints
        if request.url.path in ['/health', '/docs', '/openapi.json', '/redoc']:
            return await call_next(request)
        
        # Skip rate limiting for webhook endpoints (they have their own validation)
        if request.url.path.startswith('/api/v1/webhooks'):
            return await call_next(request)
        
        # Get user info from token if available
        user_id = None
        user_plan = None
        is_authenticated = False
        
        # Try to extract user from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(' ')[1]
                decoded_token = verify_firebase_token(token)
                user_id = decoded_token.get('uid')
                
                if user_id:
                    # Get user plan from database
                    # Use a generator to get db session
                    db_gen = get_db()
                    db = next(db_gen)
                    try:
                        user = db.query(User).filter(User.id == user_id).first()
                        if user:
                            user_plan = user.plan_tier
                            is_authenticated = True
                            # Store in request state for later use
                            request.state.user_id = user_id
                            request.state.user_plan = user_plan
                            request.state.user = user  # Store user object for tester check
                    finally:
                        db.close()
            except Exception as e:
                # If token verification fails, continue without rate limiting
                # The auth dependency will handle the error later
                logger.debug(f"Rate limit middleware: Could not verify token: {e}")
        
        # Apply rate limiting
        if is_authenticated and user_plan:
            # Testers get unlimited access - bypass rate limiting
            user = getattr(request.state, 'user', None)
            if user and user.is_tester:
                logger.debug(f"Rate limit bypassed (tester) - user: {user_id}")
                return await call_next(request)
            
            # User-based rate limiting
            if not self._check_user_rate_limit(user_id, user_plan, request):
                limits = RATE_LIMITS.get(user_plan, RATE_LIMITS['free'])
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": f"Rate limit exceeded. Your {user_plan} plan allows {limits['per_minute']} requests per minute. Please try again later.",
                        "retry_after": 60
                    },
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(limits['per_minute']),
                        "X-RateLimit-Remaining": "0",
                    }
                )
        else:
            # IP-based rate limiting for unauthenticated requests
            client_ip = self._get_client_ip(request)
            if not self._check_ip_rate_limit(client_ip, request):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Please authenticate or try again later.",
                        "retry_after": 60
                    },
                    headers={
                        "Retry-After": "60",
                    }
                )
        
        # Continue with the request
        response = await call_next(request)
        
        # Add rate limit headers to response
        if is_authenticated and user_plan:
            limits = RATE_LIMITS.get(user_plan, RATE_LIMITS['free'])
            remaining = self._get_remaining_requests(user_id, user_plan)
            response.headers["X-RateLimit-Limit"] = str(limits['per_minute'])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int((datetime.utcnow() + timedelta(minutes=1)).timestamp()))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded IP (from proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _check_user_rate_limit(self, user_id: str, user_plan: str, request: Request) -> bool:
        """Check if user is within rate limits for their plan"""
        limits = RATE_LIMITS.get(user_plan, RATE_LIMITS['free'])
        
        # Check per-minute limit
        current_minute = datetime.utcnow().replace(second=0, microsecond=0)
        minute_key = f"rate_limit:user:{user_id}:minute:{current_minute.isoformat()}"
        minute_count = self.cache.get_int(minute_key) or 0
        
        if minute_count >= limits['per_minute']:
            logger.warning(f"Rate limit exceeded (per minute) - user: {user_id}, plan: {user_plan}")
            return False
        
        # Check per-hour limit (if not unlimited)
        if limits['per_hour'] > 0:
            current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            hour_key = f"rate_limit:user:{user_id}:hour:{current_hour.isoformat()}"
            hour_count = self.cache.get_int(hour_key) or 0
            
            if hour_count >= limits['per_hour']:
                logger.warning(f"Rate limit exceeded (per hour) - user: {user_id}, plan: {user_plan}")
                return False
            
            # Increment hour counter
            self.cache.set(hour_key, hour_count + 1, ttl_minutes=60)
        
        # Increment minute counter
        self.cache.set(minute_key, minute_count + 1, ttl_minutes=1)
        
        return True
    
    def _check_ip_rate_limit(self, client_ip: str, request: Request) -> bool:
        """Check if IP address is within rate limits"""
        limits = DEFAULT_IP_LIMITS
        
        # Check per-minute limit
        current_minute = datetime.utcnow().replace(second=0, microsecond=0)
        minute_key = f"rate_limit:ip:{client_ip}:minute:{current_minute.isoformat()}"
        minute_count = self.cache.get_int(minute_key) or 0
        
        if minute_count >= limits['per_minute']:
            logger.warning(f"Rate limit exceeded (per minute) - IP: {client_ip}")
            return False
        
        # Check per-hour limit
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        hour_key = f"rate_limit:ip:{client_ip}:hour:{current_hour.isoformat()}"
        hour_count = self.cache.get_int(hour_key) or 0
        
        if hour_count >= limits['per_hour']:
            logger.warning(f"Rate limit exceeded (per hour) - IP: {client_ip}")
            return False
        
        # Increment counters
        self.cache.set(minute_key, minute_count + 1, ttl_minutes=1)
        self.cache.set(hour_key, hour_count + 1, ttl_minutes=60)
        
        return True
    
    def _get_remaining_requests(self, user_id: str, user_plan: str) -> int:
        """Get remaining requests for the current minute"""
        limits = RATE_LIMITS.get(user_plan, RATE_LIMITS['free'])
        current_minute = datetime.utcnow().replace(second=0, microsecond=0)
        minute_key = f"rate_limit:user:{user_id}:minute:{current_minute.isoformat()}"
        minute_count = self.cache.get_int(minute_key) or 0
        return max(0, limits['per_minute'] - minute_count - 1)

