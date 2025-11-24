import json
import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.cache import get_cached_executions, set_cached_executions
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.instance_service import InstanceService
from app.services.quota_service import QuotaService

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
        self.logger.info(
            f"get_workflows: Entry - instance: {instance_id}, user: {user_id}, limit: {limit}, cursor: {cursor}, active: {active}")

        try:
            # Validate limit (n8n API max is 250)
            if limit > 250:
                limit = 250
            elif limit < 1:
                limit = 100

            # Check quota for refreshes
            if not self.quota_service.check_quota(db, user_id, 'refreshes'):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily refresh quota exceeded. Upgrade your plan for more refreshes."
                )

            # Get instance and verify ownership
            instance = self.instance_service.get_instance(
                db, instance_id, user_id)

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
                    redirect_location = response.headers.get(
                        'Location', 'unknown')
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

            # Increment quota for refresh
            self.quota_service.increment_quota(db, user_id, 'refreshes')

            self.analytics.log_success(
                action='get_workflows',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_count': len(workflows_data),
                    'has_next': next_cursor is not None
                }
            )
            self.logger.info(
                f"get_workflows: Success - instance: {instance_id}, count: {len(workflows_data)}, has_next: {next_cursor is not None}")

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
        self.logger.info(
            f"toggle_workflow: Entry - user: {user_id}, workflow: {workflow_id}, enabled: {enabled}")

        try:
            # Check if user is on free plan (read-only mode)
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            if user.plan_tier == 'free':
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Free plan is read-only. Upgrade to Pro to control workflows."
                )

            # Check quota (uses user's plan tier limit)
            if not self.quota_service.check_quota(db, user_id, 'toggles'):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily toggle quota exceeded. Upgrade your plan for more toggles."
                )

            # Get instance and verify ownership
            instance = self.instance_service.get_instance(
                db, instance_id, user_id)

            # Check if instance is enabled before toggling workflows
            if not instance.enabled:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Instance is disabled. Please enable the instance to toggle workflows."
                )

            api_key = self.instance_service.get_decrypted_api_key(instance)

            # Call n8n API to activate or deactivate workflow
            # n8n uses separate endpoints: /activate (POST) or /deactivate (POST)
            endpoint = "activate" if enabled else "deactivate"
            async with httpx.AsyncClient(follow_redirects=False) as client:
                response = await client.post(
                    f"{instance.url}/api/v1/workflows/{workflow_id}/{endpoint}",
                    headers={"X-N8N-API-KEY": api_key},
                    timeout=30.0
                )

                # Check for redirects (e.g., Cloudflare Access)
                if response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = response.headers.get(
                        'Location', 'unknown')
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
            self.logger.info(
                f"toggle_workflow: Success - workflow: {workflow_id}, enabled: {enabled}")
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
        status: str | None = None,
        refresh: bool = False
    ) -> dict:
        """
        Get executions from n8n instance with pagination support.
        Returns: {data: list[dict], nextCursor: str | None}
        """
        self.logger.info(
            f"get_executions: Entry - instance: {instance_id}, user: {user_id}, workflow_id: {workflow_id}, limit: {limit}, cursor: {cursor}, status: {status}, refresh: {refresh}")

        try:
            # Validate limit (n8n API max is 250, default is 20)
            if limit > 250:
                limit = 250
            elif limit < 1:
                limit = 20

            # Get user plan to determine caching strategy
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            user_plan = user.plan_tier
            # Testers get real-time data (no caching)
            # Pro plan uses cache, free plan uses longer cache
            should_use_cache = not user.is_tester and not refresh

            # Build params dict for cache key
            params = {
                "limit": limit,
                "workflowId": workflow_id,
                "cursor": cursor,
                "status": status
            }
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            # Check cache (unless business plan or refresh requested)
            if should_use_cache:
                cached = get_cached_executions(instance_id, params)
                if cached:
                    self.logger.info(
                        f"get_executions: Cache hit - instance: {instance_id}, plan: {user_plan}")
                    return cached

            # Check quota for refreshes
            if not self.quota_service.check_quota(db, user_id, 'refreshes'):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Daily refresh quota exceeded. Upgrade your plan for more refreshes."
                )

            # Get instance and verify ownership
            instance = self.instance_service.get_instance(
                db, instance_id, user_id)

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
                    redirect_location = response.headers.get(
                        'Location', 'unknown')
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

            # Increment quota for refresh
            self.quota_service.increment_quota(db, user_id, 'refreshes')

            result = {
                "data": executions_data,
                "nextCursor": next_cursor
            }

            # Cache the response (skip for testers - they get real-time data)
            if not user.is_tester:
                ttl = self._get_cache_ttl(user_plan)
                set_cached_executions(instance_id, params, result, ttl)
                self.logger.info(
                    f"get_executions: Cached response - instance: {instance_id}, plan: {user_plan}, ttl: {ttl}min")
            else:
                self.logger.info(
                    f"get_executions: Skipped cache (tester) - instance: {instance_id}")

            self.analytics.log_success(
                action='get_executions',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'execution_count': len(executions_data),
                    'has_next': next_cursor is not None,
                    'cached': should_use_cache and cached is not None if 'cached' in locals() else False
                }
            )
            self.logger.info(
                f"get_executions: Success - instance: {instance_id}, count: {len(executions_data)}, has_next: {next_cursor is not None}")

            return result
        except httpx.HTTPError as e:
            self.analytics.log_failure(
                action='get_executions',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id,
                            'workflow_id': workflow_id}
            )
            self.logger.error(f"get_executions: Failure - {e}")
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='get_executions',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id,
                            'workflow_id': workflow_id}
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
        self.logger.info(
            f"get_execution_by_id: Entry - instance: {instance_id}, execution: {execution_id}, user: {user_id}, include_data: {include_data}")

        try:
            # Check quota for error views (only when include_data is True)
            if include_data:
                if not self.quota_service.check_quota(db, user_id, 'error_views'):
                    from fastapi import HTTPException, status
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Daily error view quota exceeded. Upgrade your plan for more detailed error views."
                    )

            # Get instance and verify ownership
            instance = self.instance_service.get_instance(
                db, instance_id, user_id)

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
                    redirect_location = response.headers.get(
                        'Location', 'unknown')
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

            # Increment quota for error view (only when include_data is True)
            if include_data:
                self.quota_service.increment_quota(db, user_id, 'error_views')

            self.analytics.log_success(
                action='get_execution_by_id',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                    'include_data': include_data,
                }
            )
            self.logger.info(
                f"get_execution_by_id: Success - execution: {execution_id}")

            return result
        except httpx.HTTPError as e:
            self.analytics.log_failure(
                action='get_execution_by_id',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id,
                            'execution_id': execution_id}
            )
            self.logger.error(f"get_execution_by_id: Failure - {e}")
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='get_execution_by_id',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id,
                            'execution_id': execution_id}
            )
            self.logger.error(f"get_execution_by_id: Failure - {e}")
            raise

    async def retry_execution(
        self,
        db: Session,
        instance_id: str,
        execution_id: str,
        user_id: str
    ) -> dict:
        """Retry a failed execution with the same input data

        Args:
            db: Database session
            instance_id: n8n instance ID
            execution_id: Execution ID to retry
            user_id: User ID for ownership verification

        Returns:
            dict: {"new_execution_id": str, "workflow_id": str}
        """
        self.logger.info(
            f"retry_execution: Entry - instance: {instance_id}, execution: {execution_id}, user: {user_id}")

        try:
            # Get instance and verify ownership
            instance = self.instance_service.get_instance(
                db, instance_id, user_id)

            # Check if instance is enabled before retrying execution
            if not instance.enabled:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Instance is disabled. Please enable the instance to retry executions."
                )

            api_key = self.instance_service.get_decrypted_api_key(instance)

            # First, get the execution details to extract workflow_id and input data
            async with httpx.AsyncClient(follow_redirects=False) as client:
                # Get execution details
                exec_response = await client.get(
                    f"{instance.url}/api/v1/executions/{execution_id}",
                    headers={"X-N8N-API-KEY": api_key},
                    params={"includeData": True},
                    timeout=30.0
                )

                # Check for redirects (e.g., Cloudflare Access)
                if exec_response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = exec_response.headers.get(
                        'Location', 'unknown')
                    self.logger.warning(
                        f"retry_execution: n8n instance returned redirect {exec_response.status_code} to {redirect_location}. "
                        "This usually indicates the instance is behind Cloudflare Access or similar authentication."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"n8n instance returned redirect. The instance may be behind Cloudflare Access or require additional authentication. Redirect location: {redirect_location}"
                    )

                # Handle 404 - execution not found
                if exec_response.status_code == 404:
                    from fastapi import HTTPException, status
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Execution {execution_id} not found."
                    )

                exec_response.raise_for_status()
                execution_data = exec_response.json()

            # Extract workflow_id
            workflow_id = execution_data.get('workflowId')
            if isinstance(workflow_id, dict):
                workflow_id = workflow_id.get(
                    'workflowId') or workflow_id.get('id')

            if not workflow_id:
                from fastapi import HTTPException, status
                self.logger.error(
                    f"retry_execution: Missing workflow_id in execution data")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot retry execution: workflow ID not found in execution data."
                )

            # Extract input data from execution
            # n8n stores input data in data.executionData or data.startData
            exec_node_data = execution_data.get('data', {})

            # Try to extract input data - n8n might store it in different places
            input_data = None
            if exec_node_data:
                # Check for executionData (common in newer versions)
                if 'executionData' in exec_node_data:
                    input_data = exec_node_data.get('executionData')
                # Check for startData (used by manual executions)
                elif 'startData' in exec_node_data:
                    input_data = exec_node_data.get('startData')

            # Validate execution status - only allow retry for error/canceled executions
            execution_status = execution_data.get('status', '').lower()
            if execution_status not in ['error', 'failed', 'failure', 'canceled', 'cancelled']:
                from fastapi import HTTPException, status
                self.logger.warning(
                    f"retry_execution: Invalid status for retry: {execution_status}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot retry execution with status '{execution_status}'. Only failed or canceled executions can be retried."
                )

            # Trigger new execution
            async with httpx.AsyncClient(follow_redirects=False) as client:
                # Build request body
                request_body = {}
                if input_data:
                    request_body = input_data

                retry_response = await client.post(
                    f"{instance.url}/api/v1/workflows/{workflow_id}/execute",
                    headers={"X-N8N-API-KEY": api_key},
                    json=request_body,
                    timeout=30.0
                )

                # Check for redirects
                if retry_response.status_code in (301, 302, 303, 307, 308):
                    from fastapi import HTTPException, status
                    redirect_location = retry_response.headers.get(
                        'Location', 'unknown')
                    self.logger.warning(
                        f"retry_execution: n8n instance returned redirect {retry_response.status_code} to {redirect_location}. "
                        "This usually indicates the instance is behind Cloudflare Access or similar authentication."
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"n8n instance returned redirect. The instance may be behind Cloudflare Access or require additional authentication. Redirect location: {redirect_location}"
                    )

                # Handle 404 - workflow not found
                if retry_response.status_code == 404:
                    from fastapi import HTTPException, status
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Workflow {workflow_id} not found."
                    )

                retry_response.raise_for_status()
                retry_result = retry_response.json()

            # Extract new execution ID from response
            new_execution_id = retry_result.get('data', {}).get(
                'executionId') or retry_result.get('executionId') or retry_result.get('id')

            if not new_execution_id:
                self.logger.error(
                    f"retry_execution: Could not extract new execution ID from response: {retry_result}")
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Workflow execution triggered but execution ID not returned by n8n."
                )

            # Create audit log
            audit_log = AuditLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                action='retry_execution',
                resource_type='execution',
                resource_id=execution_id,
                meta_data=json.dumps({
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                    'new_execution_id': new_execution_id,
                    'workflow_id': workflow_id
                })
            )
            db.add(audit_log)
            db.commit()

            self.analytics.log_success(
                action='retry_execution',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                    'new_execution_id': new_execution_id,
                    'workflow_id': workflow_id,
                }
            )
            self.logger.info(
                f"retry_execution: Success - execution: {execution_id}, new_execution: {new_execution_id}")

            return {
                "new_execution_id": new_execution_id,
                "workflow_id": workflow_id
            }

        except httpx.HTTPStatusError as e:
            db.rollback()
            # Extract error message from response if available
            error_detail = str(e)
            try:
                if e.response.text:
                    error_data = e.response.json()
                    error_detail = error_data.get(
                        'message') or error_data.get('detail') or str(e)
            except:
                pass

            self.analytics.log_failure(
                action='retry_execution',
                error=f"HTTP {e.response.status_code}: {error_detail}",
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                }
            )
            self.logger.error(
                f"retry_execution: HTTP Error - {e.response.status_code}: {error_detail}")

            # Re-raise HTTP exceptions as-is (they're already HTTPException from above)
            from fastapi import HTTPException
            if isinstance(e, HTTPException):
                raise

            # Otherwise, raise as 502 Bad Gateway
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"n8n API error: {error_detail}"
            )

        except httpx.TimeoutException as e:
            db.rollback()
            self.analytics.log_failure(
                action='retry_execution',
                error=f"Timeout: {str(e)}",
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                }
            )
            self.logger.error(f"retry_execution: Timeout - {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Request to n8n instance timed out. Please try again."
            )

        except httpx.HTTPError as e:
            db.rollback()
            self.analytics.log_failure(
                action='retry_execution',
                error=str(e),
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                }
            )
            self.logger.error(f"retry_execution: Network Error - {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Network error communicating with n8n instance: {str(e)}"
            )

        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='retry_execution',
                error=str(e),
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'execution_id': execution_id,
                }
            )
            self.logger.error(f"retry_execution: Failure - {e}")
            raise

    def _get_cache_ttl(self, user_plan: str) -> int:
        """Get cache TTL in minutes based on user plan."""
        ttl_map = {
            'free': 30,  # 30 minutes for free tier (reduces API load)
            'pro': 3,    # 3 minutes for pro tier
        }
        return ttl_map.get(user_plan, 30)  # Default to free tier
