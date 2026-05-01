# Family Office Portfolio App — Implementation Plan

## Context

This is a hobby FastAPI project for a small household "family office." The current repo is a bare skeleton (`main.py` with demo routes, only `fastapi[standard]` as a dependency, Python 3.14+). We are designing the full feature set from scratch on top of it.

**Goals:**
- Google OAuth login for household members
- One portfolio per member (stocks + ETFs), with live prices and gain/loss
- The family office manager can manage all portfolios; members manage their own; (future; ignore for v1) members can share read-only views to others
- Authorization enforced by Cedar policies
- Earnings dates for held tickers pushed to Google Calendar (server-side, using stored refresh token)
- REST API consumed by a **Vite + React web app** (mobile browser supported); Android deferred to a future phase — FastAPI's OpenAPI spec means a Kotlin/Retrofit client can be generated later with no backend changes
- **PostgreSQL** as the database (via SQLAlchemy + psycopg2-binary; local dev via Docker Compose)

---

## Module Structure

Split `main.py` into an `app/` package. `main.py` becomes the entry point only.

```
family_office/
├── main.py                        # app instance + router registration + CORS middleware
├── pyproject.toml
├── docker-compose.yml
├── alembic.ini
├── alembic/                      # db Migration tool for FastAPI apps
│   ├── env.py
│   └── versions/
├── .env                           # secrets, never committed
├── app/
│   ├── config.py                  # pydantic-settings: GOOGLE_CLIENT_ID, JWT_SECRET, etc.
│   ├── database.py                # SQLAlchemy engine, SessionLocal, Base, get_db
│   ├── models.py                  # ORM: User, Portfolio, Holding
│   ├── schemas.py                 # Pydantic I/O schemas for the API routers to use
│   ├── auth.py                    # Google ID token verification + app JWT issuance
│   ├── dependencies.py            # get_current_user Depends()
│   ├── cedar_authz.py             # load policies, authorize() helper
│   ├── policies/
│   │   ├── policies.cedar         # Cedar policy text
│   │   └── schema.cedarschema     # Cedar entity schema
│   ├── routers/
│   │   ├── auth.py                # POST /auth/google, GET /auth/google-calendar*
│   │   ├── users.py               # GET /users/me
│   │   ├── portfolios.py          # portfolio + holdings CRUD
│   │   └── calendar.py            # POST /portfolios/{id}/earnings-calendar
│   └── services/
│       ├── market_data.py         # yfinance: get_price(), get_earnings_date()
│       └── google_calendar.py     # httpx calls to Google Calendar REST API
├── tests/
│   ├── conftest.py                # Postgres test DB, savepoint isolation, TestClient
│   ├── test_auth.py
│   ├── test_portfolios.py
│   └── test_cedar.py
└── web/                           # Vite + React frontend
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── types/api.d.ts         # generated — npx openapi-typescript ...
        ├── lib/api.ts             # typed fetch wrappers
        ├── pages/
        │   ├── Login.tsx
        │   ├── Portfolio.tsx
        │   └── Holdings.tsx
        └── components/
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

Four tables. One portfolio per user enforced by `uselist=False` - enforce a 1-1 relationship between User and Portfolio

```python
class User(Base):
    id: str               # UUID PK
    google_sub: str       # unique, from Google token
    email: str
    name: str
    role: Enum("manager", "member")
    google_calendar_token: str | None   # JSON-encoded OAuth2 credentials
    portfolio: Portfolio  # uselist=False

class Portfolio(Base):
    id: str
    owner_id: str         # FK → users.id
    name: str
    holdings: list[Holding]
    # shares: list[PortfolioShare] - pushed out for v2 

class Holding(Base):
    id: str
    portfolio_id: str     # FK → portfolios.id
    ticker: str           # e.g. "AAPL", "VOO"
    shares: float
    purchase_price: float
    purchase_date: date
    sale_price: float     # nullable
    sale_date: date       # nullable

