from fastapi import APIRouter
from app.api.v1.routes import workflows, instances, webhooks, devices

api_router = APIRouter()

api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])

