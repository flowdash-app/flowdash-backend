# FlowDash Backend - Development Plan

## Overview
This document provides a comprehensive development plan for the FlowDash backend API built with FastAPI (Python).

## Prerequisites

### 1. Research Latest Package Versions
Before installation, verify the latest stable versions on [PyPI](https://pypi.org):
- Python: 3.11+
- FastAPI: Latest stable
- uvicorn: Latest stable
- sqlalchemy: Latest stable
- psycopg2-binary: Latest stable (or psycopg for async)
- alembic: Latest stable
- firebase-admin: Latest stable
- pydantic: Latest stable (usually comes with FastAPI)
- python-dotenv: Latest stable

### 2. Python Installation
```bash
# Check Python version (must be 3.11+)
python3 --version

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Upgrade pip
pip install --upgrade pip
```

## Project Initialization

### 1. Create Project Structure
```bash
cd flowdash-backend
mkdir -p app/{api,core,models,services,notifier}
mkdir -p alembic/versions
touch app/__init__.py
touch app/main.py
touch requirements.txt
touch .env.example
touch Dockerfile
```

### 2. Install Dependencies
Create `requirements.txt`:

```txt
# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9

# Database
sqlalchemy==2.0.35
psycopg2-binary==2.9.10
alembic==1.13.2

# Firebase
firebase-admin==6.5.0

# Authentication & Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Environment
python-dotenv==1.0.1
pydantic==2.9.0
pydantic-settings==2.5.0

# HTTP Client (for FCM)
httpx==0.27.0

# Logging
structlog==24.1.0

# Encryption
cryptography==42.0.7

# Development
pytest==8.3.0
pytest-asyncio==0.23.7
black==24.4.2
ruff==0.5.0
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Project Structure

```
app/
├── __init__.py
├── main.py
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── workflows.py
│   │   │   ├── instances.py
│   │   │   └── webhooks.py
│   │   └── router.py
│   └── dependencies.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── firebase.py
│   ├── middleware.py
│   └── security.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── n8n_instance.py
│   ├── quota.py
│   └── audit_log.py
├── services/
│   ├── __init__.py
│   ├── auth_service.py
│   ├── workflow_service.py
│   ├── instance_service.py
│   ├── quota_service.py
│   └── fcm_service.py
└── notifier/
    ├── __init__.py
    └── webhook_handler.py
alembic/
├── env.py
├── script.py.mako
└── versions/
tests/
├── __init__.py
└── test_api/
.env.example
docker-compose.dev.yml
docker-compose.prod.yml
Dockerfile
requirements.txt
```

## Implementation Steps

### 1. Environment Configuration

Create `.env.example`:
```env
# Database
DATABASE_URL=postgresql://flowdash:password@localhost:5432/flowdash_db

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# API
API_V1_STR=/api/v1
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# FCM
FCM_SERVER_KEY=your-fcm-server-key

# Environment
ENVIRONMENT=development
DEBUG=True
```

Create `app/core/config.py`:
```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str
    
    # Firebase
    firebase_project_id: str
    firebase_credentials_path: str
    
    # API
    api_v1_str: str = "/api/v1"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # FCM
    fcm_server_key: Optional[str] = None
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### 2. Database Setup

Create `app/core/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 3. Firebase Admin SDK Setup

Create `app/core/firebase.py`:
```python
import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def init_firebase():
    """Initialize Firebase Admin SDK"""
    logger.info("init_firebase: Entry")
    
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.firebase_credentials_path)
            firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id,
            })
            logger.info("init_firebase: Success")
        else:
            logger.info("init_firebase: Already initialized")
    except Exception as e:
        logger.error(f"init_firebase: Failure - {e}")
        raise

def verify_firebase_token(token: str) -> dict:
    """Verify Firebase JWT token and return decoded token"""
    logger.info("verify_firebase_token: Entry")
    
    try:
        decoded_token = auth.verify_id_token(token)
        logger.info(f"verify_firebase_token: Success - {decoded_token.get('uid')}")
        return decoded_token
    except Exception as e:
        logger.error(f"verify_firebase_token: Failure - {e}")
        raise
