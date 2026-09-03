"""频道路由 - /api/channels"""
import json
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    group: Optional[str] = None
    tag: Optional[str] = None
    logo: Optional[str] = None
    sources: Optional[List[str]] = None
    source_groups: Optional[List[dict]] = None


class BatchSelectReq(BaseModel):
    ids: List[int]
    state: bool = True
    clear: bool = True


class TagReq(BaseModel):
    tag: str


class TagToggleReq(BaseModel):
    tag: str


class BatchTagAddReq(BaseModel):
    ids: List[int]
    tags: str


class BatchTagClearReq(BaseModel):
    ids: List[int]


class FakeLiveReq(BaseModel):
    is_fake_live: bool


class BatchFakeLiveReq(BaseModel):
    ids: List[int]
    is_fake_live: bool


class SourceTagReq(BaseModel):
    url: str
    tag: str


class SourceFakeLiveReq(BaseModel):
    url: str
    is_fake_live: bool


class BatchGroupReq(BaseModel):
    ids: List[int]
    group: str


class HealthReportReq(BaseModel):
    """播放器上报某次播放/检测结果，回写健康度。"""
    url: str
    success: bool = True
    error: Optional[str] = None
    first_frame_ms: Optional[int] = None


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_log():
    from app.main import log
    return log


def get_tag_db():
    from app.main import tag_db
    return tag_db


def get_fake_live_db():
    from app.main import fake_live_db
    return fake_live_db


def get_settings():
    from app.main import settings
    return settings


def _save_cache(channel_service, settings=None):
    """保存频道缓存到磁盘（原子写，避免并发/崩溃截断损坏）"""
    from app.config import FileManager, Config
    try:
        cache_file = (settings or {}).get("cache_file_name", "channels_cache.json")
        with channel_service.lock:
            data = channel_service.pool.copy()
        FileManager.write_json_atomic(cache_file, data)
    except Exception:
        pass


@router.get("")
def get_channels(channel_service=Depends(get_channel_service)):
    return channel_service.get_all()


@router.get("/search")
def search_channels(q: str = Query("", description="名称/分组/标记模糊匹配"),
                   offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=2000),
                   channel_service=Depends(get_channel_service)):
    """全文检索：按名称/分组/标记模糊匹配（SQLite 优先，回退内存）"""
    return channel_service.search(q, offset, limit)


@router.get("/groups")
def groups(channel_service=Depends(get_channel_service)):
    """分组树数据：各分组频道数（按数量降序）"""
    return channel_service.get_groups()


@router.get("/stats")
def stats(channel_service=Depends(get_channel_service)):
    """汇总统计：总数/在线/离线/未检查"""
    total, online, offline = channel_service.get_stats()
    unchecked = channel_service.count_unchecked()
    return {"total": total, "online": online, "offline": offline, "unchecked": unchecked}


@router.post("/health")
def report_health(body: HealthReportReq, channel_service=Depends(get_channel_service)):
    """播放器/检测上报一次播放结果，回写频道健康度评分。

    成功则 success=True；致命失败则 success=False 并附带 error 细节。
    返回更新后的 health 字典；未命中频道返回 {"ok": False}。
    """
    health = channel_service.update_health(
        url=body.url, success=body.success,
        error=body.error, first_frame_ms=body.first_frame_ms,
    )
    if health is None:
        return {"ok": False, "reason": "channel_not_found"}
    # 播放上报较稀疏，立即落盘缓存以持久化健康度
    try:
        _save_cache(channel_service)
    except Exception:
        pass
    return {"ok": True, "health": health}


@router.delete("")
def clear_all(channel_service=Depends(get_channel_service), log=Depends(get_log),
              settings=Depends(get_settings)):
    channel_service.clear_all()
    _save_cache(channel_service, settings)
    log("已清空所有频道")
    return {"ok": True}


