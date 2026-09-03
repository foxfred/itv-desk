"""网络工具函数 - 从现有 utils.py 迁移"""
import re
import time
import ssl
import threading
import gzip
import urllib.request
import urllib.error
from app.config import Config


def normalize_url(url):
    if not url:
        return url
    u = url.strip()
    u = re.sub(r'^([A-Z]+)://', lambda m: m.group(1).lower() + '://', u)
    u = re.sub(r'\?$', '', u).rstrip('/')
    return u


def format_github_raw_url(url, mirror_addr=""):
    """将 GitHub 链接转换为使用镜像加速的 raw 链接"""
    if not url:
        return url
    low = url.lower()
    if "github" not in low and "fastgit" not in low and "kkgithub" not in low:
        return url

    mirror = (mirror_addr or "").strip()
    if not mirror or mirror == "不使用加速":
        if "/blob/" in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        return url

    if not mirror.startswith("http"):
        mirror = f"https://{mirror}"
    mirror_host = mirror.rstrip("/").split("//")[-1].lower()

    raw_url = url
    if "raw.githubusercontent.com" in low:
        raw_url = url
    elif "/blob/" in url:
        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    elif "github.com/" in low and "/raw/" in low:
        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/raw/", "/")

    if "kkgithub" in mirror_host:
        if "raw.githubusercontent.com" in raw_url:
            return raw_url.replace("raw.githubusercontent.com", "raw.kkgithub.com")
        return raw_url.replace("github.com", "kkgithub.com")
    if "fastgit" in mirror_host:
        return raw_url.replace("raw.githubusercontent.com", "raw.fastgit.org")

    return f"{mirror}/{raw_url.lstrip('https://')}"


def build_link_pattern(suffix_list):
    """构建链接提取正则，支持 href / src / markdown / 纯文本URL 等多种格式"""
    suffix_regex = "|".join(suffix_list)
    return re.compile(
        rf'(?:'
        rf'(https?://[^\s<>"\']+?\.({suffix_regex})(?:\?[^\s<>"\']*)?)'  # 纯文本完整URL
        rf'|(?:href|src)=["\']([^"\']+?\.({suffix_regex})(?:\?[^"\']*)?)["\']'  # href/src 属性
        rf'|\[[^\]]*\]\(([^)]+?\.({suffix_regex})(?:\?[^)]*)?)\)'  # Markdown 链接
        rf')',
        re.IGNORECASE
    )


def _normalize_proxy(proxy):
    """规范化代理地址：支持 ip:port、http://ip:port、socks5://ip:port 等格式。

    未带协议前缀时返回 None，由调用方按 http 与 socks5 分别尝试（urllib 的
    ProxyHandler 不支持 socks5，需借助 requests + PySocks）。
    """
    if not proxy:
        return None
    p = str(proxy).strip()
    if not p:
        return None
    if "://" in p:
        return p
    return None


def _build_proxy_list(proxy):
    """构造待尝试的代理地址列表。

    - 无前缀（如 127.0.0.1:10808）：依次尝试 http 与 socks5（10808 等常为 socks 端口）
    - 带协议前缀：原样使用
    """
    if not proxy:
        return []
    p = str(proxy).strip()
    if not p:
        return []
    if "://" in p:
        return [p]
    return [f"http://{p}", f"socks5://{p}"]


def _request_download(url, proxy_url, timeout, chunk_size, headers, stop_event):
    """使用 requests 下载，支持 http/https/socks 代理。返回 (text, err)。"""
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, proxies=proxies,
                            verify=False, stream=True)
        chunks = []
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if stop_event and stop_event.is_set():
                resp.close()
                return "", "用户中断"
            if not chunk:
                break
            chunks.append(chunk)
        resp.close()
        raw = b''.join(chunks)
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        return raw.decode('utf-8', errors='ignore'), None
    except Exception as e:
        return "", str(e)


def _urllib_download(url, proxies, timeout, chunk_size, headers, stop_event):
    """使用 urllib 下载（http/https 代理）。返回 (text, err)。"""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers=headers)
        if proxies:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
            with opener.open(req, timeout=timeout, context=ssl_ctx) as r:
                chunks = []
                while True:
                    if stop_event and stop_event.is_set():
                        return "", "用户中断"
                    chunk = r.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b''.join(chunks)
        else:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as r:
                chunks = []
                while True:
                    if stop_event and stop_event.is_set():
                        return "", "用户中断"
                    chunk = r.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                raw = b''.join(chunks)
        if raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        return raw.decode('utf-8', errors='ignore'), None
    except Exception as e:
        return "", str(e)


