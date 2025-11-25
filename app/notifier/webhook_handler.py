import logging
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.middleware import get_current_user
from app.services.fcm_service import FCMService
from app.services.instance_service import InstanceService
from app.services.subscription_service import PlanConfiguration
from app.services.analytics_service import AnalyticsService
from app.models.user import User

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
    workflowName: Optional[str] = Field(
        None, description="Human-readable workflow name"
    )
    severity: Severity = Field(
        Severity.ERROR, description="Notification severity level"
    )

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

    Requires:
    - Valid instance ID
    - Instance must be enabled
    - User must have Pro plan (or be a tester) for push notifications
    """
    logger.info(
        f"handle_n8n_error: Entry - execution: {request.executionId}, instance: {request.instanceId}"
    )
    analytics = AnalyticsService()

    try:
        # Get instance
        instance_service = InstanceService()
        instance = instance_service.get_instance_by_id(db, request.instanceId)

        if not instance:
            analytics.log_failure(
                action="webhook_n8n_error",
                error="Instance not found",
                parameters={
                    "instance_id": request.instanceId,
                    "execution_id": request.executionId,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instance not found: {request.instanceId}",
            )

        # Get user
        user = db.query(User).filter(User.id == instance.user_id).first()
        if not user:
            analytics.log_failure(
                action="webhook_n8n_error",
                error="User not found",
                user_id=instance.user_id,
                parameters={
                    "instance_id": request.instanceId,
                    "execution_id": request.executionId,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if instance is enabled
        if not instance.enabled:
            analytics.log_failure(
                action="webhook_n8n_error",
                error="Instance disabled",
                user_id=instance.user_id,
                parameters={
                    "instance_id": request.instanceId,
                    "execution_id": request.executionId,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Instance is disabled. Please enable the instance in FlowDash to receive error notifications.",
            )

        # Check plan allows push notifications
        # Testers get unlimited access - bypass plan restrictions
        plan_config = PlanConfiguration.get_plan(db, user.plan_tier)

        if not plan_config["push_notifications"] and not user.is_tester:
            analytics.log_failure(
                action="webhook_n8n_error",
                error="Plan does not support push notifications",
                user_id=instance.user_id,
                parameters={
                    "instance_id": request.instanceId,
                    "execution_id": request.executionId,
                    "plan_tier": user.plan_tier,
                    "is_tester": user.is_tester,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Push notifications are not available on the Free plan. "
                "Upgrade to Pro or higher to receive instant error alerts from your workflows.",
            )

        # Extract error message
        error_message = (
            request.error.get("message", "Unknown error")
            if request.error
            else "Workflow execution failed"
        )

        # Determine effective plan for logging (testers get pro-level access)
        effective_plan = user.plan_tier + (" (Tester)" if user.is_tester else "")

        logger.info(
            f"handle_n8n_error: Processing - "
            f"workflow: {request.workflowId}, "
            f"instance: {request.instanceId}, "
            f"severity: {request.severity}, "
            f"user_plan: {effective_plan}"
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
            workflow_name=request.workflowName,
        )

        analytics.log_success(
            action="webhook_n8n_error",
            user_id=instance.user_id,
            parameters={
                "instance_id": request.instanceId,
                "execution_id": request.executionId,
                "workflow_id": request.workflowId,
                "severity": request.severity,
                "plan_tier": effective_plan,
            },
        )

        logger.info(
            f"handle_n8n_error: Success - notification sent to user: {instance.user_id}"
        )
        return {
            "status": "success",
            "message": "Notification sent",
            "user_id": instance.user_id,
            "severity": request.severity,
        }

    except HTTPException:
        raise
    except Exception as e:
        analytics.log_failure(
            action="webhook_n8n_error",
            error=str(e),
            parameters={
                "instance_id": request.instanceId,
                "execution_id": request.executionId,
            },
        )
        logger.error(f"handle_n8n_error: Failure - {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/google-play")
async def handle_google_play_notification(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Handle Google Play Real-time Developer Notifications

    Google sends notifications for subscription events like:
    - Subscription purchased
    - Subscription renewed
    - Subscription cancelled
    - Subscription expired

    See: https://developer.android.com/google/play/billing/rtdn-reference
    """
    logger.info(f"handle_google_play_notification: Entry")

    try:
        # Extract notification data
        # Note: In production, you should verify the notification signature
        # using Google's public key

        message = request.get("message", {})
        data = message.get("data", {})

        # Decode base64 data if present
        import base64
        import json

        if isinstance(data, str):
            decoded_data = base64.b64decode(data).decode("utf-8")
            notification_data = json.loads(decoded_data)
        else:
            notification_data = data

        logger.info(
            f"handle_google_play_notification: Processing - {notification_data}"
        )

        # Handle different notification types
        notification_type = notification_data.get("notificationType")
        subscription_notification = notification_data.get(
            "subscriptionNotification", {}
        )

        purchase_token = subscription_notification.get("purchaseToken")

        # TODO: Implement actual subscription update logic based on notification type
        # For now, just log the notification

        logger.info(
            f"handle_google_play_notification: Success - type: {notification_type}, "
            f"token: {purchase_token[:20] if purchase_token else 'None'}..."
        )

        return {
            "status": "success",
            "message": "Notification processed",
            "notification_type": notification_type,
        }

    except Exception as e:
        logger.error(f"handle_google_play_notification: Failure - {e}", exc_info=True)
        # Don't return error to Google - acknowledge receipt
        return {
            "status": "acknowledged",
            "message": "Notification received but processing failed",
        }


