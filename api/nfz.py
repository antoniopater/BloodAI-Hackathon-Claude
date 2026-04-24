"""GET /nfz/queues — proxy to the Polish National Health Fund open API."""
from __future__ import annotations

import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

NFZ_API_BASE = "https://api.nfz.gov.pl/app-itl-api/queues"

router = APIRouter(tags=["nfz"])

PROVINCE_NAMES = {
    "01": "Dolnośląskie", "02": "Kujawsko-Pomorskie", "03": "Lubelskie",
    "04": "Lubuskie", "05": "Łódzkie", "06": "Małopolskie",
    "07": "Mazowieckie", "08": "Opolskie", "09": "Podkarpackie",
    "10": "Podlaskie", "11": "Pomorskie", "12": "Śląskie",
    "13": "Świętokrzyskie", "14": "Warmińsko-Mazurskie",
    "15": "Wielkopolskie", "16": "Zachodniopomorskie",
}

# Frontend sends exact benefit strings (TRIAGE_TO_NFZ_BENEFIT in constants.ts).
# NFZ benefit catalog uses different names — this map translates to working search terms.
BENEFIT_SEARCH_MAP: dict[str, str] = {
    "PORADNIA NEFROLOGICZNA":        "NEFRO",
    "PORADNIA KARDIOLOGICZNA":       "KARDIO",
    "PORADNIA GASTROENTEROLOGICZNA": "GASTROENTER",
    "PORADNIA CHORÓB PŁUC":          "PULMONOLOG",
    "PORADNIA LEKARZA POZ":          "PODSTAWOWEJ OPIEKI",
    "SZPITALNY ODDZIAŁ RATUNKOWY":   "RATUNKOWY",
}


class NFZQueueEntry(BaseModel):
    provider: str
    address: str
    city: str
    province: str
    phone: Optional[str] = None
    firstAvailable: Optional[str] = None
    waitDays: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class NFZQueuesResponse(BaseModel):
    entries: List[NFZQueueEntry]


def _map_entry(item: dict, province_name: str) -> NFZQueueEntry:
    attrs = item.get("attributes", {})

    # NFZ: 'place' is the facility/ward name; 'address' is the street address.
    facility = attrs.get("place", "")
    street = attrs.get("address", "")
    display_address = f"{facility}, {street}".strip(", ") if facility or street else ""

    dates = attrs.get("dates") or {}
    first_available = dates.get("date") if dates.get("applicable") else None

    stats = attrs.get("statistics") or {}
    provider_data = stats.get("provider-data") or {}
    average_period = provider_data.get("average-period")
    wait_days = int(average_period) if average_period is not None else None

    return NFZQueueEntry(
        provider=attrs.get("provider", ""),
        address=display_address,
        city=attrs.get("locality", ""),
        province=province_name,
        phone=attrs.get("phone") or None,
        firstAvailable=first_available,
        waitDays=wait_days,
        lat=attrs.get("latitude") or None,
        lng=attrs.get("longitude") or None,
    )


@router.get("/nfz/queues", response_model=NFZQueuesResponse)
async def get_nfz_queues(
    benefit: str = Query(..., description="NFZ benefit name, e.g. PORADNIA NEFROLOGICZNA"),
    province: str = Query("07", description="2-digit province code"),
    case: int = Query(1, ge=1, le=2, description="1=stable, 2=urgent"),
    limit: int = Query(15, ge=1, le=50),
) -> NFZQueuesResponse:
    """Proxy the NFZ open API and return normalised clinic queue entries."""
    # Translate frontend benefit strings to NFZ-compatible search terms where needed.
    search_term = BENEFIT_SEARCH_MAP.get(benefit, benefit)

    params = {
        "benefit": search_term,
        "province": province,
        "case": case,
        "format": "json",
        "limit": limit,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(NFZ_API_BASE, params=params)
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=503, detail="NFZ API timed out.")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"NFZ API error: HTTP {exc.response.status_code}",
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Could not reach NFZ API: {exc}")

    data = resp.json().get("data") or []
    province_name = PROVINCE_NAMES.get(province, province)

    entries: List[NFZQueueEntry] = []
    for item in data:
        try:
            entries.append(_map_entry(item, province_name))
        except Exception:
            logger.exception("Failed to map NFZ entry: %s", item)

    return NFZQueuesResponse(entries=entries)
