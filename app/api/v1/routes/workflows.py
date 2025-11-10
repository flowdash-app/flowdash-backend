from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.middleware import get_current_user
from app.core.database import get_db
from app.services.workflow_service import WorkflowService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
@router.get("/")
async def get_workflows(
    instance_id: str = Query(..., description="n8n instance ID"),
    limit: int = Query(100, ge=1, le=250, description="Number of workflows per page (max 250)"),
    cursor: str | None = Query(None, description="Cursor for pagination (from nextCursor in previous response)"),
    active: bool | None = Query(None, description="Filter by active status (true/false)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get workflows for an n8n instance with pagination support.
    
    Returns paginated response:
    {
        "data": [...workflows...],
        "nextCursor": "cursor_string" | null
    }
    
    Use nextCursor in subsequent requests to get next page.
    """
    logger.info(f"get_workflows: Entry - user: {current_user['uid']}, instance: {instance_id}, limit: {limit}, cursor: {cursor}, active: {active}")
    
    try:
        service = WorkflowService()
        result = await service.get_workflows(
            db,
            instance_id,
            current_user['uid'],
            limit=limit,
            cursor=cursor,
            active=active
        )
        logger.info(f"get_workflows: Success - {len(result['data'])} workflows, has_next: {result['nextCursor'] is not None}")
        return result
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


@router.get("/executions")
async def get_executions(
    instance_id: str = Query(..., description="n8n instance ID"),
    workflow_id: str | None = Query(None, description="Filter by workflow ID"),
    limit: int = Query(20, ge=1, le=250, description="Number of executions per page (default 20, max 250)"),
    cursor: str | None = Query(None, description="Cursor for pagination (from nextCursor in previous response)"),
    status: str | None = Query(None, description="Filter by status (success, error, running, waiting, canceled)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get executions for an n8n instance with pagination support.
    
    Returns paginated response:
    {
        "data": [...executions...],
        "nextCursor": "cursor_string" | null
    }
    
    Use nextCursor in subsequent requests to get next page.
    """
    logger.info(f"get_executions: Entry - user: {current_user['uid']}, instance: {instance_id}, workflow_id: {workflow_id}, limit: {limit}, cursor: {cursor}, status: {status}")
    
    try:
        service = WorkflowService()
        result = await service.get_executions(
            db,
            instance_id,
            current_user['uid'],
            workflow_id=workflow_id,
            limit=limit,
            cursor=cursor,
            status=status
        )
        logger.info(f"get_executions: Success - {len(result['data'])} executions, has_next: {result['nextCursor'] is not None}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_executions: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}")
async def get_execution_by_id(
    execution_id: str,
    instance_id: str = Query(..., description="n8n instance ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution details by ID"""
    logger.info(f"get_execution_by_id: Entry - user: {current_user['uid']}, execution: {execution_id}, instance: {instance_id}")
    
    try:
        service = WorkflowService()
        result = await service.get_execution_by_id(
            db,
            instance_id,
            execution_id,
            current_user['uid']
        )
        logger.info(f"get_execution_by_id: Success - execution: {execution_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_execution_by_id: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))

