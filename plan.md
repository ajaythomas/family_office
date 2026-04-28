# Family Office Portfolio App — Implementation Plan

## Context

This is a hobby FastAPI project for a small household "family office." The current repo is a bare skeleton (`main.py` with demo routes, only `fastapi[standard]` as a dependency, Python 3.14+). We are designing the full feature set from scratch on top of it.

**Goals:**
- Google OAuth login for household members
- One portfolio per member (stocks + ETFs), with live prices and gain/loss
- The family office manager can manage all portfolios; members manage their own; members can share read-only views to others
- Authorization enforced by Cedar policies
- Earnings dates for held tickers pushed to Google Calendar (server-side, using stored refresh token)
- REST API consumed by Android app (and web browser)
- **PostgreSQL** as the database (via SQLAlchemy + psycopg2-binary; local dev via Docker Compose)

---

## Module Structure

Split `main.py` into an `app/` package. `main.py` becomes the entry point only.

```
family_office/
├── main.py                        # app instance + router registration only
├── pyproject.toml
├── docker-compose.yml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── .env                           # secrets, never committed
├── app/
│   ├── config.py                  # pydantic-settings: GOOGLE_CLIENT_ID, JWT_SECRET, etc.
│   ├── database.py                # SQLAlchemy engine, SessionLocal, Base, get_db
│   ├── models.py                  # ORM: User, Portfolio, Holding, PortfolioShare
│   ├── schemas.py                 # Pydantic I/O schemas
│   ├── auth.py                    # Google ID token verification + app JWT issuance
│   ├── dependencies.py            # get_current_user Depends()
│   ├── cedar_authz.py             # load policies, authorize() helper
│   ├── policies/
│   │   ├── policies.cedar         # Cedar policy text
│   │   └── schema.cedarschema     # Cedar entity schema
│   ├── routers/
│   │   ├── auth.py                # POST /auth/google
│   │   ├── users.py               # GET /users/me
│   │   ├── portfolios.py          # portfolio + holdings CRUD
│   │   └── calendar.py            # POST /portfolios/{id}/earnings-calendar
│   └── services/
│       ├── market_data.py         # yfinance: get_price(), get_earnings_date()
│       └── google_calendar.py     # Google Calendar API client
└── tests/
    ├── conftest.py                # Postgres test DB, fake JWT, TestClient
    ├── test_auth.py
    ├── test_portfolios.py
    └── test_cedar.py
```

**`main.py` after refactor:**
```python
from fastapi import FastAPI
from app.routers import auth, users, portfolios, calendar

app = FastAPI(title="Family Office API")
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(portfolios.router)
app.include_router(calendar.router)
```

---

## Data Models (`app/models.py`)

Four tables. One portfolio per user enforced by `uselist=False`.

```python
class User(Base):
    id: str               # UUID PK
    google_sub: str       # unique, from Google token
    email: str
    name: str
    role: Enum("head", "member")
    google_calendar_token: str | None   # JSON-encoded OAuth2 credentials
    portfolio: Portfolio  # uselist=False

class Portfolio(Base):
    id: str
    owner_id: str         # FK → users.id
    name: str
    holdings: list[Holding]
    shares: list[PortfolioShare]

class Holding(Base):
    id: str
    portfolio_id: str     # FK → portfolios.id
    ticker: str           # e.g. "AAPL", "VOO"
    shares: float
    purchase_price: float
    purchase_date: date

class PortfolioShare(Base):
    id: str
    portfolio_id: str     # FK → portfolios.id
    shared_with_id: str   # FK → users.id
    # UNIQUE(portfolio_id, shared_with_id)
```

**Computed fields** (current value, gain/loss) are derived at query time via `market_data.get_price()` — never stored.

---

## Auth Flow (`app/auth.py`, `app/routers/auth.py`)

Android handles Google Sign-In and sends the resulting **ID token** to the server.

```
Android → POST /auth/google { id_token: "..." }
Server  → google-auth: verify_oauth2_token(id_token, GOOGLE_CLIENT_ID)
        → upsert User in DB (first login = role "member"; manually set one user to "head")
        → sign app JWT (HS256, 8h TTL, payload: { sub: user.id, role })
        → return { access_token, token_type: "bearer" }
```

- **Google ID token verification**: `google-auth` library (`id_token.verify_oauth2_token`)
- **App JWT**: `python-jose[cryptography]` with HS256
- **`get_current_user`** in `app/dependencies.py`: Bearer token → User; raises 401 on any failure

---

## Cedar Authorization (`app/cedar_authz.py`)

Use `cedarpy` (official AWS Rust-backed Python binding). Verify a Python 3.14 wheel exists on PyPI before `uv add cedarpy`; if not, build from source (requires Rust toolchain via `rustup`).

