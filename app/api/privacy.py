"""The privacy notice's details (Nigeria Data Protection Act 2023). Public: a worker reads
it before registering a phone, and anyone may read it at /privacy."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["privacy"])


@router.get("/privacy")
def privacy(settings: Settings = Depends(get_settings)) -> dict:
    return {"company": settings.company_name, "contact": settings.privacy_contact}
