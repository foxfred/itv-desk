"""检查服务 - 包装 CheckerEngine 的调用"""
import sys
import os
import threading
import logging

from app.services.checker_engine import CheckerEngine

logger = logging.getLogger(__name__)


class CheckService:
    """管理检查状态和后台检查任务"""

    def __init__(self, channel_service, log_callback=None, save_cache_callback=None):
        self.channel_service = channel_service
        self.log_callback = log_callback or (lambda msg: None)
        self.save_cache_callback = save_cache_callback
        self._state = {"running": False, "processed": 0, "total": 0, "status": "空闲"}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def state(self):
        with self._lock:
            return dict(self._state)

    def start_check(self, items, threads, timeout, retries, resume=False):
        """启动后台检查任务。

        resume=True 时使用「断点续检」模式：仅对仍处于「未检查」状态的频道
        发起检测，已检测（在线/离线/未知）的频道会被跳过，避免崩溃/中断后
        重跑全部。配合每 50 个频道与结束时的缓存落盘，可实现安全续检。
        """
        if resume:
            items = [ch for ch in items if ch.get("status", "未检查") == "未检查"]
        with self._lock:
            if self._state["running"]:
                return False
            self._state = {"running": True, "processed": 0, "total": len(items), "status": "检查中..."}
        self._stop_event.clear()
        last_save = {"n": 0}

        def work():
            try:
                def progress_cb(p, t):
                    self._state.update(processed=p, total=t)
                    # 周期性自动保存（每 50 个频道保存一次），防止中途崩溃丢失检查结果
                    if self.save_cache_callback and p - last_save["n"] >= 50:
                        last_save["n"] = p
                        try:
                            self.save_cache_callback()
                        except Exception:
                            pass

                engine = CheckerEngine(
                    manager=self.channel_service,
                    ui_callback=lambda *a: None,
                    progress_callback=progress_cb,
                    status_callback=lambda m: self._state.update(status=m),
                    stop_event=self._stop_event,
                )
                engine.run(items, thread_num=threads, timeout=timeout, retries=retries)
            except Exception as e:
                self.log_callback(f"检查出错: {e}")
            finally:
                self._state["running"] = False
                self._state["status"] = "检查完成"
                if self.save_cache_callback:
                    try:
                        self.save_cache_callback()
                    except Exception:
                        pass
                self.log_callback("检查完成")

        threading.Thread(target=work, daemon=True).start()
        return True

    def stop(self):
        if self._state["running"]:
            self._stop_event.set()
            self._state["status"] = "已停止"
            self.log_callback("检查已停止")

    def get_status(self):
        return self.state