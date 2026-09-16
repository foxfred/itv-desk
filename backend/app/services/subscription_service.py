import os
import re
import json
import threading
from datetime import datetime

AUTO_DISABLE_FAILS = 3


def _extract_tvg_urls(text):
    if not text:
        return []
    head = text[:8192]
    urls = []
    for m in re.finditer(r'(?:url-tvg|x-tvg-url|tvg-url)\s*=\s*"([^"]+)"', head, re.I):
        for u in m.group(1).split(','):
            u = u.strip()
            if u.startswith('http') and u not in urls:
                urls.append(u)
    return urls


class SubscriptionService:
    def __init__(self, channel_service, log_callback=None, data_dir=None, save_cache_callback=None):
        self.channel_service = channel_service
        self.log_callback = log_callback or (lambda m: None)
        self.save_cache_callback = save_cache_callback
        self.data_dir = data_dir or "."
        self.file = os.path.join(self.data_dir, "subscriptions.json")
        self.auto_epg_file = os.path.join(self.data_dir, "epg_auto_sources.json")
        self._lock = threading.RLock()
        self.subs = self._load()
        self._stop = threading.Event()
        self._thread = None

    def _load(self):
        try:
            with open(self.file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _save(self):
        try:
            tmp = self.file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.subs, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.file)
        except Exception:
            pass

    def list(self):
        with self._lock:
            return [dict(s) for s in self.subs]

    def add(self, url, name="", suffix_list="m3u,m3u8,txt", proxy="", mirror="不使用加速", enabled=True):
        url = (url or "").strip()
        if not url:
            return {"error": "订阅地址不能为空"}
        from app.services.repair_service import _classify_url
        if _classify_url(url) != "parent":
            return {"error": "该地址是频道直链，不是母链。订阅源只接受母链（目录/播放列表），频道请用频道管理添加"}
        with self._lock:
            if any(s["url"] == url for s in self.subs):
                return {"error": "订阅源已存在"}
            self.subs.append({
                "url": url,
                "name": name.strip() or url,
                "suffix_list": suffix_list,
                "proxy": proxy,
                "mirror": mirror,
                "enabled": bool(enabled),
                "last_update": None,
                "last_count": 0,
                "last_error": None,
                "fail_count": 0,
            })
            self._save()
        self.log_callback(f"已添加订阅源: {url}")
        return {"ok": True}

    def remove(self, url):
        with self._lock:
            before = len(self.subs)
            self.subs = [s for s in self.subs if s["url"] != url]
            if len(self.subs) == before:
                return {"error": "未找到订阅源"}
            self._save()
        return {"ok": True}

    def set_enabled(self, url, enabled):
        with self._lock:
            for s in self.subs:
                if s["url"] == url:
                    s["enabled"] = bool(enabled)
                    self._save()
                    return {"ok": True}
        return {"error": "未找到订阅源"}

    def update_one(self, url):
        with self._lock:
            sub = next((s for s in self.subs if s["url"] == url), None)
        if not sub:
            return {"error": "未找到订阅源"}
        return self._pull(sub)

    def update_all(self):
        with self._lock:
            targets = [s for s in self.subs if s.get("enabled", True)]
        results = []
        for sub in targets:
            r = self._pull(sub)
            r["url"] = sub["url"]
            r["name"] = sub.get("name", sub["url"])
            results.append(r)
        total_added = sum(r.get("added", 0) for r in results)
        if self.save_cache_callback:
            try:
                self.save_cache_callback()
            except Exception:
                pass
        return {"added": total_added, "results": results}

    def _pull(self, sub):
        from app.services.scraper_engine import ScraperEngine
        url = sub["url"]
        try:
            collected = []
            import threading as _th
            stop_evt = _th.Event()

            def log_cb(msg):
                self.log_callback(msg.rstrip("\n"))

            def inject_cb(chs):
                if chs:
                    collected.extend(chs)

            def status_cb(_msg, _prog=None):
                pass

            engine = ScraperEngine(log_cb, inject_cb, stop_evt, status_cb)
            engine.run(url, 1, 1, sub.get("suffix_list") or "m3u,m3u8,txt",
                       sub.get("proxy") or None, sub.get("mirror") or None)

            added, dup = self.channel_service.add_channels(collected, origin="subscription")
            sub["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sub["last_count"] = added
            sub["last_error"] = None
            sub["fail_count"] = 0
            self._save()
            self.log_callback(f"订阅更新 [{sub.get('name', url)}]: 新增 {added}, 去重 {dup}")
            self._auto_register_epg(sub)
            return {"added": added, "dup": dup}
        except Exception as e:
            sub["last_error"] = str(e)
            fails = int(sub.get("fail_count") or 0) + 1
            sub["fail_count"] = fails
            auto_disabled = False
            if sub.get("enabled", True) and fails >= AUTO_DISABLE_FAILS:
                sub["enabled"] = False
                auto_disabled = True
            self._save()
            self.log_callback(f"订阅更新异常 [{sub.get('name', url)}]: {e}（连续失败 {fails} 次）")
            if auto_disabled:
                self.log_callback(f"订阅已自动停用 [{sub.get('name', url)}]：连续 {fails} 次失败，修复地址后手动重新启用")
            return {"added": 0, "error": str(e), "fail_count": fails, "auto_disabled": auto_disabled}

    def _auto_register_epg(self, sub):
        url = sub.get("url", "")
        if not re.search(r'\.(m3u8?|txt)(\?|$)', url, re.I):
            return
        try:
            from app.utils.network import download_url
            text = download_url(url, proxy=sub.get("proxy") or None, timeout=12, max_retries=1)
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="ignore")
            found = _extract_tvg_urls(text or "")
        except Exception:
            return
        if not found:
            return
        try:
            known = self.auto_epg_sources()
            merged = list(known)
            for u in found:
                if u not in merged:
                    merged.append(u)
            if merged != known:
                tmp = self.auto_epg_file + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(merged, f, ensure_ascii=False, indent=2)
                os.replace(tmp, self.auto_epg_file)
                self.log_callback(f"发现订阅源自带 EPG 源 {len(found)} 个，已登记到 EPG 自动源列表")
        except Exception:
            pass

    def auto_epg_sources(self):
        try:
            if os.path.exists(self.auto_epg_file):
                with open(self.auto_epg_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [u for u in data if isinstance(u, str) and u.startswith("http")]
        except Exception:
            pass
        return []

    def start_scheduler(self, interval_seconds):
        self.stop_scheduler()
        if interval_seconds and interval_seconds > 0:
            self._stop.clear()
            self._thread = threading.Thread(target=self._scheduler_loop, args=(interval_seconds,), daemon=True)
            self._thread.start()
            self.log_callback(f"订阅定时更新已开启，间隔 {interval_seconds}s")

    def _scheduler_loop(self, interval_seconds):
        while not self._stop.is_set():
            if self._stop.wait(interval_seconds):
                break
            try:
                self.update_all()
            except Exception as e:
                self.log_callback(f"定时订阅更新出错: {e}")

    def stop_scheduler(self):
        self._stop.set()
        self._thread = None
