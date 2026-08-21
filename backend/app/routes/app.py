"""应用自更新路由 - /api/app

零服务器设计：由用户自行托管的「更新清单」(JSON) + 新包地址。
配置项 settings['update_url'] 指向该清单；比对版本后可将新包下载到本地暂存目录。
实际替换程序由用户退出后手动覆盖（避免运行中的 PyInstaller --onedir 自替换风险）。
"""
import os
import json
import urllib.request

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/app", tags=["app"])

# 单一版本真相源（与 FastAPI title 版本保持一致；由 version.py 集中定义）
from app.version import APP_VERSION


def get_settings():
    from app.main import settings
    return settings


def get_data_dir():
    from app.main import DATA_DIR
    return DATA_DIR


@router.get("/version")
def app_version():
    return {"version": APP_VERSION}


def _ver_tuple(v):
    """把 '7.0.2' 之类版本号解析成可比较的整数元组（忽略非数字后缀）。"""
    parts = []
    for p in str(v).split("."):
        num = ""
        for c in p:
            if c.isdigit():
                num += c
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


class CheckUpdateReq(BaseModel):
    url: Optional[str] = None


@router.post("/check-update")
def check_update(body: CheckUpdateReq = None, settings=Depends(get_settings)):
    url = (body.url if body else None) or settings.get("update_url", "")
    if not url:
        raise HTTPException(400, "未配置 update_url，请在「设置 / 更新」中填写更新清单地址")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Core-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            manifest = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise HTTPException(502, f"获取更新清单失败: {e}")
    latest = manifest.get("version")
    if not latest:
        raise HTTPException(502, "更新清单缺少 version 字段")
    has_update = _ver_tuple(latest) > _ver_tuple(APP_VERSION)
    return {
        "current": APP_VERSION,
        "latest": latest,
        "has_update": has_update,
        "notes": manifest.get("notes", ""),
        "url": manifest.get("url", ""),
        "package_name": manifest.get("package_name", ""),
    }


class DownloadUpdateReq(BaseModel):
    url: str
    filename: Optional[str] = None


@router.post("/download-update")
def download_update(body: DownloadUpdateReq, data_dir=Depends(get_data_dir)):
    if not body.url:
        raise HTTPException(400, "缺少下载地址")
    try:
        os.makedirs(os.path.join(data_dir, "update_staging"), exist_ok=True)
        fn = body.filename or os.path.basename(body.url.split("?")[0]) or "update_package"
        dest = os.path.join(data_dir, "update_staging", fn)
        req = urllib.request.Request(body.url, headers={"User-Agent": "IPTV-Core-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return {"ok": True, "path": dest, "size": os.path.getsize(dest)}
    except Exception as e:
        raise HTTPException(500, f"下载失败: {e}")
