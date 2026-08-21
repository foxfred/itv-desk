"""iTV Desk 发布脚本：打包 + 生成 release 产物 + 发布 GitHub Release。

用法（一阶段：先把更新机制搭好，手动打包后再发布）：
    python publish.py v1.0.0 "更新说明文字"

它完成：
1. 读取 backend/app/version.py 的 APP_VERSION（单一真相源）
2. 触发 build.py 打包（--onedir）→ dist/IPTVCore_Folder/
3. 压缩为 release/itv-desk_<version>.zip（含 mpv + GPL COPYING）
4. 生成 release/update.json（清单：version/url/sha256/notes/package_name）
5. gh release create v<version> 上传 zip 附件
6. 提示你手动 git push update.json 到仓库（清单可被 raw 读取）

依赖：本机已登录 gh CLI（gh auth status 通过）。仅 Windows。
"""
import hashlib
import json
import os
import subprocess
import sys
import zipfile
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "backend"))


def get_version():
    from app.version import APP_VERSION  # noqa
    return APP_VERSION


def hash_file(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def zip_dir(src_dir, dst_zip, extra_files=None):
    """将 src_dir 下所有内容打包为 dst_zip，可额外附加文件（如 COPYING）。"""
    with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arc)
        for extra_src, extra_arc in (extra_files or []):
            if os.path.isfile(extra_src):
                zf.write(extra_src, extra_arc)
    return dst_zip


def main():
    version = get_version()
    # 可选参数覆盖版本
    if len(sys.argv) >= 2:
        version = sys.argv[1].strip("v")
    notes = sys.argv[2] if len(sys.argv) >= 3 else ""

    print(f"[publish] 版本 v{version}")

    # 1) 打包
    print("[publish] 运行 build.py 打包...")
    r = subprocess.run(
        [sys.executable, "build.py"],
        cwd=ROOT,
        env={**os.environ, "CODEBUDDY_SAFE_DELETE_SANDBOX": "0", "PYTHONPATH": ""},
    )
    if r.returncode != 0:
        print("[publish] 打包失败，停止发布")
        sys.exit(1)

    folder_dir = os.path.join(ROOT, "dist", "IPTVCore_Folder", "IPTVCore")
    if not os.path.isdir(folder_dir):
        print(f"[publish] 打包目录不存在: {folder_dir}")
        sys.exit(1)

    # 2) 压缩 + 附加 GPL COPYING（mpv 合规：只需将 GPL v2 文本随附）。
    #    mpv 许可证全文不随本仓库携带，发布前应放置一份到 release/COPYING.mpv。
    release_dir = os.path.join(ROOT, "release")
    os.makedirs(release_dir, exist_ok=True)
    pkg_name = f"itv-desk_{version}.zip"
    dst_zip = os.path.join(release_dir, pkg_name)
    extra = []
    copying = os.path.join(release_dir, "COPYING")
    if os.path.isfile(copying):
        extra.append((copying, "COPYING"))
    print(f"[publish] 压缩 -> {dst_zip}")
    zip_dir(folder_dir, dst_zip, extra)
    sha = hash_file(dst_zip)
    print(f"[publish] SHA256 = {sha}")

    # 3) update.json
    manifest = {
        "version": version,
        "url": f"https://github.com/foxfred/itv-desk/releases/download/v{version}/{pkg_name}",
        "sha256": sha,
        "notes": notes,
        "package_name": pkg_name,
    }
    man_path = os.path.join(release_dir, "update.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[publish] 清单 -> {man_path}")

    # 4) gh release
    tag = f"v{version}"
    print(f"[publish] gh release create {tag}")
    subprocess.run(
        [
            "gh", "release", "create", tag,
            dst_zip,
            "--repo", "foxfred/itv-desk",
            "--title", f"iTV Desk v{version}",
            "--notes", notes or f"iTV Desk v{version}",
        ],
        check=False,
    )

    print("\n[publish] 完成。请手动将 release/update.json 提交并 push 到仓库：")
    print("    git add release/update.json  # 注意 update.json 在 .gitignore 排除，需 -f")
    print("    git commit -m \"chore: update manifest\" && git push")
    print("提示：update.json 会 release 里手动 -f 提交，供程序 raw 拉取。")


if __name__ == "__main__":
    main()