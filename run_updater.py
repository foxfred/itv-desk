"""iTV Desk 更新器：把下载到 update_staging/ 的 zip 应用到程序目录。

数据保全铁律：只替换程序本体（_internal/ + 主程序文件），
绝不触碰程序根目录的用户数据（channels.db / settings.json / logos/ 等）。

支持多包：
  - main 包：程序本体（_internal/ + exe），全量替换
  - mpv 包：mpv 引擎，解压到 _internal/mpv/

用法（命令行，程序退出后运行）：
    python run_updater.py <main.zip> [mpv.zip ...]

仅 Windows（PyInstaller onedir）。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

# 程序根目录下需要保留的用户数据（按后缀/目录匹配）
KEEP_SUFFIXES = (".db", ".json", ".m3u", ".m3u8", ".txt")
KEEP_DIRS = ("logos",)


def find_app_dir(start=None):
    """定位 IPTVCore/ 程序根目录（含 IPTVCore.exe）。"""
    candidates = []
    if start:
        candidates.append(start)
    # 常见位置：本脚本所在目录、../IPTVCore
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(here)
    candidates.append(os.path.join(os.path.dirname(here), "IPTVCore"))
    # 环境变量
    env = os.environ.get("ITV_APP_DIR")
    if env:
        candidates.append(env)
    for c in candidates:
        if os.path.isfile(os.path.join(c, "IPTVCore.exe")):
            return c
    return None


def collect_user_data(app_dir):
    """收集程序根目录下的用户数据文件/目录（不含 _internal）。"""
    keep = []
    try:
        for name in os.listdir(app_dir):
            full = os.path.join(app_dir, name)
            if name == "_internal":
                continue
            if os.path.isdir(full) and name in KEEP_DIRS:
                keep.append(full)
            elif os.path.isfile(full) and name.endswith(KEEP_SUFFIXES):
                keep.append(full)
    except OSError:
        pass
    return keep


def backup_data(app_dir):
    """把用户数据复制到临时备份目录，返回备份根路径。"""
    tmp = tempfile.mkdtemp(prefix="itv_backup_")
    for src in collect_user_data(app_dir):
        dst = os.path.join(tmp, os.path.basename(src))
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)
            print(f"[updater] 备份 {os.path.basename(src)}")
        except Exception as e:
            print(f"[updater] 备份跳过 {src}: {e}")
    return tmp


def restore_data(app_dir, backup_dir):
    """从备份目录回迁用户数据到程序根目录。"""
    if not backup_dir or not os.path.isdir(backup_dir):
        return
    for name in os.listdir(backup_dir):
        src = os.path.join(backup_dir, name)
        dst = os.path.join(app_dir, name)
        try:
            if os.path.isdir(src):
                if os.path.isdir(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)
            print(f"[updater] 恢复 {name}")
        except Exception as e:
            print(f"[updater] 恢复失败 {name}: {e}")


def apply_main(zip_path, app_dir):
    """应用主程序包：备份数据 → 替换 _internal + exe → 回迁数据。"""
    backup = backup_data(app_dir)
    extract_dir = tempfile.mkdtemp(prefix="itv_new_")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        print(f"[updater] 已解压主包 {zip_path}")
    except Exception as e:
        print(f"[updater] 解压失败: {e}")
        shutil.rmtree(extract_dir, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        return False

    new_root = extract_dir
    if os.path.isfile(os.path.join(extract_dir, "IPTVCore.exe")):
        pass
    else:
        for cand in ["IPTVCore", "dist/IPTVCore_Folder/IPTVCore"]:
            if os.path.isfile(os.path.join(extract_dir, cand, "IPTVCore.exe")):
                new_root = os.path.join(extract_dir, cand)
                break
        else:
            print("[updater] 主包未找到 IPTVCore.exe，终止")
            shutil.rmtree(extract_dir, ignore_errors=True)
            shutil.rmtree(backup, ignore_errors=True)
            return False

    # 替换 _internal
    old_internal = os.path.join(app_dir, "_internal")
    if os.path.isdir(old_internal):
        shutil.rmtree(old_internal)
    shutil.copytree(
        os.path.join(new_root, "_internal"),
        old_internal,
        symlinks=True,
        dirs_exist_ok=True,
    )
    # 主程序文件覆盖
    for name in os.listdir(new_root):
        if name == "_internal":
            continue
        src = os.path.join(new_root, name)
        dst = os.path.join(app_dir, name)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            print(f"[updater] 覆盖 {name} 失败: {e}")

    # 回迁数据
    restore_data(app_dir, backup)
    shutil.rmtree(extract_dir, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    return True


def apply_mpv(zip_path, app_dir):
    """应用 mpv 包：解压到 _internal/mpv/。"""
    mpv_dir = os.path.join(app_dir, "_internal", "mpv")
    os.makedirs(mpv_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(mpv_dir)
        print(f"[updater] 已解压 mpv 包到 {mpv_dir}")
        return True
    except Exception as e:
        print(f"[updater] mpv 解压失败: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python run_updater.py <main.zip> [mpv.zip ...]")
        sys.exit(1)
    # 第一个参数是 main 包，后续是 mpv 等附加包
    zip_paths = [os.path.abspath(a) for a in sys.argv[1:] if a.endswith(".zip")]
    if not zip_paths:
        print("[updater] 未提供 zip 包")
        sys.exit(1)
    app_dir = find_app_dir()
    if not app_dir:
        print("[updater] 找不到程序目录（未找到 IPTVCore.exe）")
        sys.exit(1)
    print(f"[updater] 程序目录: {app_dir}")
    # 第一个包当 main
    main_zip = zip_paths[0]
    print(f"[updater] 主包: {main_zip}")
    if not apply_main(main_zip, app_dir):
        print("[updater] 主包应用失败，终止")
        sys.exit(1)
    # 其余包按文件名判断是否 mpv
    for zp in zip_paths[1:]:
        if "mpv" in os.path.basename(zp).lower():
            print(f"[updater] mpv 包: {zp}")
            apply_mpv(zp, app_dir)
        else:
            print(f"[updater] 跳过未知包: {zp}")
    # 启动新版本
    exe = os.path.join(app_dir, "IPTVCore.exe")
    if os.path.isfile(exe):
        print(f"[updater] 启动新版本...")
        subprocess.Popen([exe], cwd=app_dir)
    print("[updater] 更新完成")
    sys.exit(0)


if __name__ == "__main__":
    main()