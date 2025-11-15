from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.middleware import get_current_user
from app.services.device_service import DeviceService
from app.services.analytics_service import AnalyticsService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class DeviceRegisterRequest(BaseModel):
    device_id: str
    fcm_token: str
    platform: str  # 'ios' or 'android'


class DeviceDeleteRequest(BaseModel):
    device_id: str


@router.post("/register")
async def register_device(
    request: DeviceRegisterRequest,
    current_user: dict = Depends(get_current_user)
):
    """Register or update device token for push notifications"""
    logger.info(f"register_device: Entry - user: {current_user['uid']}, device: {request.device_id}")
    
    device_service = DeviceService()
    analytics = AnalyticsService()
    
    try:
        # Validate platform
        if request.platform not in ['ios', 'android']:
            logger.warning(f"register_device: Invalid platform - {request.platform}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Platform must be 'ios' or 'android'"
            )
        
        # Register device
        device_service.register_device(
            user_id=current_user['uid'],
            device_id=request.device_id,
            fcm_token=request.fcm_token,
            platform=request.platform
        )
        
        # Log success to analytics
        analytics.log_success(
            action='register_device',
            user_id=current_user['uid'],
            parameters={
                'device_id': request.device_id,
                'platform': request.platform,
            }
        )
        
        logger.info(f"register_device: Success - user: {current_user['uid']}, device: {request.device_id}")
        
        return {
            "success": True,
            "message": "Device registered successfully"
        }
    except Exception as e:
        # Log failure to analytics
        analytics.log_failure(
            action='register_device',
            error=str(e),
            user_id=current_user['uid'],
            parameters={
                'device_id': request.device_id,
                'platform': request.platform,
            }
        )
        
        logger.error(f"register_device: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device"
        )


@router.delete("")
async def delete_device(
    request: DeviceDeleteRequest,
    current_user: dict = Depends(get_current_user)
):
    """Delete device token (on logout)"""
    logger.info(f"delete_device: Entry - user: {current_user['uid']}, device: {request.device_id}")
    
    device_service = DeviceService()
    analytics = AnalyticsService()
    
    try:
        # Delete device
        device_service.delete_device(
            user_id=current_user['uid'],
            device_id=request.device_id
        )
        
        # Log success to analytics
        analytics.log_success(
            action='delete_device',
            user_id=current_user['uid'],
            parameters={
                'device_id': request.device_id,
            }
        )
        
        logger.info(f"delete_device: Success - user: {current_user['uid']}, device: {request.device_id}")
        
        return {
            "success": True,
            "message": "Device deleted successfully"
        }
    except Exception as e:
        # Log failure to analytics
        analytics.log_failure(
            action='delete_device',
            error=str(e),
            user_id=current_user['uid'],
            parameters={
                'device_id': request.device_id,
            }
        )
        
        logger.error(f"delete_device: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete device"
        )

