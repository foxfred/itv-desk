"""IPTV Core 桌面版入口：内嵌 WebView 窗口 + 后端服务。

双击启动后：
1. 动态获取一个空闲端口
2. 在后台线程启动 FastAPI 后端（serve 前端静态资源 + API）
3. 用 PyWebView 打开内嵌浏览器窗口指向该地址
4. 关闭窗口时自动停止后端并退出
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import ctypes

# --update-only 模式：作为内嵌更新器运行，不走正常启动。
# 必须在 import webview 等重模块之前拦截，避免加载 GUI 依赖。
if "--update-only" in sys.argv:
    import os as _os
    import shutil as _sh
    import subprocess as _sp
    import sys as _sys
    import tempfile as _tf
    import time as _time
    import zipfile as _zf

    _KEEP_SUFFIXES = (".db", ".json", ".m3u", ".m3u8", ".txt")
    _KEEP_DIRS = ("logos",)

    def _find_app_dir():
        if getattr(_sys, "frozen", False):
            ed = _os.path.dirname(_os.path.abspath(_sys.executable))
            return ed if _os.path.isfile(_sys.executable) else None
        return _os.path.dirname(_os.path.abspath(__file__))

    def _collect_user(app_dir):
        keep = []
        try:
            for n in _os.listdir(app_dir):
                full = _os.path.join(app_dir, n)
                if n == "_internal":
                    continue
                if _os.path.isdir(full) and n in _KEEP_DIRS:
                    keep.append(full)
                elif _os.path.isfile(full) and n.endswith(_KEEP_SUFFIXES):
                    keep.append(full)
        except OSError:
            pass
        return keep

    def _backup(app_dir):
        tmp = _tf.mkdtemp(prefix="itv_backup_")
        for s in _collect_user(app_dir):
            if _os.path.isfile(s):
                _sh.copy2(s, _os.path.join(tmp, _os.path.basename(s)))
            else:
                _sh.copytree(s, _os.path.join(tmp, _os.path.basename(s)), symlinks=True)
        return tmp

    def _find_exe_root(d, exe_name):
        if _os.path.isfile(_os.path.join(d, exe_name)):
            return d
        for cur, _, files in _os.walk(d):
            if exe_name in files:
                return cur
        return None

    def _run_updater(argv):
        zips = [_os.path.abspath(a) for a in argv if a.endswith(".zip")]
        if not zips:
            print("[updater] no zip provided")
            return 1
        app_dir = _find_app_dir()
        if not app_dir:
            print("[updater] cannot find app dir")
            return 1
        exe_name = _os.path.basename(_sys.executable) if getattr(_sys, "frozen", False) else "IPTVCore.exe"
        print("[updater] app dir: " + app_dir)

        tmp_root = _tf.mkdtemp(prefix="itv_stage_")
        roots = []
        main_root = None
        try:
            for i, zp in enumerate(zips):
                _d = _tf.mkdtemp(prefix="itv_pkg_", dir=tmp_root)
                with _zf.ZipFile(zp, "r") as z:
                    z.extractall(_d)
                roots.append(_d)
                print("[updater] extracted " + _os.path.basename(zp))
                if main_root is None:
                    main_root = _find_exe_root(_d, exe_name)
        except Exception as e:
            print("[updater] extract fail: " + repr(e))
            return 1
        if not main_root:
            print("[updater] main pkg missing " + exe_name + ", abort")
            return 1

        backup_dir = _backup(app_dir)
        print("[updater] user data backed up")

        real_internal = _os.path.join(app_dir, "_internal")
        exe_path = _os.path.join(app_dir, exe_name)
        log_path = _os.path.join(app_dir, "update.log")
        # mpv 引擎备份目录：替换 _internal 前先把现有 mpv 移出，替换后移回，
        # 避免 core(zip 不含 mpv)替换 _internal 时把 mpv 清掉
        mpv_bak = _os.path.join(_tf.mkdtemp(prefix="itv_mpvbak_"), "mpv")
        bat = _os.path.join(_tf.gettempdir(), "itv_apply_new.bat")
        L = []
        L.append("@echo off")
        L.append("rem wait for app to fully exit and release DLL handles")
        L.append("ping 127.0.0.1 -n 6 > nul")
        L.append('echo [updater] apply start > "' + log_path + '"')
        L.append('taskkill /IM "' + exe_name + '" /F >nul 2>&1')
        L.append("timeout /t 2 /nobreak >nul")
        # 备份现有 mpv 引擎（move 到临时目录），防止 core 包替换 _internal 时被清除
        L.append('if exist "' + real_internal + '\\mpv" (mkdir "' + mpv_bak + '" & move /y "' + real_internal + '\\mpv" "' + mpv_bak + '" >nul 2>&1 & echo [updater] mpv backed up >> "' + log_path + '")')
        L.append('if exist "' + real_internal + '" (rd /s /q "' + real_internal + '")')
        L.append('if exist "' + real_internal + '" (echo [updater] _internal locked retry >> "' + log_path + '" & ping 127.0.0.1 -n 4 > nul & rd /s /q "' + real_internal + '")')
        L.append('xcopy "' + _os.path.join(main_root, "_internal") + '" "' + real_internal + '" /e /i /y /q >> "' + log_path + '" 2>&1')
        # 恢复备份的 mpv 引擎（move 回来）
        L.append('if exist "' + mpv_bak + '" (move /y "' + mpv_bak + '" "' + real_internal + '\\mpv" >nul 2>&1 & echo [updater] mpv restored >> "' + log_path + '")')
        L.append('for /d %%d in ("' + main_root + '\\*") do (if not "%%~nxd"=="_internal" (if not exist "' + app_dir + '\\%%~nxd" mkdir "' + app_dir + '\\%%~nxd" & xcopy "%%d" "' + app_dir + '\\%%~nxd\\" /e /i /y /q >> "' + log_path + '" 2>&1))')
        L.append('for %%f in ("' + main_root + '\\*") do (if not "%%~nxf"=="_internal" (echo f | copy /y "%%f" "' + app_dir + '\\" >> "' + log_path + '" 2>&1))')
        for _d in roots:
            if _d is main_root:
                continue
            mpm = _os.path.join(_d, "mpv")
            if _os.path.isdir(mpm):
                L.append('if not exist "' + real_internal + '\\mpv" mkdir "' + real_internal + '\\mpv"')
                L.append('xcopy "' + mpm + '" "' + real_internal + '\\mpv" /e /i /y /q >> "' + log_path + '" 2>&1')
        # 回迁用户数据：备份根下保存的是「原名字原结构」——子目录(如 logos)整目录、
        # 文件则平铺。逐项精确回迁，子目录目标带尾斜杠保证进目录而非平铺。
        if _os.path.isdir(backup_dir):
            for _it in sorted(_os.listdir(backup_dir)):
                _bs = _os.path.join(backup_dir, _it)
                if _os.path.isdir(_bs):
                    # 目录(如 logos/) → xcopy 到 app_dir/<name>/，带尾斜杠，/e 含空子目录
                    L.append('if not exist "' + app_dir + '\\' + _it + '" mkdir "' + app_dir + '\\' + _it + '"')
                    L.append('xcopy "' + _bs + '" "' + app_dir + '\\' + _it + '\\" /e /i /y /q >> "' + log_path + '" 2>&1')
                else:
                    # 文件 → copy 平铺到根目录
                    L.append('echo f | copy /y "' + _bs + '" "' + app_dir + '\\" >> "' + log_path + '" 2>&1')
        L.append('rd /s /q "' + tmp_root + '" >nul 2>&1')
        L.append('cd /d "' + app_dir + '"')
        L.append('start "" "' + exe_path + '"')
        L.append('del /q /f "%~f0" >nul 2>&1')
        with open(bat, "w", encoding="gbk") as f:
            f.write("\n".join(L))
        print("[updater] apply script: " + bat)

        _sp.Popen(["cmd", "/c", bat], creationflags=0x08000000)
        print("[updater] apply script launched, exiting")
        return 0

    _sys.exit(_run_updater(_sys.argv))


import webview

# mpv 解码引擎（Phase 5 Track A）。dev 模式同目录 import；frozen 由 PyInstaller 打入。
try:
    from mpv_engine import MpvEngine, resolve_mpv_exe as _resolve_mpv_exe
except Exception:  # 缺二进制/打包异常不致命——只影响 mpv 分支，WebView 兜底仍可用
    MpvEngine = None
    _resolve_mpv_exe = None

PORT = 0


def _launch_external_player(url, player_path):
    """调用外部播放器（VLC / PotPlayer）打开 url；返回 True 成功 / False 失败。"""
    try:
        if not player_path or not os.path.isfile(player_path):
            return False
        subprocess.Popen([player_path, url])
        return True
    except Exception:
        return False


class PlayerApi:
    """独立播放器窗口的原生窗口控制（全屏/最大化/最小化/置顶/缩放/关闭）"""

    def __init__(self):
        self._window = None
        self._main_window = None
        self._pending = None
        self._maximized = False
        self._hwnd = None
        # mpv 引擎（Phase 5 Track A：复刻 iptvnator 解码能力）。
        # 注意：单窗口架构下主浮层 PlayerView 跑在主窗口（js_api=Api），mpv_* 实际由 Api 承载；
        # 本 PlayerApi 仅服务独立的 #/player 路由窗口（浏览器直访/遗留路径），两条路径各有 mpv_* 副本。
        self._mpv = MpvEngine() if MpvEngine else None
        self._mpv_last_error = ""

    def set_main_window(self, w):
        """记录主应用窗口，供画中画退出时把最小化主窗口恢复。"""
        self._main_window = w

    def notify_main(self, payload=None):
        """跨窗口状态上报（Phase 3）：播放窗把 引擎/频道/分辨率 推给主窗。

        payload 为前端 JSON.stringify 后的字符串，直接拼进主窗
        window.__updatePlaying(...) 调用（Pinia store 不跨窗口，靠经纪人转发）。
        """
        try:
            if self._main_window is None:
                return False
            js = "window.__updatePlaying && window.__updatePlaying(" + (payload or "{}") + ")"
            self._main_window.evaluate_js(js)
            return True
        except Exception:
            return False

    def set_window(self, w):
        self._window = w

    def pop_pending(self):
        """取出主窗口传入的待播放频道（由播放器页面轮询）"""
        p = self._pending
        self._pending = None
        return p

    def get_client_rect(self):
        """返回播放器窗口 client area 的屏幕坐标 + 标题栏高度（mpv 视频区定位用）。
        返回 {x, y, w, h, chrome_h} 或 None。"""
        if not self._window:
            return None
        try:
            import ctypes
            from ctypes import wintypes as wt
            user32 = ctypes.windll.user32
            native = getattr(self._window, "native", None)
            if native is None:
                return None
            hwnd = native.Handle.ToInt64()
            rect = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w_win = rect.right - rect.left
            h_win = rect.bottom - rect.top
            # GetClientRect 取客户区尺寸，与窗口尺寸差 = 标题栏/边框高度
            crect = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(crect))
            w_client = crect.right - crect.left
            h_client = crect.bottom - crect.top
            chrome_h = h_win - h_client
            return {
                "x": int(rect.left), "y": int(rect.top),
                "w": int(w_client), "h": int(h_client),
                "chrome_h": int(chrome_h),
            }
        except Exception:
            return None

    def _get_hwnd(self):
        """缓存窗口原生句柄（避免每次跨线程读 .NET 属性）。用 64 位 Int64，避免截断"""
        if self._hwnd is None:
            native = getattr(self._window, "native", None)
            if native is not None:
                self._hwnd = native.Handle.ToInt64()
        return self._hwnd

    @staticmethod
    def _hwnd_of(window):
        """读取任意 pywebview 窗口的原生 HWND（64 位）。"""
        try:
            native = getattr(window, "native", None)
            if native is not None:
                return native.Handle.ToInt64()
        except Exception:
            pass
        return None

    def _force_foreground(self, window):
        """Windows：把窗口恢复到前台并强制置顶可见（绕过系统焦点窃取保护）。
        失败时回退到 pywebview 原生 show/restore。非 Windows 直接走回退。"""
        if not window:
            return False
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0001
            SWP_NOSIZE = 0x0002
            SWP_SHOWWINDOW = 0x0040
            user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            user32.SetWindowPos.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
            ]
            user32.GetWindowThreadProcessId.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
            ]

            hwnd = self._hwnd_of(window)
            if not hwnd:
                raise RuntimeError("no hwnd")
            hwnd_p = ctypes.c_void_p(hwnd)
            # 1) 恢复（解除最小化）并确保可见
            user32.ShowWindow(hwnd_p, SW_RESTORE)
            # 2) 绕过焦点窃取保护：挂接前台窗口线程后抢前台
            fg = user32.GetForegroundWindow()
            if fg:
                cur = wintypes.DWORD()
                fg_t = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd_p, ctypes.byref(cur))
                user32.GetWindowThreadProcessId(fg, ctypes.byref(fg_t))
                if cur.value and fg_t.value and cur.value != fg_t.value:
                    user32.AttachThreadInput(cur.value, fg_t.value, True)
                    user32.SetForegroundWindow(hwnd_p)
                    user32.AttachThreadInput(cur.value, fg_t.value, False)
                else:
                    user32.SetForegroundWindow(hwnd_p)
            else:
                user32.SetForegroundWindow(hwnd_p)
            # 3) 强制 z-order 最前（置顶→取消置顶，避免长期浮动在最前）
            user32.SetWindowPos(
                hwnd_p, ctypes.c_void_p(HWND_TOPMOST), 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            user32.SetWindowPos(
                hwnd_p, ctypes.c_void_p(HWND_NOTOPMOST), 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            return True
        except Exception:
            # 回退：原生 show / restore
            try:
                window.show()
            except Exception:
                pass
            try:
                if hasattr(window, "restore"):
                    window.restore()
            except Exception:
                pass
            return False

    def toggle_fullscreen(self):
        """切换系统全屏（覆盖整个屏幕）"""
        try:
            self._window.toggle_fullscreen()
            return True
        except Exception as e:
            return f"ERROR: {e}"

    def maximize(self):
        """最大化/还原 切换"""
        try:
            if self._maximized:
                self._window.restore()
            else:
                self._window.maximize()
            return True
        except Exception:
            return False

    def minimize(self):
        try:
            self._window.minimize()
            return True
        except Exception:
            return False

    def move(self, x, y):
        """移动窗口到指定屏幕坐标（供前端标题栏拖拽）"""
        try:
            self._window.move(int(x), int(y))
            return True
        except Exception:
            return False

    def restore(self):
        try:
            self._window.restore()
            return True
        except Exception:
            return False

    def hide_window(self):
        """画中画进入时隐藏播放器窗口（视频已转入系统画中画浮层）。"""
        try:
            if self._window:
                self._window.hide()
            return True
        except Exception:
            return False

    def show_window(self):
        """画中画退出时恢复显示播放器窗口，并强制置顶到前台（修复：返回后窗口滞留后台）。"""
        try:
            if self._window:
                self._force_foreground(self._window)
            return True
        except Exception:
            return False

    def restore_main_window(self):
        """画中画退出时若主应用窗口最小化则自动恢复弹出可见（不抢前台，置顶交给 show_window）。"""
        try:
            if self._main_window:
                try:
                    self._main_window.show()
                except Exception:
                    pass
                try:
                    if hasattr(self._main_window, "restore"):
                        self._main_window.restore()
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _mark_maximized(self, *_):
        self._maximized = True

    def _mark_restored(self, *_):
        self._maximized = False

    def resize(self, w, h, fix_point=None):
        try:
            from webview.window import FixPoint
            if fix_point:
                self._window.resize(int(w), int(h), FixPoint(int(fix_point)))
            else:
                self._window.resize(int(w), int(h))
            return True
        except Exception:
            return False

    def close_player(self):
        """关闭播放器窗口：真正关闭并停止播放，而非后台隐藏继续播放。
        先通知前端 __iptvCleanup（释放 hls/flv/mpv），再销毁窗口，防 mpv 残留。"""
        try:
            w = self._window
            self._window = None
            if w is not None:
                try:
                    w.evaluate_js("window.__iptvCleanup && window.__iptvCleanup()")
                except Exception:
                    pass
                # 兜底：直接 quit mpv（前端 onUnmounted 若未触发也不残留）
                try:
                    if self._mpv:
                        self._mpv.quit()
                except Exception:
                    pass
                w.destroy()
            return True
        except Exception:
            return False

    def set_topmost(self, on=True):
        """置顶/取消置顶播放窗口（Windows SetWindowPos HWND_TOPMOST/NOTOPMOST）。"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0001
            SWP_NOSIZE = 0x0002
            hwnd = self._hwnd_of(self._window)
            if not hwnd:
                return False
            flag = HWND_TOPMOST if on else HWND_NOTOPMOST
            ok = user32.SetWindowPos(
                ctypes.c_void_p(hwnd), ctypes.c_void_p(flag), 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE,
            )
            return bool(ok)
        except Exception:
            return False

    def move_window(self, dx, dy):
        """无外框模式下移动播放窗口（前端拖拽顶部条时调用）。
        dx/dy 为相对偏移量，基于 pywebview 窗口当前位置移动。"""
        try:
            w = self._window
            if w is None:
                return False
            w.move(int(getattr(w, 'x', 0)) + int(dx), int(getattr(w, 'y', 0)) + int(dy))
            return True
        except Exception:
            return False

    def resize_window(self, w, h, corner=0):
        """无外框模式下调整播放窗口大小（前端拖拽角手柄时调用）。
        w/h 为最终宽高；corner 为锚点角（0=左上, 1=右上, 2=右下, 3=左下）。"""
        try:
            w_win = self._window
            if w_win is None:
                return False
            if corner:
                from webview.window import FixPoint
                w_win.resize(int(w), int(h), FixPoint(int(corner)))
            else:
                w_win.resize(int(w), int(h))
            return True
        except Exception:
            return False

    def play_external(self, url, player_path):
        """用外部播放器打开直播源（VLC / PotPlayer）"""
        return _launch_external_player(url, player_path)

    # ===== mpv 引擎桥（Phase 5 Track A）=====
    # 挂在 PlayerApi 上：服务于独立的 #/player 路由窗口（window.pywebview.api 即本实例）。
    # 单窗口主浮层路径由 Api.mpv_* 承载，二者逻辑保持一致。
    def mpv_available(self):
        """是否已部署 mpv 引擎。返回 {ok, path, candidates:[{label,path,exists}], meipass, exe_dir}。
        探测路径由 resolve_mpv_exe() 统一负责（dev/frozen 双路，避免各自拼路径造成不一致）。"""
        if not _resolve_mpv_exe:
            return {"ok": False, "reason": "MpvEngine 未加载", "candidates": []}
        try:
            import sys as _s
            meipass = getattr(_s, "_MEIPASS", None) or ""
            exe_dir = os.path.dirname(os.path.abspath(_s.executable))
            # frozen 探测用同于 resolve_mpv_exe 的候选；dev 态 _resolve_mpv_exe 会解析到 vendov/mpv。
            cands = []
            if getattr(_s, "frozen", False):
                if meipass:
                    cands.append(("sys._MEIPASS/mpv", os.path.join(meipass, "mpv", "mpv.exe")))
                cands.append(("EXE_DIR/_internal/mpv", os.path.join(exe_dir, "_internal", "mpv", "mpv.exe")))
                cands.append(("EXE_DIR/mpv", os.path.join(exe_dir, "mpv", "mpv.exe")))
            # dev：REPO_ROOT/vendor/mpv/mpv.exe（_repo_root 由 resolve_mpv_exe 内部解析）
            resolved = _resolve_mpv_exe()
            cands.append(("resolve_mpv_exe()", resolved))
            row = [{"label": l, "path": p, "exists": os.path.isfile(p)} for l, p in cands]
            any_ok = any(r["exists"] for r in row)
            # D2 修复：文件存在只是必要条件，再轻量探测能否真正启动（--version <500ms）
            launchable = False
            probe_error = ""
            if any_ok:
                try:
                    import subprocess as _sp
                    exe = resolved if os.path.isfile(resolved) else next(
                        (r["path"] for r in row if r["exists"]), None
                    )
                    if exe:
                        r0 = _sp.run(
                            [exe, "--version", "--no-config"],
                            capture_output=True, timeout=5,
                            creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
                        )
                        launchable = r0.returncode == 0
                        if not launchable:
                            probe_error = (r0.stderr or r0.stdout or b"").decode("utf-8", "replace")[:200]
                except Exception as e:
                    launchable = False
                    probe_error = repr(e)
            return {
                "ok": any_ok and launchable,
                "path": resolved if os.path.isfile(resolved) else None,
                "launchable": launchable,
                "probe_error": probe_error,
                "candidates": row,
                "meipass": meipass,
                "exe_dir": exe_dir,
            }
        except Exception as e:
            return {"ok": False, "reason": repr(e), "candidates": []}

    def mpv_get_main_hwnd(self):
        """返回播放器窗口的 HWND（int64）。前端可用于计算视频区屏幕坐标。"""
        try:
            hwnd = self._get_hwnd()
            return int(hwnd) if hwnd else 0
        except Exception:
            return 0

    def mpv_init(self, proxy=None):
        """启动 mpv 子进程（前端按需调用）。返回 {ok, error?, pid?}。"""
        if not self._mpv:
            return {"ok": False, "error": "MpvEngine 未加载"}
        self._mpv_last_error = ""

        def _on_err(msg):
            self._mpv_last_error = msg

        ok = self._mpv.start(proxy=proxy, on_error=_on_err)
        return {
            "ok": ok,
            "error": "" if ok else (self._mpv_last_error or "mpv 启动失败"),
            "pid": self._mpv._proc.pid if (ok and self._mpv._proc) else None,
        }

    def mpv_load(self, url):
        if not self._mpv or not self._mpv.is_alive():
            return {"ok": False, "error": "mpv 未运行"}
        r = self._mpv.load(url)  # send(wait=True, timeout=10) 超时返回 None
        # B6 修复：IPC 无响应（10s 超时）时给出明确错误，前端据此可触发 webview 回退
        if r is None:
            return {"ok": False, "error": "mpv 无响应(10s 超时)，建议回退 WebView"}
        if r.get("error") != "success":
            return {"ok": False, "error": r.get("error") or "loadfile 失败"}
        return {"ok": True, "error": ""}

    def mpv_play(self):
        if not self._mpv: return {"ok": False}
        self._mpv.play()
        return {"ok": True}

    def mpv_pause(self):
        if not self._mpv: return {"ok": False}
        self._mpv.pause()
        return {"ok": True}

    def mpv_toggle_pause(self):
        if not self._mpv: return {"ok": False}
        self._mpv.toggle_pause()
        return {"ok": True}

    def mpv_set_volume(self, v):
        if not self._mpv: return {"ok": False}
        self._mpv.set_volume(int(v))
        return {"ok": True}

    def mpv_seek(self, sec, mode="relative"):
        if not self._mpv: return {"ok": False}
        self._mpv.seek(float(sec), mode=mode)
        return {"ok": True}

    def mpv_set_speed(self, speed):
        if not self._mpv: return {"ok": False}
        self._mpv.set_speed(float(speed))
        return {"ok": True}

    def mpv_set_rect(self, x, y, w=None, h=None):
        """定位 mpv 窗口到屏幕坐标。w/h 传 None 时只动位置（spike 验证 mpv 按视频比例自调 size）。"""
        if not self._mpv: return {"ok": False, "error": "mpv 未加载"}
        ok = self._mpv.set_rect(int(x), int(y),
                                int(w) if w is not None else None,
                                int(h) if h is not None else None)
        return {"ok": ok}

    def mpv_state(self):
        """轮询：返回 {alive, last_error, ...}。前端可据此判断是否回退 WebView。"""
        if not self._mpv:
            return {"alive": False, "error": "MpvEngine 未加载"}
        return {
            "alive": self._mpv.is_alive(),
            "last_error": self._mpv_last_error,
            "state": self._mpv.state(),
        }

    def mpv_quit(self):
        """退出 mpv 并确认进程已结束。返回 {ok, exited}；前端可据此判断是否残留。"""
        if not self._mpv:
            return {"ok": False, "exited": True}
        try:
            self._mpv.quit()
            # quit 内部已 wait/kill；此处再确认一次 poll 结果
            proc = getattr(self._mpv, "_proc", None)
            exited = proc is None or proc.poll() is not None
            return {"ok": True, "exited": exited}
        except Exception as e:
            return {"ok": False, "exited": False, "error": repr(e)}


