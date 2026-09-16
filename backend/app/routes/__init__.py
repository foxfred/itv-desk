from fastapi import APIRouter
from app.routes import channels, scrape, check, epg, rules, repair, export, config, history

api_router = APIRouter()

api_router.include_router(channels.router)
api_router.include_router(scrape.router)
api_router.include_router(check.router)
api_router.include_router(epg.router)
api_router.include_router(rules.router)
api_router.include_router(repair.router)
api_router.include_router(export.router)
api_router.include_router(config.router)
api_router.include_router(history.router)