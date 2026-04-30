from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_google_id_token
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


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
    else:
        user.email = claims.get("email", user.email)
        user.name = claims.get("name", user.name)

    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))
