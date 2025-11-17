# FlowDash Backend - AI Agents Configuration

This document provides essential information for AI agents working on the FlowDash backend API.

## Middleware Configuration

### Firebase JWT Authentication Middleware

All protected routes must use the `get_current_user` dependency:

```python
from app.core.middleware import get_current_user

@router.get("/protected")
async def protected_route(current_user: dict = Depends(get_current_user)):
    # current_user contains: {'uid', 'email', 'token'}
    pass
```

### Middleware Application Order

1. CORS middleware (first)
2. Authentication middleware (via dependencies)
3. Route handlers

### Protected vs Public Routes

- **Protected Routes**: Use `Depends(get_current_user)`
- **Public Routes**: No dependency required
- **Webhook Routes**: No authentication (validate webhook secret instead)

### Token Validation Patterns

```python
# Token is extracted from Authorization header
# Format: "Bearer <token>"
# Validated using Firebase Admin SDK
decoded_token = auth.verify_id_token(token)
```

### Error Responses for Auth Failures

- **401 Unauthorized**: Invalid or missing token
- **403 Forbidden**: Valid token but insufficient permissions
- Always include `WWW-Authenticate: Bearer` header

## Database Schema

### User Model

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # Firebase UID
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    is_active = Column(Boolean)
    
    # Relationships
    n8n_instances = relationship("N8NInstance", back_populates="user")
```

### N8NInstance Model

```python
class N8NInstance(Base):
    __tablename__ = "n8n_instances"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    name = Column(String)
    url = Column(String)
    api_key_encrypted = Column(Text)  # Encrypted!
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="n8n_instances")
```

### Quota Model

```python
class Quota(Base):
    __tablename__ = "quotas"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    quota_type = Column(String, index=True)  # 'toggles', 'refreshes', etc.
    count = Column(Integer, default=0)
    quota_date = Column(Date, index=True)  # Daily quotas
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

### AuditLog Model

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    action = Column(String, index=True)  # 'toggle_workflow', etc.
    resource_type = Column(String)
    resource_id = Column(String)
    metadata = Column(Text)  # JSON
    created_at = Column(DateTime, index=True)
```

### Table Relationships and Foreign Keys

- `n8n_instances.user_id` → `users.id` (CASCADE DELETE)
- `quotas.user_id` → `users.id`
- `audit_logs.user_id` → `users.id`

### Indexes for Performance

- All foreign keys are indexed
- `quotas.quota_date` indexed for daily quota queries
- `audit_logs.created_at` indexed for time-based queries
- `quotas.quota_type` indexed for quota type lookups

### Constraints and Validations

- `users.email` must be unique
- `n8n_instances.user_id` must reference valid user
- `quotas.count` must be >= 0
- All timestamps use UTC

### Migration Patterns

- Use Alembic for all schema changes
- Always create migrations: `alembic revision --autogenerate`
- Review generated migrations before applying
- Test migrations on development database first

## API Structure

### Endpoint Organization

```
/api/v1/
  /workflows
    GET / - List workflows
    GET /{id} - Get workflow details
    POST /{id}/toggle - Toggle workflow
  /instances
    GET / - List instances
    POST / - Create instance
    GET /{id} - Get instance
    PUT /{id} - Update instance
    DELETE /{id} - Delete instance
  /webhooks
    POST /n8n-error - Handle n8n error webhook
```

### Request/Response Models (Pydantic)

```python
from pydantic import BaseModel

class WorkflowResponse(BaseModel):
    id: str
    name: str
    active: bool
    nodes: list[dict]
    
    class Config:
        from_attributes = True
```

### Route Decorators and Dependencies

```python
@router.get("/", dependencies=[Depends(get_current_user)])
async def get_workflows():
    pass

# Or inline dependency
@router.post("/")
async def create_workflow(
    current_user: dict = Depends(get_current_user)
):
    pass
```

### Error Handling Patterns

```python
from fastapi import HTTPException, status