class Api:
    """暴露给前端 JS 的原生能力（保存文件对话框等）"""

    def __init__(self):
        self._window = None
        self._player_window = None
        self._player_api = None
        self._player_url = None
        self._last_channel = None  # 双窗口：记录上次播放频道，用于「恢复播放窗口」
        # mpv 引擎只归 PlayerApi（播放窗 js_api，Phase 2 去嵌入后职责分离），
        # 主窗 Api 不再承载任何 mpv 方法（--wid 嵌入已废弃）。

    def set_window(self, w):
        self._window = w

    def set_player(self, window, api):
        self._player_window = window
        self._player_api = api
        # 让播放器窗口原生桥能恢复（最小化）主应用窗口
        try:
            api.set_main_window(self._window)
        except Exception:
            pass

    def _clear_player(self):
        """播放器窗口真正关闭后清空引用，下次 open_player 自动重建"""
        self._player_window = None
        if self._player_api is not None:
            self._player_api._window = None

    def save_text(self, default_name, content):
        """弹出保存对话框，将 content 写入用户选择的位置。返回保存路径或 None(取消)"""
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name
            )
            if not result:
                return None
            path = result if isinstance(result, str) else result[0]
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            return path
        except Exception as e:
            return f"ERROR: {e}"

    def save_file_from(self, src_path, default_name="iptv_backup.zip"):
        """弹出保存对话框，将服务器端已生成的二进制文件(src_path)复制到用户选择的位置。
        返回用户选择的完整路径，或 None(取消/失败)"""
        import shutil as _sh
        try:
            if not self._window or not src_path or not os.path.isfile(src_path):
                return None
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_name
            )
            if not result:
                return None
            dest = result if isinstance(result, str) else result[0]
            if os.path.abspath(dest) == os.path.abspath(src_path):
                return dest
            _sh.copyfile(src_path, dest)
            return dest
        except Exception:
            return None

    def minimize_window(self):
        """最小化系统窗口"""
        try:
            if self._window:
                self._window.minimize()
            return True
        except Exception:
            return False

    def focus_window(self):
        """将窗口带到前台显示"""
        try:
            if self._window:
                self._window.show()
                if hasattr(self._window, "restore"):
                    try:
                        self._window.restore()
                    except Exception:
                        pass
            return True
        except Exception:
            return False

    def close_player(self):
        """关闭播放器窗口：真正关闭并停止播放，而非后台隐藏继续播放"""
        try:
            # D4 修复：destroy 前先通知前端清理（hls/flv/mpv 等资源），
            # 兜底系统标题栏 X 关闭时 Vue onUnmounted 可能不触发的场景
            if self._player_window:
                try:
                    self._player_window.evaluate_js(
                        "window.__iptvCleanup && window.__iptvCleanup()"
                    )
                except Exception:
                    pass
                self._player_window.destroy()
            self._player_window = None
            return True
        except Exception:
            return False

    def play_external(self, url, player_path):
        """用外部播放器打开直播源（VLC / PotPlayer）"""
        return _launch_external_player(url, player_path)

    def select_file(self, title="选择文件", filter_str=""):
        """弹出文件选择对话框，返回用户选择的文件路径或 None(取消)。

        filter_str 支持两种格式（自动校正）：
          - pywebview 标准：'描述 (*.ext)|描述2 (*.ext2)'
          - 旧式交错：    '描述|*.ext|描述2|*.*'  → 自动合并为 '描述 (*.ext)'
        """
        try:
            if not self._window:
                return None
            file_types = []
            if filter_str:
                parts = [p for p in filter_str.split('|') if p]
                # 旧式交错格式：奇数位是描述、偶数位是扩展名（如 '描述|*.ext'）
                if (
                    len(parts) >= 2
                    and '(' not in parts[0]
                    and not parts[1].startswith('*')
                ):
                    it = iter(parts)
                    for desc in it:
                        ext = next(it, '*.*')
                        file_types.append(f"{desc} ({ext})")
                else:
                    file_types = parts
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=tuple(file_types),
            )
            if not result:
                return None
            return result[0] if isinstance(result, (list, tuple)) else result
        except Exception as e:
            return f"ERROR: {e}"

    def play_channel(self, payload=None):
        """经纪人：主窗列表双击 → 打开/复用独立播放窗并播放。

        payload: {url, name, group, id}（来自前端双击频道）。
        返回 True 成功 / False 失败 / "ERROR: ..." 异常。
        """
        if isinstance(payload, dict):
            url = payload.get("url")
            name = payload.get("name") or "未命名频道"
            group = payload.get("group") or ""
        else:
            url = payload
            name = "未命名频道"
            group = ""
        if not url:
            return False
        row = {"url": url, "name": name, "group": group}
        return self.open_player(row, None)

    def open_player(self, row=None, channel_list=None):
        """打开/复用独立播放器窗口并播放指定频道。

        双窗口架构（Phase 1）：播放窗口是独立 pywebview 窗口（#/player 路由，
        js_api=PlayerApi）。row 为 None 时复用上次频道（_last_channel）仅恢复窗口。
        channel_list 不再下发给播放窗——选源统一由主窗列表驱动（见计划书 §3）。
        """
        try:
            if self._player_api is None:
                self._player_api = PlayerApi()
            if self._player_window is None:
                # 播放器此前已被真正关闭，按需重建窗口
                if not _create_player_window(self, self._player_api, self._player_url):
                    return False
            # 双窗口：选源一律由主窗列表驱动；播放窗不维护频道列表导航
            effective = row or self._last_channel
            if not effective:
                # 无待播频道：仅恢复/显示已存在的窗口（通常为空白待播）
                self._player_window.show()
                if hasattr(self._player_window, "restore"):
                    try:
                        self._player_window.restore()
                    except Exception:
                        pass
                return True
            self._last_channel = effective
            self._player_api._pending = effective
            # push 模式：直接把播放指令推给播放器页面，换台即时生效，
            # 不依赖 JS→Python 二次调用链（poll 作为兜底）
            try:
                import json as _json
                def _pick_channel_fields(ch):
                    out = {k: ch.get(k) for k in ("url", "name", "group", "sources", "source_groups", "tag") if ch.get(k)}
                    # id / is_fake_live 需要显式保留（False/0 会被上式过滤）
                    if ch.get("id") is not None:
                        out["id"] = ch.get("id")
                    if ch.get("is_fake_live"):
                        out["is_fake_live"] = True
                    # 每个源独立的标记/假直播状态（聚合频道按源显示）
                    if ch.get("source_tags"):
                        out["source_tags"] = ch.get("source_tags")
                    if ch.get("source_is_fake_live"):
                        out["source_is_fake_live"] = ch.get("source_is_fake_live")
                    # 1.5: $ 后标签（如「组播超高清-50fps」）透传给播放器展示
                    if ch.get("url_note"):
                        out["url_note"] = ch.get("url_note")
                    return out
                payload = _json.dumps(_pick_channel_fields(effective), ensure_ascii=False)
                self._player_window.evaluate_js(
                    "window.__iptvPlay && window.__iptvPlay(" + payload + ")"
                )
            except Exception:
                pass
            self._player_window.show()
            if hasattr(self._player_window, "restore"):
                try:
                    self._player_window.restore()
                except Exception:
                    pass
            return True
        except Exception as e:
            return f"ERROR: {e}"