'''class PortfolioShare(Base):
    id: str
    portfolio_id: str     # FK → portfolios.id
    shared_with_id: str   # FK → users.id
    # UNIQUE(portfolio_id, shared_with_id)'''
```

**Computed fields** (current value, gain/loss) are derived at query time via `market_data.get_price()` — never stored.

---

## Auth Flow (`app/auth.py`, `app/routers/auth.py`)

The web app uses **Google Identity Services (GIS)** to get an ID token in the browser, then sends it to the backend.
GoogleLogin component uses Google Identity Services (GIS) which defaults to popup mode. GIS deliberately chose popup over
redirect for SPAs because:
1. The user stays on the app page — no navigation away, no lost state
2. No redirect callback route to implement
3. The popup closes automatically on success; onSuccess fires in the parent window
```
Browser → @react-oauth/google: renders "Sign in with Google" button
        → user clicks → Google returns credential (ID token) in the browser
Browser → POST /auth/google { id_token: "..." }
Server  → joserfc: verify Google OIDC ID token via JWKS (fetched from Google, cached 1h)
        → upsert User in DB (first login = role "member"; manually set one user to "manager")
        → sign app JWT (HS256, 24h TTL, payload: { sub: user.id, role }) via joserfc
        → return { access_token, token_type: "bearer" }
Browser → store JWT in localStorage → attach as Authorization: Bearer on every request
```

- **Google ID token verification**: `joserfc` (authlib.jose deprecated in 1.7+)
- **App JWT**: `joserfc` with HS256
- **`get_current_user`** in `app/dependencies.py`: Bearer token → User; raises 401 on any failure
- **Future Android**: same `POST /auth/google` endpoint accepts ID tokens from the Android Google Sign-In SDK — no backend changes needed

---

## Cedar Authorization (`app/cedar_authz.py`)

Use `cedarpy` — this is the official Python SDK maintained by AWS in the `cedar-policy` GitHub org (Rust-backed via PyO3). Verify a Python 3.14 wheel exists on PyPI before `uv add cedarpy`; if not, ask how to proceed.

**`app/policies/policies.cedar`:**
```cedar
// manager can do everything
permit(principal, action, resource)
when { principal.role == "manager" };

// Member can read and write their own portfolio
permit(
  principal,
  action in [Action::"readPortfolio", Action::"writePortfolio"],
  resource
)
when { resource.owner == principal };

// Member can read a portfolio explicitly shared with them - pushed out to v2
// permit(principal, action == Action::"readPortfolio", resource)
// when { principal in resource.sharedViewers };
```

**`cedar_authz.py` pattern:**
- Policies loaded once at startup from the `.cedar` file
- `authorize(action, principal: User, resource: Portfolio)` builds Cedar entities from DB objects, calls `cedarpy.is_authorized()`, raises HTTP 403 on Deny
---

## Google Calendar Integration (`app/services/google_calendar.py`)

Server-side push: user grants Calendar OAuth once via a web redirect flow using `authlib`'s Starlette OAuth client, server stores the resulting access + refresh tokens (JSON) in `users.google_calendar_token`.

Flow:
1. `GET /auth/google-calendar` — `authlib` Starlette client redirects user to Google OAuth consent (scope: `https://www.googleapis.com/auth/calendar`)
2. `GET /auth/google-calendar/callback` — `authlib` exchanges code for tokens, store in DB
3. `POST /portfolios/{id}/earnings-calendar` — for each holding, look up earnings date via `yfinance`, call Google Calendar REST API directly via `httpx` using the stored access token (refresh via `authlib` if expired), create event if not already present

No `google-api-python-client` needed — `httpx` + the Calendar REST API is sufficient.

---

## Frontend (Vite + React)

Lives in `web/` at the repo root — a separate app, separate dev server, talks to the FastAPI backend via fetch.

