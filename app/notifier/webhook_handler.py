import logging
from enum import Enum
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.fcm_service import FCMService
from app.services.instance_service import InstanceService

logger = logging.getLogger(__name__)

router = APIRouter()


class Severity(str, Enum):
    """Notification severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class N8NErrorRequest(BaseModel):
    """Request model for n8n error webhook"""
    executionId: str = Field(..., description="n8n execution ID")
    workflowId: str = Field(..., description="n8n workflow ID")
    instanceId: str = Field(..., description="FlowDash instance ID")
    error: Optional[Dict[str, Any]] = Field(None, description="Error details from n8n")
    workflowName: Optional[str] = Field(None, description="Human-readable workflow name")
    severity: Severity = Field(Severity.ERROR, description="Notification severity level")

    class Config:
        populate_by_name = True  # Allow both camelCase and snake_case
        use_enum_values = True  # Use enum values in JSON


@router.post("/n8n-error")
async def handle_n8n_error(
    request: N8NErrorRequest,
    db: Session = Depends(get_db),
):
    """Handle n8n error webhook and send FCM push notification
    
    This endpoint receives error notifications from n8n workflows and sends
    push notifications to the instance owner's registered devices.
    """
    logger.info(f"handle_n8n_error: Entry - execution: {request.executionId}")
    
    try:
        # Get instance owner
        instance_service = InstanceService()
        instance = instance_service.get_instance_by_id(db, request.instanceId)
        
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instance not found: {request.instanceId}"
            )
        
        # Extract error message
        error_message = (
            request.error.get("message", "Unknown error") 
            if request.error 
            else "Workflow execution failed"
        )
        
        logger.info(
            f"handle_n8n_error: Processing - "
            f"workflow: {request.workflowId}, "
            f"instance: {request.instanceId}, "
            f"severity: {request.severity}"
        )
        
        # Send FCM notification to all user devices
        fcm_service = FCMService()
        await fcm_service.send_error_notification(
            user_id=instance.user_id,
            workflow_id=request.workflowId,
            execution_id=request.executionId,
            instance_id=request.instanceId,
            error_message=error_message,
            severity=request.severity,
            workflow_name=request.workflowName
        )
        
        logger.info(f"handle_n8n_error: Success - notification sent to user: {instance.user_id}")
        return {
            "status": "success",
            "message": "Notification sent",
            "user_id": instance.user_id,
            "severity": request.severity
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"handle_n8n_error: Failure - {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
