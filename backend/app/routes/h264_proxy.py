import asyncio
import logging
import os

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.utils.flv_proxy import ffmpeg_popen, stream_flv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/h264-proxy", tags=["h264-proxy"])

_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")

_CONNECT_TIMEOUT = 15

_PRESET = os.environ.get("IPTV_H264_PRESET", "veryfast")
_CRF = os.environ.get("IPTV_H264_CRF", "23")

_ALLOWED_SCHEMES = ("http://", "https://")

# 起进程后等待多久再探活；转码启动比纯转封装慢，需留足时间
_READY_DELAY = 0.5


def _is_http_url(url: str) -> bool:
    return url.lower().startswith(_ALLOWED_SCHEMES)


def _build_ffmpeg_cmd(src_url: str) -> list[str]:
    return [
        _FFMPEG,
        "-hide_banner",
        "-loglevel", "warning",
        "-rw_timeout", str(_CONNECT_TIMEOUT * 1000000),
        "-i", src_url,
        "-c:v", "libx264",
        "-preset", _PRESET,
        "-tune", "zerolatency",
        "-crf", _CRF,
        "-vf", "scale=in_range=full:out_range=tv,format=yuv420p",
        "-g", "30",
        "-keyint_min", "30",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        "-fflags", "nobuffer",
        "-f", "flv",
        "pipe:",
    ]


@router.get("")
async def h264_proxy(url: str, request: Request):
    if not url:
        return Response(status_code=400, content="Missing url parameter")

    if not _is_http_url(url):
        return Response(
            status_code=403,
            content="Only http/https source URLs are allowed"
        )

    cmd = _build_ffmpeg_cmd(url)
    logger.info("[h264-proxy] Starting ffmpeg transcode for: %s", url[:120])

    try:
        proc = ffmpeg_popen(cmd)

        await asyncio.sleep(_READY_DELAY)
        if proc.poll() is not None:
            logger.error("[h264-proxy] ffmpeg exited immediately for %s", url[:100])
            return Response(
                status_code=502,
                content="ffmpeg transcode failed to start (source may be offline/invalid)",
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
        logger.exception("[h264-proxy] Unexpected error")
        return Response(
            status_code=500,
            content=f"Internal error: {e!s}",
            media_type="text/plain",
        )