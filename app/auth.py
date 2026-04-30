import base64
import time
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet, OctKey

from app.config import settings

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_JWKS_TTL = 3600

_jwks_raw: dict | None = None
_jwks_fetched_at: float = 0.0


def _get_google_jwks() -> KeySet:
    # These are global vars so the values are cached every time _get_google_jwks() is called
    # if cache is empty or older than _JWKS_TTL, it re-fetches from Google
    # so the state survives across multiple calls to _get_google_jwks(). 
    # If they were local to the function, every call would re-download the JWKS that would be slow and unnecessary
    # Think of this as a cheap cache, unlike using a decorator like @lru_cache(maxsize=1)
    # Drawbacks of this global (primtive cache) are:
    # 1. harder debugging becuase value depend on previous calls
    # 2. multi-process servers - if you run FastAPI under multiple workers, each worker gets its own cache. global is not shared across processes. 
    # In the above case, it just means that GOOGLE_JWKS_URI is called more often than needed.
    global _jwks_raw, _jwks_fetched_at # "use the shared module vars"
    if _jwks_raw is None or time.time() - _jwks_fetched_at > _JWKS_TTL:
        resp = httpx.get(GOOGLE_JWKS_URI, timeout=5)
        resp.raise_for_status()
        _jwks_raw = resp.json()
        _jwks_fetched_at = time.time()
    return KeySet.import_key_set(_jwks_raw)  # type: ignore[arg-type]


def _check_exp(claims: dict) -> None:
    exp = claims.get("exp")
    # int cast comparison works because both will be seconds since epoch
    if exp is None or int(exp) < int(datetime.now(UTC).timestamp()):
        raise JoseError("token has expired")


def verify_google_id_token(id_token: str) -> dict:
    try:
        claims = jwt.decode(id_token, _get_google_jwks()).claims
        _check_exp(claims)
        if claims.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
            raise JoseError("invalid issuer")
        if claims.get("aud") != settings.google_client_id:
            raise JoseError("invalid audience")
        return dict(claims)
    except JoseError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {exc}",
        )

    """Create a symmetric JWT signing key from the app's JWT secret.
    
    Encodes the JWT secret as base64 URL-safe format and returns an OctKey
    for signing and verifying HS256 tokens.
    
    Returns:
        OctKey: The symmetric key used for JWT operations.
    """
def _app_key() -> OctKey:
    k = base64.urlsafe_b64encode(settings.jwt_secret.encode()).rstrip(b"=").decode()
    return OctKey.import_key({"kty": "oct", "k": k})


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
    }
    return jwt.encode({"alg": "HS256"}, payload, _app_key())


def decode_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(token, _app_key()).claims
        _check_exp(claims)
        return dict(claims)
    except JoseError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        )
