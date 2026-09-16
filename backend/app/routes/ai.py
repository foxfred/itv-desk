from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai", tags=["ai"])

KEY_FIELDS = ("ai_enabled", "ai_base_url", "ai_api_key", "ai_model", "ai_timeout",
              "ai_temperature", "ai_max_tokens", "ai_use_proxy", "ai_prompt_extra")


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


def get_ai():
    from app.main import ai_service
    return ai_service


def get_settings():
    from app.main import settings
    return settings


def get_channel_service():
    from app.main import channel_service
    return channel_service


@router.get("/config")
def ai_config(settings=Depends(get_settings)):
    return {k: settings.get(k) for k in KEY_FIELDS}


@router.post("/config")
def ai_config_save(body: dict, settings=Depends(get_settings)):
    from app import main
    from app.config import Config
    merged = dict(getattr(main, "settings", {}) or {})
    for k, v in Config.DEFAULTS.items():
        merged.setdefault(k, v)
    for k in KEY_FIELDS:
        if k in (body or {}):
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
