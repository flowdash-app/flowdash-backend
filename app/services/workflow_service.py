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
        user_id: str,
        limit: int = 100,
        cursor: str | None = None,
        active: bool | None = None
    ) -> dict:
        """
        Get workflows from n8n instance with pagination support.
        Returns: {data: list[dict], nextCursor: str | None}
        """
        self.logger.info(f"get_workflows: Entry - instance: {instance_id}, user: {user_id}, limit: {limit}, cursor: {cursor}, active: {active}")
        
        try:
            # Validate limit (n8n API max is 250)
            if limit > 250:
                limit = 250
            elif limit < 1:
                limit = 100
            
            # Get instance and verify ownership
            instance = self.instance_service.get_instance(db, instance_id, user_id)
            
            # Check if instance is enabled before fetching workflows
            if not instance.enabled:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Instance is disabled. Please enable the instance to fetch workflows."
                )
            
            api_key = self.instance_service.get_decrypted_api_key(instance)
            
            # Build query parameters
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            if active is not None:
                params["active"] = str(active).lower()
            
            # Call n8n API
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.get(
                    f"{instance.url}/api/v1/workflows",
                    headers={"X-N8N-API-KEY": api_key},
                    params=params,
                    timeout=30.0
                )
                
                # Check for redirects (e.g., Cloudflare Access)
                if response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = response.headers.get('Location', 'unknown')
                    self.logger.warning(
                        f"get_workflows: n8n instance returned redirect {response.status_code} to {redirect_location}. "
                        "This usually indicates the instance is behind Cloudflare Access or similar authentication."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"n8n instance returned redirect. The instance may be behind Cloudflare Access or require additional authentication. Redirect location: {redirect_location}"
                    )
                
                response.raise_for_status()
                result = response.json()
            
            # Handle n8n API response structure
            # n8n returns: {data: [...], nextCursor: "..."} or just array for older versions
            if isinstance(result, list):
                # Legacy format - return as array, no pagination
                workflows_data = result
                next_cursor = None
            else:
                # New format with pagination
                workflows_data = result.get("data", [])
                next_cursor = result.get("nextCursor")
            
            self.analytics.log_success(
                action='get_workflows',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_count': len(workflows_data),
                    'has_next': next_cursor is not None
                }
            )
            self.logger.info(f"get_workflows: Success - instance: {instance_id}, count: {len(workflows_data)}, has_next: {next_cursor is not None}")
            
            return {
                "data": workflows_data,
                "nextCursor": next_cursor
            }
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
            
            # Check if instance is enabled before toggling workflows
            if not instance.enabled:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Instance is disabled. Please enable the instance to toggle workflows."
                )
            
            api_key = self.instance_service.get_decrypted_api_key(instance)
            
            # Call n8n API to toggle workflow
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.post(
                    f"{instance.url}/api/v1/workflows/{workflow_id}/activate",
                    headers={"X-N8N-API-KEY": api_key},
                    json={"active": enabled},
                    timeout=30.0
                )
                
                # Check for redirects (e.g., Cloudflare Access)
                if response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = response.headers.get('Location', 'unknown')
                    self.logger.warning(
                        f"toggle_workflow: n8n instance returned redirect {response.status_code} to {redirect_location}. "
                        "This usually indicates the instance is behind Cloudflare Access or similar authentication."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"n8n instance returned redirect. The instance may be behind Cloudflare Access or require additional authentication. Redirect location: {redirect_location}"
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
                meta_data=json.dumps({
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
    
    async def get_executions(
        self,
        db: Session,
        instance_id: str,
        user_id: str,
        workflow_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
        status: str | None = None
    ) -> dict:
        """
        Get executions from n8n instance with pagination support.
        Returns: {data: list[dict], nextCursor: str | None}
        """
        self.logger.info(f"get_executions: Entry - instance: {instance_id}, user: {user_id}, workflow_id: {workflow_id}, limit: {limit}, cursor: {cursor}, status: {status}")
        
        try:
            # Validate limit (n8n API max is 250, default is 20)
            if limit > 250:
                limit = 250
            elif limit < 1:
                limit = 20
            
            # Get instance and verify ownership
            instance = self.instance_service.get_instance(db, instance_id, user_id)
            
            # Check if instance is enabled before fetching executions
            if not instance.enabled:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Instance is disabled. Please enable the instance to fetch executions."
                )
            
            api_key = self.instance_service.get_decrypted_api_key(instance)
            
            # Build query parameters
            params = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            if workflow_id:
                params["workflowId"] = workflow_id
            if status:
                params["status"] = status
            
            # Call n8n API
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.get(
                    f"{instance.url}/api/v1/executions",
                    headers={"X-N8N-API-KEY": api_key},
                    params=params,
                    timeout=30.0
                )
                
                # Check for redirects (e.g., Cloudflare Access)
                if response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = response.headers.get('Location', 'unknown')
                    self.logger.warning(
                        f"get_executions: n8n instance returned redirect {response.status_code} to {redirect_location}. "
                        "This usually indicates the instance is behind Cloudflare Access or similar authentication."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"n8n instance returned redirect. The instance may be behind Cloudflare Access or require additional authentication. Redirect location: {redirect_location}"
                    )
                
                response.raise_for_status()
                result = response.json()
            
            # Handle n8n API response structure
            # n8n returns: {data: [...], nextCursor: "..."} or just array for older versions
            if isinstance(result, list):
                # Legacy format - return as array, no pagination
                executions_data = result
                next_cursor = None
            else:
                # New format with pagination
                executions_data = result.get("data", [])
                next_cursor = result.get("nextCursor")
            
            self.analytics.log_success(
                action='get_executions',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'execution_count': len(executions_data),
                    'has_next': next_cursor is not None
                }
            )
            self.logger.info(f"get_executions: Success - instance: {instance_id}, count: {len(executions_data)}, has_next: {next_cursor is not None}")
            
            return {
                "data": executions_data,
                "nextCursor": next_cursor
            }
        except httpx.HTTPError as e:
            self.analytics.log_failure(
                action='get_executions',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id, 'workflow_id': workflow_id}
            )
            self.logger.error(f"get_executions: Failure - {e}")
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='get_executions',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id, 'workflow_id': workflow_id}
            )
            self.logger.error(f"get_executions: Failure - {e}")
            raise
    
    async def get_execution_by_id(
        self,
        db: Session,
        instance_id: str,
        execution_id: str,
        user_id: str,
        include_data: bool = True
    ) -> dict:
        """Get execution details by ID
        
        Args:
            db: Database session
            instance_id: n8n instance ID
            execution_id: Execution ID
            user_id: User ID for ownership verification
            include_data: Whether to include the execution's detailed data (default True)
        """
        self.logger.info(f"get_execution_by_id: Entry - instance: {instance_id}, execution: {execution_id}, user: {user_id}, include_data: {include_data}")
        
        try:
            # Get instance and verify ownership
            instance = self.instance_service.get_instance(db, instance_id, user_id)
            
            # Check if instance is enabled before fetching execution
            if not instance.enabled:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Instance is disabled. Please enable the instance to fetch execution details."
                )
            
            api_key = self.instance_service.get_decrypted_api_key(instance)
            
            # Call n8n API with includeData parameter
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.get(
                    f"{instance.url}/api/v1/executions/{execution_id}",
                    headers={"X-N8N-API-KEY": api_key},
                    params={"includeData": include_data},
                    timeout=30.0
                )
                
                # Check for redirects (e.g., Cloudflare Access)
                if response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = response.headers.get('Location', 'unknown')
                    self.logger.warning(
                        f"get_execution_by_id: n8n instance returned redirect {response.status_code} to {redirect_location}. "
                        "This usually indicates the instance is behind Cloudflare Access or similar authentication."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"n8n instance returned redirect. The instance may be behind Cloudflare Access or require additional authentication. Redirect location: {redirect_location}"
                    )
                
                response.raise_for_status()
                result = response.json()
            
            self.analytics.log_success(
                action='get_execution_by_id',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                }
            )
            self.logger.info(f"get_execution_by_id: Success - execution: {execution_id}")
            
            return result
        except httpx.HTTPError as e:
            self.analytics.log_failure(
                action='get_execution_by_id',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id, 'execution_id': execution_id}
            )
            self.logger.error(f"get_execution_by_id: Failure - {e}")
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='get_execution_by_id',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id, 'execution_id': execution_id}
            )
            self.logger.error(f"get_execution_by_id: Failure - {e}")
            raise

