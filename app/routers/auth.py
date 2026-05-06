import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_google_id_token
from app.database import get_db
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
