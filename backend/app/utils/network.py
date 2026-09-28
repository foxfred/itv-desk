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
    suffix_regex = "|".join(suffix_list)
    return re.compile(
        rf'(?:'
        rf'(https?://[^\s<>"\']+?\.({suffix_regex})(?:\?[^\s<>"\']*)?)'
        rf'|(?:href|src)=["\']([^"\']+?\.({suffix_regex})(?:\?[^"\']*)?)["\']'
        rf'|\[[^\]]*\]\(([^)]+?\.({suffix_regex})(?:\?[^)]*)?)\)'
        rf')',
        re.IGNORECASE
    )


def _normalize_proxy(proxy):
    if not proxy:
        return None
    p = str(proxy).strip()
    if not p:
        return None
    if "://" in p:
        return p
    return None


def _build_proxy_list(proxy):
    if not proxy:
        return []
    p = str(proxy).strip()
    if not p:
        return []
    if "://" in p:
        return [p]
    return [f"http://{p}", f"socks5://{p}"]


def _request_download(url, proxy_url, timeout, chunk_size, headers, stop_event):
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


def resolve_proxy(settings, key="proxy"):
    """统一代理解析（2026-09-28 统一入口）。

    语义：开关 `use_proxy` 打开 → 返回 `settings[key]` 里的代理地址；
          开关关闭 → 返回 ""（空串 = 交给 requests/urllib 走系统代理环境变量）。

    **所有网络消费点都必须调本函数**，不要各自 `settings.get("proxy")` ——
    此前 scan / repair / channel 三处只看地址非空、不看开关，
    导致「设置里填了地址但开关关着」时行为不一致。
    """
    if not settings:
        return ""
    if not settings.get("use_proxy", False):
        return ""
    p = str(settings.get(key) or "").strip()
    if not p or p == "不使用加速":
        return ""
    return p


def _rm_quiet(path):
    try:
        import os
        if path and os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def download_binary(url, proxy=None, dest_path=None, timeout=120, max_retries=3,
                    headers=None, stop_event=None, min_size=None, chunk_size=256 * 1024,
                    progress_cb=None):
    """下载二进制文件到 dest_path（流式写文件，不解码）。
    优先 requests（支持 socks5/http 代理 + verify=False），无 requests 时回退 urllib。
    复用 _build_proxy_list 同时尝试 http:// 与 socks5:// 候选；
    每个 attempt 内遍历完所有 proxy 候选，再进入下一轮 attempt（带 backoff）。
    返回 (ok, size, err)：err 为 None 表示成功。
    """
    if not url:
        return False, 0, "缺少下载地址"
    if not dest_path:
        return False, 0, "缺少目标路径"

    proxy_list = _build_proxy_list(proxy)  # http + socks5 候选

    have_requests = False
    try:
        import requests  # noqa
        have_requests = True
    except ImportError:
        pass

    if headers is None:
        headers = {"User-Agent": "IPTV-Core-Updater/1.0",
                   "Accept": "*/*", "Connection": "keep-alive"}

    last_err = "未尝试"
    last_size = 0
    _rm_quiet(dest_path)

    def _attempt(proxy_url):
        """单次尝试；返回 (ok, size, err)。"""
        if have_requests:
            import requests as _req
            import requests.exceptions as _rqe
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            try:
                with _req.get(url, headers=headers, timeout=timeout,
                              proxies=proxies, stream=True, verify=False) as resp:
                    resp.raise_for_status()
                    try:
                        _total = int(resp.headers.get("Content-Length") or 0)
                    except Exception:
                        _total = 0
                    size = 0
                    with open(dest_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=chunk_size):
                            if stop_event and stop_event.is_set():
                                resp.close()
                                _rm_quiet(dest_path)
                                return False, 0, "用户中断"
                            if chunk:
                                f.write(chunk)
                                size += len(chunk)
                                if progress_cb:
                                    try:
                                        progress_cb(size, _total)
                                    except Exception:
                                        pass
                    if min_size and size < min_size:
                        _rm_quiet(dest_path)
                        return False, size, f"下载不完整（{size} < {min_size}），疑似中途被掐断"
                    return True, size, None
            except _rqe.SSLError as e:
                _rm_quiet(dest_path)
                return False, 0, f"SSL 错误: {e}"
            except Exception as e:
                _rm_quiet(dest_path)
                return False, 0, f"{type(e).__name__}: {e}"
        else:
            # urllib 兜底（仅 http 代理；socks5 跳过避免报错）
            if proxy_url and proxy_url.lower().startswith("socks"):
                return False, 0, "当前环境缺少 requests/PySocks，无法使用 socks5 代理"
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=headers)
            try:
                if proxy_url:
                    opener = urllib.request.build_opener(
                        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
                else:
                    opener = urllib.request.build_opener()
                with opener.open(req, timeout=timeout, context=ssl_ctx) as resp:
                    if resp.status != 200:
                        return False, 0, f"HTTP {resp.status}"
                    try:
                        _total = int(resp.headers.get("Content-Length") or 0)
                    except Exception:
                        _total = 0
                    size = 0
                    with open(dest_path, "wb") as f:
                        while True:
                            if stop_event and stop_event.is_set():
                                _rm_quiet(dest_path)
                                return False, 0, "用户中断"
                            try:
                                chunk = resp.read(chunk_size)
                            except Exception as e:
                                _rm_quiet(dest_path)
                                return False, size, f"读取中断: {e}"
                            if not chunk:
                                break
                            f.write(chunk)
                            size += len(chunk)
                            if progress_cb:
                                try:
                                    progress_cb(size, _total)
                                except Exception:
                                    pass
                    if min_size and size < min_size:
                        _rm_quiet(dest_path)
                        return False, size, f"下载不完整（{size} < {min_size}），疑似中途被掐断"
                    return True, size, None
            except Exception as e:
                _rm_quiet(dest_path)
                return False, 0, f"{type(e).__name__}: {e}"

    for attempt in range(max_retries):
        if stop_event and stop_event.is_set():
            return False, 0, "用户中断"
        candidates = proxy_list if proxy_list else [None]
        round_errs = []
        for proxy_url in candidates:
            if stop_event and stop_event.is_set():
                return False, 0, "用户中断"
            ok, size, err = _attempt(proxy_url)
            if ok:
                return True, size, None
            last_size = size
            if err:
                round_errs.append(f"{proxy_url or '直连'}: {err}")
            last_err = "; ".join(round_errs) if round_errs else "未尝试"
        # 本轮所有候选都失败：仅当还有下一轮时才 sleep
        if attempt < max_retries - 1:
            time.sleep(0.5 + attempt * 0.5)

    return False, last_size, last_err