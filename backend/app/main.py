import os
import sys
import json
import threading

#
if os.environ.get("ITV_DATA_DIR"):
    DATA_DIR = os.path.abspath(os.environ["ITV_DATA_DIR"])
    RES_DIR = DATA_DIR
    if getattr(sys, 'frozen', False):
        RES_DIR = getattr(sys, '_MEIPASS', DATA_DIR)
elif getattr(sys, 'frozen', False):
    RES_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    DATA_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RES_DIR = BASE_DIR
    DATA_DIR = os.path.dirname(BASE_DIR)

for p in (RES_DIR, DATA_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(DATA_DIR)

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import Config, FileManager
from app.services.channel_service import ChannelService
from app.services.scrape_service import ScrapeService
from app.services.check_service import CheckService
from app.services.epg_service import EpgService
from app.services.rule_service import RuleService
from app.services.repair_service import RepairService
from app.services.export_service import ExportService
from app.services.subscription_service import SubscriptionService
from app.services.dlna_service import DlnaService
from app.services.scan_service import ScanService
from app.services.screenshot_service import ScreenshotService
from app.services.stats_service import StatsService
from app.services.namefix_service import NamefixService
from app.routes import channels, scrape, check, epg, rules as rules_router, repair, export, config, history, play_history, backup, realtime, subscriptions, dlna, stream_proxy, rtmp_proxy, h264_proxy, app as app_routes, scan as scan_router, screenshots, gateway, aliases, stats as stats_router, namefix
from app.realtime import publish_event

from app.version import APP_VERSION as _APP_VERSION
app = FastAPI(title="IPTV Core API", version=_APP_VERSION)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

channel_service = ChannelService()
tag_db = Config.load_json(Config.TAG_DB_FILE, {})
fake_live_db = Config.load_json(Config.FAKE_LIVE_DB_FILE, {})
rules = Config.load_json(Config.RULES_FILE, [])
settings = Config.load_settings()

server_logs = []
_log_lock = threading.Lock()
_LOG_FILE = os.path.join(DATA_DIR, "app.log")
_MAX_LOG_FILE_BYTES = 2 * 1024 * 1024


def _write_log_to_file(msg):
    try:
        import time as _time
        line = f"[{_time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        try:
            if os.path.exists(_LOG_FILE) and os.path.getsize(_LOG_FILE) > _MAX_LOG_FILE_BYTES:
                backup = _LOG_FILE + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(_LOG_FILE, backup)
        except Exception:
            pass
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def log(msg):
    with _log_lock:
        server_logs.append(msg)
        if len(server_logs) > 5000:
            del server_logs[:len(server_logs) - 5000]
    _write_log_to_file(msg)
    try:
        from app.realtime import publish_log
        publish_log(msg)
    except Exception:
        pass


def _save_cache():
    from app.config import FileManager
    cache_file = settings.get("cache_file_name", "channels_cache.json")
    try:
        with channel_service.lock:
            data = channel_service.pool.copy()
        FileManager.write_json_atomic(cache_file, data)
    except Exception:
        pass

scrape_service = ScrapeService(channel_service, log_callback=log, save_cache_callback=_save_cache)
check_service = CheckService(channel_service, log_callback=log, save_cache_callback=_save_cache)
epg_service = EpgService(log_callback=log, data_dir=DATA_DIR)
rule_service = RuleService(log_callback=log)
repair_service = RepairService(log_callback=log, settings=settings, data_dir=DATA_DIR)
export_service = ExportService(settings=settings, data_dir=DATA_DIR)
subscription_service = SubscriptionService(
    channel_service, log_callback=log, data_dir=DATA_DIR, save_cache_callback=_save_cache
)
dlna_service = DlnaService(log_callback=log)
scan_service = ScanService(log_callback=log, settings=settings)
screenshot_service = ScreenshotService(log_callback=log, data_dir=DATA_DIR)
namefix_service = NamefixService(log_callback=log, data_dir=DATA_DIR)
stats_service = StatsService(log_callback=log, data_dir=DATA_DIR)

try:
    from app.services.play_history_service import init as init_play_history
    init_play_history()
    log("SQLite 数据库已就绪 (channels.db)")
except Exception as e:
    log(f"SQLite 数据库初始化失败: {e}")

cache_file = settings.get("cache_file_name", "channels_cache.json")


def _load_cached_channels():
    content, err = FileManager.read_text(cache_file)
    if err or not content:
        return
    try:
        data = json.loads(content)
        if not data or not isinstance(data, list):
            return
        with channel_service.lock:
            channel_service.pool.clear()
            for idx, item in enumerate(data, 1):
                item["id"] = idx
                item.setdefault("checked", False)
                item.setdefault("status", "未检查")
                item.setdefault("code", "-")
                item.setdefault("ms", "-")
                item.setdefault("res", "-")
                item.setdefault("quality", "-")
                item.setdefault("geo", settings.get("cache_default_geo", "中国"))
                item.setdefault("stack", settings.get("cache_default_stack", "IPv4"))
                item.setdefault("group", settings.get("cache_default_group", "杂项频道"))
                item.setdefault("tag", "")
                item.setdefault("is_fake_live", False)
                item.setdefault("origin", "manual")
                channel_service.pool.append(item)
        log(f"已恢复 {len(data)} 个频道")
    except Exception as e:
        log(f"恢复缓存失败: {e}")


def _migrate_fake_live_tags():
    global tag_db, fake_live_db
    dirty_tag_db = False
    dirty_fake_db = False
    for url, tag_val in list(tag_db.items()):
        if not isinstance(tag_val, str) or "假直播" not in tag_val:
            continue
        parts = [p.strip() for p in tag_val.split(",") if p.strip() and p.strip() != "假直播"]
        fake_live_db[url] = True
        dirty_fake_db = True
        if parts:
            tag_db[url] = ",".join(parts)
            dirty_tag_db = True
        else:
            tag_db.pop(url, None)
            dirty_tag_db = True
    with channel_service.lock:
        for ch in channel_service.pool:
            url = ch.get("url", "")
            tag_val = ch.get("tag", "") or ""
            if "假直播" in tag_val:
                parts = [p.strip() for p in tag_val.split(",") if p.strip() and p.strip() != "假直播"]
                ch["is_fake_live"] = True
                fake_live_db[url] = True
                dirty_fake_db = True
                ch["tag"] = ",".join(parts) if parts else ""
            elif url and fake_live_db.get(url):
                ch["is_fake_live"] = True
            else:
                ch.setdefault("is_fake_live", False)
            if ch.get("is_fake_live") and url:
                fake_live_db[url] = True
                dirty_fake_db = True
    if dirty_tag_db:
        Config.save_json(Config.TAG_DB_FILE, tag_db)
    if dirty_fake_db:
        Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
    if dirty_tag_db or dirty_fake_db:
        log(f"已迁移 '假直播' 标记：{len(fake_live_db)} 条 URL 写入 fake_live_tags.json，并从 tag 字段移除")


def _enrich_channel_tags():
    global tag_db, fake_live_db
    with channel_service.lock:
        for ch in channel_service.pool:
            primary = ch.get("url", "")
            ch["tag"] = tag_db.get(primary) or ch.get("tag", "") or ""
            ch["is_fake_live"] = bool(fake_live_db.get(primary)) or bool(ch.get("is_fake_live"))
            for f in ("sources", "source_groups", "source_tags",
                      "source_is_fake_live", "source_health", "source_is_fake"):
                ch.pop(f, None)


def _migrate_multi_sources():
    try:
        stats = channel_service.ungroup_all()
    except Exception as e:
        log(f"聚合源展开迁移失败: {e}")
        return
    if not stats.get("split"):
        return
    log(f"聚合源已展开为一源一行：新增 {stats['split']} 行，当前共 {stats['total']} 条")
    try:
        from app.config import FileManager
        cache_file = (settings or {}).get("cache_file_name", "channels_cache.json")
        with channel_service.lock:
            data = channel_service.pool.copy()
        FileManager.write_json_atomic(cache_file, data)
        log("展开结果已写回频道缓存")
    except Exception as e:
        log(f"展开结果落盘失败（下次启动会重试）: {e}")


_load_cached_channels()
_migrate_fake_live_tags()
_migrate_multi_sources()
_enrich_channel_tags()

app.include_router(channels.router)
app.include_router(scrape.router)
app.include_router(check.router)
app.include_router(epg.router)
app.include_router(rules_router.router)
app.include_router(repair.router)
app.include_router(export.router)
app.include_router(config.router)
app.include_router(history.router)
app.include_router(play_history.router)
app.include_router(backup.router)
app.include_router(realtime.router)
app.include_router(subscriptions.router)
app.include_router(dlna.router)
app.include_router(stream_proxy.router)
app.include_router(rtmp_proxy.router)
app.include_router(h264_proxy.router)
app.include_router(scan_router.router)
app.include_router(app_routes.router)
app.include_router(screenshots.router)
app.include_router(namefix.router)
app.include_router(gateway.router)
app.include_router(gateway.public)
app.include_router(aliases.router)
app.include_router(stats_router.router)

logos_dir = os.path.join(DATA_DIR, "logos")
try:
    os.makedirs(logos_dir, exist_ok=True)
    app.mount("/logos", StaticFiles(directory=logos_dir), name="logos")
except Exception:
    pass

try:
    app.mount("/screenshots", StaticFiles(directory=screenshot_service.dir), name="screenshots")
except Exception:
    pass


@app.on_event("startup")
async def _start_realtime_publisher():
    import asyncio as _asyncio

    async def _publish_loop():
        was_checking = False
        while True:
            try:
                total, online, offline = channel_service.get_stats()
                publish_event("stats", {"total": total, "online": online, "offline": offline})
                try:
                    st = check_service.get_status()
                    publish_event("check", st)
                    running = bool(st.get("running"))
                    if was_checking and not running:
                        try:
                            stats_service.snapshot(channel_service)
                        except Exception:
                            pass
                    was_checking = running
                except Exception:
                    pass
                try:
                    publish_event("scrape", scrape_service.get_status())
                except Exception:
                    pass
            except Exception:
                pass
            await _asyncio.sleep(1.5)

    _asyncio.create_task(_publish_loop())


@app.on_event("startup")
async def _start_subscription_scheduler():
    try:
        interval = int(settings.get("subscription_auto_update_interval", 0) or 0)
        if interval > 0:
            subscription_service.start_scheduler(interval)
    except Exception:
        pass


@app.on_event("startup")
async def _start_epg_refresh_scheduler():
    try:
        interval = int(settings.get("epg_auto_refresh_interval", 0) or 0)
        if interval > 0:
            epg_service.start_refresh_scheduler(interval)
    except Exception:
        pass


def resync_schedulers():
    try:
        try:
            subscription_service.stop_scheduler()
        except Exception:
            pass
        sub_interval = int(settings.get("subscription_auto_update_interval", 0) or 0)
        if sub_interval > 0:
            subscription_service.start_scheduler(sub_interval)
        try:
            epg_service.stop_refresh_scheduler()
        except Exception:
            pass
        epg_interval = int(settings.get("epg_auto_refresh_interval", 0) or 0)
        if epg_interval > 0:
            epg_service.start_refresh_scheduler(epg_interval)
    except Exception as e:
        log(f"定时任务重新同步失败: {e}")


@app.get("/api/stats")
def stats():
    total, online, offline = channel_service.get_stats()
    return {"total": total, "online": online, "offline": offline}


@app.get("/api/logs")
def get_logs(since: int = 0):
    with _log_lock:
        return {"logs": server_logs[since:], "count": len(server_logs)}


@app.post("/api/logs/clear")
def clear_logs():
    with _log_lock:
        server_logs.clear()
    try:
        if os.path.exists(_LOG_FILE):
            os.remove(_LOG_FILE)
        backup = _LOG_FILE + ".1"
        if os.path.exists(backup):
            os.remove(backup)
    except Exception:
        pass
    return {"ok": True}


@app.get("/api/logs/file")
def get_log_file():
    try:
        if not os.path.exists(_LOG_FILE):
            return {"path": _LOG_FILE, "content": ""}
        content, _ = FileManager.read_text(_LOG_FILE)
        return {"path": _LOG_FILE, "content": content}
    except Exception as e:
        return {"path": _LOG_FILE, "content": "", "error": str(e)}


@app.post("/api/cache/save")
def save_cache():
    try:
        with channel_service.lock:
            data = channel_service.pool.copy()
        FileManager.write_json_atomic(cache_file, data)
        return {"ok": True, "count": len(data)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/players")
def find_players():
    import shutil
    return {
        "vlc": shutil.which("vlc.exe"),
        "pot": shutil.which("potplayermini.exe"),
        "mpv": shutil.which("mpv.exe"),
    }


_FRONTEND_DIST = None
_env_frontend = os.environ.get("ITV_FRONTEND_DIR")
for cand in (
    _env_frontend,
    os.path.join(RES_DIR, "frontend-new", "dist"),
    os.path.join(DATA_DIR, "frontend-new", "dist"),
    os.path.join(RES_DIR, "frontend"),
    os.path.join(DATA_DIR, "frontend"),
):
    if cand and os.path.isdir(cand):
        _FRONTEND_DIST = cand
        break

if _FRONTEND_DIST:
    from fastapi.staticfiles import StaticFiles

    _index_mtime = os.path.getmtime(os.path.join(_FRONTEND_DIST, "index.html"))

    def _serve_index_html():
        import uuid as _uuid
        import re as _re
        _v = _uuid.uuid4().hex[:12]
        html_path = os.path.join(_FRONTEND_DIST, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = _re.sub(
            r'(src|href)="(/assets/[^"]+)"',
            rf'\1="\2?_v={_v}"',
            content,
        )
        content = _re.sub(
            r'(src|href)="(/themes/[^"]+)"',
            rf'\1="\2?_v={_v}"',
            content,
        )
        return Response(
            content=content,
            media_type="text/html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Vary": "*",
            },
        )

    @app.get("/", include_in_schema=False)
    def serve_index():
        log(f"[serve_index] 返回 index.html, _FRONTEND_DIST={_FRONTEND_DIST}")
        return _serve_index_html()

    @app.get("/player.html", include_in_schema=False)
    def serve_player():
        log(f"[serve_player] 返回 index.html (player)")
        return _serve_index_html()

    @app.get("/favicon.ico", include_in_schema=False)
    def serve_favicon():
        return Response(status_code=204)

    assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        class NoStoreStaticFiles(StaticFiles):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
            async def get_response(self, path, scope):
                resp = await super().get_response(path, scope)
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                resp.headers["Expires"] = "0"
                return resp
        app.mount("/assets", NoStoreStaticFiles(directory=assets_dir), name="assets")

    themes_dir = os.path.join(_FRONTEND_DIST, "themes")
    if os.path.isdir(themes_dir):
        app.mount("/themes", StaticFiles(directory=themes_dir), name="themes")

    vendor_dir = os.path.join(_FRONTEND_DIST, "vendor")
    if os.path.isdir(vendor_dir):
        app.mount("/vendor", StaticFiles(directory=vendor_dir), name="vendor")

    log(f"前端静态资源目录: {_FRONTEND_DIST}")


def run_server(host="0.0.0.0", port=8000):
    import uvicorn
    import traceback
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    log(f"IPTV Core Web 版后端启动 http://{host}:{port}")
    try:
        uvicorn.run(app, host=host, port=port)
    except Exception as _e:
        log("后端启动异常: " + traceback.format_exc())
        raise


if __name__ == "__main__":
    run_server()