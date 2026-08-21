# -*- coding: utf-8 -*-
"""内嵌 mpv 解码引擎管理器（Phase 5 / Track A · mpv 嵌入）

设计要点（来自 spike 验证）：
- 子进程 + 命名管道（--input-ipc-server）+ ctypes 控制（零 pywin32 依赖）。
- mpv 0.41 关键坑：必须用 --osc=no（--onscreen-controls= 旧别名已废弃，会导致选项解析失败退出）。
- SetWindowPos 定位时只设位置（SWP_NOSIZE），让 mpv 内部按视频比例调整 size。
- 后台读线程解析事件流（file-loaded/end-file/property-change/...）+ command 响应（按 request_id 路由）。
- mpv 进程退出 / 管道断开 / 命令 error → 触发 on_error 回调，前端可回退 WebView 引擎。

用法（run.py 集成）：
    eng = MpvEngine()
    eng.start(on_error=lambda e: ...)
    eng.load("http://example.com/playlist.m3u8")
    eng.set_volume(60)
    eng.set_rect(200, 150)   # 屏幕坐标
    eng.quit()
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import ctypes
import ctypes.wintypes as wt


# ======================================================================
# 路径解析（dev / frozen 双路）
# ======================================================================
IS_FROZEN = getattr(sys, "frozen", False)


def _repo_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def resolve_mpv_exe() -> str:
    """解析 mpv.exe 路径。多路探测（PyInstaller onedir 实际落点因版本而异）：
    1) frozen + sys._MEIPASS/mpv/mpv.exe（标准 _MEIPASS）
    2) frozen + EXE_DIR/_internal/mpv/mpv.exe（onedir 最稳定路径，PyInstaller 6 默认）
    3) frozen + EXE_DIR/mpv/mpv.exe（备选）
    4) dev: REPO_ROOT/vendor/mpv/mpv.exe
    返回值存在性需调用方 os.path.isfile 校验。"""
    candidates = []
    if IS_FROZEN:
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if meipass:
            candidates.append(os.path.join(meipass, "mpv", "mpv.exe"))
        candidates.append(os.path.join(exe_dir, "_internal", "mpv", "mpv.exe"))
        candidates.append(os.path.join(exe_dir, "mpv", "mpv.exe"))
    candidates.append(os.path.join(_repo_root(), "vendor", "mpv", "mpv.exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return candidates[0]


# ======================================================================
# ctypes 绑定（stdlib，无 pywin32 依赖）
# ======================================================================
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value

kernel32.CreateFileW.restype = wt.HANDLE
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                                 wt.DWORD, wt.DWORD, wt.HANDLE]
kernel32.WriteFile.restype = wt.BOOL
kernel32.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                               ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
kernel32.ReadFile.restype = wt.BOOL
kernel32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                              ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
kernel32.PeekNamedPipe.restype = wt.BOOL
kernel32.PeekNamedPipe.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                                   ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.DWORD),
                                   ctypes.POINTER(wt.DWORD)]
kernel32.CloseHandle.argtypes = [wt.HANDLE]

user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.IsWindowVisible.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.EnumWindows.restype = wt.BOOL
user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.SetWindowPos.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetParent.restype = wt.HWND
user32.SetParent.argtypes = [wt.HWND, wt.HWND]
user32.ShowWindow.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
SW_SHOW = 5
SW_HIDE = 0
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
HWND_TOPMOST = wt.HWND(-1)


def _pipe_connect(name: str, timeout: float = 5.0):
    """CreateFileW 轮询等待管道就绪。成功返回 HANDLE，失败 None。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        h = kernel32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None,
                                 OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
        if h and h != INVALID_HANDLE_VALUE:
            return h
        time.sleep(0.1)
    return None


def _pipe_avail(h) -> int:
    avail = wt.DWORD(0)
    total = wt.DWORD(0)
    left = wt.DWORD(0)
    kernel32.PeekNamedPipe(h, None, 0, None, ctypes.byref(avail), ctypes.byref(total))
    return int(avail.value)


def _pipe_write(h, data: bytes) -> bool:
    n = wt.DWORD(0)
    ok = kernel32.WriteFile(h, data, len(data), ctypes.byref(n), None)
    return bool(ok) and n.value == len(data)


def _pipe_read_line(h, timeout: float = 0.5):
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _pipe_avail(h) > 0:
            chunk = ctypes.create_string_buffer(4096)
            n = wt.DWORD(0)
            kernel32.ReadFile(h, chunk, min(_pipe_avail(h), 4095),
                              ctypes.byref(n), None)
            if n.value > 0:
                buf += chunk.raw[:n.value]
                if b"\n" in buf:
                    line, _ = buf.split(b"\n", 1)
                    return line.decode("utf-8", "replace").strip()
        else:
            time.sleep(0.02)
    return buf.decode("utf-8", "replace").strip() if buf else None


