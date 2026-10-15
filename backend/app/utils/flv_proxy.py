"""ffmpeg 管道转封装（FLV over HTTP）的共享实现。

`routes/h264_proxy.py`（H.264 转码，为兼容老播放器）与
`routes/rtmp_proxy.py`（RTMP/RTMPS 转封装）除了「允许的协议」和
「ffmpeg 参数」外，其余流程完全一致：校验入参 → 起 ffmpeg → 探活 →
流式回吐 stdout → 断连时兜底清理子进程。

此处抽出可复用的部分，两个路由各自只声明：
    - `is_target_ok(url)`：目标是否被允许（http/https 校验 / SSRF 黑名单）
    - `build_cmd(url)`    ：拼 ffmpeg 命令行
    - `ready_delay`       ：起进程后等多久再探活（转码比转封装慢，需要更长）
    - `tag`               ：日志前缀
"""

import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024


def ffmpeg_popen(cmd):
    """以「无控制台窗口 + 三段管道」的固定参数拉起 ffmpeg。"""
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


async def stream_flv(proc):
    """把 ffmpeg 的 stdout 分块 yield 给 StreamingResponse。

    必须用 run_in_executor 包 `read`：`proc.stdout.read` 是阻塞调用，
    直接在事件循环里调会卡死整个服务。
    客户端断连时（生成器被 GC 触发 finally）兜底 terminate → kill。
    """
    loop = asyncio.get_running_loop()
    try:
        while True:
            chunk = await loop.run_in_executor(None, proc.stdout.read, CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(None, proc.wait), timeout=3)
                except Exception:
                    proc.kill()
                    try:
                        await asyncio.wait_for(
                            loop.run_in_executor(None, proc.wait), timeout=2)
                    except Exception:
                        pass
            except Exception:
                pass