try:
    result = await service.do_something()
    return result
except NotFoundError:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Resource not found"
    )
except ValidationError as e:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(e)
    )
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )
```

### API Versioning Strategy

- Current version: `/api/v1`
- Future versions: `/api/v2`, etc.
- Version in URL path, not headers
- Maintain backward compatibility when possible

## Authentication/Authorization

### Firebase Admin SDK Initialization

```python
# Initialize once at application startup
cred = credentials.Certificate(settings.firebase_credentials_path)
firebase_admin.initialize_app(cred, {
    'projectId': settings.firebase_project_id,
})
```

### JWT Token Verification Flow

1. Extract token from `Authorization: Bearer <token>` header
2. Verify token using `auth.verify_id_token(token)`
3. Extract user ID from decoded token
4. Optionally fetch user from database
5. Inject user context into route handler

### User Context Injection

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security
) -> dict:
    token = credentials.credentials
    decoded_token = verify_firebase_token(token)
    return {
        'uid': decoded_token.get('uid'),
        'email': decoded_token.get('email'),
        'token': decoded_token
    }
```

### Permission Checking Patterns

```python
# Check if user owns resource
if resource.user_id != current_user['uid']:
    raise HTTPException(status_code=403, detail="Forbidden")

# Check user tier/permissions
user = await get_user_from_db(current_user['uid'])
if user.tier == 'free' and action_requires_pro:
    raise HTTPException(status_code=403, detail="Upgrade required")
```

## Database Migrations (Alembic)

### Migration Creation Commands

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description"

