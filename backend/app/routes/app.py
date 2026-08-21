"""应用自更新路由 - /api/app

零服务器设计：由用户自行托管的「更新清单」(JSON) + 新包地址。
配置项 settings['update_url'] 指向该清单；比对版本后可将新包下载到本地暂存目录。
实际替换程序由用户退出后手动覆盖（避免运行中的 PyInstaller --onedir 自替换风险）。
"""
import os
import json
import sys
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
    # 内置默认更新清单地址（用户可在设置页覆盖）
    DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/foxfred/itv-desk/master/release/update.json"
    url = (body.url if body else None) or settings.get("update_url", "") or DEFAULT_UPDATE_URL
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
    # 兼容单包（旧格式 url/package_name/sha256）和多包（packages 数组）
    packages = manifest.get("packages")
    if not packages:
        # 旧单包格式转成 packages 数组
        packages = [{
            "name": manifest.get("package_name", ""),
            "url": manifest.get("url", ""),
            "sha256": manifest.get("sha256", ""),
            "role": "main"
        }]
    return {
        "current": APP_VERSION,
        "latest": latest,
        "has_update": has_update,
        "notes": manifest.get("notes", ""),
        "packages": packages,
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
        # 防路径穿越：只保留安全文件名
        fn = os.path.basename(fn)
        dest = os.path.join(data_dir, "update_staging", fn)
        req = urllib.request.Request(body.url, headers={"User-Agent": "IPTV-Core-Updater/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return {"ok": True, "path": dest, "size": os.path.getsize(dest)}
    except Exception as e:
        raise HTTPException(500, f"下载失败: {e}")


class ApplyUpdateReq(BaseModel):
    zip_paths: Optional[list] = None  # 多包路径列表
    zip_path: Optional[str] = None   # 兼容旧单包


@router.post("/apply-update")
def apply_update(body: ApplyUpdateReq, data_dir=Depends(get_data_dir)):
    """退出并安装更新：支持多包（main + mpv）。启动更新器依次应用。

    - 开发态（非 frozen）：直接用本解释器后台启动 run_updater.py。
    - 打包态（frozen）：写 pending_update.json，提示用户手动运行。
    """
    # 统一成列表
    paths = []
    if body.zip_paths:
        paths = [p for p in body.zip_paths if p and os.path.isfile(p)]
    if body.zip_path and os.path.isfile(body.zip_path):
        paths.append(body.zip_path)
    if not paths:
        raise HTTPException(400, "更新包不存在，请先下载")
    import subprocess

    # 定位仓库根/程序目录的 run_updater.py
    updater = None
    candidates = []
    if getattr(sys, "frozen", False):
        candidates = []
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidates = [os.path.join(root, "run_updater.py")]

    updater = next((c for c in candidates if os.path.isfile(c)), None)

    # 把路径列表写成 JSON 给更新器读
    paths_json = json.dumps(paths)

    if updater:
        python = sys.executable or "python"
        subprocess.Popen(
            [python, "-c",
             f"import time; time.sleep(2); import subprocess,sys,json; "
             f"paths=json.loads({json.dumps(paths_json)}); "
             f"subprocess.run([sys.executable, r'{updater}'] + paths)",
             ],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return {"ok": True, "launched": True, "mode": "auto", "packages": len(paths)}
    else:
        try:
            os.makedirs(os.path.join(data_dir, "update_staging"), exist_ok=True)
            with open(os.path.join(data_dir, "update_staging", "pending_update.json"), "w", encoding="utf-8") as f:
                json.dump({"zip_paths": paths, "data_dir": data_dir}, f, ensure_ascii=False)
        except Exception:
            pass
        return {"ok": True, "launched": False, "mode": "manual", "packages": len(paths),
                "error": "打包版更新器需手动运行：退出程序后运行程序目录的 run_updater.py"}
