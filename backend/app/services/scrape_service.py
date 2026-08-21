"""抓取服务 - 包装 ScraperEngine 的调用"""
import sys
import os
import threading
import logging

from app.services.scraper_engine import ScraperEngine

logger = logging.getLogger(__name__)


class ScrapeService:
    """管理抓取状态和后台抓取任务"""

    def __init__(self, channel_service, log_callback=None, save_cache_callback=None):
        self.channel_service = channel_service
        self.log_callback = log_callback or (lambda msg: None)
        self.save_cache_callback = save_cache_callback
        self._state = {"running": False, "done": False, "error": None, "current": "", "index": 0, "total": 0}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def state(self):
        with self._lock:
            return dict(self._state)

    def _run_scrape_engine(self, url, start, end, suffix_list, proxy, mirror):
        """运行单个抓取任务"""
        logs = []

        def log_cb(msg):
            logs.append(msg.rstrip("\n"))
            self.log_callback(msg.rstrip("\n"))

        def inject_cb(chs):
            added, dup = self.channel_service.add_channels(chs, origin="scrape")
            log_cb(f"抓取完成，新增 {added} 个频道，去重 {dup} 个")

        def status_cb(msg, prog):
            if prog is not None:
                log_cb(f"{msg} ({prog}%)")
            else:
                log_cb(msg)

        engine = ScraperEngine(log_cb, inject_cb, self._stop_event, status_cb)
        engine.run(url, start, end, suffix_list, proxy, mirror)
        return "".join(l + "\n" for l in logs)

    def _scrape_worker(self, tasks, suffix_list, proxy, mirror):
        """后台抓取工作线程"""
        with self._lock:
            self._state = {
                "running": True, "done": False, "error": None,
                "current": tasks[0][0] if tasks else "", "index": 0, "total": len(tasks)
            }
        self._stop_event.clear()
        try:
            for i, (url, start, end) in enumerate(tasks):
                if self._stop_event.is_set():
                    self.log_callback("抓取已停止")
                    break
                with self._lock:
                    self._state["current"] = url
                    self._state["index"] = i
                self.log_callback(f"开始抓取: {url}")
                self._run_scrape_engine(url, start, end, suffix_list, proxy, mirror)
        except Exception as e:
            with self._lock:
                self._state["error"] = str(e)
            self.log_callback(f"抓取出错: {e}")
        finally:
            with self._lock:
                self._state["running"] = False
                self._state["done"] = True
            if self.save_cache_callback:
                try:
                    self.save_cache_callback()
                except Exception:
                    pass
            self.log_callback("抓取任务结束")

    def run_scrape(self, url, start, end, suffix_list, proxy, mirror):
        """启动单个抓取任务"""
        with self._lock:
            if self._state["running"]:
                return False, "已有抓取在进行中"
        tasks = [(url, start, end)]
        threading.Thread(
            target=self._scrape_worker,
            args=(tasks, suffix_list, proxy, mirror),
            daemon=True
        ).start()
        return True, None

    def run_scrape_batch(self, urls, suffix_list, proxy, mirror):
        """启动批量抓取任务"""
        with self._lock:
            if self._state["running"]:
                return False, "已有抓取在进行中"
        tasks = [(url, 1, 1) for url in urls]
        threading.Thread(
            target=self._scrape_worker,
            args=(tasks, suffix_list, proxy, mirror),
            daemon=True
        ).start()
        return True, None

    def get_status(self):
        return self.state

    def stop(self):
        with self._lock:
            if self._state["running"]:
                self._stop_event.set()
                self._state["status_msg"] = "已停止"
                self.log_callback("正在停止抓取...")