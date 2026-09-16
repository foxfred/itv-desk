import time
import re
import socket
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from app.utils.helpers import is_url_blacklisted, is_url_whitelisted


class CheckerEngine:

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

    _AD_KW = re.compile(
        r'(?:^|[/_\-\.])(ads?|adv|advert|adverts|advertise|guanggao|preroll|promo|tvc)(?:[/_\-\.]|$)',
        re.I
    )

    def __init__(self, manager, ui_callback, progress_callback, status_callback, stop_event):
        self.manager = manager
        self.ui = ui_callback
        self.progress = progress_callback
        self.status = status_callback
        self.stop = stop_event
        self.ad_flags = {}

    def _detect_placeholder_manifest(self, text):
        if not text or '#EXTM3U' not in text[:2048]:
            return None
        seg_lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')]
        for s in seg_lines:
            if self._AD_KW.search(s):
                return "ad_keyword"
        durs = []
        for m in re.findall(r'#EXTINF:\s*([\d.]+)', text):
            try:
                durs.append(float(m))
            except ValueError:
                pass
        total = sum(durs)
        n = len(seg_lines)
        if n and n <= 2 and total and total <= 30:
            return "short_loop"
        if '#EXT-X-ENDLIST' in text and (total < 900 or (n and n <= 10)):
            return "vod_loop"
        return None

    def run(self, items, thread_num=20, timeout=10, retries=2):
        total = len(items)
        processed = 0
        self.progress(0, total)
        self.status("检查中...")

        def check_one(ch):
            if self.stop and self.stop.is_set():
                return None
            url = ch.get("url", "")
            if not url:
                return (ch["id"], "离线", "无URL", "离线", "-", "-", "-", "-", None)

            t0 = time.time()
            if is_url_blacklisted(url):
                t = (ch["id"], "离线", "黑名单", "离线", "-", "-", "-", "-", None)
            elif is_url_whitelisted(url):
                t = (ch["id"], "在线", "白名单", "在线", "-", "-", "-", "-",
                     self._detect_stack(url), None)
            else:
                stream_proto = self._get_stream_protocol(url)
                if stream_proto:
                    t = self._check_stream_protocol(ch, url, t0, timeout, retries, stream_proto)
                else:
                    t = self._check_http_source(ch, url, t0, timeout, retries)
            ad_hits = {url: self.ad_flags[url]} if url in self.ad_flags else {}
            try:
                self.manager.update_channel(ch["id"], ad_suspect=ad_hits)
            except Exception:
                pass
            return (ch["id"], t[1], t[2], t[1], t[4], t[5], t[6], t[7], t[8])

        with ThreadPoolExecutor(max_workers=thread_num) as executor:
            futures = {executor.submit(check_one, ch): ch for ch in items}
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


    _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def _check_http_source(self, ch, url, t0, timeout, retries):
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

        watchable, first_frame_ms, detail, res, quality = self._probe_watchable(url, timeout, t0)
        ms = str(first_frame_ms) if first_frame_ms is not None else str(int((time.time() - t0) * 1000))
        if watchable:
            status = "在线"
            if code_disp in ("-",):
                code_disp = "200"
        else:
            status = "离线"
            code_disp = detail or "unwatchable"
        stack = self._detect_stack(url)
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
        url_lower = url.lower()
        if '.m3u8' in url_lower:
            return self._probe_hls(url, timeout, t0)
        return self._probe_direct_media(url, timeout, t0, max_bytes=65536)

    def _probe_direct_media(self, url, timeout, t0, max_bytes=65536):
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
            _read_deadline = time.time() + 5
            remaining = max_bytes - len(data)
            while remaining > 0 and time.time() < _read_deadline:
                more = resp.read(min(8192, remaining))
                if not more:
                    break
                data += more
                remaining = max_bytes - len(data)
            resp.close()

            if b'#EXTM3U' in data[:2048]:
                return True, first_frame_ms, "playlist", "-", "-"
            if not data or len(data) < 64:
                return False, first_frame_ms, "empty", "-", "-"
            if not self._looks_like_media(data, url):
                return False, first_frame_ms, "non_media", "-", "-"

            res, quality = "-", "-"
            if b'\x47' in data[:2048]:
                res, quality = self._resolution_from_ts_bytes(data)
            return True, first_frame_ms, "ok", res, quality
        except Exception as e:
            return False, None, f"probe_err:{str(e)[:24]}", "-", "-"

    def _probe_hls(self, url, timeout, t0):
        try:
            mreq = urllib.request.Request(
                url,
                headers={"User-Agent": self._UA, "Accept": "*/*", "Connection": "keep-alive"}
            )
            mresp = urllib.request.urlopen(mreq, timeout=min(timeout, 8))
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

            _reason = self._detect_placeholder_manifest(manifest)
            if _reason:
                self.ad_flags[url] = _reason

            res, quality = "-", "-"
            if '#EXT-X-STREAM-INF' in manifest:
                resolutions = re.findall(r'RESOLUTION=(\d+)x(\d+)', manifest)
                if resolutions:
                    mr = max(resolutions, key=lambda r: int(r[0]) * int(r[1]))
                    w, h = int(mr[0]), int(mr[1])
                    res, quality = self._format_resolution(w, h), self._get_quality(w, h)

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
                try:
                    vreq = urllib.request.Request(variant[0], headers={"User-Agent": self._UA})
                    vresp = urllib.request.urlopen(vreq, timeout=min(timeout, 8))
                    vdata = vresp.read(65536).decode('utf-8', errors='ignore')
                    vresp.close()
                    if not _reason:
                        _r2 = self._detect_placeholder_manifest(vdata)
                        if _r2:
                            self.ad_flags[url] = _r2
                    for line in vdata.splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            candidate = line if line.startswith('http') else urljoin(variant[0], line)
                            break
                except Exception:
                    candidate = None

            if not candidate:
                ff = int((time.time() - t0) * 1000)
                return True, ff, "manifest_only", res, quality

            watchable, ff, detail, sres, squal = self._probe_direct_media(candidate, timeout, t0, max_bytes=65536)
            if sres != "-":
                res, quality = sres, squal
            return watchable, ff, detail, res, quality
        except Exception as e:
            return False, None, f"probe_err:{str(e)[:24]}", "-", "-"

    def _looks_like_media(self, data, url):
        if len(data) < 64:
            return False
        head = data[:512].lstrip().lower()
        if head.startswith(b'<!doctype') or head.startswith(b'<html') or b'<title' in data[:1024].lower():
            return False
        if data[:3] == b'FLV':
            return True
        if data[:4] == b'ftyp' or data[4:8] == b'ftyp':
            return True
        if self._is_ts_data(data):
            return True
        sample = data[:4096]
        printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13))
        return (printable / len(sample)) < 0.55

    def _is_ts_data(self, data):
        if len(data) < 376:
            return data.count(b'\x47') >= 2
        cnt = 0
        for i in range(0, min(len(data), 1880), 188):
            if data[i] == 0x47:
                cnt += 1
        return cnt >= 3

    def _resolution_from_ts_bytes(self, data):
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


    def _get_stream_protocol(self, url):
        url_lower = url.lower()
        for prefix, config in self.STREAM_PROTOCOLS.items():
            if url_lower.startswith(prefix):
                return config
        return None

    def _check_stream_protocol(self, ch, url, t0, timeout, retries, stream_proto):
        proto_name, default_port, transport = stream_proto
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or default_port

        if not host:
            return (ch["id"], "离线", "无效地址", "离线", "-", "-", "-", "-", None)

        if transport == "udp":
            return self._check_udp_stream(ch, url, t0, timeout, retries, proto_name, host, port)

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
        try:
            addrs = socket.getaddrinfo(host, port or None, socket.AF_UNSPEC, socket.SOCK_DGRAM)
            if not addrs:
                return (ch["id"], "离线", "解析失败", "离线", "-", "-", "-", "-", None)

            ms = str(int((time.time() - t0) * 1000))
            stack = "IPv6" if ':' in addrs[0][4][0] else "IPv4"
            res, quality = self._detect_resolution(url, timeout)
            return (ch["id"], "未知", proto_name, "未知", ms, res, quality, stack, None)

        except socket.gaierror:
            return (ch["id"], "离线", "解析失败", "离线", "-", "-", "-", "-", None)
        except Exception as e:
            return (ch["id"], "离线", str(e)[:20], "离线", "-", "-", "-", "-", None)


    def _detect_resolution(self, url, timeout):
        width, height = self._detect_from_url_pattern(url)
        if width and height:
            return self._format_resolution(width, height), self._get_quality(width, height)

        width, height = self._detect_from_query_params(url)
        if width and height:
            return self._format_resolution(width, height), self._get_quality(width, height)

        if self._get_stream_protocol(url):
            return self._format_resolution(1920, 1080), self._get_quality(1920, 1080)

        if '.m3u8' in url:
            result = self._detect_hls_resolution(url, timeout)
            if result != ("-", "-"):
                return result
            return self._format_resolution(1920, 1080), self._get_quality(1920, 1080)

        url_lower = url.lower()
        if any(url_lower.endswith(ext) for ext in ('.ts', '.flv', '.mp4', '.xs', '.m3u')):
            result = self._detect_ts_resolution(url, timeout)
            if result != ("-", "-"):
                return result

        return self._format_resolution(1920, 1080), self._get_quality(1920, 1080)

    def _detect_from_url_pattern(self, url):
        url_lower = url.lower()

        # 2160p → 4K
        if '2160p' in url_lower:
            return 3840, 2160
        if re.search(r'(?:^|[^a-z0-9])4k(?:[^a-z0-9]|$)', url_lower) or '4k_' in url_lower or '_4k' in url_lower:
            return 3840, 2160

        # 1080p → FHD
        if '1080p' in url_lower:
            return 1920, 1080
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

        for num, w, h in [
            ('1080', 1920, 1080), ('1920', 1920, 1080),
            ('720', 1280, 720), ('1280', 1280, 720),
            ('2160', 3840, 2160), ('3840', 3840, 2160),
        ]:
            if re.search(rf'{num}\.(?:m3u8|ts|flv)', url_lower):
                return w, h

        for num, w, h in [
            ('1080', 1920, 1080), ('1920', 1920, 1080),
            ('720', 1280, 720), ('1280', 1280, 720),
            ('2160', 3840, 2160), ('3840', 3840, 2160),
        ]:
            if re.search(rf'(?:[/._-]|^){num}(?:[/._-]|\.m3u8|\.ts|\.flv|$)', url_lower):
                return w, h

        # 2K / 1440P
        if re.search(r'(?:^|[^a-z0-9])(2k|1440p|qhd)(?:[^a-z]|$)', url_lower):
            return 2560, 1440
        if re.search(r'2560\s*[x*×]\s*1440', url_lower):
            return 2560, 1440

        if re.search(r'1920\s*[x*×]\s*1080', url_lower):
            return 1920, 1080
        if re.search(r'1280\s*[x*×]\s*720', url_lower):
            return 1280, 720
        if re.search(r'3840\s*[x*×]\s*2160', url_lower):
            return 3840, 2160

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

        if re.search(r'hd(?:[/._-]|\d|\.m3u8|\.ts|$)', url_lower):
            return 1280, 720
        if re.search(r'_h\.(?:live|m3u8|ts)', url_lower):
            return 1280, 720
        if re.search(r'(?:[/._-]|^)high(?:[/._-]|\.m3u8|$)', url_lower):
            return 1280, 720
        if re.search(r'sd(?:[/._-]|\.m3u8|\.ts|$)', url_lower):
            return 854, 480
        if re.search(r'(?:[/._-]|^)low(?:[/._-]|\.m3u8|$)', url_lower):
            return 854, 480

        return None, None

    def _detect_from_query_params(self, url):
        url_lower = url.lower()

        size_match = re.search(r'[?&]size=(\d{3,4})\s*[x*×]\s*(\d{3,4})', url_lower)
        if size_match:
            w, h = int(size_match.group(1)), int(size_match.group(2))
            if w > 0 and h > 0 and w < 8192 and h < 8192:
                return w, h

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

            if '#EXT-X-STREAM-INF' in data:
                resolutions = re.findall(r'RESOLUTION=(\d+)x(\d+)', data)
                if resolutions:
                    max_res = max(resolutions, key=lambda r: int(r[0]) * int(r[1]))
                    width, height = int(max_res[0]), int(max_res[1])
                    return self._format_resolution(width, height), self._get_quality(width, height)

            ts_urls = self._extract_ts_urls(data, url)
            if ts_urls:
                for ts_url in ts_urls:
                    w, h = self._detect_from_url_pattern(ts_url)
                    if w and h:
                        return self._format_resolution(w, h), self._get_quality(w, h)

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
        urls = []
        for line in m3u8_content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('http'):
                full_url = urljoin(base_url, line)
                urls.append(full_url)
            elif line and line.startswith('http'):
                urls.append(line)
        return urls

    def _detect_ts_resolution(self, url, timeout):
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