import hashlib
import os
import socket
import threading
import time

DEFAULT_TUNER_COUNT = 3
DEFAULT_LIMIT = 300

_ADULT_HINTS = ("成人", "色情", "18+", "十八禁", "福利", "porn", "adult")


class HdHomeRunService:
    """HDHomeRun 仿真：把频道库按 HDHomeRun 协议暴露，供 Plex / Emby / Kodi 等直接添加为调谐器。"""

    def __init__(self, channel_service, log_callback=None, settings_provider=None, data_dir=None):
        self.channel_service = channel_service
        self.log = log_callback or (lambda m: None)
        self.settings_provider = settings_provider or (lambda: {})
        self.data_dir = data_dir
        self._lock = threading.Lock()
        self._tuners = {}
        self._ssdp_thread = None
        self._ssdp_stop = threading.Event()

    # ---------- 配置 ----------

    def cfg(self):
        s = self.settings_provider() or {}
        port = int(s.get("hdhr_port") or 0) or int(os.environ.get("IPTVCORE_PORT") or 8000)
        return {
            "enabled": bool(s.get("hdhr_enabled")),
            "device_id": str(s.get("hdhr_device_id") or "").strip(),
            "tuner_count": max(1, int(s.get("hdhr_tuner_count") or DEFAULT_TUNER_COUNT)),
            "only_online": bool(s.get("hdhr_only_online", True)),
            "groups": [str(g) for g in (s.get("hdhr_groups") or [])],
            "limit": max(1, int(s.get("hdhr_limit") or DEFAULT_LIMIT)),
            "transcode": bool(s.get("hdhr_transcode")),
            "ssdp": bool(s.get("hdhr_ssdp")),
            "exclude_adult": bool(s.get("hdhr_exclude_adult", True)),
            "base_override": str(s.get("hdhr_base_url") or "").strip().rstrip("/"),
            "port": port,
        }

    def lan_ip(self):
        """探测本机局域网 IP；失败则退回 127.0.0.1。"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
            finally:
                s.close()
        except Exception:
            return "127.0.0.1"

    def base_url(self):
        c = self.cfg()
        if c["base_override"]:
            return c["base_override"]
        return "http://%s:%d" % (self.lan_ip(), c["port"])

    def device_id(self):
        """8 位十六进制 DeviceID，未配置时按数据目录稳定派生。"""
        c = self.cfg()
        raw = c["device_id"].strip().upper()
        if len(raw) == 8 and all(ch in "0123456789ABCDEF" for ch in raw):
            return raw
        seed = ("itvdesk:" + os.path.abspath(self.data_dir or os.getcwd())).encode("utf-8")
        h = hashlib.md5(seed).hexdigest().upper()
        return (h[:8]) if h[:2].isalpha() else ("A" + h[:7])

    def device_id_int(self):
        return int(self.device_id(), 16)

    # ---------- 频道 -> lineup ----------

    def _channels(self):
        c = self.cfg()
        if not c["enabled"]:
            return []
        with self.channel_service.lock:
            items = [dict(ch) for ch in self.channel_service.pool]
        out = []
        for ch in items:
            name = (ch.get("name") or "").strip()
            url = (ch.get("url") or "").strip()
            if not name or not url:
                continue
            group = (ch.get("group") or "").strip()
            if c["groups"] and group not in c["groups"]:
                continue
            if c["only_online"]:
                state = (ch.get("status") or ch.get("state") or "").strip()
                if state and state not in ("在线", "可用", "online"):
                    continue
            if c["exclude_adult"]:
                low = (name + " " + group).lower()
                if any(h.lower() in low for h in _ADULT_HINTS):
                    continue
            out.append({"name": name, "url": url, "group": group, "ch": ch})
        out.sort(key=lambda d: (d["group"], d["name"]))
        return out[:c["limit"]]

    def lineup(self):
        base = self.base_url()
        rows = []
        for idx, item in enumerate(self._channels(), start=1):
            number = str(idx)
            rows.append({
                "GuideNumber": number,
                "GuideName": item["name"],
                "URL": "%s/auto/v%s" % (base, number),
                "Group": item["group"],
            })
        return rows

    def find(self, number):
        """按 GuideNumber 取回条目，附源地址（src）。"""
        num = str(number).lstrip("v").strip()
        for idx, item in enumerate(self._channels(), start=1):
            if str(idx) == num:
                return {
                    "GuideNumber": str(idx),
                    "GuideName": item["name"],
                    "URL": "%s/auto/v%d" % (self.base_url(), idx),
                    "Group": item["group"],
                    "src": item["url"],
                }
        return None

    # ---------- 调谐器占用 ----------

    def tuner_count_active(self):
        with self._lock:
            return len(self._tuners)

    def acquire(self, key):
        c = self.cfg()
        with self._lock:
            if key in self._tuners:
                self._tuners[key] += 1
                return True
            if len(self._tuners) >= c["tuner_count"]:
                return False
            self._tuners[key] = 1
            return True

    def release(self, key):
        with self._lock:
            if key in self._tuners:
                self._tuners[key] -= 1
                if self._tuners[key] <= 0:
                    self._tuners.pop(key, None)

    def active_list(self):
        with self._lock:
            return [{"channel": k, "clients": v} for k, v in self._tuners.items()]

    # ---------- SSDP ----------

    def ssdp_start(self):
        if self._ssdp_thread and self._ssdp_thread.is_alive():
            return True
        self._ssdp_stop.clear()
        self._ssdp_thread = threading.Thread(target=self._ssdp_loop, daemon=True)
        self._ssdp_thread.start()
        return True

    def ssdp_stop_serve(self):
        self._ssdp_stop.set()

    def _ssdp_loop(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
            sock.bind(("", 1900))
            mreq = socket.inet_aton("239.255.255.250") + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(1.0)
        except Exception as e:
            self.log("[HDHomeRun] SSDP 监听启动失败（%s），设备需手动添加地址" % str(e)[:80])
            return
        self.log("[HDHomeRun] SSDP 已启动，局域网客户端可自动发现")
        base = self.base_url()
        while not self._ssdp_stop.is_set():
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except Exception:
                break
            text = data.decode("utf-8", "ignore")
            if "M-SEARCH" not in text and "NOTIFY" not in text:
                continue
            low = text.lower()
            if "hdhomerun" not in low and "ssdp:all" not in low and "ssdp:discover" not in low:
                continue
            lines = [
                "HTTP/1.1 200 OK",
                "CACHE-CONTROL: max-age=1800",
                "EXT:",
                "ST: urn:schemas-upnp-org:device:MediaServer:1",
                "USN: uuid:%s::urn:schemas-upnp-org:device:MediaServer:1" % self.device_id(),
                "LOCATION: %s/device.xml" % base,
                "SERVER: HDHomeRun/1.0 UPnP/1.0",
                "",
                "",
            ]
            try:
                sock.sendto("\r\n".join(lines).encode("utf-8"), addr)
            except Exception:
                pass
        try:
            sock.close()
        except Exception:
            pass

    # ---------- 描述文档 ----------

    def device_xml(self):
        base = self.base_url()
        return (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<root xmlns="urn:schemas-upnp-org:device-1-0">\n'
            '  <specVersion><major>1</major><minor>0</minor></specVersion>\n'
            '  <device>\n'
            '    <deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>\n'
            '    <friendlyName>ITV Desk</friendlyName>\n'
            '    <manufacturer>Silicondust</manufacturer>\n'
            '    <modelName>HDHomeRun</modelName>\n'
            '    <UDN>uuid:%s</UDN>\n'
            '    <URLBase>%s</URLBase>\n'
            '  </device>\n'
            '</root>\n' % (self.device_id(), base)
        )

    def discover_json(self):
        base = self.base_url()
        c = self.cfg()
        return {
            "FriendlyName": "ITV Desk",
            "Manufacturer": "Silicondust",
            "ModelNumber": "HDHR-US",
            "FirmwareName": "hdhomerun4_atsc",
            "FirmwareVersion": "20240101",
            "DeviceID": self.device_id(),
            "DeviceAuth": "itvdesk",
            "BaseURL": base,
            "LineupURL": base + "/lineup.json",
            "TunerCount": c["tuner_count"],
        }

    def lineup_status_json(self):
        return {
            "ScanInProgress": 0,
            "ScanPossible": 1,
            "Source": "Cable",
            "SourceList": ["Cable"],
        }

    # ---------- 流地址构造 ----------

    @staticmethod
    def input_opts(url):
        """仅 http(s) 源注入 UA，避免非 HTTP 输入被 ffmpeg 直接拒绝。"""
        return ["-user_agent", "okhttp/3.14.9"] if url.lower().startswith(("http://", "https://")) else []

    def build_ffmpeg_cmd(self, src_url):
        c = self.cfg()
        cmd = [os.environ.get("IPTV_FFMPEG", "ffmpeg"),
               "-hide_banner", "-loglevel", "warning",
               "-rw_timeout", "15000000"]
        cmd += self.input_opts(src_url)
        cmd += ["-i", src_url]
        if c["transcode"]:
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
                    "-crf", "23", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0"]
        else:
            cmd += ["-c:v", "copy"]
        cmd += ["-c:a", "aac", "-b:a", "128k", "-f", "mpegts", "pipe:"]
        return cmd

    def start_stream(self, src_url):
        import subprocess
        cmd = self.build_ffmpeg_cmd(src_url)
        try:
            return subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError:
            return None

    def wait_ready(self, proc, seconds=0.6):
        time.sleep(seconds)
        return proc.poll() is None


_hdhr_service = None


def get_service():
    return _hdhr_service


def init_service(channel_service, log_callback=None, settings_provider=None, data_dir=None):
    global _hdhr_service
    _hdhr_service = HdHomeRunService(channel_service, log_callback, settings_provider, data_dir)
    return _hdhr_service
