# Push Notification Integration Documentation

## Overview

Complete push notification system with severity-based smart notifications for workflow execution failures.

## Backend Changes

### 1. Pydantic Models (`app/models/fcm_notification.py`)

**NEW FILE** - Type-safe FCM notification models:

```python
class FCMNotificationData(BaseModel):
    """Data payload for FCM notification"""
    type: Literal["workflow_error"]
    workflow_id: str
    execution_id: str
    instance_id: str  # ← CRITICAL: Required for deep linking
    error_message: str
    severity: Literal["info", "warning", "error", "critical"] = "error"
    workflow_name: Optional[str] = None
```

**Benefits:**
- ✅ Type safety with Pydantic
- ✅ Validation at runtime
- ✅ Auto-generated documentation
- ✅ IDE autocomplete

### 2. FCM Service (`app/services/fcm_service.py`)

**Updated** - Added severity-based notifications:

```python
async def send_error_notification(
    self,
    user_id: str,
    workflow_id: str,
    execution_id: str,
    instance_id: str,  # ← NEW
    error_message: str,
    severity: Literal["info", "warning", "error", "critical"] = "error",  # ← NEW
    workflow_name: Optional[str] = None  # ← NEW
):
```

**Features:**
- ✅ Severity-based notification titles (🚨 for critical)
- ✅ Full Pydantic model validation
- ✅ Android notification channel configuration
- ✅ iOS APNS payload with sound/badge

### 3. Webhook Handler (`app/notifier/webhook_handler.py`)

**Updated** - Passes all required parameters:

```python
await fcm_service.send_error_notification(
    user_id=instance.user_id,
    workflow_id=workflow_id,
    execution_id=execution_id,
    instance_id=instance_id,  # ← NOW INCLUDED
    error_message=error_message,
    severity=severity,  # ← SMART SEVERITY
    workflow_name=workflow_name  # ← OPTIONAL NAME
)
```

## Mobile Changes

### 1. Severity-Based Notifications (`lib/core/notifications/push_notification_service.dart`)

**Smart Notification Display:**

| Severity | Display | Color | Dismissible |
|----------|---------|-------|-------------|
| **critical** | Alert Dialog | Red | No (must dismiss) |
| **error** | Alert Dialog | Red | No (must dismiss) |
| **warning** | SnackBar | Orange | Auto (6s) |
| **info** | SnackBar | Blue | Auto (6s) |

### 2. Dialog for Critical/Error

```dart
AlertDialog(
  icon: Icon(Icons.error, color: Colors.red[700], size: 48),
  title: Text('🚨 Critical Workflow Error'),
  content: Column(
    children: [
      Text(errorMessage),
      Container(
        // Critical warning banner
        child: Text('Requires immediate attention'),
      ),
    ],
  ),
  actions: [
    TextButton('Dismiss'),
    ElevatedButton.icon('View Details'),
  ],
)
```

### 3. SnackBar for Warning/Info

```dart
SnackBar(
  content: Row([
    Icon(Icons.warning_amber),
    Text(errorMessage),
  ]),
  backgroundColor: Colors.orange[700],
  duration: Duration(seconds: 6),
  action: SnackBarAction('View'),
)
```

## Complete Data Flow

### 1. n8n Webhook → Backend

```json
POST /api/v1/webhooks/n8n-error
{
  "executionId": "exec123",
  "workflowId": "wf456",
  "instanceId": "inst789",
  "workflowName": "Data Sync",
  "error": {
    "message": "Connection timeout"
  }
}
```

### 2. Backend → FCM

```json
{
  "message": {
    "token": "fcm_device_token",
    "notification": {
      "title": "🚨 Critical Workflow Error",
      "body": "Workflow Data Sync failed: Connection timeout"
    },
    "data": {
      "type": "workflow_error",
      "workflow_id": "wf456",
      "execution_id": "exec123",
      "instance_id": "inst789",
      "error_message": "Connection timeout",
      "severity": "critical",
      "workflow_name": "Data Sync"
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
```

### 3. Mobile Handling by App State

#### Foreground (App Open)
```
FCM Message → Check Severity
├─ critical/error → Alert Dialog with View button
└─ warning/info → SnackBar with View action
```

#### Background (App Minimized)
```
FCM Message → System Notification
User Taps → App Opens → Execution Details Bottom Sheet
```

#### Terminated (App Closed)
```
FCM Message → Background Handler → Local Notification
User Taps → App Starts → Execution Details Bottom Sheet
```

## Testing

