from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/epg", tags=["epg"])


class EpgReq(BaseModel):
    url: str
    proxy: str = ""


class EpgSourceReq(BaseModel):
    url: str
    proxy: str = ""
    auto_refresh_interval: int = 0


class SearchReq(BaseModel):
    keyword: str


class EpgBatchReq(BaseModel):
    sources: list[dict]  # [{"url": "...", "proxy": ""}, ...]


def get_epg_service():
    from app.main import epg_service
    return epg_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_settings():
    from app.main import settings
    return settings


@router.post("/load")
def epg_load(body: EpgReq, epg_service=Depends(get_epg_service)):
    return epg_service.load_epg(body.url, body.proxy)


@router.post("/load-batch")
def epg_load_batch(body: EpgBatchReq, epg_service=Depends(get_epg_service),
                   settings=Depends(get_settings)):
    proxy = settings.get("proxy", "") if settings.get("use_proxy", False) else ""
    urls = [(s["url"], proxy) for s in body.sources if s.get("url")]
    if not urls:
        return {"error": "未提供 EPG 源地址"}
    return epg_service.load_epg_batch(urls)


@router.get("/auto-sources")
def epg_auto_sources():
    from app.main import subscription_service
    return {"sources": subscription_service.auto_epg_sources()}


@router.get("/status")
def epg_status(epg_service=Depends(get_epg_service)):
    return epg_service.get_status()


@router.post("/correct-names")
def epg_correct_names(epg_service=Depends(get_epg_service),
                      channel_service=Depends(get_channel_service)):
    return epg_service.correct_names(channel_service)


@router.post("/update-groups")
def epg_update_groups(epg_service=Depends(get_epg_service),
                      channel_service=Depends(get_channel_service)):
    return epg_service.update_groups(channel_service)


@router.post("/search")
def epg_search(body: SearchReq, epg_service=Depends(get_epg_service)):
    return epg_service.search(body.keyword)


@router.get("/program")
def epg_program(name: str = Query(...), epg_service=Depends(get_epg_service)):
    return epg_service.get_program(name)


@router.get("/channels")
def epg_channels(epg_service=Depends(get_epg_service)):
    return epg_service.get_channels()


@router.get("/programs")
def epg_programs(name: str = Query(...), epg_service=Depends(get_epg_service)):
    return epg_service.get_programs(name)


@router.get("/match")
def epg_match(name: str = Query(...), epg_service=Depends(get_epg_service)):
    return epg_service.match_channel(name)


@router.post("/set-source")
def epg_set_source(body: EpgSourceReq, epg_service=Depends(get_epg_service)):
    epg_service.save_source(body.url, body.proxy)
    if body.auto_refresh_interval and body.auto_refresh_interval > 0:
        epg_service.start_refresh_scheduler(body.auto_refresh_interval)
    return epg_service.load_epg(body.url, body.proxy)


@router.post("/refresh")
def epg_refresh(epg_service=Depends(get_epg_service)):
    return epg_service.refresh_from_source()

@router.get("/catchup")
def epg_catchup(name: str = Query(...), start: int = Query(...), stop: int = Query(0),
                channel_service=Depends(get_channel_service),
                settings=Depends(get_settings)):
    import datetime as _dt
    from app.utils.catchup import build_catchup_url, has_catchup

    if not settings.get("catchup_enabled", True):
        return {"ok": False, "error": "回看功能已在设置中关闭"}
    fallback = None
    found = None
    for ch in getattr(channel_service, "pool", []) or []:
        n = ch.get("name") or ""
        if not n or not (n == name or n in name or name in n):
            continue
        if has_catchup(ch):
            found = ch
            break
        if fallback is None:
            fallback = ch
    target = found or fallback
    if target is None:
        return {"ok": False, "error": "未在频道列表中找到「%s」" % name}
    if not has_catchup(target):
        return {"ok": False, "error": "该频道源未提供回看（catchup）信息"}
    s = _dt.datetime.fromtimestamp(int(start))
    e = _dt.datetime.fromtimestamp(int(stop)) if stop else s + _dt.timedelta(hours=1)
    url = build_catchup_url(target, s, e)
    if not url:
        return {"ok": False, "error": "该频道的回看格式暂不支持"}
    return {"ok": True, "url": url, "channel": target.get("name"),
            "start": s.strftime("%Y-%m-%d %H:%M"), "stop": e.strftime("%H:%M")}
