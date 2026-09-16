import asyncio
import logging
import os
import shlex
import subprocess

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rtmp-proxy", tags=["rtmp-proxy"])

_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")

_CONNECT_TIMEOUT = 15
_STREAM_TIMEOUT = 0

_ALLOWED_SCHEMES = ("rtmp://", "rtmps://")

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


async def _stream_flv(proc: subprocess.Popen) -> bytes:
    loop = asyncio.get_event_loop()
    chunk_size = 64 * 1024
    try:
        while True:
            chunk = await loop.run_in_executor(None, proc.stdout.read, chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, proc.wait), timeout=3
                    )
                except (asyncio.TimeoutError, subprocess.TimeoutExpired):
                    proc.kill()
                    try:
                        await asyncio.wait_for(
                            loop.run_in_executor(None, proc.wait), timeout=2
                        )
                    except Exception:
                        pass
            except Exception:
                pass


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
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        await asyncio.sleep(0.3)
        if proc.poll() is not None:
            logger.error("[rtmp-proxy] ffmpeg exited immediately")
            return Response(
                status_code=502,
                content="ffmpeg failed to start (source may be offline or invalid)",
                media_type="text/plain",
            )

        return StreamingResponse(
            _stream_flv(proc),
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
            content=f"Internal error: {str(e)}",
            media_type="text/plain",
        )