### Test Backend Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/n8n-error \
  -H "Content-Type: application/json" \
  -d '{
    "executionId": "test123",
    "workflowId": "wf456",
    "instanceId": "inst789",
    "workflowName": "Test Workflow",
    "error": {
      "message": "Test error message"
    }
  }'
```

### Test Different Severities

```python
# Critical - Shows dialog with warning banner
await fcm_service.send_error_notification(
    user_id="user123",
    workflow_id="wf456",
    execution_id="exec123",
    instance_id="inst789",
    error_message="Database connection lost",
    severity="critical",
    workflow_name="Critical Process"
)

# Warning - Shows orange snackbar
await fcm_service.send_error_notification(
    user_id="user123",
    workflow_id="wf456",
    execution_id="exec123",
    instance_id="inst789",
    error_message="Rate limit approaching",
    severity="warning",
    workflow_name="API Sync"
)

# Info - Shows blue snackbar
await fcm_service.send_error_notification(
    user_id="user123",
    workflow_id="wf456",
    execution_id="exec123",
    instance_id="inst789",
    error_message="Workflow completed with warnings",
    severity="info",
    workflow_name="Batch Job"
)
```

### Test Mobile App States

1. **Foreground Test:**
   - Have app open and visible
   - Trigger webhook
   - Expected: Dialog (critical/error) or SnackBar (warning/info)

2. **Background Test:**
   - Minimize app (home button)
   - Trigger webhook
   - Expected: System notification
   - Tap: App opens → Execution details

3. **Terminated Test:**
   - Force close app
   - Trigger webhook
   - Expected: System notification
   - Tap: App starts → Execution details

## Customization

### Adding Custom Severity Logic

In `webhook_handler.py`, add custom rules:

```python
# Determine severity based on error patterns
error_message = error.get("message", "Unknown error")
severity = "error"  # Default

# Custom rules
if any(word in error_message.lower() for word in ["critical", "fatal", "crash"]):
    severity = "critical"
elif any(word in error_message.lower() for word in ["timeout", "connection", "network"]):
    severity = "error"
elif any(word in error_message.lower() for word in ["warning", "deprecated", "slow"]):
    severity = "warning"
elif any(word in error_message.lower() for word in ["info", "notice", "completed"]):
    severity = "info"
```

### Adding User Preferences (Future)

Could add settings to override severity-based display:

```dart
enum NotificationPreference {
  alwaysDialog,
  alwaysSnackBar,
  auto  // Use severity-based (current)
}

// Store in SharedPreferences
final prefs = await SharedPreferences.getInstance();
final preference = prefs.getString('notification_preference') ?? 'auto';
```

## Migration Notes

### For Existing Webhooks

The new parameters are **backward compatible**:
- `instance_id`: Now **required** (was missing before - THIS IS A FIX)
- `severity`: Optional, defaults to `"error"`
- `workflow_name`: Optional, uses `workflow_id` if not provided

### Breaking Changes

⚠️ **BREAKING:** `instance_id` is now **required** in webhook payload and FCM service.

**Before:**
```python
await fcm_service.send_error_notification(
    user_id=user_id,
    workflow_id=workflow_id,
    execution_id=execution_id,
    error_message=error_message
)
```

**After:**
```python
await fcm_service.send_error_notification(
    user_id=user_id,
    workflow_id=workflow_id,
    execution_id=execution_id,
    instance_id=instance_id,  # ← NOW REQUIRED
    error_message=error_message,
    severity="error",  # ← OPTIONAL
    workflow_name=None  # ← OPTIONAL
)
```

## Troubleshooting

### Notification Not Received

1. Check FCM token exists in Firestore (`fcm_tokens` collection)
2. Verify `instance_id` is correct
3. Check backend logs for FCM API errors
4. Verify mobile app has notification permissions

### Deep Link Not Working

1. Verify `instance_id` is included in notification data
2. Check mobile logs for navigation errors
3. Ensure execution details route is registered

### Wrong Notification Type

1. Check `severity` field in webhook payload
2. Verify severity logic in `webhook_handler.py`
3. Test with different severity values

## Performance

- ✅ **Type-safe**: Pydantic validation prevents runtime errors
- ✅ **Async**: FCM calls are non-blocking
- ✅ **Graceful failure**: Notification failures don't break webhook processing
- ✅ **Logging**: Full logging for debugging

## Security

- ✅ **OAuth2**: Uses Firebase Admin SDK for authentication
- ✅ **Validated**: All inputs validated by Pydantic
- ✅ **User-scoped**: Only sends to instance owner
- ✅ **No secrets**: FCM tokens stored securely in Firestore


