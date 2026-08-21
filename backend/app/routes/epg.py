"""EPG 路由"""
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


def get_epg_service():
    from app.main import epg_service
    return epg_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


@router.post("/load")
def epg_load(body: EpgReq, epg_service=Depends(get_epg_service)):
    return epg_service.load_epg(body.url, body.proxy)


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
    """按频道名自动匹配 EPG（当前节目 + 今日节目单）"""
    return epg_service.match_channel(name)


@router.post("/set-source")
def epg_set_source(body: EpgSourceReq, epg_service=Depends(get_epg_service)):
    """保存 EPG 源并（可选）开启定时刷新；随后立即拉取一次"""
    epg_service.save_source(body.url, body.proxy)
    if body.auto_refresh_interval and body.auto_refresh_interval > 0:
        epg_service.start_refresh_scheduler(body.auto_refresh_interval)
    return epg_service.load_epg(body.url, body.proxy)


@router.post("/refresh")
def epg_refresh(epg_service=Depends(get_epg_service)):
    """按已保存的源重新拉取 EPG"""
    return epg_service.refresh_from_source()