@router.put("/{channel_id}")
def update_channel(channel_id: int, body: ChannelUpdate, channel_service=Depends(get_channel_service),
                   settings=Depends(get_settings)):
    data = body.dict(exclude_none=True)
    ok = channel_service.update_channel(channel_id, **data)
    if not ok:
        raise HTTPException(404, "频道不存在")
    _save_cache(channel_service, settings)
    return {"ok": True}


@router.post("/toggle/{channel_id}")
def toggle_check(channel_id: int, channel_service=Depends(get_channel_service)):
    ok = channel_service.toggle_check(channel_id)
    if not ok:
        raise HTTPException(404, "频道不存在")
    return {"ok": True}


@router.post("/check-all")
def set_check_all(state: bool = Query(...), channel_service=Depends(get_channel_service)):
    channel_service.set_check_all(state)
    return {"ok": True}


@router.post("/select")
def set_select(body: BatchSelectReq, channel_service=Depends(get_channel_service)):
    with channel_service.lock:
        idset = set(body.ids)
        for ch in channel_service.pool:
            ch["checked"] = ch["id"] in idset if body.clear else (ch["checked"] or ch["id"] in idset)
    return {"ok": True, "count": len(body.ids)}


@router.delete("/invalid")
def remove_invalid(channel_service=Depends(get_channel_service), log=Depends(get_log),
                   settings=Depends(get_settings)):
    removed = channel_service.remove_by_filter(lambda ch: ch.get("status") == "离线")
    if removed > 0:
        _save_cache(channel_service, settings)
        log(f"已清除 {removed} 个离线频道")
    return {"removed": removed}


@router.delete("/{channel_id}")
def delete_channel(channel_id: int, channel_service=Depends(get_channel_service),
                   log=Depends(get_log), settings=Depends(get_settings)):
    removed = channel_service.remove_by_filter(lambda ch: ch["id"] == channel_id)
    if not removed:
        raise HTTPException(404, "频道不存在")
    _save_cache(channel_service, settings)
    log(f"已删除频道 {channel_id}")
    return {"ok": True}


@router.post("/delete-many")
def delete_many(ids: List[int], channel_service=Depends(get_channel_service),
                log=Depends(get_log), settings=Depends(get_settings)):
    idset = set(ids)
    removed = channel_service.remove_by_filter(lambda ch: ch["id"] in idset)
    if removed > 0:
        _save_cache(channel_service, settings)
    log(f"已删除 {removed} 个频道")
    return {"removed": removed}


class DeleteByGroupReq(BaseModel):
    group: str


@router.post("/delete-by-group")
def delete_by_group(body: DeleteByGroupReq, channel_service=Depends(get_channel_service),
                    log=Depends(get_log), settings=Depends(get_settings)):
    group = (body.group or "").strip()
    if not group:
        raise HTTPException(status_code=400, detail="分组名不能为空")
    removed = channel_service.remove_by_filter(lambda ch: (ch.get("group") or "未分组") == group)
    if removed > 0:
        _save_cache(channel_service, settings)
    log(f"已删除分组 [{group}] 下的 {removed} 个频道")
    return {"removed": removed, "group": group}


def _set_source_tag(ch, url, new_tag, tag_db):
    """按源 URL 设置/清除普通 tag；若 url 为频道主 URL 则同步 ch['tag']。"""
    if isinstance(new_tag, str) and "假直播" in new_tag:
        parts = [p.strip() for p in new_tag.split(",") if p.strip() and p.strip() != "假直播"]
        new_tag = ",".join(parts) if parts else ""
    ch.setdefault("source_tags", {})
    primary = ch.get("url", "")
    if new_tag:
        tag_db[url] = new_tag
        ch["source_tags"][url] = new_tag
    else:
        tag_db.pop(url, None)
        ch["source_tags"].pop(url, None)
    if url == primary:
        ch["tag"] = new_tag


