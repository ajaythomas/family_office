from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Portfolio, RoleEnum, User


def _make_user(db: Session, *, google_sub: str, email: str, name: str, role: RoleEnum) -> User:
    user = User(google_sub=google_sub, email=email, name=name, role=role)
    db.add(user)
    db.flush()
    return user


def _make_portfolio(db: Session, owner: User, name: str = "Test Portfolio") -> Portfolio:
    p = Portfolio(owner_id=owner.id, name=name)
    db.add(p)
    db.flush()
    return p


def _login(client: TestClient, *, sub: str, email: str, name: str) -> str:
    with patch("app.routers.auth.verify_google_id_token", return_value={"sub": sub, "email": email, "name": name}):
        resp = client.post("/auth/google", json={"id_token": "fake"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# list portfolios
# ---------------------------------------------------------------------------

def test_member_sees_own_portfolio_only(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="m1", email="m1@x.com", name="M1", role=RoleEnum.member)
    other = _make_user(db, google_sub="m2", email="m2@x.com", name="M2", role=RoleEnum.member)
    p_owner = _make_portfolio(db, owner)
    _make_portfolio(db, other)
    db.commit()

    token = _login(client, sub="m1", email="m1@x.com", name="M1")
    resp = client.get("/portfolios", headers=_auth(token))
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert ids == [p_owner.id]


def test_manager_sees_all_portfolios(client: TestClient, db: Session) -> None:
    mgr = _make_user(db, google_sub="mgr1", email="mgr1@x.com", name="Mgr", role=RoleEnum.manager)
    m1 = _make_user(db, google_sub="u1", email="u1@x.com", name="U1", role=RoleEnum.member)
    m2 = _make_user(db, google_sub="u2", email="u2@x.com", name="U2", role=RoleEnum.member)
    _make_portfolio(db, mgr)
    _make_portfolio(db, m1)
    _make_portfolio(db, m2)
    db.commit()

    token = _login(client, sub="mgr1", email="mgr1@x.com", name="Mgr")
    resp = client.get("/portfolios", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


# ---------------------------------------------------------------------------
# get portfolio
# ---------------------------------------------------------------------------

def test_member_can_read_own_portfolio(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="r1", email="r1@x.com", name="R1", role=RoleEnum.member)
    p = _make_portfolio(db, owner)
    db.commit()

    token = _login(client, sub="r1", email="r1@x.com", name="R1")
    resp = client.get(f"/portfolios/{p.id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == p.id


def test_member_cannot_read_others_portfolio(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="o1", email="o1@x.com", name="O1", role=RoleEnum.member)
    intruder = _make_user(db, google_sub="i1", email="i1@x.com", name="I1", role=RoleEnum.member)
    p = _make_portfolio(db, owner)
    db.commit()

    token = _login(client, sub="i1", email="i1@x.com", name="I1")
    resp = client.get(f"/portfolios/{p.id}", headers=_auth(token))
    assert resp.status_code == 403


def test_get_nonexistent_portfolio_is_404(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="nx1", email="nx1@x.com", name="NX1", role=RoleEnum.member)
    db.commit()
    token = _login(client, sub="nx1", email="nx1@x.com", name="NX1")
    resp = client.get("/portfolios/does-not-exist", headers=_auth(token))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# holdings CRUD
# ---------------------------------------------------------------------------

HOLDING_BODY = {
    "ticker": "AAPL",
    "shares": 10.0,
    "purchase_price": 150.0,
    "purchase_date": "2024-01-15",
}


def test_member_can_add_and_remove_holding(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="h1", email="h1@x.com", name="H1", role=RoleEnum.member)
    p = _make_portfolio(db, owner)
    db.commit()

    token = _login(client, sub="h1", email="h1@x.com", name="H1")
    hdrs = _auth(token)

    add_resp = client.post(f"/portfolios/{p.id}/holdings", json=HOLDING_BODY, headers=hdrs)
    assert add_resp.status_code == 201
    holding_id = add_resp.json()["id"]
    assert add_resp.json()["ticker"] == "AAPL"

    del_resp = client.delete(f"/portfolios/{p.id}/holdings/{holding_id}", headers=hdrs)
    assert del_resp.status_code == 204


def test_member_cannot_write_others_portfolio(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="w1", email="w1@x.com", name="W1", role=RoleEnum.member)
    intruder = _make_user(db, google_sub="w2", email="w2@x.com", name="W2", role=RoleEnum.member)
    p = _make_portfolio(db, owner)
    db.commit()

    token = _login(client, sub="w2", email="w2@x.com", name="W2")
    resp = client.post(f"/portfolios/{p.id}/holdings", json=HOLDING_BODY, headers=_auth(token))
    assert resp.status_code == 403


def test_manager_can_write_any_portfolio(client: TestClient, db: Session) -> None:
    member = _make_user(db, google_sub="wm1", email="wm1@x.com", name="WM1", role=RoleEnum.member)
    mgr = _make_user(db, google_sub="wm2", email="wm2@x.com", name="WM2", role=RoleEnum.manager)
    p = _make_portfolio(db, member)
    db.commit()

    token = _login(client, sub="wm2", email="wm2@x.com", name="WM2")
    resp = client.post(f"/portfolios/{p.id}/holdings", json=HOLDING_BODY, headers=_auth(token))
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# sell holding
# ---------------------------------------------------------------------------

def test_member_can_sell_own_holding(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="s1", email="s1@x.com", name="S1", role=RoleEnum.member)
    p = _make_portfolio(db, owner)
    db.commit()

    token = _login(client, sub="s1", email="s1@x.com", name="S1")
    hdrs = _auth(token)

    add_resp = client.post(f"/portfolios/{p.id}/holdings", json=HOLDING_BODY, headers=hdrs)
    assert add_resp.status_code == 201
    holding_id = add_resp.json()["id"]

    sell_resp = client.patch(
        f"/portfolios/{p.id}/holdings/{holding_id}/sell",
        json={"sale_price": 175.0, "sale_date": "2025-03-01"},
        headers=hdrs,
    )
    assert sell_resp.status_code == 200
    body = sell_resp.json()
    assert body["sale_price"] == 175.0
    assert body["sale_date"] == "2025-03-01"
    assert body["ticker"] == "AAPL"


def test_member_cannot_sell_others_holding(client: TestClient, db: Session) -> None:
    owner = _make_user(db, google_sub="s2", email="s2@x.com", name="S2", role=RoleEnum.member)
    intruder = _make_user(db, google_sub="s3", email="s3@x.com", name="S3", role=RoleEnum.member)
    p = _make_portfolio(db, owner)
    db.commit()

    owner_token = _login(client, sub="s2", email="s2@x.com", name="S2")
    add_resp = client.post(f"/portfolios/{p.id}/holdings", json=HOLDING_BODY, headers=_auth(owner_token))
    holding_id = add_resp.json()["id"]

    intruder_token = _login(client, sub="s3", email="s3@x.com", name="S3")
    sell_resp = client.patch(
        f"/portfolios/{p.id}/holdings/{holding_id}/sell",
        json={"sale_price": 175.0, "sale_date": "2025-03-01"},
        headers=_auth(intruder_token),
    )
    assert sell_resp.status_code == 403
