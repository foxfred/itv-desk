"""DLNA 投屏路由 - /api/dlna"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/dlna", tags=["dlna"])


class DlnaPlayReq(BaseModel):
    device: Any  # 设备字典（含 control_url）或设备名称字符串
    url: str


class DlnaStopReq(BaseModel):
    device: Any


def get_dlna_service():
    from app.main import dlna_service
    return dlna_service


@router.get("/devices")
def list_devices(dlna_service=Depends(get_dlna_service)):
    """发现局域网内可投屏的 DLNA 设备"""
    return dlna_service.discover(timeout=3)


@router.post("/play")
def play(body: DlnaPlayReq, dlna_service=Depends(get_dlna_service)):
    """向指定设备投屏并播放直播源"""
    return dlna_service.play(body.device, body.url)


@router.post("/stop")
def stop(body: DlnaStopReq, dlna_service=Depends(get_dlna_service)):
    """停止指定设备播放"""
    return dlna_service.stop(body.device)
