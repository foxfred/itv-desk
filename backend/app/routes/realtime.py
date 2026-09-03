"""实时推送路由 —— 以 SSE（Server-Sent Events）替代高频轮询。

- GET /api/logs/stream   ：实时推送服务端日志（新行即推，连接即回放缓冲）。
- GET /api/events/stream  ：实时推送运行快照（stats / check / scrape），由后台任务周期发布。

保留原有 /api/logs、/api/stats、/check/status、/scrape/status 轮询接口不变，
两者可并存；前端可在支持 EventSource 时优先使用 SSE，否则回退轮询。
"""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.realtime import subscribe_logs, subscribe_events

router = APIRouter(prefix="/api", tags=["realtime"])


def _sse_pack(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


async def _logs_gen():
    yield ": connected\n\n"
    async for item in subscribe_logs():
        yield _sse_pack(item)


async def _events_gen():
    yield ": connected\n\n"
    async for item in subscribe_events():
        yield _sse_pack(item)


@router.get("/logs/stream")
async def logs_stream():
    return StreamingResponse(
        _logs_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/events/stream")
async def events_stream():
    return StreamingResponse(
        _events_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
