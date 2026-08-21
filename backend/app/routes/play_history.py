"""播放历史路由 - /api/play-history"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services import play_history_service

router = APIRouter(prefix="/api/play-history", tags=["play-history"])


class PlayReq(BaseModel):
    name: str = ""
    url: str
    group: str = ""
    favorite: bool = False


@router.get("")
def list_history(limit: int = 50):
    return {"items": play_history_service.list_history(limit=limit)}


@router.post("")
def record_play(body: PlayReq):
    if not body.url:
        raise HTTPException(400, "url 不能为空")
    record_id = play_history_service.record_play(body.name, body.url, body.group, body.favorite)
    return {"ok": True, "id": record_id}


@router.post("/{record_id}/favorite")
def toggle_favorite(record_id: int):
    fav = play_history_service.toggle_favorite(record_id)
    if fav is None:
        raise HTTPException(404, "记录不存在")
    return {"ok": True, "is_favorite": fav}


@router.delete("/{record_id}")
def remove(record_id: int):
    ok = play_history_service.remove(record_id)
    if not ok:
        raise HTTPException(404, "记录不存在")
    return {"ok": True}


@router.delete("")
def clear():
    count = play_history_service.clear()
    return {"ok": True, "removed": count}
