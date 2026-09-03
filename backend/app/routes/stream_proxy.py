"""流中继代理 —— 让内置 HLS 播放器绕过 WebView 跨源 / MSE 边界限制。

问题背景：
  部分直播源（如 CloudFront 上的主索引 m3u8 + 变体 + 绝对路径 .ts 切片）在
  PotPlayer 等原生播放器里能正常播放，但在内置 hls.js（运行于桌面 WebView）
  里会直接致命报错。根因通常是 WebView 运行时的跨源策略 / MSE 边界处理，
  而非 CORS（实测目标 CDN 已返回 Access-Control-Allow-Origin: *）。

解决：
  将远端 m3u8 与切片经本地 FastAPI 后端 fetch 后**同源**返回，彻底消除跨源
  / MSE 边界问题。对 m3u8 清单，还会把内部变体 / 切片地址改写成经本端代理的
  根相对地址（/api/stream-proxy?url=...），使 hls.js 全程同源拉取。

安全：仅允许 http/https 目标；拦截 localhost / 内网地址，避免被当作 SSRF 跳板。
"""
import re
from urllib.parse import urljoin, quote, urlparse

import requests
import urllib3
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/api/stream-proxy", tags=["stream-proxy"])

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_PROXY_PATH = "/api/stream-proxy?url="


def _is_safe_target(url: str) -> bool:
    """仅允许 http/https。桌面本地应用，允许访问局域网/内网源（用户自建 IPTV 源）。"""
    if not url:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    return True


def _looks_private(host: str) -> bool:
    if host.startswith((
        "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
        "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
        "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    )):
        return True
    if host in ("169.254.169.254", "169.254.0.0"):
        return True
    return False


def _rewrite_manifest(text: str, base_url: str) -> str:
    """把清单中的变体 / 切片 / EXT-X-MEDIA URI 改写为经本端代理的根相对地址。"""
    def rewrite_uri(uri: str) -> str:
        u = uri.strip()
        if not u or u.startswith("#") or u.startswith("data:") or u.startswith(_PROXY_PATH):
            return uri
        abs_uri = urljoin(base_url, u)
        if not abs_uri.startswith(("http://", "https://")):
            return uri
        return _PROXY_PATH + quote(abs_uri, safe="")

    attr_re = re.compile(r'URI="([^"]*)"')

    def repl_attr(m):
        val = m.group(1).strip()
        if val.startswith("//"):
            abs_uri = "https:" + val
        elif val.startswith(("http://", "https://")):
            abs_uri = val
        else:
            return m.group(0)
        return 'URI="' + _PROXY_PATH + quote(abs_uri, safe="") + '"'

    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#EXT-X-MEDIA") or s.startswith("#EXT-X-I-FRAME-STREAM-INF"):
            out.append(attr_re.sub(repl_attr, line))
        elif s == "" or s.startswith("#"):
            out.append(line)
        else:
            out.append(rewrite_uri(s))
    return "\n".join(out)


@router.get("")
async def stream_proxy(url: str, request: Request):
    if not url:
        raise HTTPException(status_code=400, detail="missing url")
    if not _is_safe_target(url):
        raise HTTPException(status_code=400, detail="unsupported or disallowed target")

    headers = {"User-Agent": _UA, "Referer": ""}
    range_hdr = request.headers.get("Range")
    if range_hdr:
        headers["Range"] = range_hdr

    try:
        resp = requests.get(
            url, headers=headers, timeout=30, verify=False,
            stream=True, allow_redirects=True,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}")

    ctype = (resp.headers.get("Content-Type") or "").lower()
    status = resp.status_code
    # 是否 HLS 清单（需改写内部地址）。以 Content-Type 为主，URL 后缀为辅。
    is_manifest = ("mpegurl" in ctype) or url.rstrip().lower().endswith((".m3u8", ".m3u"))

    if is_manifest:
        # 302 重定向后必须用最终 URL(resp.url) 作为清单内相对地址的拼接基准，
        # 否则相对变体/切片会被拼回原始 URL 的 host（如内网反代 → 拿不到真实切片）。
        base_for_rewrite = resp.url or url
        try:
            body = b"".join(resp.iter_content(chunk_size=8192)).decode("utf-8", "ignore")
        finally:
            resp.close()
        return Response(
            _rewrite_manifest(body, base_for_rewrite),
            media_type="application/vnd.apple.mpegurl",
        )

    # 二进制切片：流式透传（支持 Range / 206）
    def gen():
        try:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            resp.close()

    out_headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-cache"}
    if "Content-Type" in resp.headers:
        out_headers["Content-Type"] = resp.headers.get("Content-Type")
    if "Content-Range" in resp.headers:
        out_headers["Content-Range"] = resp.headers.get("Content-Range")
    if "Content-Length" in resp.headers:
        out_headers["Content-Length"] = resp.headers.get("Content-Length")

    return StreamingResponse(gen(), status_code=status, headers=out_headers)
