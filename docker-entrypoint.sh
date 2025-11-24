#!/bin/bash

# FlowDash Backend Production Entrypoint
# Waits for database and Redis, runs migrations, then starts the application

set -e

echo "Starting FlowDash Backend..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
timeout=60
counter=0

# Extract database connection details from DATABASE_URL
# Format: postgresql://user:password@host:port/dbname
DB_URL="${DATABASE_URL}"

# Use Python to check database connectivity
while [ $counter -lt $timeout ]; do
    if python3 -c "
import sys
import psycopg2
from urllib.parse import urlparse

try:
    parsed = urlparse('${DB_URL}')
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path[1:] if parsed.path else 'postgres'
    )
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    
    if [ $counter -eq 0 ]; then
        echo "Waiting for database connection..."
    fi
    
    sleep 1
    counter=$((counter + 1))
done

if [ $counter -ge $timeout ]; then
    echo "⚠ Warning: PostgreSQL did not become ready in time"
    echo "Continuing anyway - migrations may fail"
else
    # Run database migrations
    echo "Running database migrations..."
    alembic upgrade head
    
    if [ $? -eq 0 ]; then
        echo "✓ Migrations completed"
    else
        echo "⚠ Warning: Migration failed"
        echo "You may need to check your database connection or migration files."
        exit 1
    fi
fi

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
timeout=60
counter=0

# Use redis-cli when available; fall back to python redis client
REDIS_URL="${REDIS_URL:-redis://redis:6379/0}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"

# Parse host and port from REDIS_URL in a shell-safe way
# Example formats handled: redis://:password@host:6379/0 or redis://host:6379/0
host_port_part="${REDIS_URL#*://}"
# If there's an '@', take the part after it (host:port/...)
if [[ "$host_port_part" == *"@"* ]]; then
    host_port_part="${host_port_part#*@}"
fi
# Remove any path after host:port
host_port_part="${host_port_part%%/*}"

REDIS_HOST="${host_port_part%%:*}"
REDIS_PORT="${host_port_part##*:}"

# Fallbacks
if [ -z "${REDIS_HOST}" ] || [ "${REDIS_HOST}" = "${REDIS_PORT}" ]; then
    REDIS_HOST="redis"
fi
if ! [[ "${REDIS_PORT}" =~ ^[0-9]+$ ]]; then
    REDIS_PORT=6379
fi

while [ $counter -lt $timeout ]; do
    if command -v redis-cli >/dev/null 2>&1; then
        if [ -n "${REDIS_PASSWORD}" ]; then
            if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" ping >/dev/null 2>&1; then
                echo "✓ Redis is ready"
                break
            fi
        else
            if redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping >/dev/null 2>&1; then
                echo "✓ Redis is ready"
                break
            fi
        fi
    else
        # Fall back to python redis if installed
        if python3 -c "
import sys
from urllib.parse import urlparse
try:
    import redis
    parsed = urlparse('${REDIS_URL}')
    host = parsed.hostname or '${REDIS_HOST}'
    port = parsed.port or ${REDIS_PORT}
    password = '${REDIS_PASSWORD}' if '${REDIS_PASSWORD}' else None
    r = redis.Redis(host=host, port=int(port), password=password, socket_connect_timeout=2)
    r.ping()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            echo "✓ Redis is ready (python)"
            break
        fi
    fi

    if [ $counter -eq 0 ]; then
        echo "Waiting for Redis connection..."
    fi

    sleep 1
    counter=$((counter + 1))
done

if [ $counter -ge $timeout ]; then
    echo "❌ Error: Redis did not become ready in time"
    echo "Redis is required for rate limiting and caching"
    exit 1
fi

echo ""
echo "Starting FastAPI application..."
echo ""

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000


