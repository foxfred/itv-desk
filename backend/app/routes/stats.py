"""频道健康统计路由（P1-10）"""
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/stats", tags=["stats"])


def get_stats_service():
    from app.main import stats_service
    return stats_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


@router.get("/report")
def stats_report(days: int = Query(7, ge=1, le=90),
                 stats_service=Depends(get_stats_service),
                 channel_service=Depends(get_channel_service)):
    """健康报告：按天趋势 + 当前失效 Top + 延迟/清晰度分布"""
    return stats_service.report(channel_service, days=days)


@router.post("/snapshot")
def stats_snapshot(force: bool = Query(False),
                   stats_service=Depends(get_stats_service),
                   channel_service=Depends(get_channel_service)):
    """立即记录一次当天的健康快照（force=true 覆盖当天已有记录）"""
    return stats_service.snapshot(channel_service, force=force)
