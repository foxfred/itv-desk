from fastapi import APIRouter, Depends
from pydantic import BaseModel
import time

router = APIRouter(prefix="/api/ai", tags=["ai"])

KEY_FIELDS = ("ai_enabled", "ai_base_url", "ai_api_key", "ai_model", "ai_timeout",
              "ai_temperature", "ai_max_tokens", "ai_use_proxy", "ai_prompt_extra",
              "ai_vision_enabled", "ai_vision_base_url", "ai_vision_api_key",
              "ai_vision_model", "ai_vision_timeout", "ai_daily_token_limit", "ai_cache_enabled")

KEY_SECRETS = ("ai_api_key", "ai_vision_api_key")


def _mask(v):
    s = str(v or "")
    if not s:
        return ""
    if len(s) <= 8:
        return "****"
    return s[:4] + "****" + s[-4:]


def _is_masked(v):
    return "****" in str(v or "")


class ModelsReq(BaseModel):
    base_url: str = ""
    api_key: str = ""


class TestReq(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class GroupReq(BaseModel):
    apply: bool = False
    limit: int = 400
    extra: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    mapping: dict | None = None


class NamefixReq(BaseModel):
    apply: bool = False
    limit: int = 400
    extra: str = ""
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    mapping: dict | None = None


def get_ai():
    from app.main import ai_service
    return ai_service


def get_settings():
    from app.main import settings
    return settings


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_namefix_service():
    from app.main import namefix_service
    return namefix_service


@router.get("/config")
def ai_config(settings=Depends(get_settings)):
    out = {k: settings.get(k) for k in KEY_FIELDS}
    for k in KEY_SECRETS:
        raw = str(out.get(k) or "")
        out[k] = _mask(raw)
        out[k + "_set"] = bool(raw)
    return out


@router.post("/config")
def ai_config_save(body: dict, settings=Depends(get_settings)):
    from app import main
    from app.config import Config
    merged = dict(getattr(main, "settings", {}) or {})
    for k, v in Config.DEFAULTS.items():
        merged.setdefault(k, v)
    body = body or {}
    for k in KEY_FIELDS:
        if k not in body:
            continue
        if k in KEY_SECRETS:
            sv = str(body[k] or "").strip()
            if not sv or _is_masked(sv):
                continue
        merged[k] = body[k]
    main.settings = merged
    Config.save_settings(merged)
    return {"ok": True}


@router.post("/models")
def ai_models(body: ModelsReq, ai=Depends(get_ai)):
    return ai.list_models(base_url=body.base_url or None, api_key=body.api_key or None)


@router.post("/test")
def ai_test(body: TestReq, ai=Depends(get_ai)):
    return ai.test(base_url=body.base_url or None, api_key=body.api_key or None,
                   model=body.model or None)


def _apply_mapping(channel_service, mapping, settings):
    changed = 0
    touched = set()
    with channel_service.lock:
        for ch in channel_service.pool:
            name = ch.get("name")
            if name in mapping:
                g = mapping[name]
                if g and ch.get("group") != g:
                    ch["group"] = g
                    changed += 1
                touched.add(name)
    if changed:
        try:
            channel_service._store_rebuild()
        except Exception:
            pass
        try:
            from app import main
            main._save_cache()
        except Exception:
            pass
    return changed, len(touched)


@router.post("/group")
def ai_group(body: GroupReq, ai=Depends(get_ai), settings=Depends(get_settings),
             channel_service=Depends(get_channel_service)):
    mapping = body.mapping if isinstance(body.mapping, dict) and body.mapping else None
    if mapping is None:
        with channel_service.lock:
            names = [ch.get("name") for ch in channel_service.pool if ch.get("name")]
            groups = sorted({(ch.get("group") or "") for ch in channel_service.pool if ch.get("group")})
        names = list(dict.fromkeys(names))[:max(1, min(body.limit, 400))]
        r = ai.suggest_groups(names, groups, base_url=body.base_url or None,
                              api_key=body.api_key or None, model=body.model or None,
                              extra=body.extra or "")
        if not r.get("ok"):
            return r
        mapping = r["mapping"]
    counts = {}
    for v in mapping.values():
        counts[v] = counts.get(v, 0) + 1
    out = {"ok": True, "mapping": mapping, "count": len(mapping), "groups": counts,
           "applied": 0}
    if body.apply:
        changed, _matched = _apply_mapping(channel_service, mapping, settings)
        out["applied"] = changed
    return out


@router.post("/apply-groups")
def ai_apply_groups(body: dict, settings=Depends(get_settings),
                    channel_service=Depends(get_channel_service)):
    mapping = body.get("mapping") if isinstance(body, dict) else None
    if not isinstance(mapping, dict) or not mapping:
        return {"ok": False, "error": "没有可应用的分组结果"}
    changed, matched = _apply_mapping(channel_service, mapping, settings)
    return {"ok": True, "applied": changed, "matched": matched}


def _apply_namefix(channel_service, mapping, nf):
    targets = []
    with channel_service.lock:
        for ch in channel_service.pool:
            name = ch.get("name")
            new = mapping.get(name)
            if name and new and new != name and ch.get("id") is not None:
                targets.append((ch.get("id"), name, new))
    if not targets:
        return 0, [], []
    try:
        nf._backup()
    except Exception:
        pass
    changes, failed = [], []
    for cid, old, new in targets:
        try:
            r = channel_service.update_channel(cid, name=new)
            if r is False:
                failed.append({"cid": cid, "error": "频道不存在（可能已被删除）"})
                continue
            changes.append({"cid": cid, "old": old, "new": new, "url": None})
        except Exception as e:
            failed.append({"cid": cid, "error": str(e)[:120]})
    if changes:
        batches = nf._load_undo()
        batches.append({"id": "ai%d" % int(time.time()), "ts": time.time(),
                        "count": len(changes), "source": "ai_namefix", "changes": changes})
        nf._save_undo(batches)
        try:
            channel_service._store_rebuild()
        except Exception:
            pass
        try:
            from app import main
            main._save_cache()
        except Exception:
            pass
    return len(changes), failed, changes


@router.post("/namefix")
def ai_namefix(body: NamefixReq, ai=Depends(get_ai),
               channel_service=Depends(get_channel_service),
               nf=Depends(get_namefix_service)):
    mapping = body.mapping if isinstance(body.mapping, dict) and body.mapping else None
    if mapping is None:
        with channel_service.lock:
            names = [ch.get("name") for ch in channel_service.pool if ch.get("name")]
        names = list(dict.fromkeys(names))[:max(1, min(body.limit, 400))]
        r = ai.suggest_namefix(names, base_url=body.base_url or None,
                               api_key=body.api_key or None, model=body.model or None,
                               extra=body.extra or "")
        if not r.get("ok"):
            return r
        mapping = r["mapping"]
        if not mapping:
            return {"ok": True, "mapping": {}, "count": 0, "applied": 0,
                    "msg": r.get("msg", "没有需要清洗的频道名")}
    out = {"ok": True, "mapping": mapping, "count": len(mapping), "applied": 0, "failed": []}
    if body.apply:
        applied, failed, _changes = _apply_namefix(channel_service, mapping, nf)
        out["applied"] = applied
        out["failed"] = failed
    return out


# ================= 2026-09-28 能力扩展 =================

def get_screenshot_service():
    from app.main import screenshot_service
    return screenshot_service


def get_tag_db():
    from app.main import tag_db
    return tag_db


def get_fake_live_db():
    from app.main import fake_live_db
    return fake_live_db


def _pool_names(channel_service, limit=400):
    with channel_service.lock:
        names = [ch.get("name") for ch in channel_service.pool if ch.get("name")]
    return list(dict.fromkeys(names))[:limit]


def _pool_groups(channel_service):
    with channel_service.lock:
        return sorted({(ch.get("group") or "") for ch in channel_service.pool if ch.get("group")})


class TagsReq(BaseModel):
    apply: bool = False
    limit: int = 200
    extra: str = ""
    mapping: dict | None = None


@router.post("/tags")
def ai_tags(body: TagsReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service),
            tag_db=Depends(get_tag_db)):
    """#3 频道打标与自动分级：预览/应用（写入既有 tag 体系，url→tag 字符串）"""
    mapping = body.mapping if isinstance(body.mapping, dict) and body.mapping else None
    if mapping is None:
        names = _pool_names(channel_service, max(1, min(body.limit, 300)))
        existing = sorted({t.strip() for t in list(tag_db.values())[:200] for t in str(t).split(",") if t.strip()})
        r = ai.suggest_tags(names, existing, extra=body.extra or "")
        if not r.get("ok"):
            return r
        mapping = r.get("mapping") or {}
    applied, failed = 0, []
    if body.apply and mapping:
        from app.config import Config
        with channel_service.lock:
            for ch in channel_service.pool:
                tags = mapping.get(ch.get("name"))
                if not tags:
                    continue
                try:
                    merged = [t.strip() for t in str(ch.get("tag") or "").split(",") if t.strip()]
                    for t in tags:
                        if t and t not in merged:
                            merged.append(t)
                    new_tag = ",".join(merged)
                    ch["tag"] = new_tag
                    if ch.get("url"):
                        if new_tag:
                            tag_db[ch["url"]] = new_tag
                        else:
                            tag_db.pop(ch["url"], None)
                    applied += 1
                except Exception as e:
                    failed.append({"name": ch.get("name"), "error": str(e)[:80]})
        if applied:
            Config.save_json(Config.TAG_DB_FILE, tag_db)
            try:
                channel_service._store_rebuild()
            except Exception:
                pass
            try:
                from app import main
                main._save_cache()
            except Exception:
                pass
    return {"ok": True, "mapping": mapping, "count": len(mapping),
            "applied": applied, "failed": failed}