```
web/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── types/
    │   └── api.d.ts        # generated by openapi-typescript — never edit by hand
    ├── lib/
    │   └── api.ts          # typed fetch wrappers around the generated types
    ├── pages/
    │   ├── Login.tsx       # Google Sign-In button → POST /auth/google → store JWT
    │   ├── Portfolio.tsx   # GET /portfolios/{id} — holdings table with live prices
    │   └── Holdings.tsx    # add/remove holdings
    └── components/
```

**Type generation** — run after any backend schema change:
```bash
npx openapi-typescript http://localhost:8000/openapi.json -o web/src/types/api.d.ts
```
This generates TypeScript types from FastAPI's live OpenAPI spec. `api.ts` wraps these with typed `fetch` calls. No full SDK needed.

**Google Sign-In on web**: `@react-oauth/google` renders the GIS button; the `onSuccess` callback receives `{ credential }` (the ID token) which is POSTed directly to `/auth/google`.

**CORS**: FastAPI needs `fastapi.middleware.cors.CORSMiddleware` allowing `http://localhost:5173` (Vite default) in dev. Add to `main.py`.

**Google Cloud Console** — add these for the web app:
- Authorized JavaScript origins: `http://localhost:5173`, `http://localhost:8000`
- (Redirect URIs already covered in step 2a)

**Vertical slices** — at the end of each backend phase, the web app should show the feature end-to-end in a browser:

| Phase | Web slice |
|-------|-----------|
| 2 (Auth) | Login page with Google Sign-In button → on success shows user name + role from `/users/me` |
| 3 (Portfolio CRUD) | Portfolio page — view holdings table, add/remove holdings form |
| 4 (Market Data) | Holdings table gains a "Current Value" and "Gain/Loss" column (live prices) |
| 5 (Calendar) | "Sync to Calendar" button on the portfolio page |

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
| POST | `/portfolios/{id}/holdings` | JWT | Upsert holding (purchase/sale for x units) |
| DELETE | `/portfolios/{id}/holdings/{hid}` | JWT | Remove holding |
| POST | `/portfolios/{id}/earnings-calendar` | JWT | Push earnings events to Google Calendar |

---

## Dependencies to Add

