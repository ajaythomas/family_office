# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start Postgres (required before running the app or migrations)
docker compose up -d

# Run dev server (hot reload)
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

## Architecture

FastAPI app with an `app/` package. `main.py` is the entrypoint — it creates the `FastAPI` instance and registers routers. All logic lives in `app/`.

```
app/
├── config.py          # pydantic-settings: reads DATABASE_URL, GOOGLE_CLIENT_ID, JWT_SECRET from .env
├── database.py        # SQLAlchemy engine, SessionLocal, get_db() Depends
├── models.py          # ORM models: User, Portfolio, Holding
├── schemas.py         # Pydantic I/O schemas
├── auth.py            # Google OIDC ID token verification (authlib) + app JWT signing
├── dependencies.py    # get_current_user: decodes Bearer JWT → User ORM object
├── cedar_authz.py     # authorize() helper: builds Cedar entities, calls cedarpy.is_authorized()
├── policies/
│   ├── policies.cedar       # Cedar policy text (manager, member rules)
│   └── schema.cedarschema   # Cedar entity schema
├── routers/
│   ├── auth.py        # POST /auth/google, GET /auth/google-calendar, GET /auth/google-calendar/callback
│   ├── users.py       # GET /users/me
│   ├── portfolios.py  # Portfolio + Holding CRUD
│   └── calendar.py    # POST /portfolios/{id}/earnings-calendar
└── services/
    ├── market_data.py      # yfinance: get_price(ticker), get_earnings_date(ticker)
    └── google_calendar.py  # httpx calls to Google Calendar REST API
```

## Key Conventions

- **Auth**: Android sends a Google ID token to `POST /auth/google`; server verifies it via `authlib`, upserts the user, and returns a short-lived HS256 JWT. All other routes require `Authorization: Bearer <jwt>`.
- **Authorization**: Cedar policies in `app/policies/policies.cedar`. The `manager` role can do everything; `member` can only act on their own portfolio. Enforced via `cedar_authz.authorize()` in each route.
- **One portfolio per user**: enforced by `uselist=False` on `User.portfolio`.
- **Computed fields**: current value and gain/loss are derived at query time via `market_data.get_price()` — never stored in the DB.
- **Migrations**: always use `alembic revision --autogenerate` after changing `app/models.py`. Never modify the DB schema by hand.
- **Dependencies**: managed exclusively via `uv`. Never use `pip install` directly.
- **Roles**: set manually in the DB for the first `manager` user — all new sign-ins default to `member`.

## Database

PostgreSQL 16 via Docker Compose. Connection string read from `DATABASE_URL` in `.env`.

```bash
# Connect directly
docker compose exec db psql -U family_office

# List tables
docker compose exec db psql -U family_office -c "\dt"
```