class SearchReq(BaseModel):
    query: str
    limit: int = 400
    extra: str = ""


@router.post("/search-expand")
def ai_search_expand(body: SearchReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service)):
    """#4 模糊搜索同义词扩展（只查询，不落库）"""
    names = _pool_names(channel_service, max(1, min(body.limit, 500)))
    return ai.expand_search(body.query, names, _pool_groups(channel_service), extra=body.extra or "")


class CleanReq(BaseModel):
    limit: int = 60
    extra: str = ""


@router.post("/clean-names")
def ai_clean_names(body: CleanReq, ai=Depends(get_ai), nf=Depends(get_namefix_service)):
    """#1 增强版：用 namefix 的规则候选（含 OCR/EPG 线索）交模型裁决"""
    items = []
    try:
        src = list((getattr(nf, "items", {}) or {}).values())
    except Exception:
        src = []
    for it in src[:max(1, min(body.limit, 60))]:
        if not isinstance(it, dict):
            continue
        items.append({
            "name": it.get("old") or it.get("name") or "",
            "ocr": it.get("ocr") or it.get("ocr_text") or "",
            "epg": it.get("epg") or it.get("epg_name") or "",
            "candidates": [it.get("new")] if it.get("new") else [],
        })
    if not items:
        return {"ok": False, "error": "名称校正里还没有候选（请先运行「名称校正 → 扫描」）"}
    return ai.clean_names(items, extra=body.extra or "")


