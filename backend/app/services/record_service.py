import os
import re
import threading
import subprocess
import datetime

_FFMPEG = os.environ.get("IPTV_FFMPEG", "ffmpeg")
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_NO_SNIFF = ("udp://", "rtp://")
_VIDEO_EXT = (".mp4", ".ts", ".mkv", ".flv", ".mov")


def _safe_name(name):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (name or "").strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:60] or "channel"


def _input_opts(url):
    """-user_agent is an HTTP protocol option; passing it for other inputs aborts ffmpeg."""
    low = (url or "").lower()
    if low.startswith("http://") or low.startswith("https://"):
        return ["-user_agent", _UA]
    return []


def _human(n):
    try:
        n = float(n)
    except Exception:
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%.0f %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


class RecordService:
    """DVR recording and HLS timeshift buffer, both driven by ffmpeg."""

    def __init__(self, data_dir=None, log_callback=None):
        self.data_dir = data_dir or "."
        self.dir = os.path.join(self.data_dir, "recordings")
        self.ts_root = os.path.join(self.data_dir, "timeshift")
        for d in (self.dir, self.ts_root):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
        self.log = log_callback or (lambda m: None)
        self._lock = threading.Lock()
        self._jobs = {}
        self._sessions = {}
        self._seq = 0
        self._sweep_timeshift()

    def _next_id(self, prefix):
        with self._lock:
            self._seq += 1
            return "%s%d_%d" % (prefix, self._seq, int(datetime.datetime.now().timestamp()))

    def _spawn(self, args):
        return subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
        )

    @staticmethod
    def _graceful_stop(proc, timeout=6):
        if proc is None:
            return
        try:
            if proc.poll() is not None:
                return
            if proc.stdin:
                proc.stdin.write(b"q")
                proc.stdin.flush()
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
            return
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _sweep_timeshift(self):
        try:
            for name in os.listdir(self.ts_root):
                p = os.path.join(self.ts_root, name)
                if os.path.isdir(p):
                    for f in os.listdir(p):
                        try:
                            os.remove(os.path.join(p, f))
                        except Exception:
                            pass
                    try:
                        os.rmdir(p)
                    except Exception:
                        pass
        except Exception:
            pass

    # ------------------------------------------------------------------ record

    def start_record(self, name, url, container="mp4", max_minutes=0):
        url = (url or "").strip()
        if not url:
            return {"ok": False, "error": "缺少频道地址"}
        if url.lower().startswith(_NO_SNIFF):
            return {"ok": False, "error": "该协议无法录制（仅 HTTP/HLS/RTSP/RTMP）"}
        ext = ".ts" if str(container).lower() == "ts" else ".mp4"
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = "%s_%s" % (_safe_name(name), stamp)
        out = os.path.join(self.dir, base + ext)
        args = [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
        args += _input_opts(url)
        args += ["-i", url, "-c", "copy", "-max_muxing_queue_size", "2048"]
        if ext == ".ts":
            args += ["-f", "mpegts"]
        else:
            args += ["-movflags", "+faststart"]
        try:
            minutes = int(max_minutes or 0)
        except Exception:
            minutes = 0
        if minutes > 0:
            args += ["-t", str(minutes * 60)]
        args.append(out)
        try:
            proc = self._spawn(args)
        except FileNotFoundError:
            return {"ok": False, "error": "未找到 ffmpeg，请安装并加入 PATH，或设置环境变量 IPTV_FFMPEG"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:160]}
        jid = self._next_id("rec")
        job = {
            "id": jid,
            "name": name or base,
            "url": url,
            "file": os.path.basename(out),
            "url_path": "/recordings/" + os.path.basename(out),
            "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "recording",
            "error": None,
        }
        with self._lock:
            self._jobs[jid] = job
            job["proc"] = proc
        threading.Thread(target=self._watch_record, args=(jid, proc, out), daemon=True).start()
        self.log("开始录制：%s" % job["name"])
        return {"ok": True, "id": jid, "file": job["file"], "url_path": job["url_path"]}

    def _watch_record(self, jid, proc, out):
        try:
            proc.wait()
            code = proc.returncode
        except Exception:
            code = -1
        size = os.path.getsize(out) if os.path.isfile(out) else 0
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return
            job.pop("proc", None)
            if size > 0:
                job["status"] = "done"
            else:
                job["status"] = "error"
                job["error"] = "录制失败（ffmpeg 退出码 %s，源可能不可用）" % code
        self.log("录制结束：%s（%s）" % (job.get("name"), _human(size)))

    def active_jobs(self):
        with self._lock:
            out = []
            for j in self._jobs.values():
                if j.get("status") == "recording":
                    out.append({k: v for k, v in j.items() if k != "proc"})
            return out

    def stop_record(self, jid=None):
        with self._lock:
            targets = [self._jobs[jid]] if jid and jid in self._jobs else [
                j for j in self._jobs.values() if j.get("status") == "recording"
            ]
        if not targets:
            return {"ok": False, "error": "没有正在进行的录制"}
        for j in targets:
            self._graceful_stop(j.get("proc"))
        return {"ok": True, "stopped": len(targets)}

    def list_records(self):
        items = []
        try:
            names = os.listdir(self.dir)
        except Exception:
            names = []
        for f in names:
            if not f.lower().endswith(_VIDEO_EXT):
                continue
            p = os.path.join(self.dir, f)
            if not os.path.isfile(p):
                continue
            try:
                st = os.stat(p)
            except Exception:
                continue
            items.append({
                "file": f,
                "url_path": "/recordings/" + f,
                "size": st.st_size,
                "size_text": _human(st.st_size),
                "mtime": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "ts": st.st_mtime,
            })
        items.sort(key=lambda x: x["ts"], reverse=True)
        for it in items:
            it.pop("ts", None)
        return items

    def delete_record(self, fname):
        fname = os.path.basename((fname or "").strip())
        if not fname:
            return {"ok": False, "error": "缺少文件名"}
        p = os.path.join(self.dir, fname)
        if not os.path.isfile(p):
            return {"ok": False, "error": "文件不存在"}
        try:
            os.remove(p)
        except Exception as e:
            return {"ok": False, "error": str(e)[:160]}
        return {"ok": True}

    # --------------------------------------------------------------- timeshift

    def start_timeshift(self, url, minutes=0, segment_seconds=4):
        url = (url or "").strip()
        if not url:
            return {"ok": False, "error": "缺少频道地址"}
        if url.lower().startswith(_NO_SNIFF):
            return {"ok": False, "error": "该协议无法时移（仅 HTTP/HLS/RTSP/RTMP）"}
        try:
            seg = max(2, int(segment_seconds or 4))
        except Exception:
            seg = 4
        sid = self._next_id("ts")
        d = os.path.join(self.ts_root, sid)
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            return {"ok": False, "error": str(e)[:160]}
        playlist = os.path.join(d, "index.m3u8")
        args = [_FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
        args += _input_opts(url)
        args += ["-i", url, "-c", "copy",
                 "-f", "hls", "-hls_time", str(seg), "-hls_list_size", "0",
                 "-hls_segment_type", "mpegts",
                 "-hls_segment_filename", os.path.join(d, "seg_%05d.ts")]
        try:
            mins = int(minutes or 0)
        except Exception:
            mins = 0
        if mins > 0:
            args += ["-t", str(mins * 60)]
        args.append(playlist)
        try:
            proc = self._spawn(args)
        except FileNotFoundError:
            return {"ok": False, "error": "未找到 ffmpeg，请安装并加入 PATH，或设置环境变量 IPTV_FFMPEG"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:160]}
        with self._lock:
            self._sessions[sid] = {"id": sid, "url": url, "dir": d, "proc": proc,
                                   "started": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        deadline = datetime.datetime.now().timestamp() + 12
        ready = False
        while datetime.datetime.now().timestamp() < deadline:
            if os.path.isfile(playlist):
                try:
                    segs = [x for x in os.listdir(d) if x.endswith(".ts") and os.path.getsize(os.path.join(d, x)) > 0]
                except Exception:
                    segs = []
                if len(segs) >= 2:
                    ready = True
                    break
            if proc.poll() is not None:
                break
            import time as _t
            _t.sleep(0.3)
        if proc.poll() is not None and not os.path.isfile(playlist):
            with self._lock:
                self._sessions.pop(sid, None)
            return {"ok": False, "error": "时移启动失败（源不可用或 ffmpeg 无法解析）"}
        self.log("时移已就绪：%s" % url[:80])
        return {"ok": True, "id": sid, "ready": ready,
                "url_path": "/timeshift/%s/index.m3u8" % sid}

    def list_timeshift(self):
        with self._lock:
            return [{"id": s["id"], "url": s["url"], "started": s["started"]}
                    for s in self._sessions.values()]

    def _purge_dir(self, d):
        try:
            for f in os.listdir(d):
                try:
                    os.remove(os.path.join(d, f))
                except Exception:
                    pass
            os.rmdir(d)
        except Exception:
            pass

    def stop_timeshift(self, sid=None):
        with self._lock:
            ids = [sid] if sid and sid in self._sessions else list(self._sessions.keys())
            sessions = [self._sessions.pop(i) for i in ids]
        for s in sessions:
            self._graceful_stop(s.get("proc"), timeout=3)
            self._purge_dir(s.get("dir"))
        return {"ok": True, "stopped": len(sessions)}

    def stop_all(self):
        self.stop_record()
        self.stop_timeshift()
