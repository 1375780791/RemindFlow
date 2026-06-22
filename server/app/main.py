from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.db.session import init_db
from app.tasks.scheduler import start_scheduler, stop_scheduler


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(api_router)

    @app.on_event("startup")
    async def on_startup() -> None:
        init_db()
        start_scheduler()

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        stop_scheduler()

    return app


app = create_app()