```

### 4. JWT Middleware for Firebase Authentication

Create `app/core/middleware.py`:
```python
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.firebase import verify_firebase_token
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security
) -> dict:
    """
    Dependency to get current authenticated user from Firebase token.
    Protects routes that require authentication.
    """
    logger.info("get_current_user: Entry")
    
    try:
        token = credentials.credentials
        decoded_token = verify_firebase_token(token)
        user_id = decoded_token.get('uid')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        logger.info(f"get_current_user: Success - {user_id}")
        return {
            'uid': user_id,
            'email': decoded_token.get('email'),
            'token': decoded_token
        }
    except Exception as e:
        logger.error(f"get_current_user: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

### 5. Database Models

Create `app/models/user.py`:
```python
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)  # Firebase UID
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    n8n_instances = relationship("N8NInstance", back_populates="user", cascade="all, delete-orphan")
```

Create `app/models/n8n_instance.py`:
```python
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import json

class N8NInstance(Base):
    __tablename__ = "n8n_instances"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    api_key_encrypted = Column(Text, nullable=False)  # Encrypted API key
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="n8n_instances")
```

Create `app/models/quota.py`:
```python
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, date

class Quota(Base):
    __tablename__ = "quotas"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    quota_type = Column(String, nullable=False, index=True)  # 'toggles', 'refreshes', 'error_views', etc.
    count = Column(Integer, default=0)
    quota_date = Column(Date, default=date.today, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
```

Create `app/models/audit_log.py`:
```python
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)  # 'toggle_workflow', 'view_error', etc.
    resource_type = Column(String, nullable=False)  # 'workflow', 'instance', etc.
    resource_id = Column(String, nullable=True)
    metadata = Column(Text)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User")
```

### 6. Alembic Migration Setup

Initialize Alembic:
```bash
alembic init alembic
```

Update `alembic/env.py`:
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from app.core.database import Base
from app.core.config import settings
from app.models import user, n8n_instance, quota, audit_log

# Set database URL
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

# Import all models
target_metadata = Base.metadata

# ... rest of alembic config
```

Create initial migration:
```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 7. API Routes Structure

Create `app/api/v1/router.py`:
```python
from fastapi import APIRouter
from app.api.v1.routes import workflows, instances, webhooks

api_router = APIRouter()

api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
```

Create `app/api/v1/routes/workflows.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from app.core.middleware import get_current_user
from app.services.workflow_service import WorkflowService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def get_workflows(
    instance_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get workflows for an n8n instance"""
    logger.info(f"get_workflows: Entry - user: {current_user['uid']}, instance: {instance_id}")
    
    try:
        service = WorkflowService()
        workflows = await service.get_workflows(instance_id, current_user['uid'])
        logger.info(f"get_workflows: Success - {len(workflows)} workflows")
        return workflows
    except Exception as e:
        logger.error(f"get_workflows: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    workflow_id: str,
    instance_id: str,
    enabled: bool,
    current_user: dict = Depends(get_current_user),
):
    """Toggle workflow on/off"""
    logger.info(f"toggle_workflow: Entry - user: {current_user['uid']}, workflow: {workflow_id}")
    
    try:
        service = WorkflowService()
        result = await service.toggle_workflow(
            instance_id, workflow_id, enabled, current_user['uid']
        )
        logger.info(f"toggle_workflow: Success - workflow: {workflow_id}, enabled: {enabled}")
        return result
    except Exception as e:
        logger.error(f"toggle_workflow: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 8. Webhook Handler for n8n Errors

Create `app/notifier/webhook_handler.py`:
```python
from fastapi import APIRouter, Request, HTTPException
from app.services.fcm_service import FCMService
from app.services.instance_service import InstanceService
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/n8n-error")
async def handle_n8n_error(request: Request):
    """Handle n8n error webhook and send FCM push notification"""
    logger.info("handle_n8n_error: Entry")
    
    try:
        body = await request.json()
        
        # Validate webhook payload
        execution_id = body.get("executionId")
        workflow_id = body.get("workflowId")
        instance_id = body.get("instanceId")
        error = body.get("error")
        
        if not execution_id or not workflow_id or not instance_id:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        logger.info(f"handle_n8n_error: Processing - execution: {execution_id}, workflow: {workflow_id}")
        
        # Get instance owner
        instance_service = InstanceService()
        instance = await instance_service.get_instance(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        
        # Send FCM notification
        fcm_service = FCMService()
        await fcm_service.send_error_notification(
            user_id=instance.user_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            error_message=error.get("message", "Unknown error") if error else "Workflow execution failed"
        )
        
        logger.info(f"handle_n8n_error: Success - notification sent to user: {instance.user_id}")
        return {"status": "success", "message": "Notification sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"handle_n8n_error: Failure - {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 9. FCM Service

Create `app/services/fcm_service.py`:
```python
import httpx
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class FCMService:
    def __init__(self):
        self.server_key = settings.fcm_server_key
        self.fcm_url = "https://fcm.googleapis.com/v1/projects/{}/messages:send".format(
            settings.firebase_project_id
        )
    
    async def send_error_notification(
        self,
        user_id: str,
        workflow_id: str,
        execution_id: str,
        error_message: str
    ):
        """Send FCM push notification for n8n error"""
        logger.info(f"send_error_notification: Entry - user: {user_id}, execution: {execution_id}")
        
        try:
            # Get FCM token for user (from database or cache)
            # Implementation depends on how tokens are stored
            
            # Send notification
            # Implementation using FCM HTTP v1 API
            
            logger.info(f"send_error_notification: Success")
        except Exception as e:
            logger.error(f"send_error_notification: Failure - {e}")
            raise
```

### 10. Analytics and Monitoring Setup

#### a. Create Analytics Service
Create `app/services/analytics_service.py`:

```python
from firebase_admin import firestore
from app.core.firebase import get_firestore_client
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self):
        self.db = firestore.client()
        self.events_collection = 'analytics_events'
        self.errors_collection = 'error_logs'
    
    def log_event(
        self,
        event_name: str,
        user_id: str = None,
        parameters: dict = None,
        status: str = 'success'
    ):
        """Log analytics event to Firestore"""
        logger.info(f"log_event: Entry - {event_name}, user: {user_id}, status: {status}")
        
        try:
            event_data = {
                'event_name': event_name,
                'user_id': user_id,
                'status': status,
                'parameters': parameters or {},
                'timestamp': datetime.utcnow(),
            }
            
            self.db.collection(self.events_collection).add(event_data)
            logger.info(f"log_event: Success - {event_name}")
        except Exception as e:
            logger.error(f"log_event: Failure - {e}")
    
    def log_success(
        self,
        action: str,
        user_id: str = None,
        parameters: dict = None
    ):
        """Log successful action"""
        self.log_event(
            event_name=f'{action}_success',
            user_id=user_id,
            parameters=parameters,
            status='success'
        )
    
    def log_failure(
        self,
        action: str,
        error: str,
        user_id: str = None,
        parameters: dict = None
    ):
        """Log failed action"""
        logger.info(f"log_failure: Entry - {action}, error: {error}")
        
        try:
            # Log to analytics
            self.log_event(
                event_name=f'{action}_failure',
                user_id=user_id,
                parameters={**(parameters or {}), 'error': error},
                status='failure'
            )
            
            # Log to error collection
            error_data = {
                'action': action,
                'user_id': user_id,
                'error': error,
                'parameters': parameters or {},
                'timestamp': datetime.utcnow(),
            }
            self.db.collection(self.errors_collection).add(error_data)
            
            logger.info(f"log_failure: Success - {action}")
        except Exception as e:
            logger.error(f"log_failure: Failure - {e}")
```

#### b. Integrate Analytics in Services
Every service method MUST log analytics:

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

### 11. Main Application

Create `app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.firebase import init_firebase
from app.core.database import engine, Base
from app.api.v1.router import api_router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase
init_firebase()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FlowDash API",
    version="1.0.0",
    debug=settings.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router, prefix=settings.api_v1_str)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Docker Setup

### Dockerfile
Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Development Docker Compose
See `docker-compose.dev.yml` (created separately)

### Production Docker Compose
See `docker-compose.prod.yml` (created separately)

## Development Commands

### Run Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Testing
```bash
pytest
pytest --cov=app tests/
```

### Code Formatting
```bash
black app/
ruff check app/
```

## Next Steps

1. Implement encryption for n8n API keys
2. Complete FCM service implementation
3. Add quota checking middleware
4. Implement audit logging
5. Add rate limiting
6. Set up monitoring and logging
7. Configure CI/CD pipeline

