from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/dlna", tags=["dlna"])


class DlnaPlayReq(BaseModel):
    device: Any
    url: str


class DlnaStopReq(BaseModel):
    device: Any


def get_dlna_service():
    from app.main import dlna_service
    return dlna_service


@router.get("/devices")
def list_devices(dlna_service=Depends(get_dlna_service)):
    return dlna_service.discover(timeout=3)


@router.post("/play")
def play(body: DlnaPlayReq, dlna_service=Depends(get_dlna_service)):
    return dlna_service.play(body.device, body.url)


@router.post("/stop")
def stop(body: DlnaStopReq, dlna_service=Depends(get_dlna_service)):
    return dlna_service.stop(body.device)
