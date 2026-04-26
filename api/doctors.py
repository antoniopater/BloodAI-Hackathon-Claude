"""GET /doctors — private doctor listings via Google Places Text Search."""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import httpx
from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["doctors"])

PLACES_TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_NEARBYSEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Province code → capital city (fallback when no city filter given)
PROVINCE_CAPITALS: dict[str, str] = {
    "01": "Wrocław", "02": "Bydgoszcz", "03": "Lublin", "04": "Zielona Góra",
    "05": "Łódź", "06": "Kraków", "07": "Warszawa", "08": "Opole",
    "09": "Rzeszów", "10": "Białystok", "11": "Gdańsk", "12": "Katowice",
    "13": "Kielce", "14": "Olsztyn", "15": "Poznań", "16": "Szczecin",
}

SPECIALTY_QUERIES: dict[str, str] = {
    # TriageClass values (from frontend) → Polish Places query
    "Hematology": "hematolog poradnia hematologiczna",
    "Nephrology": "nefrolog poradnia nefrologiczna",
    "Cardiology": "kardiolog poradnia kardiologiczna",
    "Hepatology": "hepatolog gastroenterolog poradnia hepatologiczna",
    "Gastroenterology": "gastroenterolog poradnia gastroenterologiczna",
    "Pulmonology": "pulmonolog poradnia chorób płuc",
    "POZ": "lekarz pierwszego kontaktu przychodnia",
    "ER": "szpitalny oddział ratunkowy SOR",
}


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
    distanceKm: Optional[float] = None
    rating: Optional[float] = None
    reviewCount: Optional[int] = None
    pricePln: Optional[int] = None
    waitDays: Optional[int] = None
    nextAvailable: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class DoctorsResponse(BaseModel):
    doctors: List[Doctor]


import math


def _maps_url(place_id: str) -> str:
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _parse_places(results: list, specialty: str, city: str, user_lat: Optional[float], user_lng: Optional[float], limit: int) -> List[Doctor]:
    doctors: List[Doctor] = []
    for i, place in enumerate(results[:limit]):
        loc = place.get("geometry", {}).get("location", {})
        place_id = place.get("place_id", f"place-{i}")
        address = place.get("formatted_address", place.get("vicinity", ""))
        address_clean = address.replace(", Polska", "").replace(", Poland", "")
        place_lat = loc.get("lat")
        place_lng = loc.get("lng")
        dist = None
        if user_lat is not None and user_lng is not None and place_lat and place_lng:
            dist = round(_haversine_km(user_lat, user_lng, place_lat, place_lng), 2)
        doctors.append(Doctor(
            id=f"private-{place_id}",
            source="private",
            name=place.get("name", ""),
            specialty=specialty,
            triageClass=specialty,
            address=address_clean,
            city=city,
            province="",
            rating=place.get("rating"),
            reviewCount=place.get("user_ratings_total"),
            bookingUrl=_maps_url(place_id),
            distanceKm=dist,
            lat=place_lat,
            lng=place_lng,
        ))
    return doctors


async def _fetch_er_near_coords(user_lat: float, user_lng: float, limit: int) -> List[Doctor]:
    """Nearest SOR/ER hospitals using Places Nearby Search."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return []

    params = {
        "location": f"{user_lat},{user_lng}",
        "radius": 30000,  # 30 km — rankby and radius are mutually exclusive, radius wins
        "keyword": "SOR szpitalny oddział ratunkowy",
        "type": "hospital",
        "key": api_key,
        "language": "pl",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(PLACES_NEARBYSEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Google Places NearbySearch error: %s", exc)
        return []

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        logger.warning("Google Places returned status: %s", data.get("status"))
        return []

    doctors = _parse_places(data.get("results", []), "ER", "Nearest", user_lat, user_lng, limit)
    doctors.sort(key=lambda d: d.distanceKm if d.distanceKm is not None else float("inf"))
    return doctors


async def _fetch_doctors_from_places(
    specialty: str,
    city: str,
    limit: int,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
) -> List[Doctor]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return []

    query_term = SPECIALTY_QUERIES.get(specialty, "specialist clinic")
    query = f"{query_term} {city}"

    params: dict = {
        "query": query,
        "key": api_key,
        "language": "pl",
        "type": "doctor|hospital|health",
    }
    if user_lat is not None and user_lng is not None:
        params["location"] = f"{user_lat},{user_lng}"
        params["radius"] = 50000

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(PLACES_TEXTSEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Google Places API error: %s", exc)
        return []

    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        logger.warning("Google Places returned status: %s", data.get("status"))
        return []

    return _parse_places(data.get("results", []), specialty, city, user_lat, user_lng, limit)


@router.get("/doctors", response_model=DoctorsResponse)
async def get_doctors(
    specialty: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    user_lat: Optional[float] = Query(None),
    user_lng: Optional[float] = Query(None),
    limit: int = Query(10, ge=1, le=30),
) -> DoctorsResponse:
    """Private doctor listings via Google Places.

    For ER + coordinates: uses Nearby Search sorted by distance.
    For all other specialties: uses Text Search biased to province capital or city.
    Returns an empty list (not an error) when GOOGLE_MAPS_API_KEY is not set.
    """
    if not specialty or not os.getenv("GOOGLE_MAPS_API_KEY"):
        return DoctorsResponse(doctors=[])

    if specialty == "ER" and user_lat is not None and user_lng is not None:
        doctors = await _fetch_er_near_coords(user_lat, user_lng, limit)
        return DoctorsResponse(doctors=doctors)

    fallback_city = PROVINCE_CAPITALS.get(province or "07", "Warszawa")
    doctors = await _fetch_doctors_from_places(
        specialty=specialty,
        city=city or fallback_city,
        limit=limit,
        user_lat=user_lat,
        user_lng=user_lng,
    )
    return DoctorsResponse(doctors=doctors)
