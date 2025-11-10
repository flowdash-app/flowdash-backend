from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict
from app.core.middleware import get_current_user
from app.core.database import get_db
from app.services.instance_service import InstanceService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class InstanceCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allows both api_key and apiKey
    
    name: str
    url: str
    api_key: str = Field(..., alias="apiKey")
    enabled: bool = True  # Default to enabled when creating


class InstanceUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # Allows both api_key and apiKey
    
    name: str | None = None
    url: str | None = None
    api_key: str | None = Field(None, alias="apiKey")
    enabled: bool | None = None  # Optional: update enabled state


async def _list_instances(
    current_user: dict,
    db: Session,
):
    """List all n8n instances for the current user"""
    logger.info(f"list_instances: Entry - user: {current_user['uid']}")
    
    try:
        service = InstanceService()
        instances = service.list_instances(db, current_user['uid'])
        logger.info(f"list_instances: Success - {len(instances)} instances")
        return {"instances": instances}
    except Exception as e:
        logger.error(f"list_instances: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
@router.get("/")
async def list_instances(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all n8n instances for the current user"""
    return await _list_instances(current_user, db)


async def _create_instance(
    instance_data: InstanceCreate,
    current_user: dict,
    db: Session,
):
    """Create a new n8n instance"""
    logger.info(f"create_instance: Entry - user: {current_user['uid']}, name: {instance_data.name}")
    
    try:
        service = InstanceService()
        instance = service.create_instance(
            db,
            current_user['uid'],
            instance_data.name,
            instance_data.url,
            instance_data.api_key,
            instance_data.enabled
        )
        logger.info(f"create_instance: Success - instance: {instance.id}")
        return instance
    except Exception as e:
        logger.error(f"create_instance: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
@router.post("/")
async def create_instance(
    instance_data: InstanceCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new n8n instance"""
    return await _create_instance(instance_data, current_user, db)


@router.get("/{instance_id}")
async def get_instance(
    instance_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an n8n instance by ID"""
    logger.info(f"get_instance: Entry - user: {current_user['uid']}, instance: {instance_id}")
    
    try:
        service = InstanceService()
        instance = service.get_instance(db, instance_id, current_user['uid'])
        logger.info(f"get_instance: Success - instance: {instance_id}")
        return instance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_instance: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{instance_id}")
async def update_instance(
    instance_id: str,
    instance_data: InstanceUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an n8n instance"""
    logger.info(f"update_instance: Entry - user: {current_user['uid']}, instance: {instance_id}")
    
    try:
        service = InstanceService()
        instance = service.update_instance(
            db,
            instance_id,
            current_user['uid'],
            instance_data.name,
            instance_data.url,
            instance_data.api_key,
            instance_data.enabled
        )
        logger.info(f"update_instance: Success - instance: {instance_id}")
        return instance
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_instance: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}")
async def delete_instance(
    instance_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an n8n instance"""
    logger.info(f"delete_instance: Entry - user: {current_user['uid']}, instance: {instance_id}")
    
    try:
        service = InstanceService()
        service.delete_instance(db, instance_id, current_user['uid'])
        logger.info(f"delete_instance: Success - instance: {instance_id}")
        return {"status": "deleted", "instance_id": instance_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_instance: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))

