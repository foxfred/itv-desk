"""订阅源服务 - 把抓取 URL 存为订阅源，支持手动 / 定时增量更新。

设计：
- 订阅源清单持久化到 subscriptions.json（DATA_DIR，与 channels_cache.json 同级）；
- 更新时复用既有解析链路（download_url → Parser → ChannelService.add_channels），
  而 add_channels 自带 URL 去重，天然实现「增量合并」：新增源进池，已存在源跳过；
- 可选后台定时拉取（start_scheduler），间隔 <=0 表示关闭，避免无谓网络消耗。
"""
import os
import json
import threading
from datetime import datetime


class SubscriptionService:
    def __init__(self, channel_service, log_callback=None, data_dir=None, save_cache_callback=None):
        self.channel_service = channel_service
        self.log_callback = log_callback or (lambda m: None)
        self.save_cache_callback = save_cache_callback
        self.data_dir = data_dir or "."
        self.file = os.path.join(self.data_dir, "subscriptions.json")
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
        """增量拉取单个订阅源并合并进频道池（add_channels 自带去重）"""
        from app.utils.network import download_url
        from app.utils.m3u_parser import Parser, extract_channels
        url = sub["url"]
        try:
            content, err = download_url(url, sub.get("proxy") or None)
            if err:
                sub["last_error"] = err
                self._save()
                self.log_callback(f"订阅更新失败 [{sub.get('name', url)}]: {err}")
                return {"added": 0, "error": err}
            parsed = Parser.parse_local_file(content) or extract_channels(content)
            added, dup = self.channel_service.add_channels(parsed, origin="subscription")
            sub["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sub["last_count"] = added
            sub["last_error"] = None
            self._save()
            self.log_callback(f"订阅更新 [{sub.get('name', url)}]: 新增 {added}, 去重 {dup}")
            return {"added": added, "dup": dup}
        except Exception as e:
            sub["last_error"] = str(e)
            self._save()
            self.log_callback(f"订阅更新异常 [{sub.get('name', url)}]: {e}")
            return {"added": 0, "error": str(e)}

    def start_scheduler(self, interval_seconds):
        """启动定时增量更新（interval_seconds<=0 表示关闭）"""
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
