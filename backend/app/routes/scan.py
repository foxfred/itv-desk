"""网段扫描路由 - /api/scan"""
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api", tags=["scan"])


def get_scan_service():
    from app.main import scan_service
    return scan_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_log():
    from app.main import log
    return log


def get_settings():
    from app.main import settings
    return settings


def _save_cache(channel_service, settings):
    from app.config import FileManager
    try:
        cache_file = settings.get("cache_file_name", "channels_cache.json")
        with channel_service.lock:
            data = channel_service.pool.copy()
        FileManager.write_json_atomic(cache_file, data)
    except Exception:
        pass


class DeriveReq(BaseModel):
    urls: List[str]


class ScanReq(BaseModel):
    template: str
    path: str = "/"
    scheme: str = "http"
    proxy: str = ""
    timeout: int = 0
    max_workers: int = 0


class ImportReq(BaseModel):
    results: List[dict]


@router.post("/scan/derive")
def derive_from_urls(body: DeriveReq, scan_service=Depends(get_scan_service)):
    """从频道 URL 列表反推可扫描的 IP 段模板"""
    templates = scan_service.derive_templates(body.urls)
    return {"templates": templates}


@router.post("/scan")
def scan_range(body: ScanReq, scan_service=Depends(get_scan_service)):
    """按模板扫描 IP 段，返回每个探测点的结果"""
    timeout = body.timeout or int(scan_service._settings.get("scan_timeout", 5))
    max_workers = body.max_workers or int(scan_service._settings.get("scan_max_workers", 40))
    proxy = body.proxy or scan_service._settings.get("proxy", "")
    results = scan_service.scan(
        template=body.template,
        path=body.path,
        scheme=body.scheme,
        proxy=proxy or None,
        timeout=timeout,
        max_workers=max_workers,
    )
    return {"results": results, "total": len(results), "online": sum(1 for r in results if r.get("online"))}


@router.post("/scan/import")
def import_scan_results(body: ImportReq, channel_service=Depends(get_channel_service),
                        scan_service=Depends(get_scan_service),
                        log=Depends(get_log), settings=Depends(get_settings)):
    """将扫描结果导入频道池"""
    added, dup = scan_service.import_results(channel_service, body.results)
    if added > 0:
        _save_cache(channel_service, settings)
        log(f"扫描导入：新增 {added} 个频道")
    return {"added": added, "dup": dup}
