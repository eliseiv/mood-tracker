"""API v1 aggregate router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import activities, entries, me, moods, transcriptions

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(me.router)
api_v1_router.include_router(moods.router)
api_v1_router.include_router(activities.router)
api_v1_router.include_router(transcriptions.router)
api_v1_router.include_router(entries.router)
