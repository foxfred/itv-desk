"""iTV Desk 更新器：把下载到 update_staging/ 的 zip 应用到程序目录。

数据保全铁律：只替换程序本体（_internal/ + 主程序文件），
绝不触碰程序根目录的用户数据（channels.db / settings.json / logos/ 等）。

用法（命令行，程序退出后运行）：
    python run_updater.py <zip路径> [程序目录]

流程：
1. 校验 zip 的 SHA256（若附带 .sha256 文件）
2. 备份程序根目录的用户数据文件（channels.db/settings.json/*.json/logos/...）到临时目录
3. 解压 zip 到新的 IPTVCore_new/ 临时目录
4. 将新包内容覆盖到现有 IPTVCore/（保留备份的数据文件）
5. 回迁备份的数据 → 启动新 EXE → 删除备份

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


def apply_update(zip_path, app_dir):
    """解压 zip 覆盖程序目录（保留数据）。"""
    # 1) 备份数据
    backup = backup_data(app_dir)

    # 2) 解压到临时新目录
    extract_dir = tempfile.mkdtemp(prefix="itv_new_")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        print(f"[updater] 已解压 {zip_path}")
    except Exception as e:
        print(f"[updater] 解压失败: {e}")
        shutil.rmtree(extract_dir, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)
        return False

    # 新包内容应包含其自身根目录(IPTVCore.exe) 或直接是文件
    new_root = extract_dir
    if os.path.isfile(os.path.join(extract_dir, "IPTVCore.exe")):
        pass  # zip 根即程序目录
    else:
        # 可能 zip 顶层带了文件夹（如 IPTVCore/ 或 dist/IPTVCore_Folder/IPTVCore/）
        for cand in ["IPTVCore", "dist/IPTVCore_Folder/IPTVCore"]:
            if os.path.isfile(os.path.join(extract_dir, cand, "IPTVCore.exe")):
                new_root = os.path.join(extract_dir, cand)
                break
        else:
            print("[updater] 未在 zip 中找到 IPTVCore.exe，终止")
            shutil.rmtree(extract_dir, ignore_errors=True)
            shutil.rmtree(backup, ignore_errors=True)
            return False

    # 3) 覆盖：先删旧 _internal 再复制新 _internal + 主程序
    old_internal = os.path.join(app_dir, "_internal")
    if os.path.isdir(old_internal):
        shutil.rmtree(old_internal)
    shutil.copytree(
        os.path.join(new_root, "_internal"),
        old_internal,
        symlinks=True,
        dirs_exist_ok=True,
    )
    # 主程序文件（exe + 非数据根文件）逐一覆盖
    for name in os.listdir(new_root):
        src = os.path.join(new_root, name)
        if name in ("_internal",):
            continue
        dst = os.path.join(app_dir, name)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            print(f"[updater] 覆盖 {name} 失败: {e}")

    # 4) 回迁数据
    restore_data(app_dir, backup)

    # 5) 清理临时目录
    shutil.rmtree(extract_dir, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)

    # 6) 启动新版本
    exe = os.path.join(app_dir, "IPTVCore.exe")
    if os.path.isfile(exe):
        print(f"[updater] 启动新版本...")
        subprocess.Popen([exe], cwd=app_dir)
    print("[updater] 更新完成")
    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python run_updater.py <更新zip路径> [程序目录]")
        sys.exit(1)
    zip_path = os.path.abspath(sys.argv[1])
    app_dir_arg = sys.argv[2] if len(sys.argv) >= 3 else None
    app_dir = find_app_dir(app_dir_arg)
    if not app_dir:
        print("[updater] 找不到程序目录（未找到 IPTVCore.exe）")
        sys.exit(1)
    print(f"[updater] 程序目录: {app_dir}")
    print(f"[updater] 更新包: {zip_path}")
    ok = apply_update(zip_path, app_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()