@router.post("/apple-store")
async def handle_apple_store_notification(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Handle Apple App Store Server Notifications

    Apple sends notifications for subscription events like:
    - DID_RENEW
    - CANCEL
    - DID_CHANGE_RENEWAL_STATUS
    - EXPIRED
    - GRACE_PERIOD_EXPIRED

    See: https://developer.apple.com/documentation/appstoreservernotifications
    """
    logger.info(f"handle_apple_store_notification: Entry")

    try:
        # Extract notification data
        # Note: In production, you should verify the JWT signature
        # using Apple's public key

        notification_type = request.get("notificationType")
        data = request.get("data", {})

        logger.info(
            f"handle_apple_store_notification: Processing - type: {notification_type}"
        )

        # TODO: Implement actual subscription update logic based on notification type
        # For now, just log the notification

        logger.info(
            f"handle_apple_store_notification: Success - type: {notification_type}"
        )

        return {
            "status": "success",
            "message": "Notification processed",
            "notification_type": notification_type,
        }

    except Exception as e:
        logger.error(f"handle_apple_store_notification: Failure - {e}", exc_info=True)
        # Don't return error to Apple - acknowledge receipt
        return {
            "status": "acknowledged",
            "message": "Notification received but processing failed",
        }


@router.post("/test-error")
async def test_error_notification(
    request: N8NErrorRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Test error notification endpoint for manual testing

    This endpoint allows Pro users (or testers) to manually test
    error notifications without triggering actual workflow errors in n8n.

    **Plan Restrictions:**
    - Free tier: Blocked (push notifications not available)
    - Pro (or tester): Allowed
    - Testers: Allowed

    **Usage:**
    Send the same payload as the n8n-error webhook endpoint to test
    the complete notification flow from backend to mobile app.

    Requires authentication.
    """
    user_id = current_user["uid"]
    logger.info(
        f"test_error_notification: Entry - user: {user_id}, instance: {request.instanceId}"
    )
    analytics = AnalyticsService()

    try:
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            analytics.log_failure(
                action="test_error_notification",
                error="User not found",
                user_id=user_id,
                parameters={"instance_id": request.instanceId},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check plan allows push notifications (only Pro+ can test)
        # Testers get unlimited access - bypass plan restrictions
        plan_config = PlanConfiguration.get_plan(db, user.plan_tier)

        if not plan_config["push_notifications"] and not user.is_tester:
            analytics.log_failure(
                action="test_error_notification",
                error="Plan does not support push notifications",
                user_id=user_id,
                parameters={
                    "instance_id": request.instanceId,
                    "plan_tier": user.plan_tier,
                    "is_tester": user.is_tester,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Push notifications require Pro plan or higher. "
                "Upgrade to test error webhooks and receive instant alerts.",
            )

        # Get instance and verify ownership
        instance_service = InstanceService()
        instance = instance_service.get_instance_by_id(db, request.instanceId)

        if not instance:
            analytics.log_failure(
                action="test_error_notification",
                error="Instance not found",
                user_id=user_id,
                parameters={"instance_id": request.instanceId},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Instance not found: {request.instanceId}",
            )

        # Verify user owns the instance
        if instance.user_id != user_id:
            analytics.log_failure(
                action="test_error_notification",
                error="Instance ownership mismatch",
                user_id=user_id,
                parameters={
                    "instance_id": request.instanceId,
                    "instance_owner": instance.user_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to test notifications for this instance",
            )

        # Check if instance is enabled
        if not instance.enabled:
            analytics.log_failure(
                action="test_error_notification",
                error="Instance disabled",
                user_id=user_id,
                parameters={"instance_id": request.instanceId},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Instance is disabled. Enable it to test notifications.",
            )

        # Extract error message
        error_message = (
            request.error.get("message", "Test error message")
            if request.error
            else "Test workflow error notification"
        )

        # Determine effective plan for logging (testers get pro-level access)
        effective_plan = user.plan_tier + (" (Tester)" if user.is_tester else "")

        logger.info(
            f"test_error_notification: Sending test notification - "
            f"user: {user_id}, "
            f"instance: {request.instanceId}, "
            f"severity: {request.severity}, "
            f"plan: {effective_plan}"
        )

        # Send test FCM notification
        fcm_service = FCMService()
        await fcm_service.send_error_notification(
            user_id=user_id,
            workflow_id=request.workflowId,
            execution_id=request.executionId,
            instance_id=request.instanceId,
            error_message=f"[TEST] {error_message}",
            severity=request.severity,
            workflow_name=request.workflowName or "Test Workflow",
        )

        analytics.log_success(
            action="test_error_notification",
            user_id=user_id,
            parameters={
                "instance_id": request.instanceId,
                "execution_id": request.executionId,
                "workflow_id": request.workflowId,
                "severity": request.severity,
                "plan_tier": effective_plan,
            },
        )

        logger.info(f"test_error_notification: Success - user: {user_id}")
        return {
            "status": "success",
            "message": "Test notification sent successfully",
            "user_id": user_id,
            "severity": request.severity,
            "plan_tier": effective_plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        analytics.log_failure(
            action="test_error_notification",
            error=str(e),
            user_id=user_id,
            parameters={"instance_id": request.instanceId},
        )
        logger.error(f"test_error_notification: Failure - {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
