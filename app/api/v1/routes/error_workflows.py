from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.services.error_workflow_service import ErrorWorkflowService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def get_error_workflow_service() -> ErrorWorkflowService:
    """Dependency to get error workflow service instance"""
    return ErrorWorkflowService()


@router.get("/template")
async def get_workflow_template(
    instance_id: str = Query(..., description="n8n instance ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    service: ErrorWorkflowService = Depends(get_error_workflow_service)
):
    """
    Get personalized n8n workflow template for error notifications.
    
    This endpoint generates a complete n8n workflow JSON that can be imported
    directly into the user's n8n instance. The workflow is personalized with
    the specific instance_id embedded in the HTTP Request node.
    
    **How it works:**
    1. Request this endpoint with your instance_id
    2. Receive a complete n8n workflow JSON
    3. Import the JSON into your n8n instance (Settings > Workflows > Import)
    4. The workflow will automatically send error notifications to FlowDash
    
    **Important**: Each n8n instance needs its own workflow with its unique instance_id.
    If you have multiple instances, request a template for each one.
    
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(f"get_workflow_template: Entry - user: {user_id}, instance: {instance_id}")
    
    try:
        template = service.create_error_workflow_template(
            db=db,
            instance_id=instance_id,
            user_id=user_id
        )
        
        logger.info(f"get_workflow_template: Success - user: {user_id}, instance: {instance_id}")
        return template
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_workflow_template: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/create-in-n8n")
async def create_workflow_in_n8n(
    instance_id: str = Query(..., description="FlowDash instance ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    service: ErrorWorkflowService = Depends(get_error_workflow_service)
):
    """
    Automatically create and activate error workflow in user's n8n instance.
    
    This endpoint provides the "automatic" setup path where FlowDash creates
    the error workflow directly in your n8n instance via the n8n API.
    
    **How it works:**
    1. Verifies you own the instance and have Pro+ plan
    2. Uses your stored n8n API key (encrypted)
    3. Generates personalized workflow with your instance_id
    4. Checks if FlowDash error workflow already exists
    5. Creates new workflow or updates existing one
    6. Activates the workflow
    7. Returns workflow details
    
    **Requirements:**
    - Pro, Business, or Enterprise plan (push notifications feature)
    - Valid n8n instance connected to FlowDash
    - n8n API key stored and accessible
    - n8n instance must be online and accessible
    
    **Returns:**
    - workflow_id: The n8n workflow ID
    - workflow_name: Name of the created workflow
    - message: Success message indicating if created or updated
    - is_update: True if updated existing workflow, False if created new
    
    **Idempotent:** Safe to call multiple times. Will update existing workflow if found.
    
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(f"create_workflow_in_n8n: Entry - user: {user_id}, instance: {instance_id}")
    
    try:
        result = await service.create_workflow_in_n8n(
            db=db,
            instance_id=instance_id,
            user_id=user_id
        )
        
        logger.info(f"create_workflow_in_n8n: Success - user: {user_id}, workflow_id: {result.get('workflow_id')}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_workflow_in_n8n: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/webhook-url")
async def get_webhook_url(
    service: ErrorWorkflowService = Depends(get_error_workflow_service)
):
    """
    Get the base webhook URL for error notifications.
    
    This is the URL that should be used in the HTTP Request node
    of your error workflow. The actual workflow template (from /template endpoint)
    already has this configured, but this endpoint is useful if you want to
    manually configure or update your workflow.
    
    No authentication required (public endpoint).
    """
    logger.info("get_webhook_url: Entry")
    
    try:
        url = service.get_base_webhook_url()
        logger.info(f"get_webhook_url: Success - {url}")
        return {
            "webhook_url": url,
            "method": "POST",
            "required_fields": [
                "executionId",
                "workflowId",
                "instanceId",
                "error"
            ],
            "optional_fields": [
                "workflowName",
                "severity"
            ]
        }
    except Exception as e:
        logger.error(f"get_webhook_url: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

