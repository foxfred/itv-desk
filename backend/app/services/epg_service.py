"""EPG 服务 - 完整复刻现有 EPG 加载逻辑"""
import os
import re
import threading
import xml.etree.ElementTree as ET
import gzip
from datetime import datetime
from app.utils.network import download_url
from app.utils.m3u_parser import Parser


def _natural_key(name):
    """自然数排序键：CCTV10 排在 CCTV9 之后，而非 CCTV1 之后"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name or '')]


def _normalize_name(name):
    """标准化名称：转小写、压缩空白、去除常见符号"""
    if not name:
        return ''
    return re.sub(r'[\s\-_\.·]', '', name.lower())


def _name_tokens(name):
    """提取名称中的字母数字 token，如 CCTV10 -> ['cctv', '10']"""
    if not name:
        return []
    return [t for t in re.split(r'[^a-z0-9\u4e00-\u9fff]+', name.lower()) if t]


class EpgService:
    """EPG 数据管理服务

    新增能力（相较原版）：
    - 落盘缓存（epg_cache.json）：EPG 加载后自动缓存，重启后自动恢复，无需重复下载；
    - 按频道名自动匹配（match_channel）：供播放器/节目单按名称联动；
    - 定时刷新（start_refresh_scheduler）：记录最近一次 EPG 源，按间隔后台重新拉取。
    """

    def __init__(self, log_callback=None, data_dir=None):
        self.log_callback = log_callback or (lambda msg: None)
        self.data_dir = data_dir or "."
        self.cache_path = os.path.join(self.data_dir, "epg_cache.json")
        self.source_path = os.path.join(self.data_dir, "epg_source.json")
        self.epg_data = {}
        self.epg_loaded = False
        self.epg_loading = False
        self.epg_error = None
        self.epg_count = 0
        self._stop = threading.Event()
        self._thread = None
        # 启动时尝试恢复缓存，使 EPG 跨重启可用
        try:
            self.load_cache()
        except Exception:
            pass

    # -------------------- 缓存 / 源持久化 --------------------
    def save_cache(self):
        try:
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.epg_data, f, ensure_ascii=False)
            os.replace(tmp, self.cache_path)
        except Exception:
            pass

    def load_cache(self):
        try:
            if not os.path.exists(self.cache_path):
                return False
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self.epg_data = json.load(f)
            if isinstance(self.epg_data, dict) and self.epg_data:
                self.epg_loaded = True
                self.epg_count = len(self.epg_data)
                return True
        except Exception:
            pass
        return False

    def save_source(self, url, proxy=""):
        try:
            with open(self.source_path, "w", encoding="utf-8") as f:
                json.dump({"url": url, "proxy": proxy}, f, ensure_ascii=False)
        except Exception:
            pass

    def load_source(self):
        try:
            if not os.path.exists(self.source_path):
                return None
            with open(self.source_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def load_epg(self, url, proxy=""):
        """加载 EPG 数据（后台线程执行，避免阻塞请求）"""
        if self.epg_loading:
            return {"loading": True, "error": "正在加载中"}
        self.epg_loading = True
        self.epg_loaded = False
        self.epg_error = None
        self.epg_count = 0
        self.epg_data = {}
        self.save_source(url, proxy)
        threading.Thread(target=self._load_worker, args=(url, proxy), daemon=True).start()
        return {"loading": True}

    def get_status(self):
        """返回 EPG 加载状态（供前端轮询）"""
        return {
            "loading": self.epg_loading,
            "loaded": self.epg_loaded,
            "count": self.epg_count,
            "error": self.epg_error,
        }

    def _load_worker(self, url, proxy=""):
        try:
            self.log_callback(f"开始加载 EPG: {url}")
            content, err = download_url(url, proxy if proxy else None)
            if err:
                self.epg_error = err
                self.log_callback(f"EPG 下载失败: {err}")
                return
            if isinstance(content, bytes):
                if content[:2] == b'\x1f\x8b':
                    content = gzip.decompress(content).decode('utf-8', errors='ignore')
                else:
                    content = content.decode('utf-8', errors='ignore')
            if content.startswith('\ufeff'):
                content = content[1:]
            match = re.search(r'<tv\s', content) or re.search(r'<tv[> >]', content)
            if not match:
                raise Exception("未找到 <tv 标签")
            content = content[match.start():]
            root = ET.fromstring(content)
            epg_map = {}
            for channel in root.findall('channel'):
                cid = channel.get('id', '')
                dn = channel.find('display-name')
                if dn is not None and cid:
                    epg_map[dn.text or cid] = {'id': cid, 'name': dn.text or cid, 'programs': []}
            for prog in root.findall('programme'):
                cid = prog.get('channel', '')
                start = prog.get('start', '')
                stop = prog.get('stop', '')
                t = prog.find('title')
                if t is not None and cid:
                    for info in epg_map.values():
                        if info['id'] == cid:
                            info['programs'].append({'start': start, 'stop': stop, 'title': t.text or ''})
                            break
            self.epg_data = epg_map
            self.epg_count = len(epg_map)
            self.epg_loaded = True
            self.save_cache()
            self.log_callback(f"EPG 加载完成，共 {len(epg_map)} 个频道")
        except Exception as e:
            self.epg_error = str(e)
            self.log_callback(f"EPG 解析失败: {e}")
        finally:
            self.epg_loading = False

    def correct_names(self, channel_service):
        """校正频道名"""
        if not self.epg_loaded or not self.epg_data:
            self.log_callback("  [EPG] 请先加载 EPG 数据")
            return {"error": "请先加载 EPG"}
        corrected = 0
        with channel_service.lock:
            for ch in channel_service.pool:
                old_name = ch.get("name", "")
                best_match, best_score = None, 0
                for epg_name in self.epg_data.keys():
                    if epg_name in old_name or old_name in epg_name:
                        if len(epg_name) > best_score:
                            best_score, best_match = len(epg_name), epg_name
                    clean_old = re.sub(r'[\[\]\(\)（）]|HD|4K|高清|超清|标清|FHD', '', old_name).strip()
                    clean_epg = re.sub(r'[\[\]\(\)（）]|HD|4K|高清|超清|标清|FHD', '', epg_name).strip()
                    if clean_old and clean_epg and (clean_epg in clean_old or clean_old in clean_epg):
                        if len(clean_epg) > best_score:
                            best_score, best_match = len(clean_epg), epg_name
                if best_match and best_match != old_name:
                    ch["name"] = best_match
                    corrected += 1
        self.log_callback(f"  [EPG] 校正了 {corrected} 个频道名")
        return {"corrected": corrected}

    def update_groups(self, channel_service):
        """根据 EPG 数据校正频道分组（复用统一分组算法，保证与导入/重新分组一致）。"""
        if not self.epg_loaded or not self.epg_data:
            self.log_callback("  [EPG] 请先加载 EPG 数据")
            return {"error": "请先加载 EPG"}
        from app.config import Config
        _settings = Config.load_settings()
        foreign_name = _settings.get("foreign_group_name", "外国频道")
        custom_rules = _settings.get("custom_group_rules", []) or []
        updated = 0
        with channel_service.lock:
            for ch in channel_service.pool:
                ch_name = ch.get("name", "")
                epg_info = None
                for epg_name, info in self.epg_data.items():
                    if ch_name in epg_name or epg_name in ch_name:
                        epg_info = info
                        break
                if epg_info:
                    new_group = Parser.get_channel_group(epg_info.get('name', ch_name), custom_rules, foreign_name)
                    if new_group and new_group != ch.get('group'):
                        ch['group'] = new_group
                        updated += 1
        if updated:
            try:
                from app.services.channel_store import ChannelStore
                rows = [
                    ChannelStore._row_from_channel(ch, i, normalize_url(ch["url"]))
                    for i, ch in enumerate(channel_service.pool)
                ]
                channel_service.store.clear()
                channel_service.store.upsert_many(rows)
            except Exception:
                pass
        self.log_callback(f"  [EPG] 更新了 {updated} 个频道的分组")
        return {"updated": updated}

    def search(self, keyword):
        """按关键词搜索当前正在播放的节目"""
        if not self.epg_loaded or not self.epg_data:
            return {"error": "请先加载 EPG"}
        kw = keyword.lower()
        now = datetime.now()
        results = []
        for epg_name, info in self.epg_data.items():
            for prog in info.get('programs', []):
                title = prog.get('title', '')
                if kw in title.lower():
                    s, e = prog.get('start', ''), prog.get('stop', '')
                    try:
                        start = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
                        stop = datetime.strptime(e[:14], "%Y%m%d%H%M%S")
                        if start <= now <= stop:
                            results.append({
                                'channel': epg_name,
                                'title': title,
                                'start': start.strftime("%H:%M"),
                                'stop': stop.strftime("%H:%M")
                            })
                    except Exception:
                        continue
        return {"results": results}

    def get_program(self, name):
        """获取指定频道的当前节目"""
        if not self.epg_loaded or not self.epg_data:
            return {"program": None}
        now = datetime.now()
        for epg_name, info in self.epg_data.items():
            if epg_name in name or name in epg_name:
                for prog in info.get('programs', []):
                    s, e = prog.get('start', ''), prog.get('stop', '')
                    if not s or not e:
                        continue
                    try:
                        start = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
                        stop = datetime.strptime(e[:14], "%Y%m%d%H%M%S")
                        if start <= now <= stop:
                            return {"program": prog.get('title', '未知节目')}
                    except Exception:
                        continue
                break
        return {"program": None}

    def get_channels(self):
        """返回 EPG 频道列表及每个频道的当前节目（供前端节目单界面）"""
        if not self.epg_loaded or not self.epg_data:
            return {"error": "请先加载 EPG"}
        now = datetime.now()
        channels = []
        for name, info in self.epg_data.items():
            current = None
            for prog in info.get('programs', []):
                s, e = prog.get('start', ''), prog.get('stop', '')
                if not s or not e:
                    continue
                try:
                    start = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
                    stop = datetime.strptime(e[:14], "%Y%m%d%H%M%S")
                    if start <= now <= stop:
                        current = prog.get('title', '')
                        break
                except Exception:
                    continue
            channels.append({
                "name": name,
                "id": info.get('id', ''),
                "current": current,
                "count": len(info.get('programs', [])),
            })
        channels.sort(key=lambda c: _natural_key(c['name']))
        return {"channels": channels}

    def _find_info(self, name):
        """按频道名找到最匹配的 EPG 条目（精确 → 归一化 → token/包含受限匹配）"""
        if not self.epg_loaded or not self.epg_data:
            return None
        # 优先精确匹配，其次忽略大小写/空格后一致，最后才做受限的包含匹配，
        # 避免 CCTV10 被 "CCTV1" 这类前缀子串抢先匹配到错误频道
        exact = self.epg_data.get(name)
        if exact:
            return exact
        norm = _normalize_name(name)
        for epg_name, v in self.epg_data.items():
            if _normalize_name(epg_name) == norm:
                return v
        name_tokens = _name_tokens(name)
        for epg_name, v in self.epg_data.items():
            if _normalize_name(epg_name) == norm:
                continue
            epg_tokens = _name_tokens(epg_name)
            # 短名称(纯字母数字缩写)要求完全一致；长名称允许包含但不允许单向短子串误配
            if epg_tokens and epg_tokens == name_tokens:
                return v
            if len(name) >= 4 and len(epg_name) >= 4 and (
                _normalize_name(epg_name) in norm or norm in _normalize_name(epg_name)
            ):
                return v
        return None

    def match_channel(self, name):
        """按频道名自动匹配 EPG：返回匹配名 + 当前节目 + 今日节目单（供播放器联动）"""
        if not self.epg_loaded or not self.epg_data:
            return {"matched": None, "channel": name, "current": None, "programs": []}
        info = self._find_info(name)
        if not info:
            return {"matched": None, "channel": name, "current": None, "programs": []}
        now = datetime.now()
        day = now.strftime("%Y%m%d")
        current = None
        programs = []
        for prog in info.get('programs', []):
            s = prog.get('start', '')
            if not s:
                continue
            try:
                start = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
            except Exception:
                continue
            if start.strftime("%Y%m%d") != day:
                continue
            stop = None
            if prog.get('stop'):
                try:
                    stop = datetime.strptime(prog['stop'][:14], "%Y%m%d%H%M%S")
                except Exception:
                    stop = None
            state = 'upcoming'
            if stop and now > stop:
                state = 'ended'
            elif start <= now and (stop is None or now <= stop):
                state = 'current'
                current = prog.get('title', '')
            progress = 0
            if state == 'current' and stop and stop > start:
                total = (stop - start).total_seconds()
                if total > 0:
                    progress = round((now - start).total_seconds() / total * 100)
            programs.append({
                'start': start.strftime("%H:%M"),
                'stop': stop.strftime("%H:%M") if stop else '',
                'title': prog.get('title', ''),
                'state': state,
                'progress': progress,
            })
        programs.sort(key=lambda p: p['start'])
        return {"matched": info.get('name', name), "channel": name,
                "current": current, "programs": programs}

    def get_programs(self, name):
        """获取指定频道今日的完整节目单（含播放状态与进度）"""
        if not self.epg_loaded or not self.epg_data:
            return {"error": "请先加载 EPG"}
        info = self._find_info(name)
        if not info:
            return {"programs": [], "channel": name}
        now = datetime.now()
        day = now.strftime("%Y%m%d")
        programs = []
        for prog in info.get('programs', []):
            s = prog.get('start', '')
            if not s:
                continue
            try:
                start = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
            except Exception:
                continue
            if start.strftime("%Y%m%d") != day:
                continue
            stop = None
            if prog.get('stop'):
                try:
                    stop = datetime.strptime(prog['stop'][:14], "%Y%m%d%H%M%S")
                except Exception:
                    stop = None
            state = 'upcoming'
            if stop and now > stop:
                state = 'ended'
            elif start <= now and (stop is None or now <= stop):
                state = 'current'
            progress = 0
            if state == 'current' and stop and stop > start:
                total = (stop - start).total_seconds()
                if total > 0:
                    progress = round((now - start).total_seconds() / total * 100)
            programs.append({
                'start': start.strftime("%H:%M"),
                'stop': stop.strftime("%H:%M") if stop else '',
                'title': prog.get('title', ''),
                'state': state,
                'progress': progress,
            })
        programs.sort(key=lambda p: p['start'])
        return {"programs": programs, "channel": info.get('name', name)}

    # -------------------- 定时刷新 --------------------
    def start_refresh_scheduler(self, interval_seconds):
        """按间隔后台重新拉取最近一次 EPG 源（interval_seconds<=0 关闭）"""
        self.stop_refresh_scheduler()
        if interval_seconds and interval_seconds > 0:
            self._stop.clear()
            self._thread = threading.Thread(target=self._refresh_loop, args=(interval_seconds,), daemon=True)
            self._thread.start()
            self.log_callback(f"EPG 定时刷新已开启，间隔 {interval_seconds}s")

    def _refresh_loop(self, interval_seconds):
        while not self._stop.is_set():
            if self._stop.wait(interval_seconds):
                break
            src = self.load_source()
            if src and src.get("url"):
                try:
                    self.load_epg(src["url"], src.get("proxy", ""))
                except Exception as e:
                    self.log_callback(f"EPG 定时刷新失败: {e}")

    def stop_refresh_scheduler(self):
        self._stop.set()
        self._thread = None

    def refresh_from_source(self):
        """立即按已保存的源重新拉取 EPG"""
        src = self.load_source()
        if not src or not src.get("url"):
            return {"error": "没有已保存的 EPG 源，请先加载一次 EPG"}
        self.load_epg(src["url"], src.get("proxy", ""))
        return {"loading": True}