# Family Office

A household portfolio management app. Members track stock and ETF holdings; the family office manager can oversee all portfolios. Built with FastAPI + PostgreSQL, consumed by browser or an Android app.

## Features

- Google OAuth login (no passwords)
- One portfolio per member — stocks and ETFs with live prices and gain/loss
- Manager role can read and write all portfolios; members manage their own
- Cedar authorization policies
- Earnings dates pushed to Google Calendar (server-side)

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for local Postgres

## Quick Start

```bash
# 1. Copy env template and fill in your Google Client ID and a JWT secret
cp .env.example .env

# 2. Start Postgres
docker compose up -d

# 3. Run database migrations
uv run alembic upgrade head

# 4. Start the dev server (hot reload)
uv run fastapi dev
```

API is available at http://localhost:8000  
Interactive docs at http://localhost:8000/docs

## Project Structure

```
app/
├── config.py          # Settings loaded from .env
├── database.py        # SQLAlchemy engine + get_db dependency
├── models.py          # ORM models: User, Portfolio, Holding
├── schemas.py         # Pydantic request/response schemas
├── auth.py            # Google OIDC token verification + JWT issuance
├── dependencies.py    # get_current_user Depends()
├── cedar_authz.py     # Cedar policy engine wrapper
├── policies/          # .cedar policy files
├── routers/           # Route handlers (auth, users, portfolios, calendar)
└── services/          # market_data (yfinance), google_calendar (httpx)
alembic/               # Database migrations
tests/                 # pytest test suite
```

## Common Commands

```bash
# Add a dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Type check
uv run mypy app/ main.py

# Run tests
uv run pytest

# Create a new migration after changing models
uv run alembic revision --autogenerate -m "describe change"

# Apply pending migrations
uv run alembic upgrade head

# Roll back one migration
uv run alembic downgrade -1
```

## Environment Variables

See `.env.example` for all required variables. Key ones:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Postgres connection string |
| `DATABASE_URL_TEST` | Postgres connection string for test DB |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 client ID from Google Cloud Console |
| `JWT_SECRET` | Random secret for signing app JWTs (`python -c "import secrets; print(secrets.token_hex(32))"`) |
