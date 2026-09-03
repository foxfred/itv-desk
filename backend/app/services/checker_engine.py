"""检查引擎 - 检测频道链接可用性、延迟、分辨率、质量"""
import time
import re
import socket
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse


class CheckerEngine:
    """频道可用性检查引擎：多线程检测 URL 可达性，测量延迟和分辨率"""

    # 非 HTTP(S) 直播流协议配置：协议前缀 → (协议名, 默认端口, 传输层)
    STREAM_PROTOCOLS = {
        "rtmp://":  ("RTMP",  1935, "tcp"),
        "rtmps://": ("RTMPS", 1935, "tcp"),
        "rtsp://":  ("RTSP",  554,  "tcp"),
        "rtsps://": ("RTSPS", 322,  "tcp"),
        "srt://":   ("SRT",   9000, "udp"),
        "udp://":   ("UDP",   0,    "udp"),
        "rtp://":   ("RTP",   0,    "udp"),
        "mms://":   ("MMS",   1755, "tcp"),
        "mmst://":  ("MMST",  1755, "tcp"),
    }

    def __init__(self, manager, ui_callback, progress_callback, status_callback, stop_event):
        self.manager = manager
        self.ui = ui_callback
        self.progress = progress_callback
        self.status = status_callback
        self.stop = stop_event

    def run(self, items, thread_num=20, timeout=10, retries=2):
        """执行检查"""
        total = len(items)
        processed = 0
        self.progress(0, total)
        self.status("检查中...")

        def check_one(ch):
            if self.stop and self.stop.is_set():
                return None
            # 多源故障转移：频道可能携带 sources 列表，逐源检测后聚合整体状态
            sources = ch.get("sources") or []
            sources = [s for s in sources if s]
            if not sources:
                single = ch.get("url", "")
                if not single:
                    return (ch["id"], "离线", "无URL", "离线", "-", "-", "-", "-", None)
                sources = [single]

            t0 = time.time()
            per = []  # (url, (ch_id, status, code, _, ms, res, quality, stack, ff))
            for s in sources:
                stream_proto = self._get_stream_protocol(s)
                if stream_proto:
                    t = self._check_stream_protocol(ch, s, t0, timeout, retries, stream_proto)
                else:
                    t = self._check_http_source(ch, s, t0, timeout, retries)
                per.append((s, t))

            # 聚合：任一源在线则频道在线；展示取首个在线源的数据
            online = [(u, t) for u, t in per if t[1] == "在线"]
            best_u, best = (online[0] if online else per[0])
            source_health = {
                u: {"status": t[1], "ms": t[4], "res": t[5], "quality": t[6], "code": t[2]}
                for u, t in per
            }
            try:
                self.manager.update_channel(ch["id"], source_health=source_health)
            except Exception:
                pass
            return (ch["id"], best[1], best[2], best[1], best[4], best[5], best[6], best[7], best[8])

        with ThreadPoolExecutor(max_workers=thread_num) as executor:
            futures = {executor.submit(check_one, ch): ch for ch in items}
            # 每个任务最多等 timeout + 5 秒（HEAD + 探测），取整加兜底
            _task_timeout = timeout + 10
            for future in as_completed(futures, timeout=total * (_task_timeout / thread_num + 2)):
                if self.stop and self.stop.is_set():
                    break
                result = future.result()
                if result:
                    ch_id, status, code, _, ms, res, quality, stack, first_frame_ms = result
                    update_kwargs = {"status": status, "code": code, "checked": True, "ms": ms, "res": res, "quality": quality}
                    if stack and stack != "-":
                        update_kwargs["stack"] = stack
                    self.manager.update_channel(ch_id, **update_kwargs)
                    # 回写健康度：检测在线=成功，离线=失败（连续失败由 update_health 判定死源）；
                    # 首包延迟 first_frame_ms 一并回写，供健康度评分与死源判定参考
                    try:
                        self.manager.update_health(channel_id=ch_id, success=(status == "在线"), first_frame_ms=first_frame_ms)
                    except Exception:
                        pass
                processed += 1
                self.progress(processed, total)

        if self.stop and self.stop.is_set():
            self.status("已停止")
        else:
            self.status("检查完成")

    # ==================== HTTP(S) 真实可看性探测 ====================
    # 旧版仅测 HEAD 200 即判"在线"，会放过返回 200 但实为 HTML 错误页/空数据的假源。
    # 本组方法在可达性通过后，实际 GET 拉取一小段媒体数据，校验确为可解流的真实媒体，
    # 并测量首包延迟（first_frame_ms）回写健康度。

    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def _check_http_source(self, ch, url, t0, timeout, retries):
        """HTTP(S) 源检测：HEAD 快速可达性 + 真实可看性探测。

        返回 9 元组：(ch_id, status, code, status, ms, res, quality, stack, first_frame_ms)
        """
        code_disp = "-"
        for attempt in range(retries):
            if self.stop and self.stop.is_set():
                return None
            try:
                req = urllib.request.Request(
                    url, method="HEAD",
                    headers={"User-Agent": self._UA}
                )
                resp = urllib.request.urlopen(req, timeout=timeout)
                code = resp.status
                resp.close()
                # 4xx/5xx（403 除外，很多 CDN 禁 HEAD 需经 GET 再判）直接离线
                if code >= 400 and code != 403:
                    return (ch["id"], "离线", str(code), "离线", "-", "-", "-", "-", None)
                code_disp = str(code)
                break
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    code_disp = "403"
                    break
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                return (ch["id"], "离线", str(e.code), "离线", "-", "-", "-", "-", None)
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                return (ch["id"], "离线", str(e)[:20], "离线", "-", "-", "-", "-", None)

        # 真实可看性探测（实际拉取媒体数据并校验）
        watchable, first_frame_ms, detail, res, quality = self._probe_watchable(url, timeout, t0)
        ms = str(first_frame_ms) if first_frame_ms is not None else str(int((time.time() - t0) * 1000))
        if watchable:
            status = "在线"
            if code_disp in ("-",):
                code_disp = "200"
        else:
            status = "离线"
            # HTTP 可达但媒体无效：用探测原因替代状态码，便于前端辨识假源
            code_disp = detail or "unwatchable"
        stack = self._detect_stack(url)
        # 分辨率兜底：探测未取得时，仅用零网络的 URL 模式/查询参数推断
        if res in ("-", None):
            r2, q2 = self._detect_from_url_pattern(url)
            if r2:
                res, quality = r2, q2
            else:
                r3, q3 = self._detect_from_query_params(url)
                if r3:
                    res, quality = r3, q3
        return (ch["id"], status, code_disp, status, ms, res, quality, stack, first_frame_ms)

    def _probe_watchable(self, url, timeout, t0):
        """真实可看性探测入口：HLS 走 manifest+segment，其余按直接媒体处理。
        返回 (watchable, first_frame_ms, detail, res, quality)。"""
        url_lower = url.lower()
        if '.m3u8' in url_lower:
            return self._probe_hls(url, timeout, t0)
        return self._probe_direct_media(url, timeout, t0, max_bytes=65536)

    def _probe_direct_media(self, url, timeout, t0, max_bytes=65536):
        """实际 GET 拉取首段媒体数据，测首包延迟并校验是否真为媒体流。"""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self._UA,
                    "Range": "bytes=0-65535",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                }
            )
            resp = urllib.request.urlopen(req, timeout=min(timeout, 8))
            chunk = resp.read(8192)
            first_frame_ms = int((time.time() - t0) * 1000)
            data = chunk
            # 限制总读取时间不超过 5 秒，避免大文件/慢响应卡住整个检查
            _read_deadline = time.time() + 5
            remaining = max_bytes - len(data)
            while remaining > 0 and time.time() < _read_deadline:
                more = resp.read(min(8192, remaining))
                if not more:
                    break
                data += more
                remaining = max_bytes - len(data)
            resp.close()

            # 纯文本 playlist（.m3u 直链等）——可达但需二次解析，保守判可看
            if b'#EXTM3U' in data[:2048]:
                return True, first_frame_ms, "playlist", "-", "-"
            if not data or len(data) < 64:
                return False, first_frame_ms, "empty", "-", "-"
            if not self._looks_like_media(data, url):
                return False, first_frame_ms, "non_media", "-", "-"

            # 媒体有效：尝试从 TS 数据解析分辨率
            res, quality = "-", "-"
            if b'\x47' in data[:2048]:
                res, quality = self._resolution_from_ts_bytes(data)
            return True, first_frame_ms, "ok", res, quality
        except Exception as e:
            return False, None, f"probe_err:{str(e)[:24]}", "-", "-"

    def _probe_hls(self, url, timeout, t0):
        """HLS 真实可看性：下载 manifest → 取 segment → 验证可下载且为真媒体。"""
        try:
            mreq = urllib.request.Request(
                url,
                headers={"User-Agent": self._UA, "Accept": "*/*", "Connection": "keep-alive"}
            )
            mresp = urllib.request.urlopen(mreq, timeout=min(timeout, 8))
            # 限制 manifest 读取不超过 5 秒
            _mf_dead = time.time() + 5
            manifest = b''
            while len(manifest) < 131072 and time.time() < _mf_dead:
                more = mresp.read(32768)
                if not more:
                    break
                manifest += more
            manifest = manifest.decode('utf-8', errors='ignore')
            mresp.close()
            if not manifest.strip():
                return False, None, "manifest_empty", "-", "-"

            # 从 master playlist 解析最高分辨率
            res, quality = "-", "-"
            if '#EXT-X-STREAM-INF' in manifest:
                resolutions = re.findall(r'RESOLUTION=(\d+)x(\d+)', manifest)
                if resolutions:
                    mr = max(resolutions, key=lambda r: int(r[0]) * int(r[1]))
                    w, h = int(mr[0]), int(mr[1])
                    res, quality = self._format_resolution(w, h), self._get_quality(w, h)

            # 提取 segment / 子 playlist
            seg, variant = [], []
            for line in manifest.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                full = line if line.startswith('http') else urljoin(url, line)
                if '.m3u8' in full:
                    variant.append(full)
                else:
                    seg.append(full)

            candidate = seg[0] if seg else None
            if not candidate and variant:
                # master playlist：取第一个变体的首个 segment
                try:
                    vreq = urllib.request.Request(variant[0], headers={"User-Agent": self._UA})
                    vresp = urllib.request.urlopen(vreq, timeout=min(timeout, 8))
                    vdata = vresp.read(65536).decode('utf-8', errors='ignore')
                    vresp.close()
                    for line in vdata.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            candidate = line if line.startswith('http') else urljoin(variant[0], line)
                            break
                except Exception:
                    candidate = None

            if not candidate:
                # 仅 manifest 可达（无 segment 信息）—— 保守判可看
                ff = int((time.time() - t0) * 1000)
                return True, ff, "manifest_only", res, quality

            watchable, ff, detail, sres, squal = self._probe_direct_media(candidate, timeout, t0, max_bytes=65536)
            if sres != "-":
                res, quality = sres, squal
            return watchable, ff, detail, res, quality
        except Exception as e:
            return False, None, f"probe_err:{str(e)[:24]}", "-", "-"

    def _looks_like_media(self, data, url):
        """校验字节是否真实媒体流（排除 HTML 错误页 / 纯文本）。"""
        if len(data) < 64:
            return False
        head = data[:512].lstrip().lower()
        if head.startswith(b'<!doctype') or head.startswith(b'<html') or b'<title' in data[:1024].lower():
            return False
        # 已知容器特征
        if data[:3] == b'FLV':
            return True
        if data[:4] == b'ftyp' or data[4:8] == b'ftyp':
            return True
        if self._is_ts_data(data):
            return True
        # 兜底：二进制占比高（不可打印字符多）视为媒体
        sample = data[:4096]
        printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
        return (printable / len(sample)) < 0.55

    def _is_ts_data(self, data):
        """TS 流判定：0x47 同步字节按 188 字节间隔出现。"""
        if len(data) < 376:
            return data.count(b'\x47') >= 2
        cnt = 0
        for i in range(0, min(len(data), 1880), 188):
            if data[i] == 0x47:
                cnt += 1
        return cnt >= 3

    def _resolution_from_ts_bytes(self, data):
        """从已下载的 TS 字节中解析 H.264 SPS 分辨率。"""
        for marker, off in [(b'\x00\x00\x00\x01\x67', 5), (b'\x00\x00\x01\x67', 4)]:
            idx = data.find(marker)
            if idx != -1 and idx + off + 2 < len(data):
                sps = data[idx + off:idx + off + 20]
                w, h = self._parse_sps(sps)
                if w and h:
                    return self._format_resolution(w, h), self._get_quality(w, h)
        return "-", "-"

    def _detect_stack(self, url):
        if re.search(r'\[[0-9a-fA-F:]+\]', url):
            return "IPv6"
        if re.search(r'(?<!\d)([0-9a-fA-F]{1,4}:){2,}[0-9a-fA-F]{1,4}', url):
            return "IPv6"
        return "IPv4"

    # ==================== 流协议检测 ====================

    def _get_stream_protocol(self, url):
        """检测 URL 是否使用非 HTTP(S) 直播流协议，返回 (协议名, 默认端口, 传输层) 或 None"""
        url_lower = url.lower()
        for prefix, config in self.STREAM_PROTOCOLS.items():
            if url_lower.startswith(prefix):
                return config
        return None

    def _check_stream_protocol(self, ch, url, t0, timeout, retries, stream_proto):
        """统一的非 HTTP 流协议检测：TCP 用 socket 连接，UDP 用 DNS 解析"""
        proto_name, default_port, transport = stream_proto
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or default_port

        if not host:
            return (ch["id"], "离线", "无效地址", "离线", "-", "-", "-", "-", None)

        # UDP 协议无法建立连接，仅做 DNS 解析
        if transport == "udp":
            return self._check_udp_stream(ch, url, t0, timeout, retries, proto_name, host, port)

        # TCP 协议：尝试 socket 连接
        for attempt in range(retries):
            if self.stop and self.stop.is_set():
                return None
            try:
                stack = "IPv6" if ':' in host else "IPv4"
                sock = socket.create_connection((host, port), timeout=min(timeout, 5))
                sock.close()
                ms = str(int((time.time() - t0) * 1000))
                res, quality = self._detect_resolution(url, timeout)
                return (ch["id"], "在线", proto_name, "在线", ms, res, quality, stack, None)

            except (socket.timeout, ConnectionRefusedError, OSError):
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                ms = str(int((time.time() - t0) * 1000))
                return (ch["id"], "离线", "连接失败", "离线", ms, "-", "-", "-", None)
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                ms = str(int((time.time() - t0) * 1000))
                return (ch["id"], "离线", str(e)[:20], "离线", ms, "-", "-", "-", None)

    def _check_udp_stream(self, ch, url, t0, timeout, retries, proto_name, host, port):
        """UDP 流协议检测：无法验证连接，仅做 DNS 解析 + URL 模式匹配"""
        try:
            # DNS 解析
            addrs = socket.getaddrinfo(host, port or None, socket.AF_UNSPEC, socket.SOCK_DGRAM)
            if not addrs:
                return (ch["id"], "离线", "解析失败", "离线", "-", "-", "-", "-", None)

            ms = str(int((time.time() - t0) * 1000))
            stack = "IPv6" if ':' in addrs[0][4][0] else "IPv4"
            res, quality = self._detect_resolution(url, timeout)
            # UDP 无法验证服务是否在线，标记为"未知"而非"在线"
            return (ch["id"], "未知", proto_name, "未知", ms, res, quality, stack, None)

        except socket.gaierror:
            return (ch["id"], "离线", "解析失败", "离线", "-", "-", "-", "-", None)
        except Exception as e:
            return (ch["id"], "离线", str(e)[:20], "离线", "-", "-", "-", "-", None)

    # ==================== 分辨率检测 ====================

    def _detect_resolution(self, url, timeout):
        """多层级分辨率检测，无法检测时默认返回 1080P"""
        # 第1层：URL 特征匹配（最快，覆盖大部分频道，对所有协议有效）
        width, height = self._detect_from_url_pattern(url)
        if width and height:
            return self._format_resolution(width, height), self._get_quality(width, height)

        # 第2层：URL 查询参数中的分辨率/码率信息
        width, height = self._detect_from_query_params(url)
        if width and height:
            return self._format_resolution(width, height), self._get_quality(width, height)

        # 非 HTTP(S) 流协议无法下载流数据，仅靠 URL 模式匹配
        if self._get_stream_protocol(url):
            return self._format_resolution(1920, 1080), self._get_quality(1920, 1080)

        # 第3层：HLS playlist 解析（m3u8 格式）
        if '.m3u8' in url:
            result = self._detect_hls_resolution(url, timeout)
            if result != ("-", "-"):
                return result
            # HLS 下载失败，默认 1080P
            return self._format_resolution(1920, 1080), self._get_quality(1920, 1080)

        # 第4层：直接下载流数据解析 SPS（TS/FLV/其他流格式）
        url_lower = url.lower()
        if any(url_lower.endswith(ext) for ext in ('.ts', '.flv', '.mp4', '.xs', '.m3u')):
            result = self._detect_ts_resolution(url, timeout)
            if result != ("-", "-"):
                return result

        # 无法检测，默认 1080P
        return self._format_resolution(1920, 1080), self._get_quality(1920, 1080)

    def _detect_from_url_pattern(self, url):
        """从 URL 中提取分辨率线索（多层级匹配，覆盖各种 CDN 命名规范）"""
        url_lower = url.lower()

        # ============ 优先级1：带 p/k 后缀的精确分辨率标签（几乎零误匹配）============
        # 2160p → 4K
        if '2160p' in url_lower:
            return 3840, 2160
        # 4k（需要边界检查，避免匹配到如 "4kbps" 之类的）
        if re.search(r'(?:^|[^a-z0-9])4k(?:[^a-z0-9]|$)', url_lower) or '4k_' in url_lower or '_4k' in url_lower:
            return 3840, 2160

        # 1080p → FHD
        if '1080p' in url_lower:
            return 1920, 1080
        # fhd / fullhd（常见于 CDN 命名）
        if 'fhd' in url_lower or 'fullhd' in url_lower:
            return 1920, 1080

        # 720p → HD
        if '720p' in url_lower:
            return 1280, 720

        # 480p → SD
        if '480p' in url_lower:
            return 854, 480

        # 360p
        if '360p' in url_lower:
            return 640, 360

        # 576p
        if '576p' in url_lower:
            return 1024, 576

        # ============ 优先级2：数字紧邻扩展名之前（如 rtdru1080.m3u8, playlist1080p.m3u8）============
        for num, w, h in [
            ('1080', 1920, 1080), ('1920', 1920, 1080),
            ('720', 1280, 720), ('1280', 1280, 720),
            ('2160', 3840, 2160), ('3840', 3840, 2160),
        ]:
            if re.search(rf'{num}\.(?:m3u8|ts|flv)', url_lower):
                return w, h

        # ============ 优先级3：数字在路径分隔符边界（如 /1080/playlist.m3u8, _720_）============
        for num, w, h in [
            ('1080', 1920, 1080), ('1920', 1920, 1080),
            ('720', 1280, 720), ('1280', 1280, 720),
            ('2160', 3840, 2160), ('3840', 3840, 2160),
        ]:
            if re.search(rf'(?:[/._-]|^){num}(?:[/._-]|\.m3u8|\.ts|\.flv|$)', url_lower):
                return w, h

        # ============ 优先级4：传统分辨率关键词 ============
        # 2K / 1440P
        if re.search(r'(?:^|[^a-z0-9])(2k|1440p|qhd)(?:[^a-z]|$)', url_lower):
            return 2560, 1440
        if re.search(r'2560\s*[x*×]\s*1440', url_lower):
            return 2560, 1440

        # 1080×1920 格式
        if re.search(r'1920\s*[x*×]\s*1080', url_lower):
            return 1920, 1080
        # 1280×720 格式
        if re.search(r'1280\s*[x*×]\s*720', url_lower):
            return 1280, 720
        # 3840×2160 格式
        if re.search(r'3840\s*[x*×]\s*2160', url_lower):
            return 3840, 2160

        # ============ 优先级5：码率推断（常用于 CDN 流）============
        # douyu CDN: _4000.xs → 1080P, _2000.xs → 720P
        # RT playlist: playlist_4500Kb.m3u8 → 4K
        bitrate_match = re.search(r'[_-](\d{3,4})\s*\.?\s*(?:xs|kb|kbps|k)', url_lower)
        if bitrate_match:
            br = int(bitrate_match.group(1))
            if br >= 4000:
                return 3840, 2160
            if br >= 2500:
                return 1920, 1080
            if br >= 1500:
                return 1280, 720
            if br >= 800:
                return 854, 480
            return 640, 360

        # ============ 优先级6：路径中的数字分辨率线索（如 /1500.m3u8, /2500.m3u8）============
        path_match = re.search(r'/(\d{3,4})\s*\.\s*m3u8', url_lower)
        if path_match:
            num = int(path_match.group(1))
            if num >= 4000:
                return 3840, 2160
            if num >= 2000:
                return 1920, 1080
            if num >= 1000:
                return 1280, 720
            if num >= 500:
                return 854, 480

        # ============ 优先级7：hd/sd 质量标记（宽松匹配，覆盖嵌入词中的情况）============
        # hd 标记：bltvhd/bltv1, ynws-hd, tjwshd.m3u8, sxwshd.m3u8, freehd209_h.live
        if re.search(r'hd(?:[/._-]|\d|\.m3u8|\.ts|$)', url_lower):
            return 1280, 720
        # _h. 模式（如 freehd209_h.live → _h 表示高清）
        if re.search(r'_h\.(?:live|m3u8|ts)', url_lower):
            return 1280, 720
        if re.search(r'(?:[/._-]|^)high(?:[/._-]|\.m3u8|$)', url_lower):
            return 1280, 720
        # sd 标记：xjws-sd/1500
        if re.search(r'sd(?:[/._-]|\.m3u8|\.ts|$)', url_lower):
            return 854, 480
        if re.search(r'(?:[/._-]|^)low(?:[/._-]|\.m3u8|$)', url_lower):
            return 854, 480

        return None, None

    def _detect_from_query_params(self, url):
        """从 URL 查询参数中提取分辨率/码率线索"""
        url_lower = url.lower()

        # size=1920x1080, size=1280X720 等
        size_match = re.search(r'[?&]size=(\d{3,4})\s*[x*×]\s*(\d{3,4})', url_lower)
        if size_match:
            w, h = int(size_match.group(1)), int(size_match.group(2))
            if w > 0 and h > 0 and w < 8192 and h < 8192:
                return w, h

        # fmt=x264_1200K_ts → 码率推断
        fmt_match = re.search(r'[?&]fmt=x264_(\d{3,4})k', url_lower)
        if fmt_match:
            br = int(fmt_match.group(1))
            if br >= 2500:
                return 1920, 1080
            if br >= 1200:
                return 1280, 720
            if br >= 600:
                return 854, 480
            return 640, 360

        # resolution=1920x1080
        res_match = re.search(r'[?&]resolution=(\d{3,4})\s*[x*×]\s*(\d{3,4})', url_lower)
        if res_match:
            w, h = int(res_match.group(1)), int(res_match.group(2))
            if w > 0 and h > 0 and w < 8192 and h < 8192:
                return w, h

        # vtype=hd, quality=hd, q=hd
        for param in ['vtype', 'quality', 'q', 'defn', 'definition']:
            m = re.search(rf'[?&]{param}=(hd|high|fhd|fullhd|1080p|720p|480p|sd|4k)', url_lower)
            if m:
                val = m.group(1)
                if val in ('4k',):
                    return 3840, 2160
                if val in ('fhd', 'fullhd', '1080p', 'hd', 'high'):
                    return 1920, 1080
                if val in ('720p',):
                    return 1280, 720
                if val in ('480p', 'sd'):
                    return 854, 480

        return None, None

    def _detect_hls_resolution(self, url, timeout):
        """解析 HLS playlist 获取分辨率"""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                }
            )
            resp = urllib.request.urlopen(req, timeout=min(timeout, 8))
            data = resp.read(131072).decode('utf-8', errors='ignore')
            resp.close()

            if not data.strip():
                return "-", "-"

            # master playlist：提取最高分辨率
            if '#EXT-X-STREAM-INF' in data:
                resolutions = re.findall(r'RESOLUTION=(\d+)x(\d+)', data)
                if resolutions:
                    max_res = max(resolutions, key=lambda r: int(r[0]) * int(r[1]))
                    width, height = int(max_res[0]), int(max_res[1])
                    return self._format_resolution(width, height), self._get_quality(width, height)

            # 简单 playlist：从 TS 段 URL 中提取分辨率线索
            ts_urls = self._extract_ts_urls(data, url)
            if ts_urls:
                # 第1步：从 TS 段 URL 文件名中提取分辨率（如 xxx_720p.ts, xxx_1080p.ts）
                for ts_url in ts_urls:
                    w, h = self._detect_from_url_pattern(ts_url)
                    if w and h:
                        return self._format_resolution(w, h), self._get_quality(w, h)

                # 第2步：尝试下载 TS 段解析 SPS（尝试多个 TS 段）
                for ts_url in ts_urls[:5]:
                    if self.stop and self.stop.is_set():
                        return "-", "-"
                    result = self._detect_ts_resolution(ts_url, timeout)
                    if result != ("-", "-"):
                        return result

            return "-", "-"
        except Exception:
            return "-", "-"

    def _extract_ts_urls(self, m3u8_content, base_url):
        """从简单 playlist 中提取 TS 段 URL 列表"""
        urls = []
        for line in m3u8_content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('http'):
                # 相对路径，需要拼接
                full_url = urljoin(base_url, line)
                urls.append(full_url)
            elif line and line.startswith('http'):
                urls.append(line)
        return urls

    def _detect_ts_resolution(self, url, timeout):
        """从 TS/FLV 流中检测 H.264 SPS 分辨率"""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Range": "bytes=0-65536",
                }
            )
            resp = urllib.request.urlopen(req, timeout=min(timeout, 5))
            data = resp.read(65536)
            resp.close()

            # 查找 H.264 SPS NAL unit
            for marker, off in [(b'\x00\x00\x00\x01\x67', 5), (b'\x00\x00\x01\x67', 4)]:
                idx = data.find(marker)
                if idx != -1 and idx + off + 2 < len(data):
                    sps_data = data[idx + off:idx + off + 20]
                    width, height = self._parse_sps(sps_data)
                    if width and height:
                        return self._format_resolution(width, height), self._get_quality(width, height)

            return "-", "-"
        except Exception:
            return "-", "-"

    def _parse_sps(self, sps_data):
        """从 H.264 SPS 数据中解析宽高（exp-golomb 解码）"""
        try:
            bits = []
            for b in sps_data:
                for i in range(7, -1, -1):
                    bits.append((b >> i) & 1)

            pos = 0

            def read_bits(n):
                nonlocal pos
                if pos + n > len(bits):
                    return 0
                val = 0
                for _ in range(n):
                    val = (val << 1) | bits[pos]
                    pos += 1
                return val

            def read_ue():
                zeros = 0
                while pos < len(bits) and bits[pos] == 0:
                    zeros += 1
                    pos += 1
                if pos >= len(bits):
                    return 0
                pos += 1
                val = 0
                for _ in range(zeros):
                    val = (val << 1) | bits[pos]
                    pos += 1
                return (1 << zeros) - 1 + val

            pos = 24
            read_ue()

            profile_idc = sps_data[0] if len(sps_data) > 0 else 0
            if profile_idc in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
                chroma_format_idc = read_ue()
                if chroma_format_idc == 3:
                    read_bits(1)
                read_ue()
                read_ue()
                read_bits(1)
                if read_bits(1):
                    for _ in range(8 if chroma_format_idc != 3 else 12):
                        if read_bits(1):
                            pass

            read_ue()
            pic_order_cnt_type = read_ue()
            if pic_order_cnt_type == 0:
                read_ue()
            elif pic_order_cnt_type == 1:
                read_bits(1)
                read_ue()
                read_ue()
                num_ref_frames = read_ue()
                for _ in range(num_ref_frames):
                    read_ue()

            read_ue()
            read_bits(1)

            pic_width_in_mbs = read_ue() + 1
            pic_height_in_map_units = read_ue() + 1
            frame_mbs_only = read_bits(1)

            if not frame_mbs_only:
                read_bits(1)

            width = pic_width_in_mbs * 16
            height = (2 - frame_mbs_only) * pic_height_in_map_units * 16

            if width > 0 and height > 0 and width < 8192 and height < 8192:
                return width, height

            return None, None
        except Exception:
            return None, None

    def _format_resolution(self, width, height):
        if not width or not height:
            return "-"
        resolutions = {
            (7680, 4320): "8K",
            (3840, 2160): "4K",
            (2560, 1440): "2K",
            (1920, 1080): "1080P",
            (1280, 720): "720P",
            (1024, 576): "576P",
            (854, 480): "480P",
            (720, 576): "576P",
            (720, 480): "480P",
            (640, 360): "360P",
        }
        for (w, h), label in resolutions.items():
            if abs(width - w) <= 16 and abs(height - h) <= 16:
                return label
        if width >= 3840:
            return "4K+"
        if width >= 1920:
            return f"{height}P"
        if width >= 1280:
            return "720P"
        if width >= 854:
            return "480P"
        return f"{width}x{height}"

    def _get_quality(self, width, height):
        if width >= 3840:
            return "超清"
        if width >= 1920:
            return "高清"
        if width >= 1280:
            return "标清"
        if width >= 854:
            return "流畅"
        return "低清"