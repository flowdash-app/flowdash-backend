from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.quota import Quota
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.subscription_service import PlanConfiguration
from app.core.cache import get_cache
from datetime import date, datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class QuotaService:
    def __init__(self):
        self.analytics = AnalyticsService()
        self.logger = logging.getLogger(__name__)
    
    def check_quota(
        self,
        db: Session,
        user_id: str,
        quota_type: str,
        limit: int = None  # Optional - will use plan limit if not specified
    ) -> bool:
        """
        Check if user has quota available.
        If limit is not provided, uses the limit from user's plan tier.
        Returns True if quota available, False if exceeded.
        """
        self.logger.info(f"check_quota: Entry - user: {user_id}, type: {quota_type}")
        
        try:
            # Get user's plan tier
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Testers get unlimited access (treated as Business tier)
            if user.is_tester:
                self.logger.info(f"check_quota: Unlimited (tester) - user: {user_id}, type: {quota_type}")
                return True
            
            # Get limit from plan if not specified
            if limit is None:
                # Map quota_type to plan configuration key
                quota_type_map = {
                    'toggles': 'toggles_per_day',
                    'refreshes': 'refreshes_per_day',
                    'error_views': 'error_views_per_day',
                }
                plan_limit_key = quota_type_map.get(quota_type)
                if not plan_limit_key:
                    raise ValueError(f"Unknown quota type: {quota_type}")
                
                limit = PlanConfiguration.get_limit(db, user.plan_tier, plan_limit_key)
            
            # If limit is -1, it's unlimited for this plan
            if limit == -1:
                self.logger.info(f"check_quota: Unlimited - user: {user_id}, type: {quota_type}, plan: {user.plan_tier}")
                return True
            
            # Check hourly sub-limits for free users (prevent burst abuse)
            if user.plan_tier == 'free':
                hourly_limit = self._get_hourly_sub_limit(quota_type, limit)
                if hourly_limit > 0:
                    if not self._check_hourly_quota(user_id, quota_type, hourly_limit):
                        self.logger.info(f"check_quota: Hourly sub-limit exceeded - user: {user_id}, type: {quota_type}")
                        return False
            
            today = date.today()
            quota = db.query(Quota).filter(
                and_(
                    Quota.user_id == user_id,
                    Quota.quota_type == quota_type,
                    Quota.quota_date == today
                )
            ).first()
            
            if not quota:
                # Create new quota for today
                quota = Quota(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    quota_type=quota_type,
                    quota_date=today,
                    count=0
                )
                db.add(quota)
            
            if quota.count >= limit:
                self.logger.info(f"check_quota: Quota exceeded - user: {user_id}, type: {quota_type}, plan: {user.plan_tier}")
                return False
            
            self.logger.info(f"check_quota: Success - user: {user_id}, type: {quota_type}, count: {quota.count}/{limit}, plan: {user.plan_tier}")
            return True
        except Exception as e:
            self.analytics.log_failure(
                action='check_quota',
                error=str(e),
                user_id=user_id,
                parameters={'quota_type': quota_type}
            )
            self.logger.error(f"check_quota: Failure - {e}")
            raise
    
    def get_quota_status(self, db: Session, user_id: str) -> dict:
        """Get current quota usage for all quota types"""
        self.logger.info(f"get_quota_status: Entry - user: {user_id}")
        
        try:
            # Get user's plan tier
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            today = date.today()
            plan_config = PlanConfiguration.get_plan(db, user.plan_tier)
            
            result = {
                'plan_tier': user.plan_tier,
                'quotas': {}
            }
            
            # Check each quota type
            quota_types = {
                'toggles': 'toggles_per_day',
                'refreshes': 'refreshes_per_day',
                'error_views': 'error_views_per_day',
            }
            
            for quota_type, plan_key in quota_types.items():
                limit = plan_config.get(plan_key, 0)
                
                quota = db.query(Quota).filter(
                    and_(
                        Quota.user_id == user_id,
                        Quota.quota_type == quota_type,
                        Quota.quota_date == today
                    )
                ).first()
                
                current_count = quota.count if quota else 0
                
                result['quotas'][quota_type] = {
                    'used': current_count,
                    'limit': limit,
                    'remaining': limit - current_count if limit != -1 else -1,  # -1 = unlimited
                    'unlimited': limit == -1
                }
            
            self.logger.info(f"get_quota_status: Success - user: {user_id}")
            return result
        except Exception as e:
            self.analytics.log_failure(
                action='get_quota_status',
                error=str(e),
                user_id=user_id
            )
            self.logger.error(f"get_quota_status: Failure - {e}")
            raise
    
    def increment_quota(
        self,
        db: Session,
        user_id: str,
        quota_type: str
    ):
        """Increment quota count atomically"""
        self.logger.info(f"increment_quota: Entry - user: {user_id}, type: {quota_type}")
        
        try:
            today = date.today()
            quota = db.query(Quota).filter(
                and_(
                    Quota.user_id == user_id,
                    Quota.quota_type == quota_type,
                    Quota.quota_date == today
                )
            ).first()
            
            if not quota:
                quota = Quota(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    quota_type=quota_type,
                    quota_date=today,
                    count=1
                )
                db.add(quota)
            else:
                quota.count += 1
            
            # Increment hourly quota for free users (not testers)
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.plan_tier == 'free' and not user.is_tester:
                self._increment_hourly_quota(user_id, quota_type)
            
            db.commit()
            
            self.analytics.log_success(
                action='increment_quota',
                user_id=user_id,
                parameters={'quota_type': quota_type, 'count': quota.count}
            )
            self.logger.info(f"increment_quota: Success - user: {user_id}, type: {quota_type}, count: {quota.count}")
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='increment_quota',
                error=str(e),
                user_id=user_id,
                parameters={'quota_type': quota_type}
            )
            self.logger.error(f"increment_quota: Failure - {e}")
            raise
    
    def _get_hourly_sub_limit(self, quota_type: str, daily_limit: int) -> int:
        """Get hourly sub-limit for free users to prevent burst abuse."""
        # For free users: enforce hourly sub-limits
        # 0 toggles/day = no hourly limit needed (read-only)
        # 5 refreshes/day = max 2 refreshes/hour
        # 3 error views/day = max 1 error view/hour
        hourly_limits = {
            'toggles': 0,  # Read-only, no hourly limit
            'refreshes': 2,  # Max 2 per hour
            'error_views': 1,  # Max 1 per hour
        }
        return hourly_limits.get(quota_type, 0)
    
    def _check_hourly_quota(self, user_id: str, quota_type: str, hourly_limit: int) -> bool:
        """Check if user is within hourly quota limit using cache."""
        cache = get_cache()
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        cache_key = f"quota_hourly:{user_id}:{quota_type}:{current_hour.isoformat()}"
        
        cached_count = cache.get(cache_key)
        if cached_count is None:
            cached_count = 0
        
        if cached_count >= hourly_limit:
            return False
        
        return True
    
    def _increment_hourly_quota(self, user_id: str, quota_type: str):
        """Increment hourly quota count in cache."""
        cache = get_cache()
        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        cache_key = f"quota_hourly:{user_id}:{quota_type}:{current_hour.isoformat()}"
        
        cached_count = cache.get(cache_key)
        if cached_count is None:
            cached_count = 0
        
        # Increment and store for 1 hour
        cache.set(cache_key, cached_count + 1, ttl_minutes=60)