```bash
uv add "authlib"                           # Google OIDC login + Calendar OAuth + JWT signing
uv add "httpx"                             # async HTTP (used by authlib + direct Calendar REST calls)
uv add "sqlalchemy"                        # ORM
uv add "alembic"                           # migrations
uv add "psycopg2-binary"                   # PostgreSQL driver
uv add "pydantic-settings"                 # env config
uv add "cedarpy"                           # Cedar authorization (official cedar-policy Python SDK)
uv add "yfinance"                          # stock prices + earnings dates

uv add --dev "pytest"
uv add --dev "pytest-asyncio"
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

Run these three checks before committing at the end of **every** phase:

```bash
uv run mypy app/          # no type errors
uv run alembic check      # no pending migrations
uv run pytest             # all tests pass (exit 0 or exit 5 if no tests yet)
```

1. **Foundation**: `config.py`, `database.py`, `models.py`, Alembic init + first migration

   > **Completed 2026-04-29**
   > - Installed: `sqlalchemy`, `alembic`, `psycopg2-binary`, `pydantic-settings`
   > - Created `app/` package with `config.py`, `database.py`, `models.py`, `schemas.py`
   > - `models.py`: `User`, `Portfolio`, `Holding` — SQLAlchemy 2.0 `Mapped[]` style; nanoid for PKs (user switched from uuid); `sale_price`/`sale_date` added to `Holding` for tracking exits; `PortfolioShare` deferred to v2
   > - `docker-compose.yml` with Postgres 16; `.env` and `.env.example` added
   > - Alembic initialised; `alembic/env.py` wired to `app.config.settings` so DB URL is never hardcoded
   > - Migration `be918da0252e` auto-generated and applied — creates `users`, `portfolios`, `holdings` tables
   > - Added `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` as dev deps; `pyproject.toml` updated with `[tool.mypy]` (pydantic plugin) and `[tool.pytest.ini_options]`
   > - Gates passed: mypy clean, alembic check clean, pytest (0 tests, exit 5)

2. **Auth**: `auth.py`, `routers/auth.py`, `dependencies.py`, `routers/users.py` — smoke test login end-to-end

   > **Completed 2026-04-29**
   > - Installed: `authlib` (pulled in `joserfc` 1.6.4), `httpx`, `nanoid`
   > - `app/auth.py`: Google OIDC ID token verification via joserfc + JWKS (fetched from Google, cached 1h); HS256 app JWT sign/decode via joserfc `OctKey`; `_check_exp()` handles claim validation (joserfc 1.6.4 `Token` has no `.validate()` method — expiry checked manually)
   > - `app/dependencies.py`: `get_current_user` — Bearer token → `User` ORM object; raises 401 on any failure
   > - `app/routers/auth.py`: `POST /auth/google` — verifies Google token, upserts user (default role `member`), returns 24h JWT
   > - `app/routers/users.py`: `GET /users/me`
   > - `main.py` stripped to router registration only
   > - `tests/conftest.py`: test DB (`family_office_test`), savepoint-based transaction rollback per test for isolation without table recreation
   > - `tests/test_auth.py`: JWT round-trip, Google login (mocked at router import boundary), idempotent upsert, `/users/me` auth check
   > - Decision: switched from `authlib.jose` to `joserfc` directly (authlib.jose deprecated in 1.7+); `KeySet.import_key_set` arg-type ignored — joserfc uses a TypedDict that generic `dict` from `resp.json()` doesn't satisfy
   > - Gates passed: mypy clean, alembic check clean, pytest 5/5

   **Frontend slice (phase 2):** Scaffold `web/` with Vite + React + TypeScript. Add `@react-oauth/google`. Build `Login.tsx` — renders the GIS button, on success POSTs `credential` to `/auth/google`, stores JWT in localStorage, fetches `/users/me` and displays name + role. Add CORS middleware to `main.py` allowing `http://localhost:5173`. Run `npx openapi-typescript` to generate initial `api.d.ts`.

   > **Completed 2026-04-30**
   > - `main.py`: added `CORSMiddleware` allowing `http://localhost:5173` (Vite server)
   > - `web/` scaffolded with `npx create-vite@latest --template react-ts` (Node v24, npm v11)
   > - Installed: `@react-oauth/google`
   > - `web/.env`: `VITE_GOOGLE_CLIENT_ID` + `VITE_API_URL=http://localhost:8000`; committed (client ID is public, bundled into JS); root `.gitignore` updated with `!web/.env`, `web/node_modules/`, `web/dist/`
   > - `web/src/types/api.d.ts`: generated via `openapi-typescript` v7 from schema dumped from Python (no server startup needed); reflects 2 routes + 4 schemas
   > - `web/src/lib/api.ts`: typed `login()` + `getMe()` fetch wrappers using generated types
   > - `web/src/pages/Login.tsx`: `GoogleLogin` button from `@react-oauth/google`; `onSuccess` posts credential to `/auth/google`, stores JWT in localStorage
   > - `web/src/App.tsx`: no token → Login; token → fetch `/users/me` → show name/email/role + sign-out; expired token auto-clears localStorage
   > - `web/src/main.tsx`: wraps app in `GoogleOAuthProvider` with `VITE_GOOGLE_CLIENT_ID`
   > - `web/src/vite-env.d.ts`: augmented `ImportMetaEnv` with `VITE_GOOGLE_CLIENT_ID` and `VITE_API_URL`
   > - Build gate: `npm run build` clean (tsc + vite, 0 errors, 195 kB bundle)

  ## Some notes as I learn:

  1. Vite's built-in dev server defaults to port 5173. The BE FastAPI and FE Vite servers run simultaneously — browser loads the React app from localhost:5173, which then makes API calls to localhost:8000 (FastAPI). That cross-origin request is why CORS middleware is needed on the FastAPI side. Similarly, postgres db port is 5432 as mentioned in docker compose.

  2. Openapi-typescript reads the live FastAPI spec at /openapi.json and turns every Pydantic schema and route signature into TypeScript types. 
    a. It's a direct mirror of the Pydantic models. We then write api.ts that wraps these types with actual fetch calls. 
    b. Each time we add a backend route (portfolios, holdings, etc.), we re-run the openapi-typescript command and the types update automatically.

