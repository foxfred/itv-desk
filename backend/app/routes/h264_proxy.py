"""H.265 → H.264 实时转码中继端点。

将 HTTP(S) 的 H.265(HLS/TS/裸流) 源通过 ffmpeg 实时重编码为 H.264+AAC 的
HTTP-FLV 流，使前端 flv.js 能在浏览器/MSE 中播放（Chrome/Edge 的 MSE
不支持 H.265 软解，需转码）。

用法：GET /api/h264-proxy?url=<http_h265_url>
返回：video/x-flv 流（flv.js 可直接消费）

⚠️ 桌面本地应用端点：允许访问内网/局域网源（用户自建内网 IPTV 源是合法用途，
   不做 SSRF 拦截——与公网 rtmp-proxy 不同）。校验仅限制 http/https 协议与
   非常见端口，避免误用。
"""
import asyncio
import logging
import os
import subprocess
import urllib.parse

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/h264-proxy", tags=["h264-proxy"])

# ffmpeg 路径（打包后运行时可能不在系统 PATH，需可配置）
_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")

# 转码超时（秒）：ffmpeg 启动 + 首帧输出
_CONNECT_TIMEOUT = 15
# 输出 FLV 块大小
_CHUNK_SIZE = 64 * 1024

# 转码速度/质量：veryfast 兼顾 CPU 与画质；zerolatency 降延迟（直播友好）
_PRESET = os.environ.get("IPTV_H264_PRESET", "veryfast")
_CRF = os.environ.get("IPTV_H264_CRF", "23")

# 允许的协议：仅 http / https
_ALLOWED_SCHEMES = ("http://", "https://")


def _is_http_url(url: str) -> bool:
    return url.lower().startswith(_ALLOWED_SCHEMES)


def _build_ffmpeg_cmd(src_url: str) -> list[str]:
    """构建 ffmpeg 命令行：H.265 HTTP 源 → H.264 FLV。

    - 视频：libx264 重编码（veryfast/zerolatency），CRF 质量
    - 音频：aac 128k（多数源音频原生 aac，此处显式指定防不兼容）
    - 输出：FLV to stdout（pipe:），前端 flv.js 消费
    """
    return [
        _FFMPEG,
        "-hide_banner",
        "-loglevel", "warning",
        "-rw_timeout", str(_CONNECT_TIMEOUT * 1000000),  # 微秒
        "-i", src_url,
        "-c:v", "libx264",
        "-preset", _PRESET,
        "-tune", "zerolatency",
        "-crf", _CRF,
        "-pix_fmt", "yuv420p",
        # 关键帧间隔：1s（约 25/30 帧），便于首帧快速出画 + 快进也不黑屏太久
        "-g", "30",
        "-keyint_min", "30",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        # 低延迟：zerolatency tune + 短 GOP 已足够；
        # 注意：-flags low_delay / -max_delay 0 会让 FLV muxer 在 pipe 模式
        # 报 "Invalid argument" 并立即退出，故不在此使用。
        "-fflags", "nobuffer",
        "-f", "flv",
        "pipe:",
    ]


async def _stream_flv(proc: subprocess.Popen) -> bytes:
    """异步从 ffmpeg stdout 读取 FLV 数据块；客户端断开时清理进程。"""
    loop = asyncio.get_running_loop()
    try:
        while True:
            chunk = await loop.run_in_executor(None, proc.stdout.read, _CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(loop.run_in_executor(None, proc.wait), timeout=3)
                except Exception:
                    proc.kill()
                    try:
                        await asyncio.wait_for(loop.run_in_executor(None, proc.wait), timeout=2)
                    except Exception:
                        pass
            except Exception:
                pass


@router.get("")
async def h264_proxy(url: str, request: Request):
    """H.265 HTTP 源 → H.264 FLV 转码入口。"""
    if not url:
        return Response(status_code=400, content="Missing url parameter")

    # FastAPI 已对 query 参数自动解码，url 即为解码后的源地址
    if not _is_http_url(url):
        return Response(
            status_code=403,
            content="Only http/https source URLs are allowed"
        )

    cmd = _build_ffmpeg_cmd(url)
    logger.info("[h264-proxy] Starting ffmpeg transcode for: %s", url[:120])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        await asyncio.sleep(0.5)
        if proc.poll() is not None:
            logger.error("[h264-proxy] ffmpeg exited immediately for %s", url[:100])
            return Response(
                status_code=502,
                content="ffmpeg transcode failed to start (source may be offline/invalid)",
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
        logger.exception("[h264-proxy] Unexpected error")
        return Response(
            status_code=500,
            content=f"Internal error: {str(e)}",
            media_type="text/plain",
        )