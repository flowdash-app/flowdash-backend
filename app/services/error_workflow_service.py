from sqlalchemy.orm import Session
from app.models.n8n_instance import N8NInstance
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.services.subscription_service import PlanConfiguration
from app.core.config import settings
from app.core.security import decrypt_api_key
from fastapi import HTTPException, status
import logging
import httpx

logger = logging.getLogger(__name__)


class ErrorWorkflowService:
    def __init__(self):
        self.analytics = AnalyticsService()
        self.logger = logging.getLogger(__name__)
    
    def get_base_webhook_url(self) -> str:
        """Get base webhook URL for error notifications"""
        base_url = settings.api_base_url or "https://api.flow-dash.com"
        return f"{base_url}{settings.api_v1_str}/webhooks/n8n-error"
    
    def create_error_workflow_template(
        self,
        db: Session,
        instance_id: str,
        user_id: str
    ) -> dict:
        """
        Generate personalized n8n workflow template with instance_id embedded.
        
        Each instance gets a unique workflow template with its specific instance_id
        hardcoded in the HTTP Request node. This allows n8n to report errors back
        to FlowDash with the correct instance identifier.
        
        Args:
            db: Database session
            instance_id: FlowDash instance ID (UUID)
            user_id: User ID for ownership verification
            
        Returns:
            Complete n8n workflow JSON with instance_id embedded
        """
        self.logger.info(f"create_error_workflow_template: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            # Verify instance ownership
            instance = db.query(N8NInstance).filter(
                N8NInstance.id == instance_id,
                N8NInstance.user_id == user_id
            ).first()
            
            if not instance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Instance not found or you don't have permission to access it"
                )
            
            # Get webhook URL
            webhook_url = self.get_base_webhook_url()
            
            # Create personalized workflow template
            workflow = {
                "name": f"FlowDash Error Notifications - {instance.name}",
                "nodes": [
                    {
                        "parameters": {},
                        "name": "Error Trigger",
                        "type": "n8n-nodes-base.errorTrigger",
                        "typeVersion": 1,
                        "position": [250, 300]
                    },
                    {
                        "parameters": {
                            "url": webhook_url,
                            "method": "POST",
                            "sendBody": True,
                            "specifyBody": "json",
                            "jsonBody": f"""={{
  "executionId": "{{{{ $execution.id }}}}",
  "workflowId": "{{{{ $workflow.id }}}}",
  "workflowName": "{{{{ $workflow.name }}}}",
  "instanceId": "{instance_id}",
  "severity": "error",
  "error": {{
    "message": "{{{{ $json.error.message }}}}"
  }}
}}""",
                            "options": {}
                        },
                        "name": "Send to FlowDash",
                        "type": "n8n-nodes-base.httpRequest",
                        "typeVersion": 4.2,
                        "position": [450, 300]
                    }
                ],
                "connections": {
                    "Error Trigger": {
                        "main": [
                            [
                                {
                                    "node": "Send to FlowDash",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
                },
                "settings": {
                    "executionOrder": "v1"
                },
                "staticData": None,
                "tags": [
                    {
                        "name": "FlowDash",
                        "id": "flowdash"
                    }
                ],
                "meta": {
                    "instanceId": instance_id
                }
            }
            
            self.analytics.log_success(
                action='create_error_workflow_template',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'instance_name': instance.name
                }
            )
            self.logger.info(f"create_error_workflow_template: Success - instance: {instance_id}")
            
            return workflow
            
        except HTTPException:
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='create_error_workflow_template',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"create_error_workflow_template: Failure - {e}")
            raise
    
    def validate_workflow_config(self, workflow_json: dict) -> bool:
        """
        Validate that workflow JSON has the required structure for FlowDash.
        
        Checks:
        - Has Error Trigger node
        - Has HTTP Request node
        - HTTP Request points to FlowDash webhook
        - instanceId is present in the body
        
        Args:
            workflow_json: n8n workflow JSON
            
        Returns:
            True if valid, False otherwise
        """
        self.logger.info("validate_workflow_config: Entry")
        
        try:
            nodes = workflow_json.get('nodes', [])
            
            # Check for Error Trigger
            has_error_trigger = any(
                node.get('type') == 'n8n-nodes-base.errorTrigger'
                for node in nodes
            )
            
            if not has_error_trigger:
                self.logger.warning("validate_workflow_config: Missing Error Trigger node")
                return False
            
            # Check for HTTP Request node with FlowDash URL
            webhook_url_base = self.get_base_webhook_url()
            has_flowdash_webhook = False
            has_instance_id = False
            
            for node in nodes:
                if node.get('type') == 'n8n-nodes-base.httpRequest':
                    params = node.get('parameters', {})
                    url = params.get('url', '')
                    
                    if webhook_url_base in url:
                        has_flowdash_webhook = True
                        
                        # Check for instanceId in body
                        json_body = params.get('jsonBody', '')
                        if 'instanceId' in json_body:
                            has_instance_id = True
            
            if not has_flowdash_webhook:
                self.logger.warning("validate_workflow_config: Missing FlowDash webhook URL")
                return False
            
            if not has_instance_id:
                self.logger.warning("validate_workflow_config: Missing instanceId in request body")
                return False
            
            self.logger.info("validate_workflow_config: Success - workflow is valid")
            return True
            
        except Exception as e:
            self.logger.error(f"validate_workflow_config: Failure - {e}")
            return False
    
    async def create_workflow_in_n8n(
        self,
        db: Session,
        instance_id: str,
        user_id: str
    ) -> dict:
        """
        Automatically create and activate error workflow in user's n8n instance.
        
        This method:
        1. Verifies instance ownership and user plan (Pro+ required)
        2. Retrieves and decrypts the n8n API key
        3. Generates the personalized workflow template
        4. Checks if a FlowDash error workflow already exists
        5. Creates or updates the workflow in n8n
        6. Activates the workflow
        7. Returns workflow details
        
        Args:
            db: Database session
            instance_id: FlowDash instance ID
            user_id: User ID for ownership verification
            
        Returns:
            dict: {
                "status": "success",
                "workflow_id": "n8n-workflow-id",
                "workflow_name": "FlowDash Error Notifications - Instance Name",
                "message": "Workflow created and activated" | "Workflow updated and activated"
            }
            
        Raises:
            HTTPException: If user doesn't have permission, plan doesn't allow, or n8n API fails
        """
        self.logger.info(f"create_workflow_in_n8n: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            # Get user and check plan
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Check plan allows push notifications (and thus error workflows)
            # PlanConfiguration.get_plan handles tester bypass internally
            plan_config = PlanConfiguration.get_plan(db, user.plan_tier, user=user)
            
            if not plan_config['push_notifications']:
                self.analytics.log_failure(
                    action='create_workflow_in_n8n',
                    error='Plan does not support push notifications',
                    user_id=user_id,
                    parameters={
                        'instance_id': instance_id,
                        'plan_tier': user.plan_tier,
                        'is_tester': user.is_tester
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Push notifications require Pro plan or higher. Upgrade to automatically create error workflows."
                )
            
            # Get instance and verify ownership
            instance = db.query(N8NInstance).filter(
                N8NInstance.id == instance_id,
                N8NInstance.user_id == user_id
            ).first()
            
            if not instance:
                self.analytics.log_failure(
                    action='create_workflow_in_n8n',
                    error='Instance not found',
                    user_id=user_id,
                    parameters={'instance_id': instance_id}
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Instance not found or you don't have permission to access it"
                )
            
            # Decrypt API key
            try:
                api_key = decrypt_api_key(instance.api_key_encrypted)
            except Exception as e:
                self.analytics.log_failure(
                    action='create_workflow_in_n8n',
                    error=f'Failed to decrypt API key: {str(e)}',
                    user_id=user_id,
                    parameters={'instance_id': instance_id}
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to decrypt n8n API key"
                )
            
            # Generate workflow template
            workflow_template = self.create_error_workflow_template(db, instance_id, user_id)
            
            # Check if FlowDash error workflow already exists
            workflow_name = workflow_template['name']
            existing_workflow_id = None
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # List all workflows to find existing FlowDash error workflow
                    list_response = await client.get(
                        f"{instance.url}/api/v1/workflows",
                        headers={"X-N8N-API-KEY": api_key}
                    )
                    
                    if list_response.status_code == 200:
                        workflows = list_response.json().get('data', [])
                        for wf in workflows:
                            if wf.get('name') == workflow_name:
                                existing_workflow_id = wf.get('id')
                                self.logger.info(f"create_workflow_in_n8n: Found existing workflow - id: {existing_workflow_id}")
                                break
            except Exception as e:
                self.logger.warning(f"create_workflow_in_n8n: Could not check for existing workflow - {e}")
                # Continue anyway, will try to create
            
            # Create or update workflow
            workflow_id = None
            is_update = False
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    if existing_workflow_id:
                        # Update existing workflow
                        update_response = await client.put(
                            f"{instance.url}/api/v1/workflows/{existing_workflow_id}",
                            headers={
                                "X-N8N-API-KEY": api_key,
                                "Content-Type": "application/json"
                            },
                            json=workflow_template
                        )
                        
                        if update_response.status_code == 200:
                            workflow_id = existing_workflow_id
                            is_update = True
                            self.logger.info(f"create_workflow_in_n8n: Updated workflow - id: {workflow_id}")
                        else:
                            raise Exception(f"Failed to update workflow: {update_response.status_code} - {update_response.text}")
                    else:
                        # Create new workflow
                        create_response = await client.post(
                            f"{instance.url}/api/v1/workflows",
                            headers={
                                "X-N8N-API-KEY": api_key,
                                "Content-Type": "application/json"
                            },
                            json=workflow_template
                        )
                        
                        if create_response.status_code == 200:
                            workflow_data = create_response.json().get('data', {})
                            workflow_id = workflow_data.get('id')
                            self.logger.info(f"create_workflow_in_n8n: Created workflow - id: {workflow_id}")
                        else:
                            raise Exception(f"Failed to create workflow: {create_response.status_code} - {create_response.text}")
            except httpx.TimeoutException:
                self.analytics.log_failure(
                    action='create_workflow_in_n8n',
                    error='n8n API timeout',
                    user_id=user_id,
                    parameters={
                        'instance_id': instance_id,
                        'instance_url': instance.url
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Timeout connecting to n8n instance at {instance.url}. Please check your instance is running and accessible."
                )
            except Exception as e:
                self.analytics.log_failure(
                    action='create_workflow_in_n8n',
                    error=str(e),
                    user_id=user_id,
                    parameters={
                        'instance_id': instance_id,
                        'instance_url': instance.url
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to create workflow in n8n: {str(e)}"
                )
            
            if not workflow_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to get workflow ID from n8n"
                )
            
            # Activate the workflow
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    activate_response = await client.post(
                        f"{instance.url}/api/v1/workflows/{workflow_id}/activate",
                        headers={"X-N8N-API-KEY": api_key}
                    )
                    
                    if activate_response.status_code not in [200, 204]:
                        self.logger.warning(f"create_workflow_in_n8n: Failed to activate workflow - {activate_response.status_code}")
                        # Don't fail the whole operation if activation fails
            except Exception as e:
                self.logger.warning(f"create_workflow_in_n8n: Could not activate workflow - {e}")
                # Don't fail the whole operation
            
            # Success!
            result = {
                "status": "success",
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "message": "Workflow updated and activated" if is_update else "Workflow created and activated",
                "is_update": is_update
            }
            
            effective_plan = user.plan_tier + (" (Tester)" if user.is_tester else "")
            self.analytics.log_success(
                action='create_workflow_in_n8n',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'is_update': is_update,
                    'plan_tier': effective_plan
                }
            )
            
            self.logger.info(f"create_workflow_in_n8n: Success - workflow_id: {workflow_id}, is_update: {is_update}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            self.analytics.log_failure(
                action='create_workflow_in_n8n',
                error=str(e),
                user_id=user_id,
                parameters={'instance_id': instance_id}
            )
            self.logger.error(f"create_workflow_in_n8n: Failure - {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {str(e)}"
            )

