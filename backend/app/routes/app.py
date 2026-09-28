import os
import json
import sys
import urllib.request

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.utils import network

router = APIRouter(prefix="/api/app", tags=["app"])

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
    """构造 urllib opener。代理统一走 network.resolve_proxy（2026-09-28 统一入口）：
    - 开关打开 → 用抓取面板填的代理地址（保留 http:// / socks5:// 前缀）
    - 开关关闭 → 走系统代理环境变量
    """
    proxies = {}
    p = network.resolve_proxy(settings)
    if p:
        if "://" not in p:
            p = "http://" + p
        proxies = {"http": p, "https": p}
    if not proxies:
        for k in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
            v = os.environ.get(k)
            if v:
                proxies[k.lower().replace("_proxy", "")] = v
    if proxies:
        handler = urllib.request.ProxyHandler(proxies)
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener()


@router.post("/check-update")
def check_update(body: CheckUpdateReq = None, settings=Depends(get_settings)):
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
    sha256: Optional[str] = None
    size: Optional[int] = None


def _rm_quiet(path):
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@router.post("/download-update")
def download_update(body: DownloadUpdateReq, data_dir=Depends(get_data_dir), settings=Depends(get_settings)):
    if not body.url:
        raise HTTPException(400, "缺少下载地址")
    dest = ""
    try:
        os.makedirs(os.path.join(data_dir, "update_staging"), exist_ok=True)
        fn = body.filename or os.path.basename(body.url.split("?")[0]) or "update_package"
        fn = os.path.basename(fn)
        dest = os.path.join(data_dir, "update_staging", fn)
        # 2026-09-28：改走网络层下载（支持 socks5 + 重试 + 流式写文件 + verify=False），
        # 代理统一由 network.resolve_proxy 解析：开关打开用填的地址，关闭走系统代理。
        proxy = network.resolve_proxy(settings) or None
        min_size = int(body.size) if body.size and int(body.size) > 0 else None
        ok, size, err = network.download_binary(
            body.url, proxy=proxy, dest_path=dest,
            timeout=120, max_retries=3, min_size=min_size,
        )
        if not ok:
            _rm_quiet(dest)
            raise HTTPException(500, f"下载失败: {err}")
    except HTTPException:
        raise
    except Exception as e:
        _rm_quiet(dest)
        raise HTTPException(500, f"下载失败: {e}")

    actual = os.path.getsize(dest)
    if body.size and int(body.size) > 0 and actual != int(body.size):
        _rm_quiet(dest)
        got_mb = round(actual / 1048576, 1)
        want_mb = round(int(body.size) / 1048576, 1)
        raise HTTPException(500, f"更新包下载不完整（{got_mb}MB / {want_mb}MB），已删除残包，请重试")
    if body.sha256:
        if _sha256_file(dest).lower() != str(body.sha256).strip().lower():
            _rm_quiet(dest)
            raise HTTPException(500, "更新包校验失败（文件损坏），已删除，请重试下载")
    return {"ok": True, "path": dest, "size": actual}


class ApplyUpdateReq(BaseModel):
    zip_paths: Optional[list] = None
    zip_path: Optional[str] = None


@router.post("/apply-update")
def apply_update(body: ApplyUpdateReq, data_dir=Depends(get_data_dir)):
    paths = []
    if body.zip_paths:
        paths = [p for p in body.zip_paths if p and os.path.isfile(p)]
    if body.zip_path and os.path.isfile(body.zip_path):
        paths.append(body.zip_path)
    if not paths:
        raise HTTPException(400, "更新包不存在，请先下载")

    exes = [p for p in paths if p.lower().endswith((".exe", ".msi"))]
    if not exes:
        raise HTTPException(400, "文件夹版更新需在桌面客户端里点击「立即更新」完成：程序需先整体退出，再由外壳覆盖自身程序目录。")

    import subprocess
    import threading

    target = next((p for p in exes if "setup" in os.path.basename(p).lower()), exes[0])
    try:
        subprocess.Popen([target], cwd=os.path.dirname(os.path.abspath(target)))
    except Exception as e:
        raise HTTPException(500, f"启动安装包失败: {e}")

    def _force_quit():
        import time
        time.sleep(1.5)
        os._exit(0)

    threading.Thread(target=_force_quit, daemon=True).start()
    return {"ok": True, "launched": True, "mode": "installer", "package": os.path.basename(target)}
