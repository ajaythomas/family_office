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
            # Earlier, we did not explicitly put id in this attrs dict
            # principal.id in a Cedar policy accesses an attribute named id, not the entity's UID (which is what gets assessed when it was not explicitly mentioned).
            "attrs": {"role": user.role.value, "id": user.id},
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
        # First, I tried "principal": {"type": "FamilyOffice::User", "id": user.id},
        # but cedarpy failed that because they must be Cedar entity strings like ('FamilyOffice::User::"id"'), not dicts.
        "principal": f'FamilyOffice::User::"{user.id}"',
        "action": f'FamilyOffice::Action::"{action}"',
        "resource": f'FamilyOffice::Portfolio::"{portfolio.id}"',
        "context": {},
    }
    result = cedarpy.is_authorized(request, _POLICIES, _build_entities(user, portfolio))
    if not result.allowed:
        raise HTTPException(status_code=403, detail="Forbidden")
