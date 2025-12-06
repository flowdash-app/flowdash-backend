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
        limit: int = None
    ) -> bool:
        self.logger.info(f"check_quota: Entry - user: {user_id}, type: {quota_type}")
        
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            if user.is_tester:
                self.logger.info(f"check_quota: Unlimited (tester) - user: {user_id}, type: {quota_type}")
                return True
            
            if limit is None:
                quota_type_map = {
                    'toggles': 'toggles_per_day',
                    'refreshes': 'refreshes_per_day',
                    'error_views': 'error_views_per_day',
                }
                plan_limit_key = quota_type_map.get(quota_type)
                if not plan_limit_key:
                    raise ValueError(f"Unknown quota type: {quota_type}")
                
                limit = PlanConfiguration.get_limit(db, user.plan_tier, plan_limit_key)
            
            if limit == -1:
                self.logger.info(f"check_quota: Unlimited - user: {user_id}, type: {quota_type}, plan: {user.plan_tier}")
                return True
            
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
        self.logger.info(f"get_quota_status: Entry - user: {user_id}")
        
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            today = date.today()
            plan_config = PlanConfiguration.get_plan(db, user.plan_tier)
            
            result = {
                'plan_tier': user.plan_tier,
                'quotas': {}
            }
            
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
                    'remaining': limit - current_count if limit != -1 else -1,
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
            
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.plan_tier == 'free':
                self._increment_hourly_quota(user_id, quota_type)
            
            db.commit()
            self.analytics.log_success(
                action='increment_quota',
                user_id=user_id,
                parameters={'quota_type': quota_type}
            )
            self.logger.info(f"increment_quota: Success - user: {user_id}, type: {quota_type}")
            return quota.count
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

    def reset_quota(self, db: Session, user_id: str, quota_type: str = None, quota_date: date = None):
        """
        Reset quota counts for a user by setting count to 0.

        Args:
            db: Database session.
            user_id: User ID (Firebase UID).
            quota_type: Specific quota type to reset. Defaults to None (all types).
            quota_date: Target date for reset. Defaults to today.

        Returns:
            int: Number of rows updated.
        """
        self.logger.info(f"reset_quota: Entry - user: {user_id}, type: {quota_type}, date: {quota_date}")
        
        try:
            if not quota_date:
                quota_date = date.today()

            query = db.query(Quota).filter(
                and_(
                    Quota.user_id == user_id,
                    Quota.quota_date == quota_date
                )
            )

            if quota_type:
                query = query.filter(Quota.quota_type == quota_type)

            rows_updated = query.update({"count": 0})
            db.commit()

            self.logger.info(f"reset_quota: Success - user: {user_id}, rows updated: {rows_updated}")
            return rows_updated
        except Exception as e:
            db.rollback()
            self.logger.error(f"reset_quota: Failure - {e}")
            raise

    def _get_hourly_sub_limit(self, quota_type: str, daily_limit: int) -> int:
        try:
            if daily_limit <= 0:
                return 0
            hourly = max(1, int(daily_limit * 0.25))
            return hourly
        except Exception:
            return 0

    def _check_hourly_quota(self, user_id: str, quota_type: str, hourly_limit: int) -> bool:
        try:
            cache = get_cache()
            key = f"hourly_quota:{user_id}:{quota_type}"
            val = cache.get(key)
            if val is None:
                return True
            return int(val) < hourly_limit
        except Exception:
            return True

    def _increment_hourly_quota(self, user_id: str, quota_type: str):
        try:
            cache = get_cache()
            key = f"hourly_quota:{user_id}:{quota_type}"
            val = cache.get(key) or 0
            cache.set(key, int(val) + 1, ex=3600)
        except Exception:
            pass
