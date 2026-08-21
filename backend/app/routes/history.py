"""历史记录路由"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config import Config

router = APIRouter(prefix="/api", tags=["history"])


class ImportUrlReq(BaseModel):
    url: str
    proxy: str = ""


class ImportUrlsReq(BaseModel):
    urls: list[str] = []


def get_settings():
    from app.main import settings
    return settings


def _load_history(fname, default):
    return Config.load_json(fname, default)


def _save_history(fname, url, limit_key, default, settings):
    history = Config.load_json(fname, [])
    if url in history:
        history.remove(url)
    history.insert(0, url)
    limit = max(1, int(settings.get(limit_key, 20)))
    Config.save_json(fname, history[:limit], max_len=limit)
    return history[:limit]


@router.get("/history")
def get_history():
    return {
        "url": _load_history(Config.HISTORY_FILE, []),
        "mirror": _load_history(Config.MIRROR_HISTORY_FILE, []),
        "epg": _load_history(Config.EPG_HISTORY_FILE, []),
    }


@router.post("/history/url")
def save_url_history(body: ImportUrlReq, settings=Depends(get_settings)):
    _save_history(Config.HISTORY_FILE, body.url, "url_history_limit", [], settings)
    return {"ok": True}


@router.post("/history/url-batch")
def save_url_history_batch(body: ImportUrlsReq, settings=Depends(get_settings)):
    """批量保存URL历史 - 直接覆盖"""
    urls = [u.strip() for u in body.urls if u.strip()]
    limit = max(1, int(settings.get("url_history_limit", 20)))
    Config.save_json(Config.HISTORY_FILE, urls[:limit], max_len=limit)
    return {"ok": True}


@router.post("/history/mirror")
def save_mirror_history(body: ImportUrlReq, settings=Depends(get_settings)):
    _save_history(Config.MIRROR_HISTORY_FILE, body.url, "mirror_history_limit", [], settings)
    return {"ok": True}


@router.post("/history/mirror-batch")
def save_mirror_history_batch(body: ImportUrlsReq, settings=Depends(get_settings)):
    """批量保存镜像历史 - 直接覆盖"""
    urls = [u.strip() for u in body.urls if u.strip()]
    limit = max(1, int(settings.get("mirror_history_limit", 20)))
    Config.save_json(Config.MIRROR_HISTORY_FILE, urls[:limit], max_len=limit)
    return {"ok": True}


@router.post("/history/epg")
def save_epg_history(body: ImportUrlReq, settings=Depends(get_settings)):
    _save_history(Config.EPG_HISTORY_FILE, body.url, "epg_history_limit", [], settings)
    return {"ok": True}


@router.post("/history/epg-batch")
def save_epg_history_batch(body: ImportUrlsReq, settings=Depends(get_settings)):
    """批量保存EPG历史 - 直接覆盖"""
    urls = [u.strip() for u in body.urls if u.strip()]
    limit = max(1, int(settings.get("epg_history_limit", 20)))
    Config.save_json(Config.EPG_HISTORY_FILE, urls[:limit], max_len=limit)
    return {"ok": True}