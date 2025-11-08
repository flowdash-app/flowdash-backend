from sqlalchemy.orm import Session
from app.services.instance_service import InstanceService
from app.services.quota_service import QuotaService
from app.services.analytics_service import AnalyticsService
from app.models.audit_log import AuditLog
import httpx
import uuid
import logging
import json

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self):
        self.instance_service = InstanceService()
        self.quota_service = QuotaService()
        self.analytics = AnalyticsService()
        self.logger = logging.getLogger(__name__)
    
    async def get_workflows(
        self,
        db: Session,
        instance_id: str,
        user_id: str
    ) -> list[dict]:
        """Get workflows from n8n instance"""
        self.logger.info(f"get_workflows: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            # Get instance and verify ownership
            instance = self.instance_service.get_instance(db, instance_id, user_id)
            api_key = self.instance_service.get_decrypted_api_key(instance)
            
            # Call n8n API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{instance.url}/api/v1/workflows",
                    headers={"X-N8N-API-KEY": api_key},
                    timeout=30.0
                )
                response.raise_for_status()
                workflows = response.json()
            
            self.analytics.log_success(
                action='get_workflows',
                user_id=user_id,
                parameters={'instance_id': instance_id, 'workflow_count': len(workflows)}
            )
            self.logger.info(f"get_workflows: Success - instance: {instance_id}, count: {len(workflows)}")
            return workflows
        except httpx.HTTPError as e:
            self.analytics.log_failure(
                action='get_workflows',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"get_workflows: Failure - {e}")
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='get_workflows',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"get_workflows: Failure - {e}")
            raise
    
    async def toggle_workflow(
        self,
        db: Session,
        instance_id: str,
        workflow_id: str,
        enabled: bool,
        user_id: str
    ) -> dict:
        """Toggle workflow on/off"""
        self.logger.info(f"toggle_workflow: Entry - user: {user_id}, workflow: {workflow_id}, enabled: {enabled}")
        
        try:
            # Check quota
            if not self.quota_service.check_quota(db, user_id, 'toggles', limit=100):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily toggle quota exceeded"
                )
            
            # Get instance and verify ownership
            instance = self.instance_service.get_instance(db, instance_id, user_id)
            api_key = self.instance_service.get_decrypted_api_key(instance)
            
            # Call n8n API to toggle workflow
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{instance.url}/api/v1/workflows/{workflow_id}/activate",
                    headers={"X-N8N-API-KEY": api_key},
                    json={"active": enabled},
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
            
            # Increment quota
            self.quota_service.increment_quota(db, user_id, 'toggles')
            
            # Create audit log
            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                action='toggle_workflow',
                resource_type='workflow',
                resource_id=workflow_id,
                metadata=json.dumps({
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'enabled': enabled
                })
            )
            db.add(audit_log)
            db.commit()
            
            self.analytics.log_success(
                action='toggle_workflow',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'enabled': enabled,
                }
            )
            self.logger.info(f"toggle_workflow: Success - workflow: {workflow_id}, enabled: {enabled}")
            return result
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='toggle_workflow',
                error=str(e),
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'enabled': enabled,
                }
            )
            self.logger.error(f"toggle_workflow: Failure - {e}")
            raise