def download_url(url, proxy=None, timeout=None, max_retries=None, headers=None, stop_event=None):
    if timeout is None:
        timeout = Config.get_setting("download_timeout", 15)
    if max_retries is None:
        max_retries = Config.get_setting("download_retries", 2)
    chunk_size = Config.get_setting("download_chunk_size", 8192)
    if headers is None:
        headers = {"User-Agent": Config.get_setting("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")}

    proxy_list = _build_proxy_list(proxy)
    have_requests = False
    try:
        import requests
        have_requests = True
    except ImportError:
        pass

    for attempt in range(max_retries):
        if stop_event and stop_event.is_set():
            return "", "用户中断"

        last_err = None
        candidates = proxy_list if proxy_list else [None]
        for proxy_url in candidates:
            if stop_event and stop_event.is_set():
                return "", "用户中断"
            result = [None, None]

            def target():
                if have_requests:
                    text, err = _request_download(url, proxy_url, timeout, chunk_size, headers, stop_event)
                else:
                    if proxy_url and proxy_url.lower().startswith("socks"):
                        result[1] = "当前环境缺少 requests/PySocks，无法使用 socks5 代理"
                        return
                    p = proxy_url if proxy_url else None
                    proxies = None
                    if p:
                        proxies = {"http": p, "https": p}
                    text, err = _urllib_download(url, proxies, timeout, chunk_size, headers, stop_event)
                result[0], result[1] = text, err

            thread = threading.Thread(target=target, daemon=True)
            thread.start()

            deadline = time.time() + timeout + 2
            while thread.is_alive():
                if stop_event and stop_event.is_set():
                    thread.join(timeout=0.1)
                    return "", "用户中断"
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                thread.join(timeout=min(0.2, remaining))

            if stop_event and stop_event.is_set():
                return "", "用户中断"

            if thread.is_alive():
                last_err = "下载超时"
                continue

            if result[1]:
                last_err = result[1]
                continue

            return result[0] or "", None

        if last_err:
            if attempt == max_retries - 1:
                return "", last_err
            time.sleep(0.5)
            continue

        return "", "所有尝试失败"

    return "", "所有尝试失败"


def http_probe_channel(url, timeout=5, retries=1, proxy=None):
    """轻量级连通性探测（用于 repair / 快速在线判定），避免全量下载。

    策略：
    - HEAD 优先；HTTP 2xx/3xx 视为在线；4xx（含 403/405，直播源常如此）也视为「可连接=在线」；
      5xx 与连接/超时/DNS 异常视为离线。
    - HEAD 不被支持（抛异常）时回退 GET(Range: bytes=0-65535)，只读状态码 + 前 64KB 内容以识别分辨率。
    返回 (online: bool, status_code: int|None, elapsed_ms: int, resolution: str)。
    """
    import urllib.request
    import urllib.error
    import ssl
    import time

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    ua = Config.get_setting("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    proxies = {"http": proxy, "https": proxy} if proxy else None

    def _classify(code, content):
        if content and "#EXTM3U" in content:
            resolutions = re.findall(r'RESOLUTION=(\d+x\d+)', content)
            if resolutions:
                return max(resolutions, key=lambda x: int(x.split('x')[0]) * int(x.split('x')[1]))
            return "直播流"
        return "-"

    def _open(method, extra_headers=None):
        headers = {"User-Agent": ua}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, method=method, headers=headers)
        if proxies:
            return urllib.request.build_opener(urllib.request.ProxyHandler(proxies)).open(
                req, timeout=timeout, context=ssl_ctx)
        return urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx)

    last_elapsed = 0
    last_code = None
    for _ in range(max(1, retries)):
        # 第一次尝试：HEAD
        start = time.time()
        try:
            with _open("HEAD") as r:
                code = r.status
                last_code = code
                last_elapsed = int((time.time() - start) * 1000)
                if 200 <= code < 400:
                    res = "-"
                    try:
                        res = _classify(code, r.read(65536).decode("utf-8", "ignore"))
                    except Exception:
                        pass
                    return True, code, last_elapsed, res
                if 400 <= code < 500:
                    return True, code, last_elapsed, "-"
                # 5xx → 离线，重试
                continue
        except urllib.error.HTTPError as e:
            last_elapsed = int((time.time() - start) * 1000)
            code = e.code
            last_code = code
            if 400 <= code < 500:
                return True, code, last_elapsed, "-"
            continue
        except Exception:
            pass

        # HEAD 不支持 / 失败 → 回退 GET(Range)
        start = time.time()
        try:
            with _open("GET", {"Range": "bytes=0-65535"}) as r:
                code = r.status
                last_code = code
                last_elapsed = int((time.time() - start) * 1000)
                if 200 <= code < 500:
                    res = "-"
                    try:
                        res = _classify(code, r.read(65536).decode("utf-8", "ignore"))
                    except Exception:
                        pass
                    return True, code, last_elapsed, res
        except urllib.error.HTTPError as e:
            last_elapsed = int((time.time() - start) * 1000)
            code = e.code
            last_code = code
            if 400 <= code < 500:
                return True, code, last_elapsed, "-"
        except Exception:
            pass

    return False, last_code, last_elapsed, "-"