def _create_player_window(api, player_api, url):
    """创建独立播放器窗口（初始隐藏，由 open_player 显示）。

    关闭即真正销毁（destroy），再次 open_player 时按需重建；
    复用同一个 PlayerApi 实例，保证 _pending 等状态不丢。
    """
    try:
        player_window = webview.create_window(
            "IPTV 播放器",
            url + "#/player?standalone=1",  # Vue3 hash 路由；standalone=1 让 App.vue 隐藏主窗 layout，只渲染 PlayerView
            width=1100,
            height=680,
            min_size=(420, 260),
            frameless=True,
            hidden=True,
            resizable=True,
            background_color="#11151c",
            js_api=player_api,
        )
        if player_window is None:
            return False
        player_api.set_window(player_window)
        api.set_player(player_window, player_api)
        player_window.events.maximized += player_api._mark_maximized
        player_window.events.restored += player_api._mark_restored
        player_window.events.shown += lambda *_: player_api._get_hwnd()  # GUI 线程预取句柄
        # Phase 5：mpv 窗口跟随播放面板——拖动/缩放播放窗时通知前端重定位 mpv 覆盖视频区
        def _on_player_moved_resized(*_):
            try:
                player_window.evaluate_js("window.__repositionMpv && window.__repositionMpv()")
            except Exception:
                pass
        player_window.events.moved += _on_player_moved_resized
        player_window.events.resized += _on_player_moved_resized
        # 播放器被真正关闭（JS 关闭按钮 / 标题栏 X / 主窗口退出）后清空引用，
        # 下次 open_player 重建窗口，不再后台隐藏继续播放
        def _on_player_closed(*_):
            # 兜底 quit mpv：前端 onUnmounted 若不触发，mpv 进程也不残留（用户曾反馈"关掉后 mpv 还在"）
            try:
                _mpv = getattr(player_api, "_mpv", None)
                if _mpv is not None:
                    _mpv.quit()
            except Exception:
                pass
            api._clear_player()
        player_window.events.closed += _on_player_closed
        return True
    except Exception:
        return False


