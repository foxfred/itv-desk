"""周期后台线程的启停原语。

`EpgService.start_refresh_scheduler` 与 `SubscriptionService.start_scheduler`
原先各自实现了一遍「先停旧的 → 清 stop 事件 → 起 daemon 线程 → 打日志」，
唯一差异只有 loop 函数与提示文案。此处收敛为唯一定义。

约定：调用方（owner）需具备以下属性 ——
    `_stop`          threading.Event，置位即通知循环退出
    `_thread`        threading.Thread 或 None
    `log_callback`   callable(str)，写前端日志
"""

import threading


def start_periodic(owner, interval_seconds, loop, label):
    """启动（或重启）周期任务；`interval_seconds <= 0` 时仅停止不启动。

    注意顺序：必须先 `stop_periodic`（置位旧事件）再 `_stop.clear()`，
    否则新线程会立刻看到上一轮遗留的置位状态而直接退出。
    """
    stop_periodic(owner)
    if interval_seconds and interval_seconds > 0:
        owner._stop.clear()
        owner._thread = threading.Thread(
            target=loop, args=(interval_seconds,), daemon=True)
        owner._thread.start()
        owner.log_callback(f"{label}已开启，间隔 {interval_seconds}s")


def stop_periodic(owner):
    """通知循环退出并解除线程引用（线程为 daemon，不阻塞进程退出）。"""
    owner._stop.set()
    owner._thread = None