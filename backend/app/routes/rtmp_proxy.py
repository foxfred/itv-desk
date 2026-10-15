import asyncio
import logging
import os

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.utils.flv_proxy import ffmpeg_popen, stream_flv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rtmp-proxy", tags=["rtmp-proxy"])

_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")

_CONNECT_TIMEOUT = 15

_ALLOWED_SCHEMES = ("rtmp://", "rtmps://")

# 起进程后等待多久再探活；纯转封装启动快
_READY_DELAY = 0.3

# SSRF 防护：禁止把服务端 ffmpeg 指向本机/内网/云元数据地址
_BLOCKED_PATTERNS = (
    "localhost",
    "127.",
    "0.0.0.0",
    "::1",
    "[::1]",
    "10.",
    "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
    "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "169.254.169.254",
)


def _is_safe_target(url: str) -> bool:
    lower = url.lower()
    if not any(lower.startswith(s) for s in _ALLOWED_SCHEMES):
        return False
    for pat in _BLOCKED_PATTERNS:
        if pat in lower:
            return False
    return True


def _build_ffmpeg_cmd(rtmp_url: str) -> list[str]:
    return [
        _FFMPEG,
        "-hide_banner",
        "-loglevel", "warning",
        "-rw_timeout", str(_CONNECT_TIMEOUT * 1000000),
        "-i", rtmp_url,
        "-c", "copy",
        "-f", "flv",
        "pipe:",
    ]


@router.get("")
async def rtmp_proxy(url: str, request: Request):
    if not url:
        return Response(status_code=400, content="Missing url parameter")

    if not _is_safe_target(url):
        return Response(
            status_code=403,
            content="URL blocked by security policy (SSRF protection)"
        )

    cmd = _build_ffmpeg_cmd(url)
    logger.info("[rtmp-proxy] Starting ffmpeg for: %s", url[:120])

    try:
        proc = ffmpeg_popen(cmd)

        await asyncio.sleep(_READY_DELAY)
        if proc.poll() is not None:
            logger.error("[rtmp-proxy] ffmpeg exited immediately")
            return Response(
                status_code=502,
                content="ffmpeg failed to start (source may be offline or invalid)",
                media_type="text/plain",
            )

        return StreamingResponse(
            stream_flv(proc),
            media_type="video/x-flv",
            headers={
                "Accept-Ranges": "none",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except FileNotFoundError:
        return Response(
            status_code=500,
            content=f"ffmpeg not found at: {_FFMPEG}. Please install ffmpeg or set IPTV_FFMPEG env.",
            media_type="text/plain",
        )
    except Exception as e:
        logger.exception("[rtmp-proxy] Unexpected error")
        return Response(
            status_code=500,
            content=f"Internal error: {e!s}",
            media_type="text/plain",
        )