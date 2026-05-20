import json
import logging
import time
from datetime import date

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def get_valid_access_token(token_json: str) -> tuple[str, str]:
    """Return (access_token, possibly_updated_token_json). Refreshes if within 60s of expiry."""
    data = json.loads(token_json)
    if data.get("expires_at", 0) > time.time() + 60:
        return data["access_token"], token_json

    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    refreshed = resp.json()
    data["access_token"] = refreshed["access_token"]
    data["expires_at"] = time.time() + refreshed.get("expires_in", 3600)
    return data["access_token"], json.dumps(data)


def create_earnings_event(access_token: str, ticker: str, earnings_date: date) -> None:
    event = {
        "summary": f"{ticker} Earnings",
        "start": {"date": earnings_date.isoformat()},
        "end": {"date": earnings_date.isoformat()},
    }
    resp = httpx.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json=event,
    )
    resp.raise_for_status()
