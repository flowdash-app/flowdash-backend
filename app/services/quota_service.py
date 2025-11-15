from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.quota import Quota
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.subscription_service import PlanConfiguration
from datetime import date
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
                
                limit = PlanConfiguration.get_limit(user.plan_tier, plan_limit_key)
            
            # If limit is -1, it's unlimited for this plan
            if limit == -1:
                self.logger.info(f"check_quota: Unlimited - user: {user_id}, type: {quota_type}, plan: {user.plan_tier}")
                return True
            
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
            plan_config = PlanConfiguration.get_plan(user.plan_tier)
            
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

