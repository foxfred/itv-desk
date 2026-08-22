"""生成 release/itv-desk_<version>_core.zip：高压缩比打包程序本体。

排除：logos/（用户数据，不进包）、update_staging/、scraping_cache/、__pycache__/、mpv/
只保留程序本体 + _internal + 用户数据文件（让更新器回迁时不丢数据）。
版本号从 backend/app/version.py 读取，保持单真相源。
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "dist", "IPTVCore_Folder", "IPTVCore")

# 从 version.py 读取 APP_VERSION（不 import，避免污染环境）
_version = "0.0.0"
try:
    with open(os.path.join(ROOT, "backend", "app", "version.py"), encoding="utf-8") as _f:
        for _line in _f:
            _m = re.match(r'\s*APP_VERSION\s*=\s*["\']([^"\']+)["\']', _line)
            if _m:
                _version = _m.group(1)
                break
except Exception:
    pass
DST = os.path.join(ROOT, "release", f"itv-desk_{_version}_core.zip")

EXCLUDE_DIRS = {"logos", "update_staging", "scraping_cache", "__pycache__", "mpv"}
EXCLUDE_EXTS = {".pyc", ".pyo"}


def should_exclude(path, name):
    full = os.path.join(path, name)
    if os.path.isdir(full):
        return name in EXCLUDE_DIRS
    if name.endswith(tuple(EXCLUDE_EXTS)):
        return True
    return False


def main():
    if not os.path.isdir(SRC_DIR):
        print(f"错误：找不到 {SRC_DIR}")
        return 1
    if os.path.isfile(DST):
        os.remove(DST)
    count = 0
    total = 0
    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for cur, dirs, files in os.walk(SRC_DIR):
            dirs[:] = [d for d in dirs if not should_exclude(cur, d)]
            for f in files:
                if should_exclude(cur, f):
                    continue
                src = os.path.join(cur, f)
                arc = os.path.relpath(src, SRC_DIR)
                zf.write(src, arc)
                count += 1
                total += os.path.getsize(src)
    dst_size = os.path.getsize(DST)
    print(f"打包完成：{count} 个文件，原始 {total/1024/1024:.1f}MB → 压缩 {dst_size/1024/1024:.1f}MB")
    print(f"输出：{DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
