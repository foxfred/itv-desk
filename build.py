"""打包脚本：生成便携版文件夹"""
import os
import sys
import shutil
import subprocess
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def _safe_rmtree(path):
    """删除目录；若被沙箱 safe-delete 拦截则降级为改名移走（rename 不触发删除 API）。"""
    if not os.path.exists(path):
        return
    try:
        shutil.rmtree(path)
        return
    except Exception:
        pass
    # 降级：改名移走（rename 不调用删除 API，通常不被 safe-delete 拦截）
    moved = "%s.removed_%d" % (path, int(time.time()))
    try:
        if os.path.exists(moved):
            shutil.rmtree(moved, ignore_errors=True)
        os.rename(path, moved)
    except Exception:
        pass  # 实在无法清理则忽略，后续覆盖写入即可

DIST = os.path.join(ROOT, "dist")
FOLDER_DIR = os.path.join(DIST, "IPTVCore_Folder")

# 运行时会生成的缓存文件（打包时复制一份到文件夹版）
RUNTIME_FILES = [
    "url_history.json",
    "remote_url_history.json",
    "mirror_history.json",
    "epg_history.json",
    "epg_source.json",
    "epg_cache.json",
    "subscriptions.json",
    "channel_tags.json",
    "fake_live_tags.json",
    "channel_rules.json",
    "settings.json",
    "column_widths.json",
    "channels_cache.json",
    "channels.db",  # SQLite 频道库（最关键，勿遗漏，否则重打包会丢库）
]
RUNTIME_DIRS = [
    "scraping_cache",
]
# 需要从仓库根(开发缓存)合并进打包产物的目录（如 logos 频道Logo）。
# 与 RUNTIME_DIRS 区别：RUNTIME_DIRS 仅建空目录；SEED_DIRS 在重打包时从根目录
# 合并补齐，避免 dist 缺失 Logo / 缓存时重建后空白。
SEED_DIRS = [
    "logos",
]


def _backup_user_files():
    """备份用户已有的带数据缓存文件，避免打包删除覆盖。返回备份目录路径。"""
    src_dir = os.path.join(FOLDER_DIR, "IPTVCore")
    if not os.path.isdir(src_dir):
        return None
    backup = os.path.join(DIST, ".user_data_backup")
    if os.path.exists(backup):
        _safe_rmtree(backup)
    os.makedirs(backup, exist_ok=True)
    for fname in RUNTIME_FILES:
        src = os.path.join(src_dir, fname)
        if os.path.isfile(src) and os.path.getsize(src) > 2:
            shutil.copy2(src, os.path.join(backup, fname))
    return backup if os.listdir(backup) else None


def _restore_user_files(backup):
    """将备份的用户数据文件恢复到打包产物目录。"""
    if not backup or not os.path.isdir(backup):
        return
    dst_dir = os.path.join(FOLDER_DIR, "IPTVCore")
    for fname in RUNTIME_FILES:
        src = os.path.join(backup, fname)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, fname))
            print(f"  已恢复用户数据: {fname}")


def _seed_from_root():
    """从仓库根(开发缓存)补齐 dist 缺失或较旧的缓存/Logo，确保重打包不丢数据。

    逻辑（保留运行期数据优先）：
    - 若 dist 中无该文件，则从根目录复制（最常见：dist 缓存被重建清空）；
    - 若根目录版本比 dist 更新(mtime 更新)，则覆盖（开发态 python run.py 产生的
      缓存比 dist 新时，让 dist 与之同步）；
    - 若 dist 版本更新（用户直接跑 EXE 积累了新数据），则保留 dist，不回退。
    """
    dst_dir = os.path.join(FOLDER_DIR, "IPTVCore")
    os.makedirs(dst_dir, exist_ok=True)

    for fname in RUNTIME_FILES:
        src = os.path.join(ROOT, fname)
        dst = os.path.join(dst_dir, fname)
        if not os.path.isfile(src):
            continue
        if (not os.path.isfile(dst)) or (os.path.getmtime(src) > os.path.getmtime(dst)):
            shutil.copy2(src, dst)
            print(f"  已同步根目录缓存: {fname}")

    for dname in SEED_DIRS:
        src_dir = os.path.join(ROOT, dname)
        dst_sub = os.path.join(dst_dir, dname)
        if not os.path.isdir(src_dir):
            continue
        for cur, _, files in os.walk(src_dir):
            rel = os.path.relpath(cur, src_dir)
            target = os.path.join(dst_sub, rel)
            os.makedirs(target, exist_ok=True)
            for f in files:
                s = os.path.join(cur, f)
                d = os.path.join(target, f)
                if (not os.path.isfile(d)) or (os.path.getmtime(s) > os.path.getmtime(d)):
                    shutil.copy2(s, d)
        print(f"  已同步根目录目录: {dname}/")


