import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.middleware import get_current_user
from app.services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter()


class GetExecutionRequest(BaseModel):
    """Request model for getting execution by ID - uses POST with body for secure instance_id handling"""
    instance_id: str
    # Whether to include the execution's detailed data (default True)
    include_data: bool = True


@router.get("")
@router.get("/")
async def get_workflows(
    instance_id: str = Query(..., description="n8n instance ID"),
    limit: int = Query(100, ge=1, le=250,
                       description="Number of workflows per page (max 250)"),
    cursor: str | None = Query(
        None, description="Cursor for pagination (from nextCursor in previous response)"),
    active: bool | None = Query(
        None, description="Filter by active status (true/false)"),
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
    logger.info(
        f"get_workflows: Entry - user: {current_user['uid']}, instance: {instance_id}, limit: {limit}, cursor: {cursor}, active: {active}")

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
        logger.info(
            f"get_workflows: Success - {len(result['data'])} workflows, has_next: {result['nextCursor'] is not None}")
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
    logger.info(
        f"toggle_workflow: Entry - user: {current_user['uid']}, workflow: {workflow_id}, enabled: {enabled}")

    try:
        service = WorkflowService()
        result = await service.toggle_workflow(
            db, instance_id, workflow_id, enabled, current_user['uid']
        )
        logger.info(
            f"toggle_workflow: Success - workflow: {workflow_id}, enabled: {enabled}")
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
    limit: int = Query(
        20, ge=1, le=250, description="Number of executions per page (default 20, max 250)"),
    cursor: str | None = Query(
        None, description="Cursor for pagination (from nextCursor in previous response)"),
    status: str | None = Query(
        None, description="Filter by status (success, error, running, waiting, canceled)"),
    refresh: bool = Query(
        False, description="Bypass cache and fetch fresh data"),
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
    logger.info(
        f"get_executions: Entry - user: {current_user['uid']}, instance: {instance_id}, workflow_id: {workflow_id}, limit: {limit}, cursor: {cursor}, status: {status}")

    try:
        service = WorkflowService()
        result = await service.get_executions(
            db,
            instance_id,
            current_user['uid'],
            workflow_id=workflow_id,
            limit=limit,
            cursor=cursor,
            status=status,
            refresh=refresh
        )
        logger.info(
            f"get_executions: Success - {len(result['data'])} executions, has_next: {result['nextCursor'] is not None}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_executions: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/executions/{execution_id}")
async def get_execution_by_id(
    execution_id: str,
    request: GetExecutionRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get execution details by ID - uses POST with body for secure instance_id handling"""
    instance_id = request.instance_id
    include_data = request.include_data

    logger.info(
        f"get_execution_by_id: Entry - user: {current_user['uid']}, execution: {execution_id}, instance: {instance_id}, include_data: {include_data}")

    try:
        service = WorkflowService()
        result = await service.get_execution_by_id(
            db,
            instance_id,
            execution_id,
            user_id=current_user['uid'],
            include_data=include_data
        )
        logger.info(
            f"get_execution_by_id: Success - execution: {execution_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_execution_by_id: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RetryExecutionRequest(BaseModel):
    """Request model for retrying an execution - uses POST with body for secure instance_id handling"""
    instance_id: str


@router.post("/executions/{execution_id}/retry")
async def retry_execution(
    execution_id: str,
    request: RetryExecutionRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retry a failed or canceled execution with the same input data.

    This endpoint:
    - Validates the user owns the instance
    - Fetches the original execution data
    - Validates the execution is in a retryable state (error or canceled)
    - Triggers a new execution with the same input data
    - Returns the new execution ID

    **Requirements:**
    - Execution must have status 'error', 'failed', or 'canceled'
    - Instance must be enabled
    - User must own the instance

    **Returns:**
    - new_execution_id: ID of the newly triggered execution
    - workflow_id: ID of the workflow that was executed

    **Error Responses:**
    - 400: Execution cannot be retried (invalid status, missing data)
    - 403: Instance is disabled or user doesn't own instance
    - 404: Execution or workflow not found
    - 502: n8n API error (redirect, connection error)
    - 504: Request timeout
    """
    instance_id = request.instance_id

    logger.info(
        f"retry_execution: Entry - user: {current_user['uid']}, execution: {execution_id}, instance: {instance_id}")

    try:
        service = WorkflowService()
        result = await service.retry_execution(
            db,
            instance_id,
            execution_id,
            user_id=current_user['uid']
        )
        logger.info(
            f"retry_execution: Success - execution: {execution_id}, new_execution: {result['new_execution_id']}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"retry_execution: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))
