from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.fcm_service import FCMService
from app.services.instance_service import InstanceService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/n8n-error")
async def handle_n8n_error(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle n8n error webhook and send FCM push notification"""
    logger.info("handle_n8n_error: Entry")
    
    try:
        body = await request.json()
        
        # Validate webhook payload
        execution_id = body.get("executionId")
        workflow_id = body.get("workflowId")
        instance_id = body.get("instanceId")
        error = body.get("error")
        
        if not execution_id or not workflow_id or not instance_id:
            raise HTTPException(status_code=400, detail="Missing required fields: executionId, workflowId, or instanceId")
        
        logger.info(f"handle_n8n_error: Processing - execution: {execution_id}, workflow: {workflow_id}")
        
        # Get instance owner
        instance_service = InstanceService()
        instance = instance_service.get_instance_by_id(db, instance_id)
        
        # Send FCM notification
        fcm_service = FCMService()
        await fcm_service.send_error_notification(
            user_id=instance.user_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            error_message=error.get("message", "Unknown error") if error else "Workflow execution failed"
        )
        
        logger.info(f"handle_n8n_error: Success - notification sent to user: {instance.user_id}")
        return {"status": "success", "message": "Notification sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"handle_n8n_error: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))

