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


def get_settings():
    from app.main import settings
    return settings


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_epg_service():
    from app.main import epg_service
    return epg_service


def _lan_ip():
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
    from app.utils.helpers import is_url_blacklisted

    with getattr(channel_service, "lock", None) or _null_lock():
        pool = list(getattr(channel_service, "pool", []) or [])

    out = []
    for ch in pool:
        url = ch.get("url") or ""
        if not url or is_url_blacklisted(url, settings):
            continue
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
    if not settings.get("gateway_enabled"):
        return PlainTextResponse("局域网订阅网关未开启（请在 ITV Desk 设置页打开）", status_code=403)
    real = str(settings.get("gateway_token") or "")
    if not real:
        return PlainTextResponse("网关令牌为空，请在设置页重新生成后使用", status_code=403)
    if not token or not secrets.compare_digest(str(token), real):
        return PlainTextResponse("令牌无效", status_code=403)
    return None


def _base_url(settings):
    return "http://%s:%d" % (_lan_ip(), _port())


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
    if not v:
        return ""
    s = re.sub(r"[^0-9]", "", str(v))
    if len(s) < 14:
        return ""
    return s[:14] + " +0800"


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
