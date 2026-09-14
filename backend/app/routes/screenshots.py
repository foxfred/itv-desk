"""画面截图路由（P0-2）"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/screenshots", tags=["screenshots"])


class CaptureReq(BaseModel):
    url: str = ""
    channel_id: int | None = None


class BatchReq(BaseModel):
    ids: list[int] = []
    urls: list[str] = []
    only_missing: bool = True


def get_shot_service():
    from app.main import screenshot_service
    return screenshot_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def _urls_of(channel_service, ids):
    """按频道 id 收集地址（一源一行：每个频道只有一条 url）"""
    urls = []
    pool = {ch.get("id"): ch for ch in getattr(channel_service, "pool", [])}
    for cid in ids or []:
        ch = pool.get(cid)
        if not ch:
            continue
        u = ch.get("url")
        if u and u not in urls:
            urls.append(u)
    return urls


@router.get("")
def shot_list(shot=Depends(get_shot_service)):
    """截图索引（{源URL: 静态路径}）+ 批量任务状态"""
    return {"index": shot.list_index(), "status": shot.get_status()}


@router.get("/status")
def shot_status(shot=Depends(get_shot_service)):
    return shot.get_status()


@router.post("/capture")
def shot_capture(body: CaptureReq, shot=Depends(get_shot_service),
                 channel_service=Depends(get_channel_service)):
    """单个抓帧（同步返回结果，一般 2-8 秒）"""
    url = (body.url or "").strip()
    if not url and body.channel_id is not None:
        urls = _urls_of(channel_service, [body.channel_id])
        url = urls[0] if urls else ""
    if not url:
        return {"ok": False, "error": "未找到可抓取的地址"}
    return shot.capture(url)


@router.post("/batch")
def shot_batch(body: BatchReq, shot=Depends(get_shot_service),
               channel_service=Depends(get_channel_service)):
    """批量抓帧（后台执行，前端轮询 /status）"""
    urls = list(body.urls or [])
    for u in _urls_of(channel_service, body.ids):
        if u not in urls:
            urls.append(u)
    if body.only_missing:
        idx = shot.list_index()
        urls = [u for u in urls if u not in idx]
    if not urls:
        return {"started": False, "total": 0, "error": "没有需要抓取的地址"}
    return shot.capture_batch(urls)


@router.delete("")
def shot_remove(url: str, shot=Depends(get_shot_service)):
    return shot.remove(url)
