"""网段扫描服务 - 从频道链接反推 IP 段并批量探测发现源"""
import re
import time
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from app.utils.network import http_probe_channel
from app.config import Config


def _looks_like_ip(host):
    """host 是否为 IPv4/IPv6 地址（非域名）"""
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _default_port(scheme):
    """根据协议返回默认端口"""
    scheme = (scheme or "http").lower()
    if scheme in ("http",):
        return 80
    if scheme in ("https",):
        return 443
    if scheme == "rtmp":
        return 1935
    if scheme == "rtsp":
        return 554
    return 80


def _parse_template(template):
    """
    解析 IP 段模板，返回 (ips, port)。
    支持格式：
      - 192.168.1.{1-254}:8080
      - 192.168.1.1-192.168.1.254
      - 192.168.1.0/24
      - 192.168.1.1-254
    端口可省略，默认 80。
    """
    if not template:
        return [], 80
    template = template.strip()

    # 拆分端口
    port = 80
    if template.rsplit(":", 1)[-1].isdigit():
        host_part, port_str = template.rsplit(":", 1)
        try:
            port = int(port_str)
            template = host_part
        except ValueError:
            pass

    ips = []

    # CIDR: 192.168.1.0/24
    if "/" in template:
        try:
            net = ipaddress.ip_network(template, strict=False)
            # 跳过网络地址和广播地址
            for h in net.hosts():
                ips.append(str(h))
            return ips, port
        except ValueError:
            pass

    # 花括号范围: 192.168.1.{1-254}
    brace_match = re.match(r'^(\d+\.\d+\.\d+)\.\{(\d+)-(\d+)\}$', template)
    if brace_match:
        prefix = brace_match.group(1)
        start = int(brace_match.group(2))
        end = int(brace_match.group(3))
        for i in range(start, end + 1):
            ips.append(f"{prefix}.{i}")
        return ips, port

    # 起始-结束 IP: 192.168.1.1-192.168.1.254
    dash_match = re.match(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)-(\d+)\.(\d+)\.(\d+)\.(\d+)$', template)
    if dash_match:
        a, b, c, d, a2, b2, c2, d2 = (int(dash_match.group(i)) for i in range(1, 9))
        try:
            start = ipaddress.IPv4Address(f"{a}.{b}.{c}.{d}")
            end = ipaddress.IPv4Address(f"{a2}.{b2}.{c2}.{d2}")
            if end < start:
                start, end = end, start
            cur = start
            while cur <= end:
                ips.append(str(cur))
                cur += 1
            return ips, port
        except ValueError:
            pass

    # 最后一段范围: 192.168.1.1-254
    short_dash = re.match(r'^(\d+\.\d+\.\d+)\.(\d+)-(\d+)$', template)
    if short_dash:
        prefix = short_dash.group(1)
        start = int(short_dash.group(2))
        end = int(short_dash.group(3))
        for i in range(start, end + 1):
            ips.append(f"{prefix}.{i}")
        return ips, port

    # 单个 IP
    try:
        ipaddress.ip_address(template)
        ips.append(template)
        return ips, port
    except ValueError:
        pass

    return [], port


def derive_templates(urls):
    """
    从 URL 列表反推可扫描的 IP 段模板。
    仅处理 host 为 IP 的 URL；域名无法反推段。
    返回 [{url, host, template, port, path, scheme}, ...]
    """
    templates = []
    seen = set()
    for url in urls:
        if not url:
            continue
        try:
            parsed = urlparse(url.strip())
        except Exception:
            continue
        host = parsed.hostname
        if not _looks_like_ip(host):
            continue
        scheme = parsed.scheme or "http"
        port = parsed.port or _default_port(scheme)
        path = parsed.path or "/"
        # C 段模板
        octets = host.split('.')
        if len(octets) != 4:
            continue
        prefix = '.'.join(octets[:3])
        template = f"{prefix}.{{1-254}}:{port}"
        key = (template, port, path, scheme)
        if key in seen:
            continue
        seen.add(key)
        templates.append({
            "url": url,
            "host": host,
            "template": template,
            "port": port,
            "path": path,
            "scheme": scheme,
        })
    return templates


class ScanService:
    """网段扫描服务：按模板批量探测 IP:port，发现直播源"""

    def __init__(self, log_callback=None, settings=None):
        self.log_callback = log_callback or (lambda msg: None)
        self._settings = settings or {}

    def derive_templates(self, urls):
        """从频道 URL 列表反推可扫描的 IP 段模板（转发到模块级函数）"""
        return derive_templates(urls)

    def scan(self, template, path="/", scheme="http", proxy=None, timeout=None, max_workers=None):
        """
        扫描指定 IP 段模板，返回每个探测点的结果列表。
        结果项：{ip, port, url, status_code, ms, online, error}
        """
        ips, port = _parse_template(template)
        if not ips:
            return []

        if timeout is None:
            timeout = int(self._settings.get("scan_timeout", 5))
        if max_workers is None:
            max_workers = int(self._settings.get("scan_max_workers", 40))
        # 限制并发不超过 IP 数，且避免过大
        max_workers = max(1, min(max_workers, len(ips), 200))

        results = []

        def probe_one(ip):
            url = f"{scheme}://{ip}:{port}{path}"
            start = time.time()
            try:
                online, code, elapsed, res = http_probe_channel(
                    url, timeout=timeout, retries=1, proxy=proxy)
            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                return {
                    "ip": ip, "port": port, "url": url,
                    "status_code": None, "ms": elapsed,
                    "online": False, "error": str(e), "res": "-"
                }
            return {
                "ip": ip, "port": port, "url": url,
                "status_code": code, "ms": elapsed,
                "online": online, "error": "", "res": res or "-"
            }

        self.log_callback(f"开始扫描 {len(ips)} 个 IP:port ({template})")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(probe_one, ip): ip for ip in ips}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    ip = futures[future]
                    results.append({
                        "ip": ip, "port": port,
                        "url": f"{scheme}://{ip}:{port}{path}",
                        "status_code": None, "ms": 0,
                        "online": False, "error": str(e), "res": "-"
                    })

        online_count = sum(1 for r in results if r["online"])
        self.log_callback(f"扫描完成：在线 {online_count} / 共 {len(results)}")
        return results

    def import_results(self, channel_service, results, origin="scan"):
        """
        将扫描结果（在线项）导入频道池。
        results: scan 返回的列表；默认只导入 online=True 的项。
        返回 (added, dup)。
        """
        channels = []
        for r in results:
            if not r.get("online"):
                continue
            url = r["url"]
            name = f"扫描_{r['ip']}:{r['port']}"
            channels.append({
                "name": name,
                "url": url,
                "group": "",
                "status": "在线" if r.get("online") else "未检查",
                "ms": str(r.get("ms", "-")),
                "res": r.get("res", "-"),
                "origin": origin,
            })
        if not channels:
            return 0, 0
        return channel_service.add_channels(channels, origin=origin)
