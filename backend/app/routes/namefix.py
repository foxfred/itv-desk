from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/namefix", tags=["namefix"])


class ScanReq(BaseModel):
    ids: list[int] = []
    limit: int = 0
    use_vision: bool | None = None


class IdsReq(BaseModel):
    ids: list[int] = []


class UndoReq(BaseModel):
    batch_id: str = ""


def get_service():
    from app.main import namefix_service
    return namefix_service


@router.get("/status")
def nf_status(svc=Depends(get_service)):
    st = svc.get_status()
    sug = svc.suggestions()
    return {"status": st, "summary": sug.get("summary", {}), "total": sug.get("total", 0)}


@router.get("/suggestions")
def nf_suggestions(state: str = "", svc=Depends(get_service)):
    return svc.suggestions(state=state or None)


@router.post("/scan")
def nf_scan(body: ScanReq, svc=Depends(get_service)):
    return svc.scan(ids=body.ids or None, limit=body.limit or None,
                    use_vision=body.use_vision)


@router.post("/apply")
def nf_apply(body: IdsReq, svc=Depends(get_service)):
    return svc.apply(ids=body.ids or None)


@router.post("/dismiss")
def nf_dismiss(body: IdsReq, svc=Depends(get_service)):
    return svc.dismiss(body.ids)


@router.post("/undo")
def nf_undo(body: UndoReq, svc=Depends(get_service)):
    return svc.undo(body.batch_id or None)


@router.get("/undo-list")
def nf_undo_list(svc=Depends(get_service)):
    return svc.undo_list()


@router.post("/vision-test")
def nf_vision_test(svc=Depends(get_service)):
    return svc.vision_test()


@router.get("/self-check")
def nf_self_check(svc=Depends(get_service)):
    from app.services import namefix_service as nf
    a = nf.self_check()
    b = nf.resolve_check(svc._load_alias() or {}, None)
    return {"ok": not a["failed"] and not b["failed"],
            "text_rules": a, "alias_lookup": b}


@router.post("/clear")
def nf_clear(svc=Depends(get_service)):
    return svc.clear()