class VerifyReq(BaseModel):
    name: str
    url: str = ""
    group: str = ""
    extra: str = ""


@router.post("/verify-source")
def ai_verify_source(body: VerifyReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service),
                     shots=Depends(get_screenshot_service)):
    """#2 源真实性核验（视觉模型读截图）"""
    url = (body.url or "").strip()
    if not url:
        with channel_service.lock:
            for ch in channel_service.pool:
                if ch.get("name") == body.name:
                    url = ch.get("url") or ""
                    break
    path = ""
    try:
        path = shots.path_for(url) if url else ""
    except Exception:
        path = ""
    return ai.verify_source(body.name, path, group=body.group, extra=body.extra or "")


class RankReq(BaseModel):
    name: str
    extra: str = ""


@router.post("/rank-sources")
def ai_rank_sources(body: RankReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service)):
    """#6 多源择优排序"""
    sources = []
    with channel_service.lock:
        for ch in channel_service.pool:
            if ch.get("name") != body.name:
                continue
            raw = ch.get("sources") or []
            if isinstance(raw, list) and raw:
                for s in raw:
                    if isinstance(s, dict):
                        sources.append({"url": s.get("url"), "stack": s.get("stack"),
                                        "res": s.get("res"), "ms": s.get("ms"),
                                        "ok_count": s.get("ok_count", 0), "fail_count": s.get("fail_count", 0)})
                    else:
                        sources.append({"url": str(s)})
            if ch.get("url") and not any(s.get("url") == ch.get("url") for s in sources):
                sources.append({"url": ch.get("url"), "stack": ch.get("stack"), "res": ch.get("res"),
                                "ms": ch.get("ms")})
            break
    return ai.rank_sources(body.name, sources, extra=body.extra or "")


class DiagnoseReq(BaseModel):
    lines: int = 200
    context: dict | None = None
    extra: str = ""


