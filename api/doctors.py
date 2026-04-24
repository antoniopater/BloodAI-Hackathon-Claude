"""GET /doctors — private doctor listings (stub)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(tags=["doctors"])


class Doctor(BaseModel):
    id: str
    source: str
    name: str
    specialty: str
    address: str
    city: str
    province: str
    triageClass: Optional[str] = None
    phone: Optional[str] = None
    bookingUrl: Optional[str] = None
    waitDays: Optional[int] = None
    nextAvailable: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class DoctorsResponse(BaseModel):
    doctors: List[Doctor]


@router.get("/doctors", response_model=DoctorsResponse)
async def get_doctors(
    specialty: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
) -> DoctorsResponse:
    """Private doctor listings. Stub — returns empty list until a third-party
    source (Google Places / Znany Lekarz) is integrated."""
    return DoctorsResponse(doctors=[])
