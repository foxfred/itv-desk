"""轻量级实时事件总线：为「日志」与「运行状态」提供线程安全发布 / asyncio 订阅（SSE 用）。

设计要点：
- 发布端（log()、后台快照任务）可能运行在任意线程（service 后台线程）；订阅端为 asyncio 协程。
- 通过 loop.call_soon_threadsafe 把同步发布桥接到事件循环，保证跨线程安全。
- 日志保留最近 N 条缓冲，供迟到连接的订阅者补帧；事件为瞬时快照，不保留历史。
- 本模块零第三方依赖，仅依赖标准库，可被 service / route 安全导入。
"""
import asyncio
import threading
import time

_LOG_HISTORY = 500  # 保留最近 N 条日志，供新订阅者回放
_log_buffer = []
_log_buffer_lock = threading.Lock()

# 每个订阅者一个绑定到事件循环的 asyncio.Queue
_log_subscribers = set()
_event_subscribers = set()
_subs_lock = threading.Lock()


def publish_log(line):
    """同步调用（任意线程）：追加日志并推送给所有日志订阅者。"""
    with _log_buffer_lock:
        _log_buffer.append(line)
        if len(_log_buffer) > _LOG_HISTORY:
            del _log_buffer[: len(_log_buffer) - _LOG_HISTORY]
    _fanout(_log_subscribers, {"t": round(time.time(), 3), "msg": line})


def publish_event(name, data):
    """同步调用（任意线程）：发布一次命名事件（stats / check / scrape 等快照）。"""
    _fanout(_event_subscribers, {"name": name, "data": data, "t": round(time.time(), 3)})


def _fanout(subscriber_set, item):
    with _subs_lock:
        dead = []
        for q in list(subscriber_set):
            try:
                loop = getattr(q, "_loop", None) or asyncio.get_event_loop()
                loop.call_soon_threadsafe(q.put_nowait, item)
            except Exception:
                dead.append(q)
        for q in dead:
            subscriber_set.discard(q)


async def subscribe_logs():
    """异步生成器：先回放缓冲，再持续 yield 新日志（供 SSE 端点消费）。"""
    q = asyncio.Queue()
    with _subs_lock:
        _log_subscribers.add(q)
    with _log_buffer_lock:
        backlog = list(_log_buffer)
    for line in backlog:
        yield {"t": round(time.time(), 3), "msg": line}
    try:
        while True:
            item = await q.get()
            yield item
    finally:
        with _subs_lock:
            _log_subscribers.discard(q)


async def subscribe_events():
    """异步生成器：持续 yield 事件（供 SSE 端点消费）。"""
    q = asyncio.Queue()
    with _subs_lock:
        _event_subscribers.add(q)
    try:
        while True:
            item = await q.get()
            yield item
    finally:
        with _subs_lock:
            _event_subscribers.discard(q)
