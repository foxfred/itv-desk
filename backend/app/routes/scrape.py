"""抓取/导入路由"""
import os
import re
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api", tags=["scrape"])


class ScrapeReq(BaseModel):
    url: str
    start_page: int = 1
    end_page: int = 1
    suffix_list: str = "m3u,m3u8,txt"
    proxy: str = ""
    mirror: str = "不使用加速"


class BatchScrapeReq(BaseModel):
    urls: List[str]
    suffix_list: str = "m3u,m3u8,txt"
    proxy: str = ""
    mirror: str = "不使用加速"


class ImportUrlReq(BaseModel):
    url: str
    proxy: str = ""


class ImportUrlsReq(BaseModel):
    urls: List[str]
    proxy: str = ""


class ImportTextReq(BaseModel):
    text: str


class ChannelItem(BaseModel):
    name: str
    url: str
    group: str = ""
    logo: str = ""
    tag: str = ""
    status: str = "未检查"
    ms: str = "-"
    res: str = "-"


class ImportChannelsReq(BaseModel):
    channels: List[ChannelItem]


def get_scrape_service():
    from app.main import scrape_service
    return scrape_service


def get_channel_service():
    from app.main import channel_service
    return channel_service


def get_log():
    from app.main import log
    return log


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


def get_check_state():
    from app.main import check_service
    return check_service.state


def get_check_service():
    from app.main import check_service
    return check_service


@router.post("/scrape")
def scrape(body: ScrapeReq, scrape_service=Depends(get_scrape_service)):
    if scrape_service.state["running"]:
        raise HTTPException(400, "已有抓取在进行中")
    if not body.url:
        raise HTTPException(400, "请输入目标网址")
    try:
        start = int(body.start_page)
        end = int(body.end_page)
    except (ValueError, TypeError):
        raise HTTPException(400, "页码必须为数字")
    ok, err = scrape_service.run_scrape(body.url, start, end, body.suffix_list, body.proxy, body.mirror)
    if not ok:
        raise HTTPException(400, err)
    return {"started": True, "total": 1}


@router.post("/scrape-batch")
def scrape_batch(body: BatchScrapeReq, scrape_service=Depends(get_scrape_service)):
    if scrape_service.state["running"]:
        raise HTTPException(400, "已有抓取在进行中")
    if not body.urls:
        raise HTTPException(400, "请输入至少一个网址")
    ok, err = scrape_service.run_scrape_batch(body.urls, body.suffix_list, body.proxy, body.mirror)
    if not ok:
        raise HTTPException(400, err)
    return {"started": True, "total": len(body.urls)}


@router.get("/scrape/status")
def scrape_status(scrape_service=Depends(get_scrape_service)):
    return scrape_service.get_status()


@router.post("/scrape-stop")
def scrape_stop(scrape_service=Depends(get_scrape_service)):
    scrape_service.stop()
    return {"ok": True}


def _download_and_inject(url, proxy, channel_service, log):
    from app.utils.network import download_url
    from app.utils.m3u_parser import Parser, extract_channels
    content, err = download_url(url, proxy if proxy else None)
    if err:
        return 0, 0, err
    parsed = Parser.parse_local_file(content)
    if not parsed:
        parsed = extract_channels(content)
    added, dup = channel_service.add_channels(parsed, origin="manual")
    return added, dup, None


@router.post("/import-url")
def import_url(body: ImportUrlReq, channel_service=Depends(get_channel_service), log=Depends(get_log)):
    added, dup, err = _download_and_inject(body.url, body.proxy, channel_service, log)
    if err:
        return {"error": err}
    log(f"导入完成，新增 {added} 个频道，去重 {dup} 个")
    return {"added": added, "dup": dup}


@router.post("/import-urls")
def import_urls(body: ImportUrlsReq, channel_service=Depends(get_channel_service), log=Depends(get_log)):
    total_added, total_dup = 0, 0
    errs = []
    for url in body.urls:
        added, dup, err = _download_and_inject(url, body.proxy, channel_service, log)
        if err:
            errs.append({"url": url, "error": err})
            continue
        total_added += added
        total_dup += dup
    log(f"批量导入完成，新增 {total_added} 个频道，去重 {total_dup} 个")
    return {"added": total_added, "dup": total_dup, "errors": errs}


@router.post("/import-text")
def import_text(body: ImportTextReq, channel_service=Depends(get_channel_service),
                log=Depends(get_log), settings=Depends(get_settings)):
    from app.utils.m3u_parser import Parser, extract_channels
    from app.config import FileManager
    parsed = Parser.parse_local_file(body.text)
    if not parsed:
        parsed = extract_channels(body.text)
    added, dup = channel_service.add_channels(parsed, origin="manual")
    if added > 0:
        _save_cache(settings, channel_service)
    log(f"导入完成，新增 {added} 个频道，去重 {dup} 个")
    return {"added": added, "dup": dup}


