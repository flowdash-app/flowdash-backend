import httpx
from app.core.config import settings
from app.core.firebase import get_firestore_client, get_fcm_access_token
from app.models.fcm_notification import (
    FCMNotificationData,
    FCMNotificationPayload,
    FCMMessage,
    FCMAndroidConfig,
    FCMApnsConfig
)
from firebase_admin import firestore
import logging
from typing import Literal, Optional

logger = logging.getLogger(__name__)


class FCMService:
    def __init__(self):
        self.firebase_project_id = settings.firebase_project_id
        self.fcm_url = f"https://fcm.googleapis.com/v1/projects/{self.firebase_project_id}/messages:send"
        self.db = get_firestore_client()
        self.logger = logging.getLogger(__name__)
    
    def get_user_device_tokens(self, user_id: str) -> list:
        """Get all FCM tokens for user's devices from Firestore
        
        Args:
            user_id: Firebase UID
            
        Returns:
            List of dictionaries with 'token' and 'device_id' keys
        """
        self.logger.info(f"get_user_device_tokens: Entry - user: {user_id}")
        
        try:
            devices_ref = self.db.collection('users').document(user_id).collection('devices')
            devices_docs = devices_ref.stream()
            
            tokens = []
            for doc in devices_docs:
                device_data = doc.to_dict()
                fcm_token = device_data.get('fcm_token')
                if fcm_token:
                    tokens.append({
                        'token': fcm_token,
                        'device_id': doc.id
                    })
            
            self.logger.info(f"get_user_device_tokens: Success - user: {user_id}, count: {len(tokens)}")
            return tokens
        except Exception as e:
            self.logger.error(f"get_user_device_tokens: Failure - {e}")
            return []
    
    def remove_invalid_device_token(self, user_id: str, device_id: str):
        """Remove invalid device token from Firestore
        
        Args:
            user_id: Firebase UID
            device_id: Device identifier
        """
        self.logger.info(f"remove_invalid_device_token: Entry - user: {user_id}, device: {device_id}")
        
        try:
            device_ref = self.db.collection('users').document(user_id).collection('devices').document(device_id)
            device_ref.delete()
            self.logger.info(f"remove_invalid_device_token: Success - user: {user_id}, device: {device_id}")
        except Exception as e:
            self.logger.error(f"remove_invalid_device_token: Failure - {e}")
    
    async def send_error_notification(
        self,
        user_id: str,
        workflow_id: str,
        execution_id: str,
        instance_id: str,
        error_message: str,
        severity: Literal["info", "warning", "error", "critical"] = "error",
        workflow_name: Optional[str] = None
    ):
        """
        Send FCM push notification for n8n error
        
        Args:
            user_id: Firebase user ID
            workflow_id: n8n workflow identifier
            execution_id: n8n execution identifier
            instance_id: n8n instance identifier
            error_message: Full error message from workflow execution
            severity: Notification severity level (info, warning, error, critical)
            workflow_name: Optional human-readable workflow name
        """
        self.logger.info(f"send_error_notification: Entry - user: {user_id}, execution: {execution_id}, severity: {severity}")
        
        try:
            # Get all FCM tokens for user's devices
            device_tokens = self.get_user_device_tokens(user_id)
            
            if not device_tokens:
                self.logger.warning(f"send_error_notification: No FCM tokens for user: {user_id}")
                return
            
            # Create notification title and body for data payload
            notification_title = "n8n Workflow Error"
            if severity == "critical":
                notification_title = "🚨 Critical Workflow Error"
            elif severity == "warning":
                notification_title = "⚠️ Workflow Warning"
            
            workflow_display = workflow_name if workflow_name else workflow_id
            notification_body = f"Workflow {workflow_display} failed: {error_message[:100]}"
            
            # Create notification data payload (data-only notification)
            # Include title and body in data so app can display them
            notification_data = FCMNotificationData(
                type="workflow_error",
                workflow_id=workflow_id,
                execution_id=execution_id,
                instance_id=instance_id,
                error_message=error_message,
                severity=severity,
                workflow_name=workflow_name,
                title=notification_title,
                body=notification_body
            )
            
            # Get OAuth2 token once for all requests
            access_token = get_fcm_access_token()
            
            # Send notification to all user devices
            success_count = 0
            failed_count = 0
            
            async with httpx.AsyncClient() as client:
                for device in device_tokens:
                    try:
                        # Create FCM message using Pydantic model (data-only notification)
                        # Data-only messages give the app full control over notification display
                        fcm_message = FCMMessage(
                            token=device['token'],
                            notification=None,  # Data-only notification
                            data={k: str(v) for k, v in notification_data.model_dump().items() if v is not None},
                            android=FCMAndroidConfig(
                                priority="high",
                                # No notification config for data-only messages
                            ),
                            apns=FCMApnsConfig(
                                headers={"apns-priority": "10"},
                                payload={
                                    "aps": {
                                        "content-available": 1,  # Required for data-only messages on iOS
                                        "sound": "default",
                                        "badge": 1
                                    }
                                }
                            )
                        )
                        
                        # Prepare message for FCM API
                        message = {
                            "message": fcm_message.model_dump(exclude_none=True)
                        }
                        
                        # Send notification using FCM HTTP v1 API
                        response = await client.post(
                            self.fcm_url,
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json"
                            },
                            json=message,
                            timeout=30.0
                        )
                        response.raise_for_status()
                        success_count += 1
                        self.logger.info(f"send_error_notification: Sent to device: {device['device_id']}")
                        
                    except httpx.HTTPStatusError as e:
                        failed_count += 1
                        # If token is invalid (404 or 400), remove it from Firestore
                        if e.response.status_code in [404, 400]:
                            self.logger.warning(f"send_error_notification: Invalid token for device: {device['device_id']}, removing")
                            self.remove_invalid_device_token(user_id, device['device_id'])
                        else:
                            self.logger.error(f"send_error_notification: Failed for device: {device['device_id']}, error: {e}")
                    except Exception as e:
                        failed_count += 1
                        self.logger.error(f"send_error_notification: Failed for device: {device['device_id']}, error: {e}")
            
            self.logger.info(f"send_error_notification: Complete - user: {user_id}, success: {success_count}, failed: {failed_count}")
        except Exception as e:
            self.logger.error(f"send_error_notification: Failure - {e}")
            # Don't raise - notification failures shouldn't break webhook processing
            pass