def _is_port_in_use(port):
    """检查端口是否已被占用"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return False  # 绑定成功 → 空闲
    except OSError:
        return True   # 绑定失败 → 被占用
    finally:
        s.close()


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _clear_webview_cache():
    """清除 WebView2 缓存，强制加载最新前端 build 文件。

    根因：WebView2 有独立的磁盘 HTTP 缓存层，即使后端返回
    Cache-Control: no-cache，WebView2 仍可能跳过校验、直接返回
    磁盘缓存里的旧文件（同文件名不同内容 → 404）。

    pywebview 每次启动在 %TEMP% 下创建 tmp*.tmp 临时目录，
    里面会建 EBWebView 子目录存放 WebView2 缓存（含 HTTP 层缓存）。
    前端 build 更新后，旧 index.html/JS 仍被 WebView2 缓存。

    修复策略：删除整个 tmp*.tmp 目录（pywebview 下次启动会自动重建）。
    只删含 EBWebView 子目录的 tmp*.tmp，不误删其他程序的临时目录。
    """
    try:
        tmp_dir = os.environ.get('TEMP') or os.environ.get('TMP') or tempfile.gettempdir()
        if not tmp_dir or not os.path.isdir(tmp_dir):
            return
        cleaned = 0
        for name in os.listdir(tmp_dir):
            if not name.startswith('tmp'):
                continue
            candidate = os.path.join(tmp_dir, name)
            if not os.path.isdir(candidate):
                continue
            # 只清理含 EBWebView 的目录（pywebview 专属），避免误删其他程序临时目录
            if os.path.isdir(os.path.join(candidate, 'EBWebView')):
                shutil.rmtree(candidate, ignore_errors=True)
                cleaned += 1
        if cleaned:
            print(f"[cache] 已清除 {cleaned} 个 WebView2 缓存目录 (根: {tmp_dir})")
    except Exception:
        pass


def _start_backend(port):
    global PORT
    PORT = port
    if getattr(sys, "frozen", False):
        # PyInstaller: backend/ 打包在 _MEIPASS 下
        sys.path.insert(0, os.path.join(sys._MEIPASS, "backend"))
        from app.main import run_server
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(base, "backend"))
        sys.path.insert(0, base)
        from app.main import run_server
    run_server(host="127.0.0.1", port=port)


def _kill_port(port):
    """强制杀掉占用指定端口的进程"""
    import subprocess
    try:
        r = subprocess.run(f"netstat -ano | findstr :{port}", capture_output=True, text=True, shell=True)
        for line in r.stdout.splitlines():
            if "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(f"taskkill /F /PID {pid}", capture_output=True, shell=True)
                return True
    except Exception:
        pass
    return False


def _save_cache_on_exit(port):
    """退出前通知后端保存频道缓存"""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/cache/save",
            data=b"", method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def main():
    port = 8000
    # 检测端口是否被占用（如 Web 版 python backend/main.py 仍在运行）
    if _is_port_in_use(port):
        import ctypes
        ret = ctypes.windll.user32.MessageBoxW(
            0,
            f"检测到端口 {port} 已被占用，可能上次的后端未正常退出。\n\n"
            "是否自动关闭占用进程并继续启动？",
            "IPTV Core - 端口冲突", 0x34  # MB_YESNO | MB_ICONWARNING
        )
        if ret == 6:  # IDYES
            _kill_port(port)
            time.sleep(0.5)
        else:
            return 1
    t = threading.Thread(target=_start_backend, args=(port,), daemon=True)
    t.start()

    # 等待后端就绪
    url = f"http://127.0.0.1:{port}/"
    deadline = time.time() + 15
    ok = False
    while time.time() < deadline:
        try:
            import urllib.request
            urllib.request.urlopen(url, timeout=2)
            ok = True
            break
        except Exception:
            time.sleep(0.2)
    if not ok:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "后端服务启动失败，请查看是否有端口或权限问题。", "IPTV Core", 0x10)
        return 1

    # 清除 WebView2 缓存，强制加载最新前端 build 文件
    _clear_webview_cache()

    # 关键：在 URL 本身追加唯一查询参数，彻底绕过 WebView2 页面级缓存。
    # WebView2 会把查询参数纳入缓存键，URL 不同则必须重新请求。
    import uuid as _uuid
    base_url = url
    url = url + "?_v=" + _uuid.uuid4().hex[:12]
    print(f"[startup] 主窗口 URL: {url}")

    api = Api()
    window = webview.create_window(
        "IPTV Core PRO MAX",
        url,
        width=1400,
        height=900,
        min_size=(1024, 640),
        easy_drag=True,
        js_api=api,
    )
    api.set_window(window)
    # 双窗口（Phase 1）：记录前端基址，供 open_player 创建 #/player 独立播放窗
    api._player_url = base_url

    # 双窗口架构（Phase 1）：播放窗口是独立 pywebview 窗口（#/player 路由，js_api=PlayerApi），
    # 由前端双击频道经 Api.play_channel → Api.open_player 按需创建/复用。
    # 主窗口始终是纯频道库/管理（满尺寸），mpv 引擎挂在 PlayerApi（播放窗 js_api）。
    # 不再有主窗内嵌浮层（App.vue 已移除 <PlayerView embedded />）。

    # 主窗口关闭时清理播放窗 mpv 子进程，避免残留（mpv 挂在 PlayerApi，Phase 2 职责分离）
    def _on_main_closing(*_):
        try:
            _pa = getattr(api, "_player_api", None)
            _mpv = getattr(_pa, "_mpv", None) if _pa else None
            if _mpv is not None:
                _mpv.quit()
        except Exception:
            pass

    window.events.closing += _on_main_closing

    # private_mode=False 关闭隐私模式：localStorage 才持久化到磁盘，
    # 否则每次启动清空导致排序/列宽/列隐藏等偏好丢失
    webview.start(private_mode=False, debug=False)
    _save_cache_on_exit(port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
