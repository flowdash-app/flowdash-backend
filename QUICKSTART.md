# Quick Start Guide - FlowDash Backend

## Step 1: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Set Up Environment Variables

Make sure your `.env` file is configured with all required values:

```bash
# Check if .env exists
cat .env

# If missing, copy from example
cp .env.example .env
```

Required variables:
- `DATABASE_URL` - PostgreSQL connection string
- `FIREBASE_PROJECT_ID` - Your Firebase project ID
- `FIREBASE_CREDENTIALS_PATH` - Path to Firebase service account JSON
- `SECRET_KEY` - Generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- `ENCRYPTION_KEY` - Generate with: `python3 -c "import base64; import os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`

## Step 3: Start Database (Choose One)

### Option A: Using Docker (Recommended for Development)

```bash
# Start PostgreSQL container
docker-compose -f docker-compose.dev.yml up -d

# Check if database is running
docker ps | grep postgres

# Database will be available at: postgresql://flowdash:flowdash_dev_password@localhost:5432/flowdash_db
```

### Option B: Using Local PostgreSQL

Make sure PostgreSQL is installed and running, then update `DATABASE_URL` in `.env`.

## Step 4: Run Database Migrations

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Create initial migration (first time only)
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head

# Verify tables were created (optional)
# Connect to database and check: \dt
```

## Step 5: Start the Development Server

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Start server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Step 6: Verify Everything Works

### Check Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

### Check API Documentation

Open in browser: http://localhost:8000/docs

You should see:
- Swagger UI with all API endpoints
- Ability to test endpoints interactively

### Test Authentication (Requires Firebase Token)

```bash
# This will fail without a valid Firebase token (expected)
curl http://localhost:8000/api/v1/instances

# Expected: 401 Unauthorized
```

## Common Issues & Solutions

### Issue: ModuleNotFoundError

**Solution**: Make sure virtual environment is activated and dependencies are installed:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Database Connection Error

**Solution**: 
1. Check if PostgreSQL is running: `docker ps` or `pg_isready`
2. Verify `DATABASE_URL` in `.env` is correct
3. Check database credentials match docker-compose settings

### Issue: Firebase Initialization Error

**Solution**:
1. Verify `FIREBASE_CREDENTIALS_PATH` points to valid JSON file
2. Check `FIREBASE_PROJECT_ID` matches your Firebase project
3. Ensure Firebase service account has proper permissions

### Issue: Migration Errors

**Solution**:
```bash
# Check current migration status
alembic current

# If needed, rollback and reapply
alembic downgrade base
alembic upgrade head
```

## Development Commands

```bash
# Format code
black app/

# Lint code
ruff check app/

# Run tests (when tests are added)
pytest

# View logs
# Logs are printed to console when running uvicorn
```

## Stopping the Server

Press `Ctrl+C` in the terminal running uvicorn.

## Stopping Docker Database

```bash
docker-compose -f docker-compose.dev.yml down
```