2a. **Manual smoke test — live Google login**

   Start the server:
   ```bash
   docker compose up -d
   uv run fastapi dev
   ```

   Get a real Google ID token via OAuth Playground (https://developers.google.com/oauthplayground):
   - Gear icon → "Use your own OAuth credentials" → paste Client ID + Secret
   - Step 1: select `openid`, `userinfo.email`, `userinfo.profile` scopes under Google OAuth2 API v2 → Authorize APIs → sign in
    - With just openid scope, you get only the id (sub i.e. unique id given to each google user for OAuth) in the id token. Email and profile in the ID token only if you grant `userinfo.email`, `userinfo.profile` scopes too.
   - Step 2: Exchange code for tokens → copy `id_token`

   Test the flow:
   ```bash
   # 1. Login — returns a JWT
   curl -s -X POST http://localhost:8000/auth/google \
     -H "Content-Type: application/json" \
     -d '{"id_token":"PASTE_ID_TOKEN"}' | jq .

   # 2. Use the JWT to call /users/me
   curl -s http://localhost:8000/users/me \
     -H "Authorization: Bearer PASTE_ACCESS_TOKEN" | jq .

   # 3. Verify user in DB (should be role=member)
   docker compose exec db psql -U family_office \
     -c "SELECT id, email, name, role FROM users;"

   # 4. Promote yourself to manager
   docker compose exec db psql -U family_office \
     -c "UPDATE users SET role='manager' WHERE email='YOUR_EMAIL';"
   ```

   Google Cloud Console settings required for this client (Web application type):
   - Authorized JavaScript origins: `http://localhost:8000`, `http://localhost:5173` (Vite)
   - Authorized redirect URIs: `https://developers.google.com/oauthplayground`
   - Authorized redirect URIs: `http://localhost:8000/auth/google-calendar/callback` (needed for step 5)

3. **Cedar + Portfolio CRUD**: `cedar_authz.py` + policies, `routers/portfolios.py` (read, then write)

   **Frontend slice (phase 3):** `Portfolio.tsx` — fetches `GET /portfolios/{id}`, renders holdings table. `Holdings.tsx` — form to add a holding (ticker, shares, purchase price, date), calls `POST /portfolios/{id}/holdings`. Delete button per row. Regenerate `api.d.ts` from updated schema.

4. **Market Data**: `services/market_data.py`, wire prices into `GET /portfolios/{id}`

   **Frontend slice (phase 4):** Add "Current Value" and "Gain / Loss" columns to the holdings table (data comes from the enriched `GET /portfolios/{id}` response — no extra frontend calls needed).

5. **Google Calendar**: Calendar OAuth flow, `services/google_calendar.py`, `routers/calendar.py`

   **Frontend slice (phase 5):** "Connect Google Calendar" button that redirects to `GET /auth/google-calendar`. After OAuth completes, show a "Sync Earnings to Calendar" button that calls `POST /portfolios/{id}/earnings-calendar`.

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
- `POST /auth/google` with a real ID token from Google OAuth Playground
- `POST /portfolios/{id}/earnings-calendar` after completing Calendar OAuth flow
- Log in as a member, `GET /portfolios/{other_user_portfolio_id}` → expect 403
- Log in as manager → expect 200 for any portfolio

### Cedar fallback note
`cedarpy` is the official `cedar-policy` Python SDK (same GitHub org as the Cedar language). If no Python 3.14 wheel exists on PyPI:
1. Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
2. `uv add cedarpy` will build from source via PyO3
3. Worst case: implement `authorize()` as plain Python RBAC mirroring the Cedar semantics, swap in `cedarpy` later
