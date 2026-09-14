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
    # 默认走仓库内 release/update.json（raw 清单模式，零依赖开箱即用）。
    # 包地址由 release/update.json 内 packages[].url 指定，可指向 GitHub Release 资产（zip/exe）。
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
    sha256: Optional[str] = None  # 清单里的期望摘要（有值则必须匹配）
    size: Optional[int] = None    # 清单里的期望字节数（有值则必须匹配）


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
    """下载更新包 + 完整性校验。

    v3.1.2 起必须校验：清单里带 sha256/size 就严格比对，不匹配立即删掉残包并报错。
    历史 bug：下载中断（GB 级包只下到 9MB）代码不校验、照样进安装环节 →
    「能检测到更新、点了更新却什么都没装上」。
    """
    if not body.url:
        raise HTTPException(400, "缺少下载地址")
    dest = ""
    try:
        os.makedirs(os.path.join(data_dir, "update_staging"), exist_ok=True)
        fn = body.filename or os.path.basename(body.url.split("?")[0]) or "update_package"
        fn = os.path.basename(fn)
        dest = os.path.join(data_dir, "update_staging", fn)
        # 已有同名残包先清掉，避免旧文件冒充新包
        _rm_quiet(dest)
        opener = _build_opener(settings)
        req = urllib.request.Request(body.url, headers={"User-Agent": "IPTV-Core-Updater/1.0"})
        with opener.open(req, timeout=600) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
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
    zip_paths: Optional[list] = None  # 多包路径列表（兼容旧字段名）
    zip_path: Optional[str] = None   # 兼容旧单包


@router.post("/apply-update")
def apply_update(body: ApplyUpdateReq, data_dir=Depends(get_data_dir)):
    """无桌面外壳时的兜底：仅支持 exe 安装包直启。

    文件夹版（*-folder.zip）的覆盖安装必须由 Electron 外壳完成（外壳负责整应用退出 +
    「等退出→解压覆盖运行目录→自动重启」脚本），后端进程自身文件被占用无法自替换，
    因此这里明确拒绝，避免再出现"装到别处、版本号没变"的情况。
    """
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

    # 优先安装版（Setup 向导），否则取第一个
    target = next((p for p in exes if "setup" in os.path.basename(p).lower()), exes[0])
    try:
        subprocess.Popen([target], cwd=os.path.dirname(os.path.abspath(target)))
    except Exception as e:
        raise HTTPException(500, f"启动安装包失败: {e}")

    # 1.5 秒后退出后端进程（Electron 壳会随后端退出/关窗收尾）
    def _force_quit():
        import time
        time.sleep(1.5)
        os._exit(0)

    threading.Thread(target=_force_quit, daemon=True).start()
    return {"ok": True, "launched": True, "mode": "installer", "package": os.path.basename(target)}
