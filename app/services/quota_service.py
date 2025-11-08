from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.quota import Quota
from app.services.analytics_service import AnalyticsService
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
        limit: int
    ) -> bool:
        """Check if user has quota available"""
        self.logger.info(f"check_quota: Entry - user: {user_id}, type: {quota_type}, limit: {limit}")
        
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
                self.logger.info(f"check_quota: Quota exceeded - user: {user_id}, type: {quota_type}")
                return False
            
            self.logger.info(f"check_quota: Success - user: {user_id}, type: {quota_type}, count: {quota.count}/{limit}")
            return True
        except Exception as e:
            self.analytics.log_failure(
                action='check_quota',
                error=str(e),
                user_id=user_id,
                parameters={'quota_type': quota_type, 'limit': limit}
            )
            self.logger.error(f"check_quota: Failure - {e}")
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

