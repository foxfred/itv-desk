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


def _build_opener(settings=None):
    """构建 urllib opener，支持代理（从 settings.proxy 或环境变量读）。"""
    proxies = {}
    if settings:
        p = settings.get("proxy", "")
        if p and p != "不使用加速":
            # 支持 http://host:port 或 host:port 格式
            if not p.startswith("http"):
                p = "http://" + p
            proxies = {"http": p, "https": p}
    if not proxies:
        # 回退环境变量
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            v = os.environ.get(k)
            if v:
                proxies[k.lower().replace("_proxy", "")] = v
    if proxies:
        handler = urllib.request.ProxyHandler(proxies)
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener()


@router.post("/check-update")
def check_update(body: CheckUpdateReq = None, settings=Depends(get_settings)):
    # 内置默认更新清单地址（用户可在设置页覆盖）
    DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/foxfred/itv-desk/master/release/update.json"
    url = (body.url if body else None) or settings.get("update_url", "") or DEFAULT_UPDATE_URL
    try:
        opener = _build_opener(settings)
        req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Core-Updater/1.0"})
        with opener.open(req, timeout=20) as resp:
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
def download_update(body: DownloadUpdateReq, data_dir=Depends(get_data_dir), settings=Depends(get_settings)):
    if not body.url:
        raise HTTPException(400, "缺少下载地址")
    try:
        os.makedirs(os.path.join(data_dir, "update_staging"), exist_ok=True)
        fn = body.filename or os.path.basename(body.url.split("?")[0]) or "update_package"
        fn = os.path.basename(fn)
        dest = os.path.join(data_dir, "update_staging", fn)
        opener = _build_opener(settings)
        req = urllib.request.Request(body.url, headers={"User-Agent": "IPTV-Core-Updater/1.0"})
        with opener.open(req, timeout=600) as resp, open(dest, "wb") as f:
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
    """退出并安装更新：支持多包（main + mpv）。全自动应用更新。

    - 打包态（frozen）：启动 IPTVCore.exe --update-only <zip_paths> 子进程，
      主进程退出后子进程自动解压替换并重启，零手动。
    - 开发态（非 frozen）：用本解释器后台启动 run.py --update-only。
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

    if getattr(sys, "frozen", False):
        # 打包态：EXE 自己作为更新器子进程启动
        exe = sys.executable
        cmd = [exe, "--update-only"] + paths
    else:
        # 开发态：用 run.py --update-only
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        run_py = os.path.join(root, "run.py")
        if not os.path.isfile(run_py):
            raise HTTPException(500, "开发态找不到 run.py")
        python = sys.executable or "python"
        cmd = [python, run_py, "--update-only"] + paths

    # 启动更新器子进程（CREATE_NO_WINDOW），等 2 秒后由更新器接管
    subprocess.Popen(
        cmd,
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )
    return {"ok": True, "launched": True, "mode": "auto", "packages": len(paths)}
