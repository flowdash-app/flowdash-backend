from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any


class FCMNotificationData(BaseModel):
    """Data payload for FCM notification"""
    type: Literal["workflow_error"] = Field(description="Type of notification")
    workflow_id: str = Field(description="n8n workflow identifier")
    execution_id: str = Field(description="n8n execution identifier")
    instance_id: str = Field(description="n8n instance identifier")
    error_message: str = Field(description="Full error message from workflow execution")
    severity: Literal["info", "warning", "error", "critical"] = Field(
        default="error",
        description="Notification severity level for smart in-app notifications"
    )
    workflow_name: Optional[str] = Field(
        default=None,
        description="Human-readable workflow name"
    )
    # Title and body for data-only notifications (app will display these)
    title: Optional[str] = Field(
        default=None,
        description="Notification title (for data-only notifications)"
    )
    body: Optional[str] = Field(
        default=None,
        description="Notification body (for data-only notifications)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "workflow_error",
                "workflow_id": "abc123",
                "execution_id": "exec456",
                "instance_id": "inst789",
                "error_message": "Node 'HTTP Request' failed with error: Connection timeout",
                "severity": "error",
                "workflow_name": "Data Sync Workflow"
            }
        }


class FCMNotificationPayload(BaseModel):
    """Complete FCM notification message structure"""
    title: str = Field(description="Notification title")
    body: str = Field(description="Notification body text")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "n8n Workflow Error",
                "body": "Workflow abc123 failed: Connection timeout"
            }
        }


class FCMAndroidConfig(BaseModel):
    """Android-specific FCM configuration"""
    priority: Literal["normal", "high"] = Field(default="high")
    notification: Optional[Dict[str, str]] = Field(
        default=None,
        description="Android notification channel configuration (only for notification messages)"
    )


class FCMApnsConfig(BaseModel):
    """iOS APNS-specific FCM configuration"""
    headers: Dict[str, str] = Field(
        default={"apns-priority": "10"},
        description="APNS headers"
    )
    payload: Dict[str, Any] = Field(
        default={
            "aps": {
                "sound": "default",
                "badge": 1
            }
        },
        description="APNS payload configuration"
    )


class FCMMessage(BaseModel):
    """Complete FCM message structure"""
    token: str = Field(description="FCM device token")
    notification: Optional[FCMNotificationPayload] = Field(
        default=None,
        description="Notification payload (optional - use None for data-only notifications)"
    )
    data: Dict[str, str] = Field(description="Custom data payload as string key-value pairs")
    android: FCMAndroidConfig = Field(default_factory=FCMAndroidConfig)
    apns: FCMApnsConfig = Field(default_factory=FCMApnsConfig)
    
    class Config:
        json_schema_extra = {
            "example": {
                "token": "fcm_device_token_here",
                "notification": {
                    "title": "n8n Workflow Error",
                    "body": "Workflow abc123 failed: Connection timeout"
                },
                "data": {
                    "type": "workflow_error",
                    "workflow_id": "abc123",
                    "execution_id": "exec456",
                    "instance_id": "inst789",
                    "error_message": "Connection timeout",
                    "severity": "error"
                },
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": "workflow_errors"
                    }
                },
                "apns": {
                    "headers": {
                        "apns-priority": "10"
                    },
                    "payload": {
                        "aps": {
                            "sound": "default",
                            "badge": 1
                        }
                    }
                }
            }
        }