def _set_source_fake_live(ch, url, is_fake_live, fake_live_db):
    """按源 URL 设置/清除假直播标记；若 url 为频道主 URL 则同步 ch['is_fake_live']。"""
    ch.setdefault("source_is_fake_live", {})
    primary = ch.get("url", "")
    flag = bool(is_fake_live)
    if flag and url:
        fake_live_db[url] = True
        ch["source_is_fake_live"][url] = True
    else:
        fake_live_db.pop(url, None)
        ch["source_is_fake_live"].pop(url, None)
    if url == primary:
        ch["is_fake_live"] = flag


def _set_tag_channel(ch, new_tag, url, tag_db):
    _set_source_tag(ch, url, new_tag, tag_db)


def _set_fake_live_channel(ch, is_fake_live, url, fake_live_db):
    _set_source_fake_live(ch, url, is_fake_live, fake_live_db)


@router.post("/{channel_id}/tag")
def set_tag(channel_id: int, body: TagReq, channel_service=Depends(get_channel_service),
            tag_db=Depends(get_tag_db), fake_live_db=Depends(get_fake_live_db)):
    from app.config import Config
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] == channel_id:
                url = ch.get("url", "")
                # 若用户仍通过 tag 传入"假直播"，自动迁移到独立字段
                raw = (body.tag or "").strip()
                if "假直播" in raw:
                    parts = [p.strip() for p in raw.split(",") if p.strip() and p.strip() != "假直播"]
                    _set_fake_live_channel(ch, True, url, fake_live_db)
                    Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
                    _set_tag_channel(ch, ",".join(parts) if parts else "", url, tag_db)
                else:
                    _set_tag_channel(ch, raw, url, tag_db)
                Config.save_json(Config.TAG_DB_FILE, tag_db)
                return {"ok": True, "tag": ch["tag"], "is_fake_live": ch.get("is_fake_live", False)}
    raise HTTPException(404, "频道不存在")


@router.post("/{channel_id}/tag-toggle")
def tag_toggle(channel_id: int, body: TagToggleReq, channel_service=Depends(get_channel_service),
               tag_db=Depends(get_tag_db), fake_live_db=Depends(get_fake_live_db)):
    from app.config import Config
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] == channel_id:
                url = ch.get("url", "")
                # 对"假直播"的 toggle 实际切换独立字段，不再污染 tag
                if body.tag == "假直播":
                    _set_fake_live_channel(ch, not ch.get("is_fake_live", False), url, fake_live_db)
                    Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
                    return {"ok": True, "tag": ch["tag"], "is_fake_live": ch.get("is_fake_live", False)}
                current = ch.get("tag", "")
                tags = [t.strip() for t in current.split(",") if t.strip()] if current else []
                if body.tag in tags:
                    tags.remove(body.tag)
                else:
                    tags.append(body.tag)
                _set_tag_channel(ch, ",".join(tags) if tags else "", url, tag_db)
                Config.save_json(Config.TAG_DB_FILE, tag_db)
                return {"ok": True, "tag": ch["tag"], "is_fake_live": ch.get("is_fake_live", False)}
    raise HTTPException(404, "频道不存在")


@router.post("/batch-tag-add")
def batch_tag_add(body: BatchTagAddReq, channel_service=Depends(get_channel_service),
                  tag_db=Depends(get_tag_db), fake_live_db=Depends(get_fake_live_db),
                  log=Depends(get_log), settings=Depends(get_settings)):
    from app.config import Config
    raw_tags = [t.strip() for t in body.tags.split(",") if t.strip()]
    # "假直播"不再通过 tag 接口写入，自动迁移到独立字段
    set_fake_live = "假直播" in raw_tags
    normal_tags = [t for t in raw_tags if t != "假直播"]
    idset = set(body.ids)
    count = 0
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] in idset:
                url = ch.get("url", "")
                if set_fake_live:
                    _set_fake_live_channel(ch, True, url, fake_live_db)
                if normal_tags:
                    current = ch.get("tag", "")
                    existing = [t.strip() for t in current.split(",") if t.strip()] if current else []
                    for t in normal_tags:
                        if t not in existing:
                            existing.append(t)
                    _set_tag_channel(ch, ",".join(existing), url, tag_db)
                count += 1
    if set_fake_live:
        Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
    if normal_tags:
        Config.save_json(Config.TAG_DB_FILE, tag_db)
    if count > 0:
        _save_cache(channel_service, settings)
    log(f"  [批量] 为 {count} 个频道添加标记: {', '.join(raw_tags)}")
    return {"count": count}


