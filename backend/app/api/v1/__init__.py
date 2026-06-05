"""API v1 sub-package.

Routers are imported here and assembled into *api_router* which is then
mounted by the application factory in :mod:`app.main`.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.workflow.attachments import router as attachments_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(attachments_router)
