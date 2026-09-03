"""乱码修补 + 查找替换路由"""
import os
import re
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api", tags=["repair"])


class RepairReq(BaseModel):
    text: str
    mode: str = "纯净模式"
    save_only: bool = False
    fmt: str = "m3u"


class FindReplaceReq(BaseModel):
    find: str
    replace: str = ""
    field: str = "频道名"
    scope: str = "选中"
    ids: List[int] = []
    case_sensitive: bool = False


def get_repair_service():
    from app.main import repair_service
    return repair_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_log():
    from app.main import log
    return log


def get_data_dir():
    from app.main import DATA_DIR
    return DATA_DIR


@router.post("/repair")
def repair(body: RepairReq, repair_service=Depends(get_repair_service)):
    try:
        result = repair_service.repair(body.text, body.mode, body.save_only, body.fmt)
    except Exception as e:
        raise HTTPException(500, str(e))
    if "file" in result:
        return FileResponse(result["file"], filename=result["filename"])
    return result


def get_settings():
    from app.main import settings
    return settings


def _save_cache(settings, channel_service):
    """保存频道缓存到磁盘（原子写，避免并发/崩溃截断损坏）"""
    from app.config import FileManager
    try:
        cache_file = settings.get("cache_file_name", "channels_cache.json")
        with channel_service.lock:
            data = channel_service.pool.copy()
        FileManager.write_json_atomic(cache_file, data)
    except Exception:
        pass


@router.post("/find-replace")
def find_replace(body: FindReplaceReq, channel_service=Depends(get_channel_service),
                 settings=Depends(get_settings)):
    if not body.find:
        return {"error": "请输入查找内容"}
    field_map = {"频道名": "name", "分组": "group", "地址(URL)": "url", "标记": "tag"}
    key = field_map.get(body.field, "name")
    target_ids = set(body.ids)
    count = 0
    with channel_service.lock:
        for ch in channel_service.pool:
            if body.scope == "选中" and ch["id"] not in target_ids:
                continue
            old = ch.get(key, "")
            if body.case_sensitive:
                new = old.replace(body.find, body.replace)
            else:
                new = re.sub(re.escape(body.find), body.replace, old, flags=re.IGNORECASE)
            if new != old:
                ch[key] = new
                count += 1
    if count > 0:
        _save_cache(settings, channel_service)
    return {"count": count}