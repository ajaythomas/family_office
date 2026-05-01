import json
from pathlib import Path

import cedarpy
from fastapi import HTTPException

from app.models import Portfolio, User

_POLICY_DIR = Path(__file__).parent / "policies"
_POLICIES = (_POLICY_DIR / "policies.cedar").read_text()


def _build_entities(user: User, portfolio: Portfolio) -> list[dict]:
    return [
        {
            "uid": {"type": "FamilyOffice::User", "id": user.id},
            "attrs": {"role": user.role.value},
            "parents": [],
        },
        {
            "uid": {"type": "FamilyOffice::Portfolio", "id": portfolio.id},
            "attrs": {"owner": portfolio.owner_id},
            "parents": [],
        },
    ]


def authorize(action: str, user: User, portfolio: Portfolio) -> None:
    request = {
        "principal": {"type": "FamilyOffice::User", "id": user.id},
        "action": {"type": "FamilyOffice::Action", "id": action},
        "resource": {"type": "FamilyOffice::Portfolio", "id": portfolio.id},
    }
    # cedarpy 4.x Rust layer expects each request as a JSON string, not a dict
    result = cedarpy.is_authorized(json.dumps(request), _POLICIES, _build_entities(user, portfolio))
    if not result.allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
