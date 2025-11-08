# FlowDash Backend API

FastAPI backend for FlowDash - a workflow management platform for n8n instances.

## Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Firebase project with Admin SDK credentials
- Docker and Docker Compose (optional, for containerized development)

## Setup

### 1. Clone and Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project root (use `.env.example` as a template):

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

- `DATABASE_URL`: PostgreSQL connection string
- `FIREBASE_PROJECT_ID`: Your Firebase project ID
- `FIREBASE_CREDENTIALS_PATH`: Path to Firebase service account JSON file
- `ENCRYPTION_KEY`: Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Other configuration as needed

### 3. Database Setup

```bash
# Run migrations
alembic upgrade head

# Or create initial migration if needed
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 4. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Docker Setup

### Development

```bash
docker-compose -f docker-compose.dev.yml up
```

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Project Structure

```
app/
├── api/              # API routes and endpoints
│   └── v1/
│       ├── routes/   # Route handlers
│       └── router.py
├── core/             # Core functionality
│   ├── config.py     # Configuration
│   ├── database.py  # Database setup
│   ├── firebase.py  # Firebase Admin SDK
│   ├── middleware.py # Authentication middleware
│   └── security.py  # Encryption utilities
├── models/           # SQLAlchemy models
├── services/        # Business logic
├── notifier/        # Webhook handlers
└── main.py          # Application entry point
```

## API Endpoints

### Workflows
- `GET /api/v1/workflows?instance_id={id}` - List workflows
- `POST /api/v1/workflows/{workflow_id}/toggle?instance_id={id}&enabled={bool}` - Toggle workflow

### Instances
- `GET /api/v1/instances` - List instances
- `POST /api/v1/instances` - Create instance
- `GET /api/v1/instances/{id}` - Get instance
- `PUT /api/v1/instances/{id}` - Update instance
- `DELETE /api/v1/instances/{id}` - Delete instance

### Webhooks
- `POST /api/v1/webhooks/n8n-error` - Handle n8n error webhook

## Authentication

All protected routes require Firebase JWT token in the Authorization header:

```
Authorization: Bearer <firebase-id-token>
```

## Development

### Code Formatting

```bash
black app/
ruff check app/
```

### Running Tests

```bash
pytest
pytest --cov=app tests/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Environment Variables

See `.env.example` for all required environment variables.

## License

[Your License Here]

