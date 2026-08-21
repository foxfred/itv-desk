"""RTMP → HTTP-FLV 中继端点。

将 rtmp:// / rtmps:// 源通过 ffmpeg 实时转码为 HTTP-FLV 流，
使前端 flv.js（已集成）能在浏览器/MSE 环境中播放 RTMP 类视频。

用法：GET /api/rtmp-proxy?url=<rtmp_url>
返回：video/x-flv 流（flv.js 可直接消费）
"""
import asyncio
import logging
import os
import shlex
import subprocess

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rtmp-proxy", tags=["rtmp-proxy"])

# ffmpeg 路径（打包后运行时可能不在系统 PATH，需可配置）
_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")

# 转码超时（秒）：ffmpeg 启动 + 首帧输出
_CONNECT_TIMEOUT = 15
# 整体流式读取超时（秒），0 = 不限（直播流持续输出）
_STREAM_TIMEOUT = 0

# 允许的协议前缀
_ALLOWED_SCHEMES = ("rtmp://", "rtmps://")

# SSRF 防护：拦截的地址模式（同 stream_proxy）
_BLOCKED_PATTERNS = (
    "localhost",
    "127.",
    "0.0.0.0",
    "::1",
    "[::1]",
    # 内网段
    "10.",
    "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
    "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    # 云元数据
    "169.254.169.254",
)


def _is_safe_target(url: str) -> bool:
    """基本安全检查：仅允许 rtmp/rtmps，拦截内网/本地地址。"""
    lower = url.lower()
    if not any(lower.startswith(s) for s in _ALLOWED_SCHEMES):
        return False
    # 提取 host 做简单检查（RTMP URL 格式: rtmp://host[:port]/app/stream）
    for pat in _BLOCKED_PATTERNS:
        if pat in lower:
            return False
    return True


def _build_ffmpeg_cmd(rtmp_url: str) -> list[str]:
    """构建 ffmpeg 命令行：RTMP → FLV（copy 模式，零重编码）。

    ⚠️ `-c copy` 必须拆成两个参数 `-c`, `copy`，否则 ffmpeg 报
    "Unrecognized option 'c copy'"（参数解析按空格切分，单字符串不拆）。
    """
    return [
        _FFMPEG,
        "-hide_banner",
        "-loglevel", "warning",
        "-rw_timeout", str(_CONNECT_TIMEOUT * 1000000),  # 微秒
        "-i", rtmp_url,
        "-c", "copy",          # 直接封装，不重编码（低 CPU）
        "-f", "flv",           # 输出 FLV 容器
        "pipe:",               # 输出到 stdout
    ]


async def _stream_flv(proc: subprocess.Popen) -> bytes:
    """异步从 ffmpeg stdout 读取 FLV 数据块。

    客户端断开（StreamingResponse 被取消）时，generator 的 finally 触发：
    terminate → wait(3s) → kill，收紧清理窗口，避免直播流一直输出导致进程残留。
    """
    loop = asyncio.get_event_loop()
    chunk_size = 64 * 1024  # 64KB 块
    try:
        while True:
            chunk = await loop.run_in_executor(None, proc.stdout.read, chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        # 确保 ffmpeg 进程被清理（收紧：terminate 后最多等 3s 再 kill）
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
    """RTMP → HTTP-FLV 中继入口。"""
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
        # 启动 ffmpeg 子进程（CREATE_NO_WINDOW 隐藏 cmd 窗口，后台静默运行）
        # F修复：stderr 用 DEVNULL——ffmpeg 大量 warning 时若 PIPE 不读会阻塞写→卡死 stdout。
        # 启动成功判断只看存活（poll），失败信息从 stdout 兜底（ffmpeg 错误也常打 stdout）。
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        # 快速检测 ffmpeg 是否成功启动（非阻塞 poll）
        await asyncio.sleep(0.3)
        if proc.poll() is not None:
            # stderr 已丢弃，改用统一失败信息（ffmpeg 启动失败常见原因：源不可达/地址错）
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
                "X-Accel-Buffering": "no",  # 禁止 nginx 缓冲（如有反代）
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
