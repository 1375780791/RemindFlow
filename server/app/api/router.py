from fastapi import APIRouter

from app.api.routes import auth, health, llm, todos

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(todos.router, prefix="/todos", tags=["todos"])
