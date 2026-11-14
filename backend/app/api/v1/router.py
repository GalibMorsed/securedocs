from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)

# Later phases register routers here: auth, users, documents, search, chat, admin