@router.post("/diagnose")
def ai_diagnose(body: DiagnoseReq, ai=Depends(get_ai)):
    """#9 播放故障诊断：读 app.log 尾部 + 上下文"""
    import os
    from app import main
    log_path = os.path.join(getattr(main, "DATA_DIR", "."), "app.log")
    tail = ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            tail = "".join(f.readlines()[-max(20, min(body.lines, 800)):])
    except Exception as e:
        return {"ok": False, "error": "读取日志失败：%s" % str(e)[:120]}
    return ai.diagnose_playback(tail, context=body.context, extra=body.extra or "")


class EpgSuggestReq(BaseModel):
    limit: int = 200
    extra: str = ""


@router.post("/epg-suggest")
def ai_epg_suggest(body: EpgSuggestReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service)):
    """#10 EPG 智能补齐：推断每个频道该用哪类 EPG 源"""
    return ai.suggest_epg_sources(_pool_names(channel_service, max(1, min(body.limit, 300))),
                                  extra=body.extra or "")


class EpgSumReq(BaseModel):
    name: str
    programs: list[str] = []
    extra: str = ""


@router.post("/epg-summary")
def ai_epg_summary(body: EpgSumReq, ai=Depends(get_ai)):
    """#10 EPG 节目单中文摘要"""
    return ai.summarize_epg(body.name, body.programs, extra=body.extra or "")


class NlReq(BaseModel):
    text: str
    context: dict | None = None
    extra: str = ""


@router.post("/nl")
def ai_nl(body: NlReq, ai=Depends(get_ai)):
    """#8 自然语言操作：只解析成调用计划，由前端确认后自行执行（后端不代执行）"""
    return ai.nl_plan(body.text, context=body.context, extra=body.extra or "")


class GarbledReq(BaseModel):
    text: str
    extra: str = ""


@router.post("/garbled")
def ai_garbled(body: GarbledReq, ai=Depends(get_ai)):
    """#5 乱码智能还原判断"""
    return ai.judge_garbled(body.text, extra=body.extra or "")


class SubAuditReq(BaseModel):
    url: str = ""
    limit: int = 120
    extra: str = ""


@router.post("/audit-subscription")
def ai_audit_subscription(body: SubAuditReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service)):
    """#7 订阅源体检：结构/广告台/重复度打分"""
    return ai.audit_subscription(body.url, _pool_names(channel_service, max(10, min(body.limit, 200))),
                                 _pool_groups(channel_service), extra=body.extra or "")


class WallReq(BaseModel):
    limit: int = 120
    extra: str = ""


@router.post("/wall-order")
def ai_wall_order(body: WallReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service)):
    """#11 频道墙智能排布"""
    chs = []
    with channel_service.lock:
        for ch in channel_service.pool[:max(1, min(body.limit, 200))]:
            tags = [t.strip() for t in str(ch.get("tag") or "").split(",") if t.strip()]
            chs.append({"name": ch.get("name"), "fav": "fav" in tags, "ms": ch.get("ms"),
                        "res": ch.get("res"), "group": ch.get("group")})
    return ai.suggest_wall_order(chs, extra=body.extra or "")


class ExportDescReq(BaseModel):
    limit: int = 60
    extra: str = ""


@router.post("/export-desc")
def ai_export_desc(body: ExportDescReq, ai=Depends(get_ai), channel_service=Depends(get_channel_service)):
    """#12 导出描述生成：为每个分组生成一句说明"""
    names_by_group = {}
    with channel_service.lock:
        for ch in channel_service.pool:
            g = ch.get("group") or "未分组"
            names_by_group.setdefault(g, [])
            if len(names_by_group[g]) < 12 and ch.get("name"):
                names_by_group[g].append(ch.get("name"))
    groups = list(names_by_group.keys())[:max(1, min(body.limit, 60))]
    return ai.export_descriptions(groups, names_by_group, extra=body.extra or "")


@router.get("/usage")
def ai_usage(ai=Depends(get_ai)):
    return ai.usage_today()


@router.post("/usage/reset")
def ai_usage_reset(ai=Depends(get_ai)):
    try:
        import os
        if os.path.exists(ai._usage_file):
            os.remove(ai._usage_file)
    except Exception:
        pass
    return {"ok": True, **ai.usage_today()}


@router.get("/cache/stats")
def ai_cache_stats(ai=Depends(get_ai)):
    return ai.cache_stats()


@router.post("/cache/clear")
def ai_cache_clear(ai=Depends(get_ai)):
    return ai.cache_clear()
