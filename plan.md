# Family Office Portfolio App — Implementation Plan

## Context

This is a hobby FastAPI project for a small household "family office".

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

---

## Auth Flow

The web app uses **Google Identity Services (GIS)** to get an ID token in the browser, then sends it to the backend. GIS defaults to popup mode — user stays on the app page, no lost state, popup closes automatically on success.

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

**Decisions:**
- Used `joserfc` directly — `authlib.jose` deprecated in 1.7+
- Future Android: same `POST /auth/google` endpoint accepts ID tokens from the Android Google Sign-In SDK — no backend changes needed

---

## Cedar Authorization

Use `cedarpy` — official Python SDK maintained by AWS in the `cedar-policy` GitHub org (Rust-backed via PyO3). Verify a Python 3.14 wheel exists on PyPI before `uv add cedarpy`; if not, build from source (requires Rust) or implement as plain Python RBAC and swap in `cedarpy` later.

`PortfolioShare` / shared read-only access deferred to v2 — Cedar policy stub is commented out in `policies.cedar`.

---

## Google Calendar Integration

Server-side push: user grants Calendar OAuth once, server stores access + refresh tokens in `users.google_calendar_token`.

1. `GET /auth/google-calendar` — redirects user to Google OAuth consent (scope: `calendar`)
2. `GET /auth/google-calendar/callback` — exchanges code for tokens, stores in DB
3. `POST /portfolios/{id}/earnings-calendar` — for each holding, look up earnings date via `yfinance`, create Calendar event via `httpx` + stored token (refresh if expired)

No `google-api-python-client` — `httpx` + Calendar REST API is sufficient.

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
| PATCH | `/portfolios/{id}/holdings/{hid}/sell` | JWT | Mark holding as sold |
| POST | `/portfolios/{id}/earnings-calendar` | JWT | Push earnings events to Google Calendar |

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

2a. **Manual smoke test — live Google login**

   Get a real Google ID token via OAuth Playground (https://developers.google.com/oauthplayground):
   - Gear icon → "Use your own OAuth credentials" → paste Client ID + Secret
   - Step 1: select `openid`, `userinfo.email`, `userinfo.profile` scopes → Authorize APIs → sign in
     - With just `openid` scope, you get only `sub` (unique Google user ID) in the ID token. Email and profile only appear if you grant `userinfo.email`, `userinfo.profile` scopes too.
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

   **Backend complete** ✓ — Cedar authz wired (`readPortfolio` / `writePortfolio`), `GET /portfolios`, `GET /portfolios/{id}`, `POST /portfolios/{id}/holdings`, `DELETE /portfolios/{id}/holdings/{holding_id}`, `PATCH /portfolios/{id}/holdings/{holding_id}/sell`. No migration needed — `sale_price`/`sale_date` were in initial schema.

   **Frontend slice (phase 3):** `Portfolio.tsx` — fetches `GET /portfolios/{id}`, renders holdings table. `Holdings.tsx` — form to add a holding (ticker, shares, purchase price, date), calls `POST /portfolios/{id}/holdings`. Sell/Delete button per row that asks users if they want to delete erronesously added holdings or mark them as sold. Based on response, delete holdings or get more info on sale like sale date and sale price. Regenerate `api.d.ts` from updated schema. Sold holdings are not rendered in view but we should persist them in database. Deleted holdings are deleted from table.

   **Frontend complete** ✓ — `api.d.ts` regenerated (includes `PortfolioRead`, `HoldingRead`, `HoldingCreate`, `HoldingSell` + all portfolio/holding paths). `web/src/lib/api.ts` extended with `listPortfolios`, `getPortfolio`, `addHolding`, `deleteHolding`, `sellHolding`. `web/src/pages/Portfolio.tsx` created: active-holdings table (sold rows hidden), inline add-holding form, and a two-step Sell/Delete dialog (confirm-delete or collect sale price + date before calling PATCH /sell). `App.tsx` updated to fetch portfolios on login and render `<Portfolio>` for each.

4. **Market Data**: `services/market_data.py`, wire prices into `GET /portfolios/{id}`

   **Frontend slice (phase 4):** Add "Current Value" and "Gain / Loss" columns to the holdings table (data comes from the enriched `GET /portfolios/{id}` response — no extra frontend calls needed).

5. **Google Calendar**: Calendar OAuth flow, `services/google_calendar.py`, `routers/calendar.py`

   **Frontend slice (phase 5):** "Connect Google Calendar" button that redirects to `GET /auth/google-calendar`. After OAuth completes, show a "Sync Earnings to Calendar" button that calls `POST /portfolios/{id}/earnings-calendar`.

---

## Manual Smoke Tests

- `POST /auth/google` with a real ID token from Google OAuth Playground
- `POST /portfolios/{id}/earnings-calendar` after completing Calendar OAuth flow
- Log in as a member, `GET /portfolios/{other_user_portfolio_id}` → expect 403
- Log in as manager → expect 200 for any portfolio

### Cedar note
`cedarpy` is the official `cedar-policy` Python SDK (same GitHub org as the Cedar language).