# ======================================================================
# 引擎
# ======================================================================
class MpvEngine:
    """单实例 mpv 引擎。通过命名管道与 mpv 子进程通信。"""

    # 关键启动参数（spike 验证）：
    #  - --osc=no（0.41 已移除 --onscreen-controls 旧别名）
    #  - --no-config（避免用户 mpv.conf 污染）
    #  - --no-input-default-bindings + --no-input-cursor（键位交 Vue）
    #  - --idle=yes（先起再 loadfile）
    #  - IPTV 直播流：适度缓存（5s）+ 低延迟配置集，避免无缓存导致首帧超时
    LAUNCH_ARGS = [
        # Phase 2：独立窗口模式（mpv 自有顶层窗口，不嵌入 WebView）。
        # 不传 --border=no → mpv 保留系统窗口边框（可拖动/缩放/最小化/关闭），
        # --osc=no 禁用 mpv 自带 OSD 控制条（统一由 Vue 控制条经 IPC 调度）。
        "--force-window=yes", "--no-terminal", "--idle=yes",
        "--osc=no",
        "--no-config", "--no-input-default-bindings", "--no-input-cursor",
        "--vo=gpu",
        "--profile=low-latency",
        "--cache=yes", "--cache-secs=5",
    ]
    PIPE_PREFIX = r"\\.\pipe\mpv-iptvcore"

    def __init__(self):
        # 每个实例唯一管道名，避免旧 mpv 进程残留导致新建同名管道冲突
        self._pipe_name = f"{self.PIPE_PREFIX}-{os.getpid()}-{id(self)}"
        self._proc = None
        self._pipe = None
        self._reader = None
        self._state = {"pause": True, "position": 0.0, "duration": 0.0,
                       "volume": 100, "speed": 1.0,
                       "video_w": 0, "video_h": 0, "path": "",
                       # P5: 媒体信息（6.3）+ 轨道能力
                       "fps": 0.0, "audio": {}, "tracks": []}
        self._on_error = None
        self._on_state = None
        self._pending = {}  # rid -> queue.Queue
        self._rid_lock = threading.Lock()
        self._pend_lock = threading.Lock()
        self._rid_counter = 0
        self._hwnd = None
        self._stop = False
        self._alive = False

    # ---- 生命周期 ----
    def start(self, proxy: str = None, on_error=None, on_state=None,
              pipe_name: str = None, ipc_timeout: float = 5.0) -> bool:
        """启动 mpv 子进程 + 管道 + 读线程。

        Phase 2：独立窗口模式（不再传 --wid）——mpv 自有顶层窗口，
        由 PlayerApi.mpv_set_rect 定位覆盖播放窗视频区（--wid 嵌入已废弃：
        WebView2 DirectComposition 无法可靠合成 HWND 子窗，见计划书 §0）。
        """
        if self._alive:
            return True
        exe = resolve_mpv_exe()
        if not os.path.isfile(exe):
            if on_error:
                on_error("mpv.exe not found: " + exe)
            return False
        self._on_error = on_error
        self._on_state = on_state
        # 优先使用外部传入的 pipe_name；未传则使用实例唯一管道名，防止多实例/残留冲突
        effective_pipe = pipe_name or self._pipe_name
        env = os.environ.copy()
        if proxy:
            env["http_proxy"] = proxy
            env["https_proxy"] = proxy
        args = [exe, "--input-ipc-server=" + effective_pipe]
        # 诊断日志：每次启动覆盖，便于排查首帧/解码问题
        log_path = os.path.join(_repo_root(), "mpv-last.log")
        args.append("--log-file=" + log_path)
        # 独立窗口模式：--force-window=yes 确保无视频轨也建窗（LAUNCH_ARGS 已含 --border=no --osc=no）
        args.append("--force-window=yes")
        args += [a for a in self.LAUNCH_ARGS if not a.startswith("--force-window")]
        try:
            self._proc = subprocess.Popen(
                args, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            if on_error:
                on_error("mpv Popen 失败: " + repr(e))
            return False
        self._pipe = _pipe_connect(effective_pipe, timeout=ipc_timeout)
        if not self._pipe:
            self._proc.kill()
            self._proc = None
            if on_error:
                on_error("mpv IPC 管道连接失败: " + effective_pipe)
            return False
        self._stop = False
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()
        self._alive = True
        # observe 关键 property（异步，无需等响应）
        self.send("observe_property", 100, "pause")
        self.send("observe_property", 101, "time-pos")
        self.send("observe_property", 102, "duration")
        self.send("observe_property", 103, "volume")
        self.send("observe_property", 104, "speed")
        self.send("observe_property", 105, "path")
        self.send("observe_property", 106, "video-params")
        # P5: 媒体信息 + 轨道（6.3 / 音轨字幕清晰度）
        self.send("observe_property", 107, "audio-params")
        self.send("observe_property", 108, "track-list")
        self.send("observe_property", 109, "fps")
        return True

    def quit(self):
        """主动退出：发 quit 命令 → 等进程结束 → 杀残留 → 关管道。"""
        self._stop = True
        self._alive = False
        if self._pipe:
            try:
                self._write_raw(json.dumps({"command": ["quit"]}) + "\n")
            except Exception:
                pass
        if self._proc:
            try:
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._pipe:
            try:
                kernel32.CloseHandle(self._pipe)
            except Exception:
                pass
            self._pipe = None
        with self._pend_lock:
            self._pending.clear()

    def is_alive(self) -> bool:
        if not self._proc:
            return False
        if self._proc.poll() is not None:
            self._alive = False
            return False
        return self._alive

    # ---- IPC ----
    def _next_rid(self) -> int:
        with self._rid_lock:
            self._rid_counter += 1
            return self._rid_counter

    def _write_raw(self, s: str) -> bool:
        if not self._pipe:
            return False
        return _pipe_write(self._pipe, s.encode("utf-8"))

    def send(self, cmd: str, *args, wait: bool = False, timeout: float = 5.0):
        """发命令。wait=True 同步等响应（返回 dict 或 None）。"""
        if not self._pipe:
            return None
        rid = self._next_rid()
        payload = json.dumps({"command": [cmd] + list(args), "request_id": rid},
                             ensure_ascii=False) + "\n"
        if not self._write_raw(payload):
            return None
        if not wait:
            return rid
        with self._pend_lock:
            q = self._pending.get(rid) or queue.Queue()
            self._pending[rid] = q
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            with self._pend_lock:
                self._pending.pop(rid, None)
            return None

    def _reader_loop(self):
        """后台读线程：解析 JSON 行，分发到响应队列或事件处理。"""
        while not self._stop and self._proc and self._proc.poll() is None:
            line = _pipe_read_line(self._pipe, timeout=0.3)
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            # 1) command 响应（带 request_id）
            if "request_id" in obj:
                rid = obj.get("request_id")
                with self._pend_lock:
                    q = self._pending.pop(rid, None)
                if q:
                    try:
                        q.put_nowait(obj)
                    except Exception:
                        pass
                # 响应里也可能带 error，主动通知
                if obj.get("error") and obj["error"] != "success" and self._on_error:
                    try:
                        self._on_error("mpv command error: " + repr(obj))
                    except Exception:
                        pass
                continue
            # 2) 事件
            evt = obj.get("event")
            if not evt:
                continue
            self._handle_event(evt, obj)

        # 读线程退出：进程已死
        self._alive = False
        if self._on_error and not self._stop:
            try:
                self._on_error("mpv 进程退出或管道断开")
            except Exception:
                pass

    def _handle_event(self, evt: str, obj: dict):
        changed = False
        if evt == "property-change":
            name = obj.get("name")
            data = obj.get("data")
            if name == "pause":
                self._state["pause"] = bool(data) if data is not None else True
                changed = True
            elif name == "time-pos":
                self._state["position"] = float(data) if data is not None else 0.0
                changed = True
            elif name == "duration":
                self._state["duration"] = float(data) if data is not None else 0.0
                changed = True
            elif name == "volume":
                self._state["volume"] = int(data) if data is not None else 100
                changed = True
            elif name == "speed":
                self._state["speed"] = float(data) if data is not None else 1.0
                changed = True
            elif name == "path":
                self._state["path"] = str(data) if data else ""
                changed = True
            elif name == "video-params":
                vp = data or {}
                self._state["video_w"] = int(vp.get("w") or 0)
                self._state["video_h"] = int(vp.get("h") or 0)
                # P5: fps 主来源（容器提供，未知为 0）
                self._state["fps"] = float(vp.get("fps") or 0)
                changed = True
            elif name == "audio-params":
                ap = data or {}
                self._state["audio"] = {
                    "channels": ap.get("channels"),
                    "samplerate": ap.get("samplerate"),
                    "codec": ap.get("codec"),
                }
                changed = True
            elif name == "track-list":
                self._state["tracks"] = list(data or [])
                changed = True
            elif name == "fps":
                # 回退来源：video-params.fps 为 0 时用估算值
                if not self._state.get("fps"):
                    self._state["fps"] = float(data or 0)
                    changed = True
        elif evt == "file-loaded":
            self._state["path"] = obj.get("path", "")
            changed = True
        elif evt == "end-file":
            reason = (obj.get("reason") or "unknown")
            if reason not in ("eof", "stop", "replay", "redirect", "next-file"):
                if self._on_error:
                    try:
                        self._on_error("mpv end-file: " + reason)
                    except Exception:
                        pass
            changed = True
        if changed and self._on_state:
            try:
                self._on_state(dict(self._state))
            except Exception:
                pass

    # ---- 业务 API（被 run.py 桥接到前端）----
    def load(self, url: str, mode: str = "replace", wait: bool = True,
             timeout: float = 30.0) -> dict:
        return self.send("loadfile", url, mode, wait=wait, timeout=timeout)

    def play(self) -> dict:
        return self.send("set_property", "pause", False, wait=True, timeout=3)

    def pause(self) -> dict:
        return self.send("set_property", "pause", True, wait=True, timeout=3)

    def toggle_pause(self) -> dict:
        return self.send("cycle", "pause", wait=True, timeout=3)

    def set_volume(self, v: int):
        return self.send("set_property", "volume", max(0, min(130, int(v))),
                         wait=False)

    def seek(self, sec: float, mode: str = "relative"):
        return self.send("seek", float(sec), mode, wait=False)

    def set_speed(self, speed: float):
        return self.send("set_property", "speed", float(speed), wait=False)

    # ---- P5: 轨道能力（音轨/字幕/清晰度）----
    def get_tracks(self) -> list:
        """返回 track-list（[{id,type,title,lang,selected,...}]）。"""
        return list(self._state.get("tracks") or [])

    def set_track(self, kind: str, tid: int):
        """切换指定轨道（kind: audio/sub/video → {kind}-track-id）。"""
        return self.send("set_property", f"{kind}-track-id", int(tid), wait=False)

    def cycle_track(self, kind: str):
        """mpv 原生 cycle 循环切换轨道（audio/sub/video）。"""
        return self.send("cycle", kind, wait=False)

    def set_quality(self, vid: int):
        """清晰度 = video 轨切换（mpv 0.41 HLS 走 ffmpeg demuxer，hls-bitrate 只读）。"""
        return self.set_track("video", vid)

    def sub_add(self, path: str):
        """外挂字幕（B7）：探测编码 → gbk 时设 sub-codepage → sub-add select。"""
        try:
            enc = self._probe_sub_encoding(path)
            if enc == "gbk":
                self.send("set_property", "sub-codepage", "gbk", wait=False)
            return self.send("sub-add", path.replace("\\", "/"), "select", wait=True, timeout=5)
        except Exception as e:
            return {"error": repr(e)}

    @staticmethod
    def _probe_sub_encoding(path: str) -> str:
        """读文件头探测字幕编码：BOM→utf-8/utf-16；utf-8 解码失败→gbk（中文 srt 常见）。"""
        try:
            with open(path, "rb") as f:
                head = f.read(8192)
        except Exception:
            return "utf-8"
        if not head:
            return "utf-8"
        if head[:3] == b"\xef\xbb\xbf":
            return "utf-8"
        if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return "utf-16"
        try:
            head.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "gbk"

    def state(self) -> dict:
        return dict(self._state)

    # ---- 窗口定位 / 父子关系 ----
    def find_hwnd(self, timeout: float = 3.0):
        """按 PID 找 mpv 窗口 hwnd（spike 验证可见窗口 hwnd 唯一）。"""
        if self._hwnd and user32.IsWindowVisible(self._hwnd):
            return self._hwnd
        if not self._proc:
            return None
        pid = self._proc.pid
        found = []

        def cb(hwnd, lparam):
            proc = wt.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc))
            if proc.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
                return False
            return True

        deadline = time.time() + timeout
        while time.time() < deadline and not found:
            user32.EnumWindows(WNDENUMPROC(cb), 0)
            if not found:
                time.sleep(0.2)
        if found:
            self._hwnd = found[0]
        return self._hwnd

    def set_rect(self, x: int, y: int, w: int = None, h: int = None) -> bool:
        """定位 mpv 窗口到屏幕坐标并置顶（TOP 保证盖在 WebView 播放器窗之上）。
        w/h=None 时只动位置（spike 验证 mpv 按视频比例自调 size）。"""
        hwnd = self.find_hwnd()
        if not hwnd:
            return False
        if w is None or h is None:
            flags = SWP_NOSIZE | SWP_NOZORDER
            cx, cy = 0, 0
        else:
            flags = SWP_NOZORDER
            cx, cy = int(w), int(h)
        # hWndInsertAfter=HWND_TOPMOST：mpv 独立窗必须在播放器窗(WebView)之上才可见
        ok = user32.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), cx, cy, flags)
        return bool(ok)

    def set_parent(self, parent_hwnd: int) -> bool:
        hwnd = self.find_hwnd()
        if not hwnd:
            return False
        result = user32.SetParent(hwnd, wt.HWND(parent_hwnd) if parent_hwnd else None)
        return bool(result)

    def show(self):
        hwnd = self.find_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, SW_SHOW)

    def hide(self):
        hwnd = self.find_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, SW_HIDE)
