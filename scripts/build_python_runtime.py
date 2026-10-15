#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建随包分发的 Python 运行时。

产出 python-runtime/ 目录，打包时经 electron-builder 的 extraResources
复制到 <安装目录>/resources/python/，使终端用户无需自行安装 Python 与依赖。

用法：
    python scripts/build_python_runtime.py

可选环境变量：
    ITV_PY_VER      Python 版本，默认 3.12.10
    ITV_PIP_INDEX   pip 源，默认清华镜像
"""
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "python-runtime")
CACHE_DIR = os.path.join(ROOT, "_build_cache")
REQ_FILE = os.path.join(ROOT, "backend", "requirements.txt")

PY_VER = os.environ.get("ITV_PY_VER", "3.12.10")
PY_TAG = "".join(PY_VER.split(".")[:2])
EMBED_NAME = "python-%s-embed-amd64.zip" % PY_VER
EMBED_URL = "https://www.python.org/ftp/python/%s/%s" % (PY_VER, EMBED_NAME)
EMBED_ZIP = os.path.join(CACHE_DIR, EMBED_NAME)
PIP_INDEX = os.environ.get("ITV_PIP_INDEX", "https://pypi.tuna.tsinghua.edu.cn/simple")

PYTHON_EXE = os.path.join(OUT_DIR, "python.exe")

VERIFY_CODE = (
    "import fastapi, uvicorn, sqlalchemy, aiosqlite, bs4, lxml, aiohttp, "
    "requests, socks, cv2, onnxruntime, rapidocr_onnxruntime, PIL; "
    "print('IMPORTS OK')"
)


def log(msg):
    print("[build-python] %s" % msg, flush=True)


def ensure_embed():
    os.makedirs(CACHE_DIR, exist_ok=True)
    if os.path.isfile(EMBED_ZIP):
        log("复用已缓存的 embeddable 包")
        return
    log("下载 %s" % EMBED_URL)
    urllib.request.urlretrieve(EMBED_URL, EMBED_ZIP)


def extract_embed():
    if os.path.isdir(OUT_DIR):
        log("清理旧目录 %s" % OUT_DIR)
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)
    with zipfile.ZipFile(EMBED_ZIP) as z:
        z.extractall(OUT_DIR)
    log("Python %s embeddable 解压完成" % PY_VER)


def install_requirements():
    target = os.path.join(OUT_DIR, "Lib", "site-packages")
    os.makedirs(target, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", target,
        "-r", REQ_FILE,
        "--upgrade",
        "--no-warn-script-location",
        "-i", PIP_INDEX,
        "-q",
    ]
    log("安装后端依赖（首次较慢，解压后约 300MB）...")
    subprocess.check_call(cmd)
    log("依赖安装完成")


def write_pth():
    pth_path = os.path.join(OUT_DIR, "python%s._pth" % PY_TAG)
    lines = [
        "python%s.zip" % PY_TAG,
        ".",
        "Lib\\site-packages",
        "..\\backend",
    ]
    with open(pth_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log("写入 %s" % os.path.basename(pth_path))


def prune():
    """只清理确定无用的少量目录。

    注意：不要遍历删除 __pycache__ —— 数量可达数百，会触发环境的批量删除保护。
    """
    removed = 0
    for junk in ("Scripts", "bin"):
        p = os.path.join(OUT_DIR, "Lib", "site-packages", junk)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
    log("清理 %d 个无用目录" % removed)


def verify():
    log("验证依赖可导入...")
    subprocess.check_call([PYTHON_EXE, "-c", VERIFY_CODE])
    total = 0
    for dp, _dn, fn in os.walk(OUT_DIR):
        for f in fn:
            total += os.path.getsize(os.path.join(dp, f))
    log("运行时体积: %.1f MB" % (total / 1024.0 / 1024.0))


def main():
    ensure_embed()
    extract_embed()
    install_requirements()
    write_pth()
    prune()
    verify()
    log("完成 -> %s" % OUT_DIR)


if __name__ == "__main__":
    main()
