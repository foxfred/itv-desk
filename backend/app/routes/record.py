from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["record"])


def get_recorder():
    from app.main import record_service
    return record_service


def get_settings():
    from app.main import settings
    return settings


class RecordReq(BaseModel):
    name: str = ""
    url: str = ""
    container: str = ""
    max_minutes: int | None = None


class IdReq(BaseModel):
    id: str = ""


class TimeshiftReq(BaseModel):
    url: str = ""
    minutes: int | None = None


@router.get("/record/list")
def record_list(rec=Depends(get_recorder)):
    return {"records": rec.list_records(), "active": rec.active_jobs()}


@router.post("/record/start")
def record_start(body: RecordReq, rec=Depends(get_recorder), settings=Depends(get_settings)):
    container = (body.container or settings.get("record_container") or "mp4").strip()
    mm = body.max_minutes if body.max_minutes is not None else settings.get("record_max_minutes", 0)
    return rec.start_record(body.name, body.url, container=container, max_minutes=mm)


@router.post("/record/stop")
def record_stop(body: IdReq, rec=Depends(get_recorder)):
    return rec.stop_record(body.id or None)


@router.delete("/record/{fname}")
def record_delete(fname: str, rec=Depends(get_recorder)):
    return rec.delete_record(fname)


@router.get("/timeshift/list")
def timeshift_list(rec=Depends(get_recorder)):
    return {"sessions": rec.list_timeshift()}


@router.post("/timeshift/start")
def timeshift_start(body: TimeshiftReq, rec=Depends(get_recorder), settings=Depends(get_settings)):
    minutes = body.minutes if body.minutes is not None else settings.get("timeshift_minutes", 0)
    return rec.start_timeshift(
        body.url,
        minutes=minutes,
        segment_seconds=settings.get("timeshift_segment_seconds", 4),
    )


@router.post("/timeshift/stop")
def timeshift_stop(body: IdReq, rec=Depends(get_recorder)):
    return rec.stop_timeshift(body.id or None)