# Create empty migration
alembic revision -m "Description"
```

### Migration File Structure

```python
"""Description

Revision ID: xxxx
Revises: yyyy
Create Date: 2025-01-XX
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'table_name',
        sa.Column('id', sa.String(), nullable=False),
        # ... more columns
    )

def downgrade():
    op.drop_table('table_name')
```

### Rollback Procedures

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

## Environment Configuration

### Environment Variable Management

- Use `pydantic-settings` for configuration
- Store sensitive values in `.env` file (not committed)
- Provide `.env.example` with placeholder values
- Load environment variables at startup

### Configuration Classes

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    firebase_project_id: str
    # ... more settings
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### Secrets Management

- Never commit `.env` file
- Use environment variables in production
- Consider using secret management services (AWS Secrets Manager, etc.)
- Encrypt sensitive data in database (n8n API keys)

## Docker Setup

### Dockerfile Structure

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose Configuration

- **Development**: PostgreSQL only (for local development)
- **Production**: PostgreSQL + FastAPI service
- Use named volumes for data persistence
- Configure networks for service communication

### Volume Mounts

- Database data: `postgres_data:/var/lib/postgresql/data`
- Application code: Mounted as volume in dev, copied in prod

### Network Configuration

- Create custom network: `flowdash_network`
- Services communicate via service names
- Expose only necessary ports

## Webhook Handlers

### n8n Error Notification Webhook

- Endpoint: `POST /api/v1/webhooks/n8n-error`
- No authentication (validate webhook secret if needed)
- Accepts JSON payload with execution details
- Sends FCM push notification to instance owner

### Request Validation

```python
required_fields = ['executionId', 'workflowId', 'instanceId']
for field in required_fields:
    if field not in body:
        raise HTTPException(status_code=400, detail=f"Missing {field}")
```

### FCM Push Notification Integration

- Use Firebase Cloud Messaging HTTP v1 API
- Get FCM tokens from database (stored per user)
- Send notification with error details
- Include deep link to execution details

## Code Organization

### Project Structure

```
app/
  api/          # API routes and endpoints
  core/         # Core functionality (config, database, middleware)
  models/       # SQLAlchemy models
  services/     # Business logic
  notifier/     # Webhook handlers
```

### Naming Conventions

- **Files**: snake_case (`auth_service.py`)
- **Classes**: PascalCase (`AuthService`)
- **Functions**: snake_case (`get_current_user`)
- **Constants**: UPPER_SNAKE_CASE (`API_V1_STR`)
- **Variables**: snake_case (`current_user`)

### Import Organization

```python
# Standard library
import logging
from datetime import datetime

# Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# Local
from app.core.middleware import get_current_user
from app.models.user import User
```

## Error Handling

### Custom Exception Classes

```python
class AppException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class NotFoundError(AppException):
    pass

class ValidationError(AppException):
    pass
```

### Error Response Formatting

```python
{
    "detail": "Error message",
    "error_code": "ERROR_CODE",
    "timestamp": "2025-01-XX..."
}
```

### Logging Patterns

```python
import logging

logger = logging.getLogger(__name__)

def some_function():
    logger.info("some_function: Entry")
    try:
        # Implementation
        logger.info("some_function: Success")
    except Exception as e:
        logger.error(f"some_function: Failure - {e}", exc_info=True)
        raise
```

## Service Layer Patterns

### Service Method Structure

```python
class WorkflowService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def get_workflows(self, instance_id: str, user_id: str):
        self.logger.info(f"get_workflows: Entry - instance: {instance_id}, user: {user_id}")
        
        try:
            # Implementation
            self.logger.info(f"get_workflows: Success")
            return result
        except Exception as e:
            self.logger.error(f"get_workflows: Failure - {e}")
            raise
```

### Database Session Management

```python
from app.core.database import get_db

@router.get("/")
async def endpoint(db: Session = Depends(get_db)):
    # Use db session
    pass
```

### Transaction Handling

```python
try:
    db.begin()
    # Multiple operations
    db.commit()
except Exception:
    db.rollback()
    raise
```

## Quota Management

### Quota Checking

- Check quota before allowing action
- Increment quota count atomically
- Reset quotas daily (via scheduled task)
- Different quota types: toggles, refreshes, error_views

### Quota Service Pattern

```python
async def check_quota(user_id: str, quota_type: str, limit: int) -> bool:
    quota = await get_or_create_quota(user_id, quota_type)
    if quota.count >= limit:
        return False
    quota.count += 1
    await save_quota(quota)
    return True
```

## Encryption

### n8n API Key Encryption

- Use `cryptography` library
- Encrypt before storing in database
- Decrypt when needed for API calls
- Store encryption key securely (environment variable)

### Encryption Pattern

```python
from cryptography.fernet import Fernet

key = settings.encryption_key.encode()
cipher = Fernet(key)

encrypted = cipher.encrypt(api_key.encode())
decrypted = cipher.decrypt(encrypted).decode()
```

## Analytics and Monitoring (REQUIRED)

### Analytics Service

All services MUST use `AnalyticsService` to log events and errors to Firebase via Admin SDK:

```python
from app.services.analytics_service import AnalyticsService

class AnalyticsService:
    def __init__(self):
        # Firebase Admin SDK
        self.db = get_firestore_client()
        self.analytics_collection = 'analytics_events'      # Firebase Analytics
        self.crashlytics_collection = 'crashlytics_errors'  # Crashlytics-style error tracking
    
    def log_success(self, action: str, user_id: str = None, parameters: dict = None):
        """Log successful action to Firebase Analytics"""
        # Tracks successful operations for product analytics
        # Stored in: analytics_events
    
    def log_failure(self, action: str, error: str, user_id: str = None, parameters: dict = None, stack_trace: str = None):
        """Log failed action to BOTH Analytics and Crashlytics"""
        # 1. Tracks failure rate in analytics_events (product metrics)
        # 2. Logs error to crashlytics_errors (error monitoring & debugging)
    
    def log_crash(self, error: str, action: str, user_id: str = None, parameters: dict = None, stack_trace: str = None, fatal: bool = False):
        """Log error to Crashlytics-style error tracking"""
        # Use for tracking exceptions and crashes
        # Stored in: crashlytics_errors
```

### Purpose-Based Usage

#### Firebase Analytics (Product Metrics)
Use for tracking **user behavior** and **feature usage**:
- Success rates of operations
- Feature adoption
- User flows and journeys
- Performance metrics
- Stored in: `analytics_events` Firestore collection

#### Crashlytics (Error Monitoring)
Use for tracking **errors** and **debugging**:
- Exception details and stack traces
- Error frequency and patterns
- Non-fatal errors (caught exceptions)
- Fatal errors (crashes)
- Stored in: `crashlytics_errors` Firestore collection

### Required Events

Every service method MUST log both analytics and errors:

1. **Success Events** → Firebase Analytics
   - Format: `{action}_success`
   - Include: action name, user_id, relevant parameters
   - Purpose: Track successful operations, feature usage
   - Collection: `analytics_events`

2. **Failure Events** → BOTH Analytics + Crashlytics
   - Format: `{action}_failure`
   - Include: action name, error message, user_id, parameters, stack_trace
   - Purpose: 
     - Analytics: Track failure rates for product metrics
     - Crashlytics: Monitor errors for debugging
   - Collections: `analytics_events` + `crashlytics_errors`

### Integration Pattern

Every service MUST integrate analytics:

```python
class WorkflowService:
    def __init__(self):
        self.analytics = AnalyticsService()
        self.logger = logging.getLogger(__name__)
    
    async def toggle_workflow(self, instance_id: str, workflow_id: str, enabled: bool, user_id: str):
        self.logger.info(f"toggle_workflow: Entry - user: {user_id}, workflow: {workflow_id}")
        
        try:
            # Implementation
            self.analytics.log_success(
                action='toggle_workflow',
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'enabled': enabled,
                }
            )
            self.logger.info(f"toggle_workflow: Success")
            return result
        except Exception as e:
            self.analytics.log_failure(
                action='toggle_workflow',
                error=str(e),
                user_id=user_id,
                parameters={
                    'instance_id': instance_id,
                    'workflow_id': workflow_id,
                    'enabled': enabled,
                }
            )
            self.logger.error(f"toggle_workflow: Failure - {e}")
            raise
```

### Firebase Collections

#### 1. analytics_events (Firebase Analytics)

**Purpose**: Product analytics and user behavior tracking

**Event Structure**:
```json
{
  "event_name": "toggle_workflow_success",
  "user_id": "firebase_uid",
  "parameters": {
    "status": "success",
    "instance_id": "...",
    "workflow_id": "..."
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Use for**:
- Success/failure rates
- Feature usage metrics
- User journey tracking
- Performance analytics

#### 2. crashlytics_errors (Crashlytics Error Tracking)

**Purpose**: Error monitoring and debugging

**Error Structure**:
```json
{
  "action": "toggle_workflow",
  "user_id": "firebase_uid",
  "error_message": "Connection timeout",
  "stack_trace": "...",
  "parameters": {
    "instance_id": "...",
    "workflow_id": "..."
  },
  "fatal": false,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Use for**:
- Error frequency and patterns
- Stack traces for debugging
- Non-fatal error tracking
- Fatal crash tracking

#### Viewing Data

1. **Firebase Console**: Firestore Database → View both collections
2. **BigQuery Export** (optional): Export for SQL queries and dashboards
3. **Custom Monitoring**: Build alerts on error frequency
4. **Unified View**: Correlate analytics events with errors

### User ID Tracking

Always include `user_id` in analytics events:

- Extract from `current_user['uid']` in route handlers
- Pass to service methods
- Include in all analytics calls

### Event Naming Conventions

- Use snake_case: `toggle_workflow`, `refresh_workflows`
- Success suffix: `{action}_success`
- Failure suffix: `{action}_failure`
- Be consistent across the application

### Performance Considerations

- Firestore writes are asynchronous - don't block on analytics
- Analytics failures do not break main functionality
- Failed analytics are logged but do not throw exceptions
- Use Firebase Admin SDK which handles connection pooling and retries
