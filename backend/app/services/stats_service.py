import os
import json
import threading
from datetime import datetime, timedelta

from app.services.channel_service import _cue_rank, _ms_num

_LATENCY_BUCKETS = [
    ("<200ms", lambda ms: ms is not None and ms < 200),
    ("200-500ms", lambda ms: ms is not None and 200 <= ms < 500),
    ("500-1000ms", lambda ms: ms is not None and 500 <= ms < 1000),
    ("1-3s", lambda ms: ms is not None and 1000 <= ms < 3000),
    ("≥3s 或未知", lambda ms: ms is None or ms >= 3000),
]

_RANK_LABEL = {7: "4K", 6: "2K", 5: "1080P", 3: "720P", 2: "576P", 1: "480P", 0: "360P", -1: "未知"}


class StatsService:
    def __init__(self, data_dir=None, log_callback=None):
        self.data_dir = data_dir or os.getcwd()
        self.path = os.path.join(self.data_dir, "health_history.json")
        self.log = log_callback or (lambda m: None)
        self._lock = threading.RLock()

    def _snapshot_from_pool(self, channel_service):
        with getattr(channel_service, "lock", None) or _null():
            pool = [dict(c) for c in (getattr(channel_service, "pool", []) or [])]

        total = len(pool)
        online = sum(1 for c in pool if str(c.get("status")) == "在线")
        offline = sum(1 for c in pool if str(c.get("status")) == "离线")
        dead = sum(1 for c in pool if (c.get("health") or {}).get("dead"))
        ad = sum(1 for c in pool if c.get("ad_suspect"))
        fake = sum(1 for c in pool if c.get("is_fake_live"))

        lat = {name: 0 for name, _ in _LATENCY_BUCKETS}
        ms_vals = []
        res = {}
        for c in pool:
            ms = _ms_num(c.get("ms"))
            if ms is not None:
                ms_vals.append(ms)
            for name, fn in _LATENCY_BUCKETS:
                if fn(ms):
                    lat[name] += 1
                    break
            label = _RANK_LABEL.get(_cue_rank(c.get("res")), "未知")
            res[label] = res.get(label, 0) + 1

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "online": online,
            "offline": offline,
            "unchecked": total - online - offline,
            "dead": dead,
            "ad_suspect": ad,
            "fake_live": fake,
            "online_rate": round(online / total, 4) if total else None,
            "avg_ms": round(sum(ms_vals) / len(ms_vals), 1) if ms_vals else None,
            "latency": lat,
            "resolution": res,
        }

    @staticmethod
    def _top_failing(pool, limit=20):
        def bad_rank(c):
            h = c.get("health") or {}
            ms = _ms_num(c.get("ms"))
            return (
                1 if h.get("dead") else 0,
                1 if str(c.get("status")) == "离线" else 0,
                ms if ms is not None else 0,
            )
        bad = [c for c in pool
               if (c.get("health") or {}).get("dead") or str(c.get("status")) == "离线"
               or (_ms_num(c.get("ms")) or 0) >= 3000]
        bad.sort(key=bad_rank, reverse=True)
        return [{
            "id": c.get("id"),
            "name": c.get("name"),
            "group": c.get("group"),
            "url": c.get("url"),
            "status": c.get("status"),
            "ms": c.get("ms"),
            "dead": bool((c.get("health") or {}).get("dead")),
            "consecutive_fail": (c.get("health") or {}).get("consecutive_fail", 0),
            "last_error": ((c.get("health") or {}).get("last_error") or "")[:120],
        } for c in bad[:limit]]

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save(self, data):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception as e:
            self.log(f"健康快照保存失败：{e}")

    def snapshot(self, channel_service, force=False):
        snap = self._snapshot_from_pool(channel_service)
        with self._lock:
            history = self._load()
            if not force and history.get(snap["date"]):
                return {"recorded": False, "date": snap["date"], "reason": "当天已有快照"}
            history[snap["date"]] = snap
            self._save(history)
        return {"recorded": True, **snap}

    def report(self, channel_service, days=7):
        days = max(1, min(int(days or 7), 90))
        with self._lock:
            history = self._load()
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        trend = [v for k, v in sorted(history.items()) if k >= since]

        with getattr(channel_service, "lock", None) or _null():
            pool = [dict(c) for c in (getattr(channel_service, "pool", []) or [])]
        current = self._snapshot_from_pool(channel_service)
        return {
            "days": days,
            "trend": trend,
            "snapshot_count": len(history),
            "current": current,
            "top_failing": self._top_failing(pool),
            "latency_buckets": [n for n, _ in _LATENCY_BUCKETS],
            "recorded_dates": sorted(history.keys()),
        }


class _null:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
