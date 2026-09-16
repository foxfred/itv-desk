import os
import json
import time
import hashlib
import threading
import subprocess

_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_TIMEOUT = 20
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _key(url):
    return hashlib.md5((url or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


class ScreenshotService:
    def __init__(self, data_dir=None, log_callback=None):
        self.data_dir = data_dir or "."
        self.dir = os.path.join(self.data_dir, "screenshots")
        self.index_file = os.path.join(self.data_dir, "screenshots_index.json")
        try:
            os.makedirs(self.dir, exist_ok=True)
        except Exception:
            pass
        self.log = log_callback or (lambda m: None)
        self._lock = threading.Lock()
        self._running = set()
        self._state = {"running": False, "done": 0, "total": 0, "error": None}
        self.index = self._load_index()

    def _load_index(self):
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _save_index(self):
        try:
            tmp = self.index_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.index, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.index_file)
        except Exception:
            pass

    def list_index(self):
        with self._lock:
            out = {}
            for url, fname in list(self.index.items()):
                if os.path.isfile(os.path.join(self.dir, fname)):
                    out[url] = "/screenshots/" + fname
                else:
                    self.index.pop(url, None)
            return out

    def get_status(self):
        with self._lock:
            return dict(self._state)

    def path_for(self, url):
        return os.path.join(self.dir, _key(url) + ".jpg")

    def capture(self, url, timeout=None, width=320):
        url = (url or "").strip()
        if not url:
            return {"ok": False, "error": "无地址"}
        if url.lower().startswith(("udp://", "rtp://", "srt://")):
            return {"ok": False, "error": "该协议不支持截图（仅 HTTP/HLS/RTSP/RTMP）"}
        key = _key(url)
        with self._lock:
            if key in self._running:
                return {"ok": False, "error": "正在抓取中"}
            self._running.add(key)
        try:
            out = os.path.join(self.dir, key + ".jpg")
            tmp = os.path.join(self.dir, key + ".tmp.jpg")
            timeout = timeout or DEFAULT_TIMEOUT
            last_err = ""
            for prefix in (["-ss", "1"], []):
                for f in (tmp,):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                cmd = [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                       "-rw_timeout", str(int(timeout * 1_000_000)),
                       "-user_agent", _UA] + prefix + [
                       "-i", url, "-frames:v", "1",
                       "-vf", "scale=%d:-2" % width, "-q:v", "5", tmp]
                try:
                    p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                                       creationflags=_CREATE_NO_WINDOW)
                    if p.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 1024:
                        os.replace(tmp, out)
                        with self._lock:
                            self.index[url] = key + ".jpg"
                        self._save_index()
                        return {"ok": True, "path": "/screenshots/" + key + ".jpg"}
                    last_err = (p.stderr or b"").decode("utf-8", "ignore").strip()[:200] or "抓帧失败"
                except subprocess.TimeoutExpired:
                    last_err = "抓帧超时（源无响应或首帧过慢）"
                except FileNotFoundError:
                    return {"ok": False, "error": "未找到 ffmpeg：请安装并加入 PATH，或设置环境变量 IPTV_FFMPEG 指向 ffmpeg.exe"}
                except Exception as e:
                    last_err = str(e)[:160]
                finally:
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
            return {"ok": False, "error": last_err}
        finally:
            with self._lock:
                self._running.discard(key)

    def capture_batch(self, urls, timeout=None):
        urls = [u for u in (urls or []) if u]
        with self._lock:
            if self._state.get("running"):
                return {"error": "批量抓图中"}
            self._state = {"running": True, "done": 0, "total": len(urls), "error": None}

        def work():
            ok = 0
            try:
                for i, u in enumerate(urls, 1):
                    r = self.capture(u, timeout=timeout)
                    if r.get("ok"):
                        ok += 1
                    with self._lock:
                        self._state["done"] = i
                self.log("画面抓取完成：成功 %d / 共 %d" % (ok, len(urls)))
            except Exception as e:
                with self._lock:
                    self._state["error"] = str(e)[:160]
            finally:
                with self._lock:
                    self._state["running"] = False

        threading.Thread(target=work, daemon=True).start()
        return {"started": True, "total": len(urls)}

    def remove(self, url):
        with self._lock:
            fname = self.index.pop(url, None)
            if fname:
                try:
                    os.remove(os.path.join(self.dir, fname))
                except Exception:
                    pass
                self._save_index()
                return {"ok": True}
        return {"ok": False, "error": "无截图"}
