"""配置路由"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.config import Config

router = APIRouter(prefix="/api", tags=["config"])


def get_settings():
    from app.main import settings
    return settings


@router.get("/build-info")
def build_info():
    """返回前端构建信息（版本号 + 构建时间戳），用于前端比对是否过期。"""
    from app.main import _FRONTEND_DIST
    import os
    info_path = os.path.join(_FRONTEND_DIST, "build-info.json") if _FRONTEND_DIST else None
    data = {"version": "unknown", "buildTime": None}
    if info_path and os.path.isfile(info_path):
        try:
            import json
            with open(info_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    resp = JSONResponse(content=data)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@router.get("/config")
def get_config(settings=Depends(get_settings)):
    return settings


@router.post("/config/save")
def save_config(data: dict, settings=Depends(get_settings)):
    from app import main
    merged = dict(Config.DEFAULTS)
    merged.update(data)
    main.settings = merged
    Config.save_settings(merged)
    # 配置变更后重新同步定时任务（订阅自动更新 / EPG 定时刷新）
    try:
        main.resync_schedulers()
    except Exception:
        pass
    return {"ok": True}


@router.post("/config/reset")
def reset_config():
    from app import main
    main.settings = dict(Config.DEFAULTS)
    Config.save_settings(main.settings)
    return {"ok": True}