from fastapi import FastAPI

from app.routers import auth, users

app = FastAPI(title="Family Office API")
app.include_router(auth.router)
app.include_router(users.router)