**`app/policies/policies.cedar`:**
```cedar
// Head can do everything
permit(principal, action, resource)
when { principal.role == "head" };

// Member can read and write their own portfolio
permit(
  principal,
  action in [Action::"readPortfolio", Action::"writePortfolio"],
  resource
)
when { resource.owner == principal };

// Member can read a portfolio explicitly shared with them
permit(principal, action == Action::"readPortfolio", resource)
when { principal in resource.sharedViewers };
```

**`cedar_authz.py` pattern:**
- Policies loaded once at startup from the `.cedar` file
- `authorize(action, principal: User, resource: Portfolio, share_ids: list[str])` builds Cedar entities from DB objects, calls `cedarpy.is_authorized()`, raises HTTP 403 on Deny
- `sharedViewers` passed as an inline set attribute on the Portfolio entity (pre-fetched from `PortfolioShare` table)

---

## Google Calendar Integration (`app/services/google_calendar.py`)

Server-side push: user grants Calendar OAuth once via a web redirect flow, server stores their `google.oauth2.credentials.Credentials` (JSON-serialized) in `users.google_calendar_token`.

Flow:
1. `GET /auth/google-calendar` — redirect user to Google OAuth consent (scope: `calendar`)
2. `GET /auth/google-calendar/callback` — exchange code, store credentials in DB
3. `POST /portfolios/{id}/earnings-calendar` — for each holding, look up earnings date via `yfinance`, create a Google Calendar event if not already present

---

## Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/google` | public | Exchange Google ID token → app JWT |
| GET | `/auth/google-calendar` | JWT | Start Google Calendar OAuth |
| GET | `/auth/google-calendar/callback` | JWT | Store Calendar credentials |
| GET | `/users/me` | JWT | Current user profile |
| GET | `/portfolios` | JWT | All portfolios visible to user |
| GET | `/portfolios/{id}` | JWT | Portfolio detail with live prices |
| POST | `/portfolios/{id}/holdings` | JWT | Add holding |
| DELETE | `/portfolios/{id}/holdings/{hid}` | JWT | Remove holding |
| POST | `/portfolios/{id}/share` | JWT | Share portfolio view-only with user |
| DELETE | `/portfolios/{id}/share/{uid}` | JWT | Revoke share |
| POST | `/portfolios/{id}/earnings-calendar` | JWT | Push earnings events to Google Calendar |

---

## Dependencies to Add

```bash
uv add "python-jose[cryptography]"       # JWT
uv add "google-auth"                      # Google ID token verification
uv add "google-api-python-client"         # Google Calendar
uv add "google-auth-oauthlib"             # Calendar OAuth flow
uv add "sqlalchemy"                        # ORM
uv add "alembic"                           # migrations
uv add "psycopg2-binary"                   # PostgreSQL driver
uv add "pydantic-settings"                 # env config
uv add "cedarpy"                           # Cedar authorization
uv add "yfinance"                          # stock prices + earnings dates

uv add --dev "pytest"
uv add --dev "pytest-asyncio"
uv add --dev "httpx"
uv add --dev "pytest-cov"
```

---

## Local Dev: Docker Compose

`docker-compose.yml` at project root:

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: family_office
      POSTGRES_PASSWORD: family_office
      POSTGRES_DB: family_office
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

`.env` connection strings:
```
DATABASE_URL=postgresql://family_office:family_office@localhost:5432/family_office
DATABASE_URL_TEST=postgresql://family_office:family_office@localhost:5432/family_office_test
GOOGLE_CLIENT_ID=<your-google-client-id>
JWT_SECRET=<random-secret>
```

**Tests** connect to `family_office_test` (same Docker instance) — no SQLite, so tests exercise the real Postgres driver.

---

## Build Order

1. **Foundation**: `config.py`, `database.py`, `models.py`, Alembic init + first migration
2. **Auth**: `auth.py`, `routers/auth.py`, `dependencies.py`, `routers/users.py` — smoke test login end-to-end
3. **Cedar + Portfolio CRUD**: `cedar_authz.py` + policies, `routers/portfolios.py` (read, then write, then share)
4. **Market Data**: `services/market_data.py`, wire prices into `GET /portfolios/{id}`
5. **Google Calendar**: Calendar OAuth flow, `services/google_calendar.py`, `routers/calendar.py`

---

## Verification

```bash
# Start Postgres
docker compose up -d

# Run migrations
uv run alembic upgrade head

# Start dev server
uv run fastapi dev

# Type check
uv run mypy app/ main.py

# Tests
uv run pytest --cov=app
```

Manual checks:
- `POST /auth/google` with a real ID token from Android emulator or Google OAuth Playground
- `POST /portfolios/{id}/earnings-calendar` after completing Calendar OAuth flow
- Log in as a member, `GET /portfolios/{other_user_portfolio_id}` → expect 403
- Log in as head → expect 200 for any portfolio

### Cedar fallback note
If `cedarpy` does not have a Python 3.14 wheel and source build fails:
1. Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
2. `uv add cedarpy` will build from source
3. Worst case: implement `authorize()` as plain Python RBAC mirroring the Cedar semantics, swap in `cedarpy` later
