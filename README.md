# Family Office

A household portfolio management app. Members track stock and ETF holdings; the family office manager can oversee all portfolios. Built with FastAPI + PostgreSQL, consumed by browser or an Android app.

## Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Production Deploy (Hetzner)](#production-deploy-hetzner)
- [Project Structure](#project-structure)
- [Common Commands](#common-commands)
- [Environment Variables](#environment-variables)

## Features

- Google OAuth login (no passwords)
- One portfolio per member — stocks and ETFs with live prices and gain/loss
- Manager role can read and write all portfolios; members manage their own
- Cedar authorization policies
- Earnings dates pushed to Google Calendar (server-side)

## Prerequisites

- [Python](https://www.python.org/) 3.14+
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Node.js](https://nodejs.org/) 18+ — for the web frontend
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for local Postgres

## Quick Start

```bash
# 1. Copy env template and fill in your Google Client ID and a JWT secret
cp .env.example .env

# 2. Start Postgres
docker compose up -d

# 3. Run database migrations
uv run alembic upgrade head

# 4. Start the API server (hot reload)
uv run fastapi dev
```

API is available at http://localhost:8000  
Interactive docs at http://localhost:8000/docs

```bash
# 5. In a separate terminal, start the web frontend
cd web && npm install && npm run dev
```

Web app is available at http://localhost:5173

### Google Cloud Console setup

In [Google Cloud Console](https://console.cloud.google.com/) → OAuth 2.0 Client → add these to **Authorized JavaScript origins**:
- `http://localhost:5173`
Vite frontend (listening on port 5173) is where @react-oauth/google JavaScript runs. Google validates the origin of the page that initiates the sign-in flow, which is the browser loading the React app, not the FastAPI server (that listens on port 8000).

And these to **Authorized redirect URIs**:
- `http://localhost:8000/auth/google-calendar/callback`
This is needed for Google Calendar OAuth flow. The Google login uses Google Identity Services (@react-oauth/google) that follows the OIDC implicit flow. It returns the signed ID JWT token directly to a JavaScript callback in the browser — no redirect URI involved. Google never redirects to the server; our frontend just calls POST `/auth/google` with the token it received. That's why no redirect URI is needed in Cloud Console for this flow.
Google Calendar OAuth is a standard OAuth 2.0 authorization code flow — Google redirects the browser to our registered callback URL with an auth code. 
That's why http://localhost:8000/auth/google-calendar/callback must be registered.
Two different protocols, which is why the calendar OAuth flow shows up in our redirect URIs.

Also, for an unverified OAuth app like ours, we need to explicitly add test users to complete the Calendar OAuth flow. Else you get the error "FamilyOffice has not completed the Google verification process. The app is currently being tested, and can only be accessed by developer-approved testers." You add a test user in the Google Cloud Console:
  1. Go to Google Cloud Console → your project → Audience (https://console.cloud.google.com/auth/audience)
  2. Scroll down to Test users
  3. Click Add users and add the gmail address of your test user (E.g: john.doe@gmail.com)
  4. Save
After that, the OAuth flow will work for your account even though the app isn't publicly verified. The "verification process" warning only goes away once you submit the app for Google's review, which you'd only do before a public launch.

### Local Debugging
launch.json exists for your VSCode debugging pleasure.
  1. Stop uv run fastapi dev if it's running
  2. In VS Code, open the Run & Debug panel (Cmd+Shift+D), select FastAPI, hit the green play button
  3. Set a breakpoint at where you wish to debug
  4. Trigger the endpoint from the UI


## Production Deploy (Hetzner)

Requires a domain pointed at your server and Docker installed on the VM.

**One-time server setup:**
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone the repo
git clone <repo-url> && cd family_office
```

**Configure environment:**

1. Edit `web/.env.production` — replace `YOUR_DOMAIN_HERE` with your domain:
   ```
   VITE_API_URL=https://api.your-domain.com
   ```

2. Create `.env` from the template and fill in production values:
   ```bash
   cp .env.example .env
   ```
   Key differences from local dev:

   | Variable | Production value |
   |----------|-----------------|
   | `DATABASE_URL` | `postgresql://family_office:<password>@db:5432/family_office` — hostname is `db`, not `localhost` |
   | `CORS_ORIGINS` | `["https://your-domain.com"]` |
   | `APP_DOMAIN` | `your-domain.com` |
   | `JWT_SECRET` | Fresh generated secret |

3. Add your production domain to [Google Cloud Console](https://console.cloud.google.com/) → OAuth 2.0 Client → Authorized JavaScript origins and Authorized redirect URIs.

**Start everything:**
```bash
COMPOSE_PROFILES=prod docker compose up -d
```
COMPOSE_PROFILES is an inline env var that is used for the above docker command. Without specifying prod, the default profile is run; which as you can see in the docker-compose.yml file - only runs the db container.
Caddy automatically provisions SSL certificates. The app will be live at `https://your-domain.com`.

**Subsequent deploys:**
```bash
git pull
COMPOSE_PROFILES=prod docker compose up -d --build
```

## Project Structure

```
main.py                # FastAPI app, router registration, APScheduler lifespan (daily calendar cron)
app/
├── config.py          # Settings loaded from .env
├── database.py        # SQLAlchemy engine + get_db dependency
├── models.py          # ORM models: User, Portfolio, Holding (with earnings_date, calendar_event_created)
├── schemas.py         # Pydantic request/response schemas
├── auth.py            # Google OIDC token verification + JWT issuance
├── dependencies.py    # get_current_user Depends()
├── cedar_authz.py     # Cedar policy engine wrapper
├── policies/          # .cedar policy files
├── routers/
│   ├── auth.py        # POST /auth/google, GET /auth/google-calendar*
│   ├── users.py       # GET /users/me
│   ├── portfolios.py  # Portfolio + Holding CRUD; uses stored earnings_date, re-fetches only when stale
│   └── calendar.py    # POST /portfolios/{id}/earnings-calendar; daily cron via APScheduler
└── services/
    ├── market_data.py      # yfinance: get_price(), get_earnings_date()
    └── google_calendar.py  # Google Calendar REST API: token refresh + event creation
web/                   # Vite + React + TypeScript frontend
├── src/
│   ├── lib/api.ts     # Typed fetch wrappers (generated types from OpenAPI)
│   ├── pages/         # Login, Portfolio pages
│   └── types/api.d.ts # Auto-generated from FastAPI's /openapi.json
└── .env               # VITE_GOOGLE_CLIENT_ID, VITE_API_URL (safe to commit)
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
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 client secret from Google Cloud Console |
| `JWT_SECRET` | Random secret for signing app JWTs (`python -c "import secrets; print(secrets.token_hex(32))"`) |
