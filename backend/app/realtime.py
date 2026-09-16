import asyncio
import threading
import time

_LOG_HISTORY = 500
_log_buffer = []
_log_buffer_lock = threading.Lock()

_log_subscribers = set()
_event_subscribers = set()
_subs_lock = threading.Lock()


def publish_log(line):
    with _log_buffer_lock:
        _log_buffer.append(line)
        if len(_log_buffer) > _LOG_HISTORY:
            del _log_buffer[: len(_log_buffer) - _LOG_HISTORY]
    _fanout(_log_subscribers, {"t": round(time.time(), 3), "msg": line})


def publish_event(name, data):
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
