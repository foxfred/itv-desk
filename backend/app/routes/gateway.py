"""局域网订阅网关（P1-6）

把本机频道库变成一个「家庭 IPTV 服务器」：盒子/手机/电视上的播放器直接订阅本机地址即可，
不用再手动导出 m3u 拷来拷去。

公开端点（给播放器用，需带 token）：
  GET /gw/playlist.m3u?token=xxx   当前频道库 M3U（#EXTM3U 头带 url-tvg，播放器自动拉节目单）
  GET /gw/epg.xml?token=xxx        合并后的 XMLTV 节目单

本机端点（给设置页用，仅本机 UI 调用，无 token 要求）：
  GET  /api/gateway                开关状态 / 令牌 / 局域网可访问地址
  POST /api/gateway/token          重新生成令牌（旧的立即失效）

安全约定：默认关闭；开启后必须带 token；token 为空一律拒绝（不裸奔）。
"""
import os
import re
import html
import socket
import secrets

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse, Response

from app.config import Config
from app.utils.m3u_parser import render_playlist

router = APIRouter(prefix="/api/gateway", tags=["gateway"])
public = APIRouter(tags=["gateway-public"])

DEFAULT_PORT = int(os.environ.get("IPTVCORE_PORT", "8000"))


# ==================== 依赖 ====================
def get_settings():
    from app.main import settings
    return settings


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_epg_service():
    from app.main import epg_service
    return epg_service


# ==================== 工具 ====================
def _lan_ip():
    """取本机在局域网中的地址（用于拼给用户看的订阅链接）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass


def _port():
    try:
        return int(os.environ.get("IPTVCORE_PORT", DEFAULT_PORT))
    except Exception:
        return DEFAULT_PORT


def _public_channels(channel_service, settings):
    """网关输出的频道集合：排除死源与黑名单源，避免把没用的东西推给盒子"""
    from app.utils.helpers import is_url_blacklisted

    with getattr(channel_service, "lock", None) or _null_lock():
        pool = list(getattr(channel_service, "pool", []) or [])

    out = []
    for ch in pool:
        url = ch.get("url") or ""
        if not url or is_url_blacklisted(url, settings):
            continue
        # 死源不推送（没检查过的照推，避免新导入的频道被全部滤掉）
        if str(ch.get("status")) == "离线" or ch.get("health", {}).get("dead"):
            continue
        out.append(ch)
    return out


class _null_lock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _check_token(settings, token):
    """校验订阅令牌，返回 None 表示通过，否则返回错误响应"""
    if not settings.get("gateway_enabled"):
        return PlainTextResponse("局域网订阅网关未开启（请在 ITV Desk 设置页打开）", status_code=403)
    real = str(settings.get("gateway_token") or "")
    if not real:
        return PlainTextResponse("网关令牌为空，请在设置页重新生成后使用", status_code=403)
    if not token or not secrets.compare_digest(str(token), real):
        return PlainTextResponse("令牌无效", status_code=403)
    return None


def _base_url(settings):
    """对外可用的服务地址前缀（本机局域网 IP + 端口）"""
    return "http://%s:%d" % (_lan_ip(), _port())


# ==================== 公开端点（播放器订阅用） ====================
@public.get("/gw/playlist.m3u", response_class=PlainTextResponse)
def gateway_playlist(token: str = Query("", description="订阅令牌"),
                     settings=Depends(get_settings),
                     channel_service=Depends(get_channel_service)):
    bad = _check_token(settings, token)
    if bad is not None:
        return bad
    channels = _public_channels(channel_service, settings)
    epg_url = "%s/gw/epg.xml?token=%s" % (_base_url(settings), token)
    body = render_playlist(channels, "m3u", url_tvg=epg_url, with_tvg_name=True)
    return PlainTextResponse(body, media_type="audio/x-mpegurl",
                             headers={"Cache-Control": "no-cache"})


@public.get("/gw/epg.xml")
def gateway_epg(token: str = Query("", description="订阅令牌"),
                settings=Depends(get_settings),
                epg_service=Depends(get_epg_service)):
    bad = _check_token(settings, token)
    if bad is not None:
        return bad
    body = _build_xmltv(epg_service)
    resp = Response(content=body, media_type="application/xml")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def _build_xmltv(epg_service):
    """把已加载的 EPG 数据重新渲染成 XMLTV（播放器只认标准 XMLTV）"""
    data = getattr(epg_service, "epg_data", {}) or {}
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<tv generator-info-name="ITV Desk">']
    chans, progs = [], []
    for info in data.values():
        cid = info.get("id") or info.get("name") or ""
        if not cid:
            continue
        name = info.get("name") or cid
        chans.append('  <channel id="%s"><display-name lang="zh">%s</display-name></channel>'
                     % (html.escape(cid, quote=True), html.escape(name)))
        for p in info.get("programs") or []:
            start = _xmltv_time(p.get("start"))
            stop = _xmltv_time(p.get("stop"))
            title = p.get("title") or ""
            if not start or not title:
                continue
            stop_attr = ' stop="%s"' % stop if stop else ""
            progs.append('  <programme start="%s"%s channel="%s"><title lang="zh">%s</title></programme>'
                         % (start, stop_attr, html.escape(cid, quote=True), html.escape(title)))
    lines.extend(chans)
    lines.extend(progs)
    lines.append("</tv>")
    return "\n".join(lines) + "\n"


def _xmltv_time(v):
    """"20260913210000" → "20260913210000 +0800"（XMLTV 要求带时区）"""
    if not v:
        return ""
    s = re.sub(r"[^0-9]", "", str(v))
    if len(s) < 14:
        return ""
    return s[:14] + " +0800"


# ==================== 本机端点（设置页用） ====================
@router.get("")
def gateway_info(settings=Depends(get_settings),
                 channel_service=Depends(get_channel_service),
                 epg_service=Depends(get_epg_service)):
    token = str(settings.get("gateway_token") or "")
    base = _base_url(settings)
    try:
        total = len(_public_channels(channel_service, settings))
    except Exception:
        total = 0
    return {
        "enabled": bool(settings.get("gateway_enabled")),
        "token": token,
        "lan_ip": _lan_ip(),
        "port": _port(),
        "channel_count": total,
        "epg_count": len(getattr(epg_service, "epg_data", {}) or {}),
        "playlist_url": "%s/gw/playlist.m3u?token=%s" % (base, token) if token else "",
        "epg_url": "%s/gw/epg.xml?token=%s" % (base, token) if token else "",
    }


@router.post("/token")
def gateway_rotate_token(settings=Depends(get_settings)):
    """重新生成订阅令牌并开启网关（旧链接立即失效）

    注意：gateway_enabled 必须显式置 True —— 该键在 DEFAULTS 里已存在（默认 False），
    用 setdefault 是改不动的。
    """
    from app import main
    token = secrets.token_urlsafe(18)
    merged = dict(getattr(main, "settings", {}) or {})
    merged["gateway_token"] = token
    merged["gateway_enabled"] = True
    main.settings = merged
    Config.save_settings(merged)
    base = _base_url(merged)
    return {
        "ok": True,
        "token": token,
        "playlist_url": "%s/gw/playlist.m3u?token=%s" % (base, token),
        "epg_url": "%s/gw/epg.xml?token=%s" % (base, token),
    }
