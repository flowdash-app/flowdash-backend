from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.middleware import get_current_user
from app.core.database import get_db
from app.services.workflow_service import WorkflowService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def get_workflows(
    instance_id: str = Query(..., description="n8n instance ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get workflows for an n8n instance"""
    logger.info(f"get_workflows: Entry - user: {current_user['uid']}, instance: {instance_id}")
    
    try:
        service = WorkflowService()
        workflows = await service.get_workflows(db, instance_id, current_user['uid'])
        logger.info(f"get_workflows: Success - {len(workflows)} workflows")
        return {"workflows": workflows}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_workflows: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    workflow_id: str,
    instance_id: str = Query(..., description="n8n instance ID"),
    enabled: bool = Query(..., description="Enable or disable workflow"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle workflow on/off"""
    logger.info(f"toggle_workflow: Entry - user: {current_user['uid']}, workflow: {workflow_id}, enabled: {enabled}")
    
    try:
        service = WorkflowService()
        result = await service.toggle_workflow(
            db, instance_id, workflow_id, enabled, current_user['uid']
        )
        logger.info(f"toggle_workflow: Success - workflow: {workflow_id}, enabled: {enabled}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"toggle_workflow: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))

