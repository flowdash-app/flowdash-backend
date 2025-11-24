from sqlalchemy.orm import Session
from app.models.n8n_instance import N8NInstance
from app.models.user import User
from app.core.security import encrypt_api_key, decrypt_api_key
from app.services.analytics_service import AnalyticsService
from app.services.subscription_service import PlanConfiguration
from app.core.cache import get_cache
from datetime import datetime
from fastapi import HTTPException, status
import uuid
import logging

logger = logging.getLogger(__name__)


class InstanceService:
    def __init__(self):
        self.analytics = AnalyticsService()
        self.logger = logging.getLogger(__name__)
    
    def get_instance(self, db: Session, instance_id: str, user_id: str) -> N8NInstance:
        """Get n8n instance by ID, ensuring user owns it"""
        self.logger.info(f"get_instance: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            instance = db.query(N8NInstance).filter(
                N8NInstance.id == instance_id,
                N8NInstance.user_id == user_id
            ).first()
            
            if not instance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Instance not found"
                )
            
            self.analytics.log_success(
                action='get_instance',
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.info(f"get_instance: Success - instance: {instance_id}")
            return instance
        except HTTPException:
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='get_instance',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"get_instance: Failure - {e}")
            raise
    
    def get_instance_by_id(self, db: Session, instance_id: str) -> N8NInstance:
        """Get n8n instance by ID only (for webhooks)"""
        self.logger.info(f"get_instance_by_id: Entry - instance: {instance_id}")
        
        try:
            instance = db.query(N8NInstance).filter(
                N8NInstance.id == instance_id
            ).first()
            
            if not instance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Instance not found"
                )
            
            self.logger.info(f"get_instance_by_id: Success - instance: {instance_id}")
            return instance
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"get_instance_by_id: Failure - {e}")
            raise
    
    def list_instances(self, db: Session, user_id: str) -> list[N8NInstance]:
        """List all n8n instances for a user"""
        self.logger.info(f"list_instances: Entry - user: {user_id}")
        
        try:
            instances = db.query(N8NInstance).filter(
                N8NInstance.user_id == user_id
            ).all()
            
            self.analytics.log_success(
                action='list_instances',
                user_id=user_id,
                parameters={'count': len(instances)}
            )
            self.logger.info(f"list_instances: Success - user: {user_id}, count: {len(instances)}")
            return instances
        except Exception as e:
            self.analytics.log_failure(
                action='list_instances',
                error=str(e),
                user_id=user_id
            )
            self.logger.error(f"list_instances: Failure - {e}")
            raise
    
    def create_instance(
        self,
        db: Session,
        user_id: str,
        name: str,
        url: str,
        api_key: str,
        enabled: bool = True
    ) -> N8NInstance:
        """Create a new n8n instance"""
        self.logger.info(f"create_instance: Entry - user: {user_id}, name: {name}, enabled: {enabled}")
        
        try:
            # Ensure user exists
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                # Create user if doesn't exist
                user = User(
                    id=user_id,
                    email="",  # Will be updated from token
                    is_active=True
                )
                db.add(user)
                db.flush()
            
            # Testers get unlimited instances
            if not user.is_tester:
                # Check instance limit based on plan
                existing_instances = db.query(N8NInstance).filter(
                    N8NInstance.user_id == user_id
                ).count()
                
                plan_config = PlanConfiguration.get_plan(db, user.plan_tier)
                max_instances = plan_config.get('max_instances', 1)
                
                if max_instances != -1 and existing_instances >= max_instances:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Instance limit reached. Your {plan_config['name']} plan allows {max_instances} instance(s). Upgrade to add more instances."
                    )
                
                # Check rate limit for free users (max 1 creation per day)
                if user.plan_tier == 'free':
                if not self._check_instance_creation_rate_limit(user_id):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Free users can create 1 instance per day. Please try again tomorrow or upgrade your plan."
                    )
            
            # Encrypt API key
            encrypted_key = encrypt_api_key(api_key)
            
            instance = N8NInstance(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=name,
                url=url,
                api_key_encrypted=encrypted_key,
                enabled=enabled
            )
            
            db.add(instance)
            db.commit()
            db.refresh(instance)
            
            # Increment instance creation count for free users
            if user.plan_tier == 'free':
                self._increment_instance_creation_count(user_id)
            
            self.analytics.log_success(
                action='create_instance',
                user_id=user_id,
                parameters={'instance_id': instance.id, 'name': name}
            )
            self.logger.info(f"create_instance: Success - instance: {instance.id}")
            return instance
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='create_instance',
                error=str(e),
                user_id=user_id,
                parameters={'name': name, 'url': url}
            )
            self.logger.error(f"create_instance: Failure - {e}")
            raise
    
    def update_instance(
        self,
        db: Session,
        instance_id: str,
        user_id: str,
        name: str = None,
        url: str = None,
        api_key: str = None,
        enabled: bool = None
    ) -> N8NInstance:
        """Update an existing n8n instance"""
        self.logger.info(f"update_instance: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            instance = self.get_instance(db, instance_id, user_id)
            
            if name is not None:
                instance.name = name
            if url is not None:
                instance.url = url
            if api_key is not None:
                instance.api_key_encrypted = encrypt_api_key(api_key)
            if enabled is not None:
                instance.enabled = enabled
            
            db.commit()
            db.refresh(instance)
            
            self.analytics.log_success(
                action='update_instance',
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.info(f"update_instance: Success - instance: {instance_id}")
            return instance
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='update_instance',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"update_instance: Failure - {e}")
            raise
    
    def delete_instance(self, db: Session, instance_id: str, user_id: str):
        """Delete an n8n instance"""
        self.logger.info(f"delete_instance: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            instance = self.get_instance(db, instance_id, user_id)
            db.delete(instance)
            db.commit()
            
            self.analytics.log_success(
                action='delete_instance',
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.info(f"delete_instance: Success - instance: {instance_id}")
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='delete_instance',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"delete_instance: Failure - {e}")
            raise
    
    def _check_instance_creation_rate_limit(self, user_id: str) -> bool:
        """Check if free user can create instance (max 1 per day)."""
        cache = get_cache()
        today = datetime.utcnow().date().isoformat()
        cache_key = f"instance_creation:{user_id}:{today}"
        
        cached_count = cache.get(cache_key)
        if cached_count is None:
            cached_count = 0
        
        # Free users: max 1 creation per day
        if cached_count >= 1:
            return False
        
        # Increment count (will be set when instance is successfully created)
        return True
    
    def _increment_instance_creation_count(self, user_id: str):
        """Increment instance creation count for rate limiting."""
        cache = get_cache()
        today = datetime.utcnow().date().isoformat()
        cache_key = f"instance_creation:{user_id}:{today}"
        
        cached_count = cache.get(cache_key)
        if cached_count is None:
            cached_count = 0
        
        # Store for 24 hours (until end of day)
        hours_until_midnight = 24 - datetime.utcnow().hour
        cache.set(cache_key, cached_count + 1, ttl_minutes=hours_until_midnight * 60)
    
    def get_decrypted_api_key(self, instance: N8NInstance) -> str:
        """Get decrypted API key for an instance"""
        return decrypt_api_key(instance.api_key_encrypted)