@router.post("/batch-tag-clear")
def batch_tag_clear(body: BatchTagClearReq, channel_service=Depends(get_channel_service),
                    tag_db=Depends(get_tag_db), log=Depends(get_log),
                    settings=Depends(get_settings)):
    from app.config import Config
    idset = set(body.ids)
    count = 0
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] in idset:
                _set_tag_channel(ch, "", ch.get("url", ""), tag_db)
                count += 1
    Config.save_json(Config.TAG_DB_FILE, tag_db)
    if count > 0:
        _save_cache(channel_service, settings)
    log(f"  [批量] 清除了 {count} 个频道的标记")
    return {"count": count}


@router.post("/{channel_id}/fake-live")
def set_fake_live(channel_id: int, body: FakeLiveReq, channel_service=Depends(get_channel_service),
                  fake_live_db=Depends(get_fake_live_db), settings=Depends(get_settings)):
    from app.config import Config
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] == channel_id:
                _set_fake_live_channel(ch, body.is_fake_live, ch.get("url", ""), fake_live_db)
                Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
                _save_cache(channel_service, settings)
                return {"ok": True, "is_fake_live": ch.get("is_fake_live", False)}
    raise HTTPException(404, "频道不存在")


@router.post("/batch-fake-live")
def batch_fake_live(body: BatchFakeLiveReq, channel_service=Depends(get_channel_service),
                    fake_live_db=Depends(get_fake_live_db), log=Depends(get_log),
                    settings=Depends(get_settings)):
    from app.config import Config
    idset = set(body.ids)
    count = 0
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] in idset:
                _set_fake_live_channel(ch, body.is_fake_live, ch.get("url", ""), fake_live_db)
                count += 1
    Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
    if count > 0:
        _save_cache(channel_service, settings)
    action = "标记" if body.is_fake_live else "取消"
    log(f"  [批量] {action} {count} 个频道为假直播")
    return {"count": count}


@router.post("/{channel_id}/source-tag")
def set_source_tag(channel_id: int, body: SourceTagReq, channel_service=Depends(get_channel_service),
                   tag_db=Depends(get_tag_db), settings=Depends(get_settings)):
    from app.config import Config
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "缺少 url")
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] == channel_id:
                _set_source_tag(ch, url, body.tag or "", tag_db)
                Config.save_json(Config.TAG_DB_FILE, tag_db)
                _save_cache(channel_service, settings)
                return {"ok": True, "tag": ch.get("source_tags", {}).get(url, ""), "url": url}
    raise HTTPException(404, "频道不存在")


@router.post("/{channel_id}/source-fake-live")
def set_source_fake_live(channel_id: int, body: SourceFakeLiveReq, channel_service=Depends(get_channel_service),
                         fake_live_db=Depends(get_fake_live_db), settings=Depends(get_settings)):
    from app.config import Config
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(400, "缺少 url")
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] == channel_id:
                _set_source_fake_live(ch, url, body.is_fake_live, fake_live_db)
                Config.save_json(Config.FAKE_LIVE_DB_FILE, fake_live_db)
                _save_cache(channel_service, settings)
                return {"ok": True, "is_fake_live": ch.get("source_is_fake_live", {}).get(url, False), "url": url}
    raise HTTPException(404, "频道不存在")


