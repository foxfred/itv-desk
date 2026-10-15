import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.realtime import subscribe_events, subscribe_logs

router = APIRouter(prefix="/api", tags=["realtime"])


def _sse_pack(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _sse_response(gen):
    """包一层 SSE 响应头。

    /logs/stream 与 /events/stream 的响应构造完全相同（仅数据源不同），
    此处收敛为唯一定义，避免响应头两处漂移。
    """
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


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
    return _sse_response(_logs_gen())


@router.get("/events/stream")
async def events_stream():
    return _sse_response(_events_gen())
