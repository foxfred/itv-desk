import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

router = APIRouter(tags=["hdhomerun"])

KEY_FIELDS = ("hdhr_enabled", "hdhr_device_id", "hdhr_tuner_count", "hdhr_only_online",
              "hdhr_groups", "hdhr_limit", "hdhr_transcode", "hdhr_ssdp",
              "hdhr_exclude_adult", "hdhr_base_url", "hdhr_port")

_CHUNK = 64 * 1024


def _svc():
    from app.main import hdhr_service
    return hdhr_service


def _is_http(url):
    return str(url or "").lower().startswith(("http://", "https://"))


# ---------- HDHomeRun 协议端点（客户端直接访问根路径）----------

@router.get("/discover.json", include_in_schema=False)
def discover():
    return _svc().discover_json()


@router.get("/device.xml", include_in_schema=False)
def device_xml():
    return Response(content=_svc().device_xml(), media_type="application/xml")


@router.get("/lineup_status.json", include_in_schema=False)
def lineup_status():
    return _svc().lineup_status_json()


@router.post("/lineup.post", include_in_schema=False)
async def lineup_post(request: Request):
    from app import main
    try:
        body = (await request.body()).decode("utf-8", "ignore")
    except Exception:
        body = ""
    main.log("[HDHomeRun] 收到频道扫描请求：%s" % (body or "scan=start")[:60])
    return Response(content="", media_type="text/plain")


@router.get("/lineup.json", include_in_schema=False)
def lineup():
    return _svc().lineup()


@router.get("/auto/v{number}", include_in_schema=False)
async def auto_stream(number: str):
    from app import main
    svc = main.hdhr_service

    entry = svc.find(number)
    if not entry:
        if not svc.cfg()["enabled"]:
            return Response(status_code=503, content="hdhomerun disabled", media_type="text/plain")
        return Response(status_code=404, content="channel not found", media_type="text/plain")
    if not _is_http(entry["src"]):
        return Response(status_code=403, content="only http/https sources are supported",
                        media_type="text/plain")

    guide = entry["GuideNumber"]
    if not svc.acquire(guide):
        main.log("[HDHomeRun] 调谐器已占满（%d），拒绝 %s" % (svc.cfg()["tuner_count"], entry["GuideName"]))
        return Response(status_code=503, content="all tuners in use", media_type="text/plain")

    proc = svc.start_stream(entry["src"])
    if proc is None:
        svc.release(guide)
        return Response(status_code=500, content="ffmpeg not found", media_type="text/plain")
    if not svc.wait_ready(proc):
        svc.release(guide)
        main.log("[HDHomeRun] 取流失败：%s" % entry["GuideName"])
        return Response(status_code=502, content="stream unavailable", media_type="text/plain")

    main.log("[HDHomeRun] 开始输出：%s（频道号 %s，占用 %d/%d）"
             % (entry["GuideName"], guide, svc.tuner_count_active(), svc.cfg()["tuner_count"]))

    async def _gen():
        loop = asyncio.get_running_loop()
        try:
            while True:
                chunk = await loop.run_in_executor(None, proc.stdout.read, _CHUNK)
                if not chunk:
                    break
                yield chunk
        finally:
            # 顺序要紧：先同步释放，再做任何 await——客户端断开时 await 会抛 CancelledError 打断后续语句
            svc.release(guide)
            main.log("[HDHomeRun] 结束输出：%s（频道号 %s，占用 %d）"
                     % (entry["GuideName"], guide, svc.tuner_count_active()))
            if proc.poll() is None:
                try:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(loop.run_in_executor(None, proc.wait), timeout=3)
                    except Exception:
                        proc.kill()
                except Exception:
                    pass

    return StreamingResponse(
        _gen(),
        media_type="video/mp2t",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Accept-Ranges": "none"},
    )


# ---------- 管理接口 ----------

@router.get("/api/hdhomerun/config")
def get_config():
    from app.main import settings
    svc = _svc()
    c = svc.cfg()
    out = {k: settings.get(k) for k in KEY_FIELDS}
    out["base_url"] = svc.base_url()
    out["device_id_active"] = svc.device_id()
    out["lan_ip"] = svc.lan_ip()
    out["tuner_count"] = c["tuner_count"]
    return out


@router.post("/api/hdhomerun/config")
def save_config(body: dict):
    from app import main
    from app.config import Config
    merged = dict(getattr(main, "settings", {}) or {})
    for k, v in Config.DEFAULTS.items():
        merged.setdefault(k, v)
    for k in KEY_FIELDS:
        if k in (body or {}):
            merged[k] = body[k]
    main.settings = merged
    Config.save_settings(merged)
    sync_ssdp()
    return {"ok": True}


@router.get("/api/hdhomerun/status")
def status():
    svc = _svc()
    return {
        "enabled": svc.cfg()["enabled"],
        "base_url": svc.base_url(),
        "device_id": svc.device_id(),
        "tuner_count": svc.cfg()["tuner_count"],
        "active": svc.active_list(),
        "channels": len(svc.lineup()),
        "lineup_url": svc.base_url() + "/lineup.json",
    }


def sync_ssdp():
    """按配置启停 SSDP 广播监听。"""
    from app import main
    try:
        if main.hdhr_service.cfg()["ssdp"]:
            main.hdhr_service.ssdp_start()
        else:
            main.hdhr_service.ssdp_stop_serve()
    except Exception:
        pass