@router.post("/batch-group")
def batch_group(body: BatchGroupReq, channel_service=Depends(get_channel_service),
                settings=Depends(get_settings)):
    idset = set(body.ids)
    count = 0
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch["id"] in idset:
                ch["group"] = body.group
                count += 1
    if count > 0:
        _save_cache(channel_service, settings)
    return {"count": count}


class MatchLogosReq(BaseModel):
    logos_dir: Optional[str] = None


@router.post("/merge-duplicates")
def merge_duplicates(channel_service=Depends(get_channel_service),
                     log=Depends(get_log), settings=Depends(get_settings)):
    """智能去重合并：先按 URL 归并，再按频道名归并，同组合并为多源。"""
    stats = channel_service.merge_duplicates()
    if stats["removed"] > 0:
        _save_cache(channel_service, settings)
        log(f"智能去重合并：移除 {stats['removed']} 个重复频道"
            f"（URL {stats['removed_by_url']} / 名称 {stats['removed_by_name']}），剩余 {stats['remaining']}")
    else:
        log("智能去重合并：未发现重复频道")
    return {"ok": True, **stats}


@router.post("/ungroup-all")
def ungroup_all(channel_service=Depends(get_channel_service),
                log=Depends(get_log), settings=Depends(get_settings)):
    """拆解所有聚合源：把多源聚合频道还原为每个源一个独立单源频道。

    聚合源使离线源无法单独检查/清除，取消合并成源后提供此操作把历史
    聚合数据恢复为单源列表，方便逐条挑选与删除。
    """
    stats = channel_service.ungroup_all()
    if stats["split"] > 0:
        _save_cache(channel_service, settings)
        log(f"拆解聚合源：展开 {stats['split']} 个源，共 {stats['total']} 个频道")
    else:
        log("拆解聚合源：无聚合频道需要拆解")
    return {"ok": True, **stats}


@router.post("/match-logos")
def match_logos(body: MatchLogosReq, channel_service=Depends(get_channel_service),
                log=Depends(get_log), settings=Depends(get_settings)):
    """Logo 自动匹配：扫描 logos 目录，按频道名写入 logo 字段。"""
    result = channel_service.match_logos(body.logos_dir)
    if result["matched"] > 0:
        _save_cache(channel_service, settings)
    log(f"Logo 自动匹配：扫描 {result['scanned']} 张，命中 {result['matched']} 个频道")
    return {"ok": True, **result}


class OnlineLogosReq(BaseModel):
    only_missing: bool = True
    sources: Optional[list] = None


@router.post("/match-logos-online")
def match_logos_online(body: OnlineLogosReq, channel_service=Depends(get_channel_service),
                        log=Depends(get_log), settings=Depends(get_settings)):
    """在线台标补全：从多个在线源（中文台标站 / GitHub 共享台标库 / 频道自带 tvg-logo）并发下载台标，
    落地到程序目录 logos/_online/ 并写入频道 logo 字段。后台执行，返回 task_id 供轮询进度。"""
    task_id = channel_service.start_online_logos(
        settings, sources=body.sources, only_missing=body.only_missing,
        log=log, save_cache=_save_cache,
    )
    log("在线台标补全已启动（后台任务）")
    return {"ok": True, "task_id": task_id}


@router.get("/match-logos-online/{task_id}")
def match_logos_online_status(task_id: str, channel_service=Depends(get_channel_service)):
    """轮询在线台标补全进度。"""
    st = channel_service.get_online_logos_status(task_id)
    if not st:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return st


@router.post("/reclassify")
def reclassify(channel_service=Depends(get_channel_service),
               log=Depends(get_log), settings=Depends(get_settings)):
    """重新自动分组：对整个频道池按统一算法重跑分组（解决历史混乱 / 外国频道统一）。"""
    changed, total = channel_service.reclassify_all()
    if changed > 0:
        _save_cache(channel_service, settings)
        log(f"重新自动分组：调整 {changed} / 共 {total} 个频道的分组")
    else:
        log("重新自动分组：分组无需调整")
    return {"ok": True, "changed": changed, "total": total}