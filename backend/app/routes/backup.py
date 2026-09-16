import os
import json
import base64
import shutil
import zipfile
import tempfile
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import Config

router = APIRouter(prefix="/api/backup", tags=["backup"])

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=200_000)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def _encrypt_bytes(data: bytes, passphrase: str) -> bytes:
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(data)
    return salt + token


def _decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    salt = blob[:16]
    token = blob[16:]
    key = _derive_key(passphrase, salt)
    return Fernet(key).decrypt(token)

BACKUP_FILES = [
    "channels_cache.json",
    "channel_tags.json",
    "fake_live_tags.json",
    "channel_rules.json",
    "column_widths.json",
    "settings.json",
    "url_history.json",
    "remote_url_history.json",
    "mirror_history.json",
    "epg_history.json",
    "channels.db",
]


def get_data_dir():
    from app.main import DATA_DIR
    return DATA_DIR


def get_channel_service():
    from app.main import channel_service
    return channel_service


@router.get("/export")
def export_backup(data_dir: str = Depends(get_data_dir)):
    try:
        tmp = _build_zip(data_dir)
        return FileResponse(tmp, filename="iptv_backup.zip", media_type="application/zip")
    except Exception as e:
        raise HTTPException(500, f"导出失败: {e}")


@router.get("/export-file")
def export_backup_file(data_dir: str = Depends(get_data_dir)):
    try:
        tmp = _build_zip(data_dir)
        return JSONResponse({"ok": True, "path": tmp, "filename": "iptv_backup.zip"})
    except Exception as e:
        raise HTTPException(500, f"导出失败: {e}")


def _build_zip(data_dir):
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".zip", dir=tempfile.gettempdir()
    )
    tmp.close()
    count = 0
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in BACKUP_FILES:
            fp = os.path.join(data_dir, name)
            if os.path.isfile(fp):
                zf.write(fp, name)
                count += 1
        theme_dir = os.path.join(data_dir, "theme")
        if os.path.isdir(theme_dir):
            for root, _, files in os.walk(theme_dir):
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, data_dir)
                    zf.write(full, rel)
        meta = {
            "files": count,
            "channels_cache": _count_channels(os.path.join(data_dir, "channels_cache.json")),
        }
        zf.writestr("__backup_meta__.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return tmp.name


def _count_channels(path):
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            return len(data) if isinstance(data, list) else 0
    except Exception:
        return -1
    return 0


@router.post("/import")
def import_backup(
    file: UploadFile = File(...),
    mode: str = Form("overwrite"),
    data_dir: str = Depends(get_data_dir),
    channel_service=Depends(get_channel_service),
):
    try:
        if not file.filename:
            raise HTTPException(400, "请选择备份文件")
        os.makedirs(data_dir, exist_ok=True)
        restored = []
        with zipfile.ZipFile(file.file) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            for n in names:
                base = os.path.basename(n)
                if not base:
                    continue
                if base in BACKUP_FILES or n.startswith("theme/"):
                    target = os.path.join(data_dir, base) if base in BACKUP_FILES else os.path.join(data_dir, n)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with zf.open(n) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    restored.append(base)
        _reload_channels(data_dir, channel_service)
        return JSONResponse({"ok": True, "restored": restored, "mode": mode})
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(400, "上传的文件不是有效的 zip 压缩包")
    except Exception as e:
        raise HTTPException(500, f"恢复失败: {e}")


def _reload_channels(data_dir, channel_service):
    cache_file = os.path.join(data_dir, "channels_cache.json")
    try:
        data = Config.load_json(cache_file, [])
    except Exception:
        return
    try:
        if not isinstance(data, list):
            return
        with channel_service.lock:
            channel_service.pool.clear()
            for idx, item in enumerate(data, 1):
                item["id"] = idx
                item.setdefault("checked", False)
                item.setdefault("status", "未检查")
                item.setdefault("code", "-")
                item.setdefault("ms", "-")
                item.setdefault("res", "-")
                item.setdefault("quality", "-")
                item.setdefault("geo", "中国")
                item.setdefault("stack", "IPv4")
                item.setdefault("group", "自动分组")
                item.setdefault("tag", "")
                channel_service.pool.append(item)
    except Exception:
        pass


class EncExportReq(BaseModel):
    passphrase: str


@router.post("/export-encrypted")
def export_encrypted_backup(body: EncExportReq, data_dir: str = Depends(get_data_dir)):
    if not _CRYPTO_OK:
        raise HTTPException(500, "加密模块不可用（cryptography 未安装）")
    if not body.passphrase:
        raise HTTPException(400, "口令不能为空")
    try:
        tmp_zip = _build_zip(data_dir)
        try:
            with open(tmp_zip, "rb") as f:
                raw = f.read()
            enc = _encrypt_bytes(raw, body.passphrase)
        finally:
            try:
                os.remove(tmp_zip)
            except Exception:
                pass
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".enc",
                                          dir=tempfile.gettempdir())
        out.write(enc)
        out.close()
        return JSONResponse({"ok": True, "path": out.name, "filename": "iptv_backup.enc"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"加密导出失败: {e}")


@router.post("/import-encrypted")
def import_encrypted_backup(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    data_dir: str = Depends(get_data_dir),
    channel_service=Depends(get_channel_service),
):
    if not _CRYPTO_OK:
        raise HTTPException(500, "加密模块不可用（cryptography 未安装）")
    if not passphrase:
        raise HTTPException(400, "口令不能为空")
    try:
        data = file.file.read()
        raw = _decrypt_bytes(data, passphrase)
    except Exception:
        raise HTTPException(400, "解密失败：口令错误或文件损坏")
    try:
        tmpz = tempfile.NamedTemporaryFile(delete=False, suffix=".zip",
                                           dir=tempfile.gettempdir())
        tmpz.write(raw)
        tmpz.close()
        restored = []
        with zipfile.ZipFile(tmpz.name) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            for n in names:
                base = os.path.basename(n)
                if not base:
                    continue
                if base in BACKUP_FILES or n.startswith("theme/"):
                    target = (os.path.join(data_dir, base) if base in BACKUP_FILES
                              else os.path.join(data_dir, n))
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with zf.open(n) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    restored.append(base)
        try:
            os.remove(tmpz.name)
        except Exception:
            pass
        _reload_channels(data_dir, channel_service)
        return JSONResponse({"ok": True, "restored": restored})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"恢复失败: {e}")