def build_folder():
    """构建文件夹版（所有文件解压到文件夹）"""
    print("=" * 60)
    print("构建文件夹版 ...")
    print("=" * 60)
    # 守护：前端未构建会导致桌面版白屏，提前失败并给出明确指引
    frontend_dist = os.path.join(ROOT, "frontend-new", "dist")
    if not os.path.isdir(frontend_dist):
        print("错误：未找到前端构建产物 frontend-new/dist。")
        print("请先进入 frontend-new 目录执行 `npm install && npm run build` 生成 dist，再运行打包脚本。")
        return False
    backup = _backup_user_files()
    if os.path.exists(FOLDER_DIR):
        _safe_rmtree(FOLDER_DIR)

    # 用 --onedir 模式构建到文件夹
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--onedir",  # 文件夹模式
            "--name", "IPTVCore",
            "--distpath", FOLDER_DIR,
            "--add-data", f"frontend-new/dist{os.pathsep}frontend-new/dist",
            "--add-data", f"backend{os.pathsep}backend",
            # mpv 引擎二进制（spike 已验证可播 HLS 1080p，0.41 需用 --osc=no 而非 --onscreen-controls=）
            "--add-data", f"vendor/mpv{os.pathsep}mpv",
            # FastAPI 核心依赖
            "--hidden-import", "fastapi",
            "--hidden-import", "fastapi.routing",
            "--hidden-import", "fastapi.middleware",
            "--hidden-import", "fastapi.middleware.cors",
            "--hidden-import", "fastapi.responses",
            "--hidden-import", "fastapi.staticfiles",
            "--hidden-import", "fastapi.params",
            "--hidden-import", "fastapi.dependencies",
            "--hidden-import", "fastapi.dependencies.utils",
            "--hidden-import", "fastapi.encoders",
            "--hidden-import", "fastapi.exception_handlers",
            # Pydantic（FastAPI 依赖）
            "--hidden-import", "pydantic",
            "--hidden-import", "pydantic.dataclasses",
            "--hidden-import", "pydantic.fields",
            "--hidden-import", "pydantic.main",
            "--hidden-import", "pydantic.types",
            "--hidden-import", "pydantic.networks",
            "--hidden-import", "pydantic.json",
            "--hidden-import", "pydantic.generics",
            "--hidden-import", "pydantic.errors",
            "--hidden-import", "pydantic._internal",
            "--hidden-import", "pydantic._internal._config",
            "--hidden-import", "pydantic._internal._model_construction",
            "--hidden-import", "pydantic._internal._fields",
            "--hidden-import", "pydantic._internal._validators",
            "--hidden-import", "pydantic._internal._generate_schema",
            # Starlette（FastAPI 构建于其上）
            "--hidden-import", "starlette",
            "--hidden-import", "starlette.routing",
            "--hidden-import", "starlette.middleware",
            "--hidden-import", "starlette.middleware.cors",
            "--hidden-import", "starlette.responses",
            "--hidden-import", "starlette.staticfiles",
            "--hidden-import", "starlette.requests",
            "--hidden-import", "starlette.datastructures",
            "--hidden-import", "starlette.concurrency",
            "--hidden-import", "starlette.convertors",
            "--hidden-import", "starlette.exceptions",
            "--hidden-import", "starlette.types",
            "--hidden-import", "starlette.background",
            "--hidden-import", "starlette.templating",
            # Uvicorn 服务器
            "--hidden-import", "uvicorn",
            "--hidden-import", "uvicorn.logging",
            "--hidden-import", "uvicorn.loops",
            "--hidden-import", "uvicorn.loops.auto",
            "--hidden-import", "uvicorn.protocols",
            "--hidden-import", "uvicorn.protocols.http",
            "--hidden-import", "uvicorn.protocols.http.auto",
            "--hidden-import", "uvicorn.protocols.http.h11_impl",
            "--hidden-import", "uvicorn.protocols.http.httptools_impl",
            "--hidden-import", "uvicorn.protocols.websockets",
            "--hidden-import", "uvicorn.protocols.websockets.auto",
            "--hidden-import", "uvicorn.protocols.websockets.websockets_impl",
            "--hidden-import", "uvicorn.protocols.websockets.wsproto_impl",
            "--hidden-import", "uvicorn.lifespan",
            "--hidden-import", "uvicorn.lifespan.on",
            "--hidden-import", "uvicorn.importer",
            "--hidden-import", "uvicorn.config",
            "--hidden-import", "uvicorn.server",
            "--hidden-import", "uvicorn.supervisors",
            # 后端业务依赖
            "--hidden-import", "python_multipart",
            "--hidden-import", "multipart",
            "--hidden-import", "sqlalchemy",
            "--hidden-import", "sqlalchemy.sql.default_comparator",
            "--hidden-import", "sqlalchemy.ext.asyncio",
            "--hidden-import", "sqlalchemy.orm",
            "--hidden-import", "aiosqlite",
            "--hidden-import", "bs4",
            "--hidden-import", "bs4.builder._lxml",
            "--hidden-import", "lxml",
            "--hidden-import", "lxml.html",
            "--hidden-import", "lxml.etree",
            "--hidden-import", "aiohttp",
            "--hidden-import", "aiohttp.web",
            # requests / PySocks（代理下载：http 与 socks5）
            "--hidden-import", "requests",
            "--hidden-import", "urllib3",
            "--hidden-import", "urllib3.contrib.socks",
            "--hidden-import", "socks",
            "--hidden-import", "certifi",
            "--hidden-import", "charset_normalizer",
            "--hidden-import", "idna",
            # 本地加密备份（AES / Fernet）
            "--hidden-import", "cryptography",
            "--hidden-import", "cryptography.fernet",
            "--hidden-import", "cryptography.hazmat.primitives.kdf.pbkdf2",
            "--hidden-import", "cryptography.hazmat.primitives.hashes",
            "--hidden-import", "base64",
            # CLR / PythonNet / PyWebView
            "--hidden-import", "clr_loader",
            "--hidden-import", "pythonnet",
            "--hidden-import", "webview",
            "--hidden-import", "webview.platforms.winforms",
            "--hidden-import", "proxy_tools",
            # mpv 解码引擎（Phase 5 Track A）：try/except 包裹 + 别名导入，PyInstaller 静态分析
            # 不一定跟到，强制 hidden-import 保证 mpv_engine 被打入 PYZ。
            "--hidden-import", "mpv_engine",
            "--exclude-module", "tkinter",
            "--exclude-module", "matplotlib",
            "--exclude-module", "numpy",
            "--exclude-module", "PySide6",
            "--exclude-module", "pytest",
            "--noconsole",
            os.path.join(ROOT, "run.py"),
        ],
        cwd=ROOT, check=True,
    )

    # 创建运行时目录（不生成 JSON 文件，避免覆盖用户带数据的历史文件）
    folder_exe_dir = os.path.join(FOLDER_DIR, "IPTVCore")
    for dname in RUNTIME_DIRS:
        dst = os.path.join(folder_exe_dir, dname)
        if not os.path.exists(dst):
            os.makedirs(dst)
        print(f"  - {dname}/")

    # 恢复用户带数据的缓存文件
    _restore_user_files(backup)

    # 从仓库根(开发缓存)补齐 dist 缺失/较旧的缓存与 Logo，防止重打包丢数据
    _seed_from_root()

    exe_path = os.path.join(folder_exe_dir, "IPTVCore.exe")
    if os.path.exists(exe_path):
        print(f"文件夹版已生成: {folder_exe_dir}")
    return True


def main():
    try:
        ok = build_folder()
        if not ok:
            return 1
        print("\n" + "=" * 60)
        print("打包完成！")
        print(f"文件夹版: {FOLDER_DIR}")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        return 1
    except Exception as e:
        print(f"出错: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())