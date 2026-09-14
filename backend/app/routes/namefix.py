"""频道名校正路由（方案书-频道名自动校正 · 阶段 B/C）

抓帧 → 台标/字幕 OCR → EPG 交叉验证 → 改名建议表 → 人工确认/自动应用 → 撤销
"""
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
    """扫描进度 + 建议表统计"""
    st = svc.get_status()
    sug = svc.suggestions()
    return {"status": st, "summary": sug.get("summary", {}), "total": sug.get("total", 0)}


@router.get("/suggestions")
def nf_suggestions(state: str = "", svc=Depends(get_service)):
    """改名建议表。state 可选：pending / ambiguous / unresolved / unreachable / junk / no_text / consistent"""
    return svc.suggestions(state=state or None)


@router.post("/scan")
def nf_scan(body: ScanReq, svc=Depends(get_service)):
    """启动扫描（后台执行，前端轮询 /status）。ids 为空则全量。"""
    return svc.scan(ids=body.ids or None, limit=body.limit or None,
                    use_vision=body.use_vision)


@router.post("/apply")
def nf_apply(body: IdsReq, svc=Depends(get_service)):
    """应用建议（ids 为空则应用所有待确认项）。改名前自动备份，可整批撤销。"""
    return svc.apply(ids=body.ids or None)


@router.post("/dismiss")
def nf_dismiss(body: IdsReq, svc=Depends(get_service)):
    """忽略这些建议，不再提醒"""
    return svc.dismiss(body.ids)


@router.post("/undo")
def nf_undo(body: UndoReq, svc=Depends(get_service)):
    """撤销一批改名（不传 batch_id 则撤销最近一批）"""
    return svc.undo(body.batch_id or None)


@router.get("/undo-list")
def nf_undo_list(svc=Depends(get_service)):
    """可撤销的批次列表"""
    return svc.undo_list()


@router.post("/vision-test")
def nf_vision_test(svc=Depends(get_service)):
    """测试视觉兜底通道是否可用（用现有一帧试识别）"""
    return svc.vision_test()


@router.get("/self-check")
def nf_self_check(svc=Depends(get_service)):
    """关键规则回归自检（纯文本层，不抓帧不联网）。

    守的是 2026-09-14 那次实测报错：归一化把 4K 当画质后缀剥掉，
    使裸「CCTV」角标精确命中 CCTV4K，把辽宁卫视/宁夏卫视判成 CCTV4K。
    """
    from app.services import namefix_service as nf
    a = nf.self_check()
    b = nf.resolve_check(svc._load_alias() or {}, None)
    return {"ok": not a["failed"] and not b["failed"],
            "text_rules": a, "alias_lookup": b}


@router.post("/clear")
def nf_clear(svc=Depends(get_service)):
    """清空建议表（不改动频道数据）"""
    return svc.clear()
