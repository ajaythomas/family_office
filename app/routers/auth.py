import json
import logging
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, create_oauth_state_token, decode_oauth_state_token, verify_google_id_token
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Portfolio, User

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class GoogleLoginRequest(BaseModel):
    id_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/google", response_model=TokenResponse)
def google_login(body: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    claims = verify_google_id_token(body.id_token)

    user = db.query(User).filter(User.google_sub == claims["sub"]).first()
    if user is None:
        user = User(
            google_sub=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("email", "")),
        )
        db.add(user)
        db.flush()  # gets user.id assigned before we reference it in the FK below
        logger.info("New user %s created on first login", user.email)

        # Implicitly create a portfolio for this brand new user
        portfolio = Portfolio(
            owner_id=user.id,
        )
        db.add(portfolio)
        logger.info("Portfolio created for new user %s", user.email)
    else:
        user.email = claims.get("email", user.email)
        user.name = claims.get("name", user.name)
        logger.info("User %s logged in", user.email)

    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))


class CalendarConnectResponse(BaseModel):
    url: str


@router.post("/google-calendar/start", response_model=CalendarConnectResponse)
def start_google_calendar_oauth(
    current_user: User = Depends(get_current_user),
) -> CalendarConnectResponse:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.app_base_url}/auth/google-calendar/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.events", # Only ask for viewing and editing events instead of the broader auth/calendar scope
        "access_type": "offline",
        "prompt": "consent",
        "state": create_oauth_state_token(current_user.id),
    }
    return CalendarConnectResponse(url="https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@router.get("/google-calendar/callback")
def google_calendar_callback(code: str, state: str, db: Session = Depends(get_db)) -> RedirectResponse:
    user_id = decode_oauth_state_token(state)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": f"{settings.app_base_url}/auth/google-calendar/callback",
            "grant_type": "authorization_code",
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    stored = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": time.time() + token_data.get("expires_in", 3600),
    }
    user.google_calendar_token = json.dumps(stored)
    db.commit()
    logger.info("Google Calendar connected for user %s", user.email)
    return RedirectResponse(f"{settings.frontend_url}?calendar_connected=true")
