from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.firebase import init_firebase
from app.core.database import engine, Base
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.api.v1.router import api_router
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_version() -> str:
    """Read version from VERSION file, fallback to default if not found."""
    version_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    try:
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:
                    return version
    except Exception as e:
        logger.warning(f"Could not read VERSION file: {e}")
    # Fallback to default version
    return "1.0.0"


# Initialize Firebase
init_firebase()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FlowDash API",
    version=get_version(),
    debug=settings.debug,
    redirect_slashes=False,
)

# Add CORS middleware (must be first, before rate limiting)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware (applies to all requests)
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(api_router, prefix=settings.api_v1_str)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

