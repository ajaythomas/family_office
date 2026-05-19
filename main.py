from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, portfolios, users

app = FastAPI(title="Family Office API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins, # This lets you use the default from the app/config.py for local deploy or the env vars coming from the .env for prod deploy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(portfolios.router)
