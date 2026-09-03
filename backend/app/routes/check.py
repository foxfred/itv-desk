"""检查路由"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["check"])


class CheckReq(BaseModel):
    only_selected: bool = False
    selected_ids: List[int] = []
    threads: int = 40
    timeout: float = 1.5
    retries: int = 1
    resume: bool = False


def get_check_service():
    from app.main import check_service
    return check_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_log():
    from app.main import log
    return log


@router.post("/check")
def start_check(body: CheckReq, check_service=Depends(get_check_service),
                channel_service=Depends(get_channel_service), log=Depends(get_log)):
    if check_service.state["running"]:
        raise HTTPException(400, "已有检查在进行中")
    threads = min(max(1, body.threads), 60)
    timeout = min(max(0.5, body.timeout), 15)
    retries = min(max(0, body.retries), 5)
    items = channel_service.get_all()
    if body.only_selected and body.selected_ids:
        idset = set(body.selected_ids)
        items = [ch for ch in items if ch["id"] in idset]
    elif body.only_selected:
        items = [ch for ch in items if ch.get("checked")]
    if not items:
        return {"error": "没有可检查的频道"}
    if body.resume:
        log(f"断点续检：开始检查 {len(items)} 个未检测频道（线程 {threads}）")
    else:
        log(f"开始检查 {len(items)} 个频道（线程 {threads}）")
    check_service.start_check(items, threads, timeout, retries, resume=body.resume)
    return {"started": True, "total": len(items)}


@router.post("/check/stop")
def check_stop(check_service=Depends(get_check_service), log=Depends(get_log)):
    check_service.stop()
    return {"ok": True}


@router.get("/check/status")
def check_status(check_service=Depends(get_check_service)):
    return check_service.get_status()