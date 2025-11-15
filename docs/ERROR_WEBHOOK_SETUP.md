# FlowDash Error Webhook Setup Guide

## Overview

This guide explains how to set up error notifications from your n8n workflows to your FlowDash mobile app. When a workflow fails, you'll receive instant push notifications on your phone.

## Prerequisites

### Plan Requirements

- **Free Plan**: Error webhooks are **NOT available** (status polling only)
- **Pro Plan**: ✅ Error webhooks available
- **Business Plan**: ✅ Error webhooks available
- **Enterprise Plan**: ✅ Error webhooks available

If you're on the Free plan, you'll need to [upgrade to Pro or higher](https://flow-dash.com/pricing) to use error webhooks.

### What You'll Need

1. A FlowDash account (Pro or higher)
2. At least one n8n instance connected to FlowDash
3. Your FlowDash instance ID
4. Access to your n8n instance

## Understanding Instance IDs

**Important**: The `instance_id` is FlowDash's internal UUID that identifies your n8n connection.

- **NOT the same as your user ID**
- **Unique per n8n instance**: If you have 4 n8n instances, each has its own instance_id
- **Required**: n8n doesn't know about this ID - you must provide it

### Example Scenario

If you're a Pro user with multiple n8n instances:

```
User ID: user-abc123 (your FlowDash account)

Instance 1 (Production):
  - Name: "Production n8n"
  - Instance ID: 123e4567-e89b-12d3-a456-426614174000
  
Instance 2 (Staging):
  - Name: "Staging n8n"
  - Instance ID: 987f6543-c21b-43d2-9876-543210987654
  
Instance 3 (Client A):
  - Name: "Client A n8n"
  - Instance ID: 456a7890-b12c-34d5-6789-012345678901
```

Each instance needs its own error workflow with its specific `instance_id` embedded.

## Setup Methods

There are two ways to set up error notifications:

### Method 1: API-Generated Template (Recommended) ⭐

This method automatically generates a workflow with your instance_id already configured.

### Method 2: Manual Configuration

Download the example template and manually edit the instance_id.

---

## Method 1: API-Generated Template (Recommended)

### Step 1: Get Your Instance ID

#### Option A: From FlowDash Mobile App

1. Open FlowDash mobile app
2. Go to **Instances** tab
3. Tap on your n8n instance
4. Your instance ID is displayed (long UUID format)
5. Tap to copy it

#### Option B: From API

```bash
curl -X GET "https://api.flow-dash.com/api/v1/instances" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"
```

Response will include your instances with their IDs.

### Step 2: Generate Personalized Workflow

Make an API request to get your personalized workflow template:

```bash
curl -X GET "https://api.flow-dash.com/api/v1/error-workflows/template?instance_id=YOUR_INSTANCE_ID_HERE" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  > flowdash-error-workflow.json
```

Replace:
- `YOUR_INSTANCE_ID_HERE` with your actual instance ID
- `YOUR_FIREBASE_TOKEN` with your Firebase authentication token

This will save a complete workflow JSON file with your instance_id pre-configured.

### Step 3: Import Workflow into n8n

1. Log into your n8n instance
2. Click **"Workflows"** in the left sidebar
3. Click **"Import from File"** button
4. Select the `flowdash-error-workflow.json` file you downloaded
5. The workflow will be imported with your instance_id already configured

### Step 4: Activate the Workflow

1. Open the imported workflow in n8n
2. Review the workflow (optional):
   - **Error Trigger node**: Triggers when any workflow fails
   - **Send to FlowDash node**: Sends error details to FlowDash
3. Click the **"Active"** toggle in the top-right corner
4. The workflow is now live!

### Step 5: Test It

Use the FlowDash test endpoint to verify everything works:

```bash
curl -X POST "https://api.flow-dash.com/api/v1/webhooks/test-error" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "executionId": "test-exec-123",
    "workflowId": "test-workflow-456",
    "instanceId": "YOUR_INSTANCE_ID_HERE",
    "workflowName": "Test Workflow",
    "error": {
      "message": "This is a test error notification"
    },
    "severity": "error"
  }'
```

You should receive a push notification on your mobile device with "[TEST]" in the message.

---

## Method 2: Manual Configuration

### Step 1: Download Example Template

Download the example template from:
```
https://github.com/flowdash/flowdash-backend/blob/main/examples/error-workflow-template-example.json
```

Or from your FlowDash backend repository:
```
flowdash-backend/examples/error-workflow-template-example.json
```

### Step 2: Get Your Instance ID

See **Method 1, Step 1** above for how to get your instance ID.

### Step 3: Edit the Template

1. Open `error-workflow-template-example.json` in a text editor
2. Find this line (around line 10):
   ```json
   "instanceId": "YOUR_INSTANCE_ID_HERE",
   ```
3. Replace `YOUR_INSTANCE_ID_HERE` with your actual instance ID:
   ```json
   "instanceId": "123e4567-e89b-12d3-a456-426614174000",
   ```
4. Save the file

### Step 4: Import and Activate

Follow **Method 1, Steps 3-5** above.

---

## Multiple Instances

If you have multiple n8n instances (Pro: up to 5, Business: unlimited):

1. **Generate a separate workflow for each instance**
2. Each workflow must have the correct `instance_id` for that specific n8n instance
3. Import each workflow into its corresponding n8n instance

Example:

```bash
# Generate workflow for Production instance
curl -X GET "https://api.flow-dash.com/api/v1/error-workflows/template?instance_id=production-instance-id" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  > production-error-workflow.json

# Generate workflow for Staging instance
curl -X GET "https://api.flow-dash.com/api/v1/error-workflows/template?instance_id=staging-instance-id" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  > staging-error-workflow.json
```

Then import each workflow into its corresponding n8n instance.

---

## How It Works

### Data Flow

1. **Workflow Fails**: Any workflow in your n8n instance encounters an error
2. **Error Trigger**: The "Error Trigger" node catches the failure
3. **Send to FlowDash**: The "Send to FlowDash" node sends error details to FlowDash API
4. **Plan Verification**: FlowDash checks:
   - Instance exists and is enabled
   - User has Pro/Business plan (or is a tester)
5. **Push Notification**: FlowDash sends notification to your registered mobile devices
6. **Mobile Alert**: You receive instant notification on your phone

### What Data is Sent

The webhook sends this information to FlowDash:

```json
{
  "executionId": "unique-execution-id",
  "workflowId": "workflow-id",
  "workflowName": "Human readable workflow name",
  "instanceId": "your-flowdash-instance-id",
  "severity": "error",
  "error": {
    "message": "The actual error message from n8n"
  }
}
```

---

## Troubleshooting

### No Notifications Received

1. **Check your plan**: Free tier users cannot receive push notifications
   ```bash
   # Check your current plan
   curl -X GET "https://api.flow-dash.com/api/v1/subscriptions/current" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

2. **Verify instance is enabled**:
   - Open FlowDash mobile app
   - Go to Instances tab
   - Make sure your instance toggle is ON (green)

3. **Check instance_id is correct**:
   - The instance_id in your n8n workflow must exactly match your FlowDash instance ID
   - Even one character difference will cause failures

4. **Verify workflow is active**:
   - Open n8n
   - Check the workflow toggle is ON

5. **Check FCM token**:
   - Make sure you're logged into FlowDash mobile app
   - The app registers your device for push notifications

### Getting 403 Errors

**Error**: "Push notifications are not available on the Free plan"

**Solution**: Upgrade to Pro or higher plan at https://flow-dash.com/pricing

**Error**: "Instance is disabled"

**Solution**: Enable your instance in the FlowDash mobile app

### Getting 404 Errors

**Error**: "Instance not found"

**Solutions**:
1. Double-check your instance_id is correct
2. Make sure the instance exists in your FlowDash account
3. Verify you're using the correct FlowDash account

### Test Endpoint Blocked

If you get a 403 error when testing:

```json
{
  "detail": "Push notifications require Pro plan or higher. Upgrade to test error webhooks."
}
```

You need to upgrade your plan. The test endpoint is only available to Pro/Business/Enterprise users.

### Workflow Not Triggering

1. **Trigger a test error** in n8n:
   - Create a simple workflow with a node that will fail
   - Run it and verify the Error Trigger workflow catches it

2. **Check n8n executions**:
   - Go to n8n Executions tab
   - Verify the FlowDash error workflow ran
   - Check if there are any error messages

3. **Check n8n logs**:
   - Look for HTTP request errors
   - Verify the webhook URL is correct

---

## Advanced Configuration

### Custom Severity Levels

You can modify the severity logic in the workflow. Edit the "Send to FlowDash" node:

```json
{
  "severity": "={{ $json.error.message.includes('critical') ? 'critical' : 'error' }}"
}
```

Severity levels:
- `info`: Blue notification (auto-dismiss)
- `warning`: Orange notification (auto-dismiss)
- `error`: Red notification (requires dismiss)
- `critical`: Red notification with warning banner (requires dismiss)

### Filtering Errors

To only send certain errors to FlowDash, add an IF node between Error Trigger and Send to FlowDash:

```
Error Trigger → IF Node (filter) → Send to FlowDash
```

Example IF condition:
```javascript
{{ $json.workflow.name.includes('Production') }}
```

This would only send errors from workflows with "Production" in the name.

---

## Security

- ✅ **No authentication required** for the webhook endpoint (by design)
- ✅ **Instance ID acts as the secret**: Only someone with your exact instance_id can send notifications
- ✅ **User verification**: FlowDash verifies the instance exists and belongs to a valid user
- ✅ **Plan verification**: FlowDash checks user has appropriate plan
- ✅ **HTTPS only**: All communication is encrypted

**Keep your instance_id private** - treat it like a password. Anyone with your instance_id could potentially send fake error notifications to your account.

---

## API Reference

### Get Workflow Template

```
GET /api/v1/error-workflows/template?instance_id={id}
```

**Authentication**: Required (Firebase token)

**Parameters**:
- `instance_id` (required): Your FlowDash instance ID

**Response**: Complete n8n workflow JSON

### Get Webhook URL

```
GET /api/v1/error-workflows/webhook-url
```

**Authentication**: Not required

**Response**:
```json
{
  "webhook_url": "https://api.flow-dash.com/api/v1/webhooks/n8n-error",
  "method": "POST",
  "required_fields": ["executionId", "workflowId", "instanceId", "error"],
  "optional_fields": ["workflowName", "severity"]
}
```

### Test Error Notification

```
POST /api/v1/webhooks/test-error
```

**Authentication**: Required (Firebase token)

**Plan Requirement**: Pro or higher

**Body**: Same as n8n-error webhook payload

---

## Support

- **Email**: support@flow-dash.com
- **Documentation**: https://docs.flow-dash.com
- **GitHub Issues**: https://github.com/flowdash/flowdash-backend/issues

---

## Changelog

- **v1.0.0** (2025-01): Initial release
  - API-generated workflow templates
  - Manual configuration support
  - Plan-based access control
  - Test endpoint for Pro+ users