@router.post("/import-channels")
def import_channels(body: ImportChannelsReq, channel_service=Depends(get_channel_service),
                    log=Depends(get_log), settings=Depends(get_settings)):
    """导入完整频道对象（保留分组、logo等元数据）"""
    channels = [ch.dict() for ch in body.channels]
    added, dup = channel_service.add_channels(channels, origin="manual")
    if added > 0:
        _save_cache(settings, channel_service)
    log(f"导入频道完成，新增 {added} 个，去重 {dup} 个")
    return {"added": added, "dup": dup}


@router.post("/smart-paste")
def smart_paste(body: ImportTextReq, channel_service=Depends(get_channel_service),
                log=Depends(get_log), settings=Depends(get_settings),
                check_state=Depends(get_check_state),
                check_service=Depends(get_check_service)):
    """智能粘贴：完全复刻原版 _smart_paste 逻辑"""
    text = body.text.strip()
    if not text:
        return {"error": "剪贴板为空"}
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return {"error": "剪贴板为空"}
    is_m3u = any(l.startswith("#EXTM3U") or l.startswith("#EXTINF") for l in lines)
    smart_group = settings.get("smart_paste_default_group", "粘贴导入")
    new_channels = []
    duplicate_count = 0
    invalid_count = 0

    def is_valid_stream_url(u):
        if not u:
            return False
        ul = u.lower().strip()
        valid_exts = ('.m3u8', '.m3u', '.ts', '.mp4', '.flv', '.mkv', '.avi', '.mov',
                      '.wmv', '.webm', '.mpg', '.mpeg', '.rm', '.rmvb', '.3gp')
        if any(ul.endswith(e) for e in valid_exts):
            return True
        if any(k in ul for k in ('m3u8', 'm3u', 'ts', 'playlist', 'live', 'stream', 'hls')):
            return True
        try:
            p = urlparse(u)
            # 只要是有合法流媒体协议scheme的URL都接受
            if p.scheme in ('http', 'https', 'rtmp', 'rtsp', 'udp', 'mms'):
                return True
            return False
        except Exception:
            return False

    with channel_service.lock:
        existing_urls = {ch.get("url", "") for ch in channel_service.pool}

    from app.utils.m3u_parser import extract_channels
    if is_m3u:
        parsed = extract_channels(text)
        if not parsed:
            return {"error": "M3U 解析失败，未提取到频道"}
        for ch in parsed:
            url = ch.get("url", "")
            if url in existing_urls:
                duplicate_count += 1
                continue
            name = ch.get("name", "未知频道")
            for word in ["可用", "失效", "在线", "离线", "可播放", "不可用", "直播源"]:
                if name.endswith(word):
                    name = name[:-len(word)].strip()
                    break
            logo = ch.get("logo", "")
            tag = ""
            m = re.search(r'tvg-tag="([^"]+)"', ch.get("raw_extinf", ""))
            if m:
                tag = m.group(1)
            new_channels.append({"name": name, "url": url,
                                 "group": ch.get("group", smart_group),
                                 "logo": logo, "tag": tag})
    else:
        for line in lines:
            name = None
            url = None
            group = smart_group
            if ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2 and is_valid_stream_url(parts[1].strip()):
                    raw_name = parts[0].strip()
                    url = parts[1].strip()
                    if raw_name.startswith("[") and "]" in raw_name:
                        try:
                            group = raw_name.split("]", 1)[0].strip("[")
                            name = raw_name.split("]", 1)[1].strip()
                        except Exception:
                            name = raw_name
                    else:
                        name = raw_name
            if not url and is_valid_stream_url(line):
                url = line
                p = urlparse(url)
                name = os.path.basename(p.path)
                if not name or name == "/" or name == "":
                    name = "未知频道"
                if '.' in name:
                    name = os.path.splitext(name)[0]
                if len(name) < 2:
                    name = p.netloc or "未知频道"
                name = name.replace('_', ' ').replace('-', ' ').title()
            if not url:
                invalid_count += 1
                continue
            if url in existing_urls:
                duplicate_count += 1
                continue
            new_channels.append({"name": name or "未知频道", "url": url,
                                 "group": group, "logo": "", "tag": ""})

    if invalid_count:
        log(f"智能粘贴：{invalid_count} 行无效链接被忽略")
    if duplicate_count:
        log(f"智能粘贴：{duplicate_count} 条重复链接已跳过")
    if not new_channels:
        return {"added": 0, "dup": 0, "message": "没有新的有效频道可导入"}

    added, dup = channel_service.add_channels(new_channels, origin="manual")
    if added > 0:
        _save_cache(settings, channel_service)
    log(f"智能粘贴成功：新增 {added} 个频道（去重 {dup} 条）")

    auto_repair = False
    if added > 0 and not check_state["running"]:
        with channel_service.lock:
            new_added = channel_service.pool[:added]
        if new_added:
            log(f"开始自动洗选修补 {len(new_added)} 个频道...")
            check_service.start_check(new_added, 20, 2, 1)
            auto_repair = True
    return {"added": added, "dup": dup, "auto_repair": auto_repair}