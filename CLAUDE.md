# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start Postgres (required before running the app or migrations)
docker compose up -d

# Run API dev server (hot reload)
uv run fastapi dev

# Add a dependency
uv add <package>

# Add a dev dependency (e.g. pytest, mypy)
uv add --dev <package>

# Type check
uv run mypy app/ main.py

# Run tests
uv run pytest

# Create a migration after changing models
uv run alembic revision --autogenerate -m "describe change"

# Apply migrations
uv run alembic upgrade head

# Roll back one migration
uv run alembic downgrade -1
```

### Frontend (web/)

```bash
# Start Vite dev server (in a separate terminal)
cd web && npm run dev

# Install deps after a fresh clone
cd web && npm install

# Regenerate TypeScript types from FastAPI's OpenAPI schema
# (run while the API server is running, or dump schema first)
cd web && npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.d.ts

# Build for production
cd web && npm run build
```

## Architecture

FastAPI backend + Vite/React frontend. `main.py` is the API entrypoint — it creates the `FastAPI` instance and registers routers. All backend logic lives in `app/`. The frontend lives in `web/` and is a separate Node project.

```
app/
├── config.py          # pydantic-settings: reads DATABASE_URL, GOOGLE_CLIENT_ID, JWT_SECRET from .env
├── database.py        # SQLAlchemy engine, SessionLocal, get_db() Depends
├── models.py          # ORM models: User, Portfolio, Holding
├── schemas.py         # Pydantic I/O schemas
├── auth.py            # Google OIDC ID token verification (joserfc + JWKS) + HS256 JWT signing
├── dependencies.py    # get_current_user: decodes Bearer JWT → User ORM object
├── cedar_authz.py     # authorize() helper: builds Cedar entities, calls cedarpy.is_authorized()
├── policies/
│   ├── policies.cedar       # Cedar policy text (manager, member rules)
│   └── schema.cedarschema   # Cedar entity schema
├── routers/
│   ├── auth.py        # POST /auth/google
│   ├── users.py       # GET /users/me
│   ├── portfolios.py  # Portfolio + Holding CRUD
│   └── calendar.py    # POST /portfolios/{id}/earnings-calendar  [planned]
└── services/
    ├── market_data.py      # yfinance: get_price(ticker), get_earnings_date(ticker)  [planned]
    └── google_calendar.py  # Google Calendar API client  [planned]

web/
├── src/
│   ├── main.tsx       # React root, GoogleOAuthProvider
│   ├── App.tsx        # Auth state machine: login → /users/me → dashboard
│   ├── pages/
│   │   └── Login.tsx  # GoogleLogin button, exchanges credential → app JWT
│   ├── lib/
│   │   └── api.ts     # Typed fetch wrappers: login(), getMe()
│   └── types/
│       └── api.d.ts   # Auto-generated from FastAPI's /openapi.json (openapi-typescript)
└── .env               # VITE_GOOGLE_CLIENT_ID, VITE_API_URL (safe to commit — public values only)
```

## Working Conventions

- **Manually added comments**: Never remove or overwrite user-added comments. Only modify them if they are factually wrong — and explicitly call it out in the change summary. Exception: `web/src/types/api.d.ts` is fully auto-generated; always regenerate it wholesale with `openapi-typescript` and don't preserve any manual additions there.
- **plan.md steps**: Only work on one numbered step at a time. Do not proceed to the next step until the current step's changes are committed and pushed to remote.

## Key Conventions

- **Auth**: Browser/mobile sends a Google ID token to `POST /auth/google`; server verifies it via `joserfc` + Google JWKS (1h cache), upserts the user, and returns a 24h HS256 JWT. All other routes require `Authorization: Bearer <jwt>`.
- **Authorization**: Cedar policies in `app/policies/policies.cedar`. The `manager` role can do everything; `member` can only act on their own portfolio. Enforced via `cedar_authz.authorize()` in each route.
- **One portfolio per user**: enforced by `uselist=False` on `User.portfolio`.
- **Computed fields**: current value and gain/loss are derived at query time via `market_data.get_price()` — never stored in the DB.
- **Migrations**: always use `alembic revision --autogenerate` after changing `app/models.py`. Never modify the DB schema by hand.
- **Dependencies**: managed exclusively via `uv` (backend) and `npm` (frontend). Never use `pip install` directly.
- **Roles**: set manually in the DB for the first `manager` user — all new sign-ins default to `member`.
- **Frontend types**: `web/src/types/api.d.ts` is generated from FastAPI's `/openapi.json` via `openapi-typescript`. Regenerate after adding or changing API schemas.

## Database

PostgreSQL 16 via Docker Compose. Connection string read from `DATABASE_URL` in `.env`.

```bash
# Connect directly
docker compose exec db psql -U family_office

# List tables
docker compose exec db psql -U family_office -c "\dt"
```
