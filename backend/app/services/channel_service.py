import os
import re
import threading
import json
import time
import uuid
import urllib.parse
import concurrent.futures
from datetime import datetime, timezone
from app.utils.network import normalize_url, format_github_raw_url
from app.utils.m3u_parser import Parser
from app.services.channel_store import ChannelStore
from app.config import Config


def _new_health():
    return {
        "success": 0,
        "fail": 0,
        "consecutive_fail": 0,
        "decode_fail": 0,
        "last_check": None,
        "last_error": "",
        "last_first_frame_ms": None,
        "score": None,
        "dead": False,
        "decode_unsupported": False,
    }


def _normalize_sources(ch):
    s = ch.get("sources")
    if isinstance(s, list) and s:
        out = []
        for u in s:
            u = (u or "").strip()
            if u and u not in out:
                out.append(u)
        if out:
            return out
    return [ch.get("url", "")]


_MULTI_FIELDS = ("sources", "source_groups", "source_tags", "source_is_fake_live",
                 "source_health", "source_is_fake", "filter_relaxed")


def _strip_multi_fields(ch):
    for f in _MULTI_FIELDS:
        ch.pop(f, None)
    return ch


def _expand_multi(items):
    out = []
    for ch in items or []:
        srcs = _normalize_sources(ch)
        base = ch.get("name", "")
        if len(srcs) <= 1:
            row = dict(ch)
            row["url"] = srcs[0] if srcs else ch.get("url", "")
            out.append(_strip_multi_fields(row))
            continue
        src_tags = ch.get("source_tags") or {}
        src_fl = ch.get("source_is_fake_live") or {}
        for i, u in enumerate(srcs):
            row = dict(ch)
            row["url"] = u
            row["name"] = f"{base} #{i + 1}"
            row["tag"] = (src_tags.get(u) or ch.get("tag") or "")
            row["is_fake_live"] = bool(src_fl.get(u)) or bool(ch.get("is_fake_live"))
            out.append(_strip_multi_fields(row))
    return out


#   res      : '-' | '1080P' | '720P' | '3840' | '1920' | '1280' | '854' | '640' | '768x576'
_TEXT_RANK = {
    "8k": 8, "4320p": 8, "4k": 7, "2160p": 7, "uhd": 7, "超清": 7, "蓝光": 6,
    "2k": 6, "1440p": 6, "1080p": 5, "1080i": 5, "fhd": 5, "高清": 5, "全高清": 5,
    "720p": 3, "hd": 3, "标清": 2, "576p": 2, "480p": 1, "360p": 0, "低清": 0, "流畅": 0,
}


def _rank_of(height):
    if height is None:
        return -1
    for bound, rank in ((2160, 7), (1440, 6), (1080, 5), (720, 3), (576, 2), (480, 1), (360, 0)):
        if height >= bound:
            return rank
    return 0


def _num_rank(s, is_quality):
    if "x" in s:
        m2 = re.search(r"x\s*(\d{3,5})", s)
        if m2:
            return _rank_of(int(m2.group(1)))
    m = re.search(r"(\d{3,5})", s)
    if not m:
        return -1
    n = int(m.group(1))
    if re.search(r"[pi]$", s) or is_quality:
        return _rank_of(n)
    return _rank_of(int(n * 9 / 16))


def _cue_rank(x, is_quality=False):
    if x is None:
        return -1
    s = str(x).strip().lower()
    if s in ("", "-", "none", "null", "unknown"):
        return -1
    if s in _TEXT_RANK:
        return _TEXT_RANK[s]
    return _num_rank(s, is_quality)


def _ms_num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


class ChannelService:

    def __init__(self):
        self.pool = []
        self.lock = threading.RLock()
        self.clean_dup_counter = 0
        self.store = ChannelStore()
        self._online_tasks = {}

    def _store_rebuild(self):
        try:
            rows = [
                ChannelStore._row_from_channel(ch, i, normalize_url(ch["url"]))
                for i, ch in enumerate(self.pool)
            ]
            self.store.clear()
            self.store.upsert_many(rows)
        except Exception:
            pass

    def add_channels(self, parsed_list, origin=None):
        _settings = Config.load_settings()
        auto_group = _settings.get("auto_group", True)
        foreign_name = _settings.get("foreign_group_name", "外国频道")
        custom_rules = _settings.get("custom_group_rules", []) or []
        with self.lock:
            existing = {normalize_url(ch["url"]) for ch in self.pool}
            added = 0
            dup = 0
            for ch in _expand_multi(parsed_list):
                norm = normalize_url(ch["url"])
                if norm in existing:
                    dup += 1
                    continue
                existing.add(norm)
                geo, stack = Parser.detect_geo_and_stack(ch["name"], ch["url"])
                if auto_group:
                    group = Parser.get_channel_group(ch["name"], custom_rules, foreign_name)
                else:
                    group = ch.get("group", "") or Parser.get_channel_group(ch["name"], custom_rules, foreign_name)
                from app.main import tag_db, fake_live_db
                primary = ch["url"]
                self.pool.insert(0, {
                    "checked": False,
                    "id": 0,
                    "name": ch["name"],
                    "url": primary,
                    "status": ch.get("status", "未检查"),
                    "code": ch.get("code", "-"),
                    "ms": ch.get("ms", "-"),
                    "res": ch.get("res", "-"),
                    "quality": ch.get("quality", "-"),
                    "geo": geo,
                    "stack": stack,
                    "group": group,
                    "tag": tag_db.get(primary) or ch.get("tag", ""),
                    "is_fake_live": bool(fake_live_db.get(primary)) or bool(ch.get("is_fake_live", False)),
                    "logo": ch.get("logo", ""),
                    "origin": ch.get("origin") or origin or "manual",
                    "url_note": ch.get("url_note", ""),
                    "health": _new_health()
                })
                added += 1
            for idx, ch in enumerate(self.pool, 1):
                ch["id"] = idx
            self.clean_dup_counter = dup
            if added:
                try:
                    self.store.shift_orders(added)
                    new_rows = [
                        ChannelStore._row_from_channel(ch, i, normalize_url(ch["url"]))
                        for i, ch in enumerate(self.pool[:added])
                    ]
                    self.store.upsert_many(new_rows)
                except Exception:
                    pass
            return added, dup

    def reclassify_all(self):
        settings = Config.load_settings()
        foreign_name = settings.get("foreign_group_name", "外国频道")
        custom_rules = settings.get("custom_group_rules", []) or []
        changed = 0
        with self.lock:
            for ch in self.pool:
                new_g = Parser.get_channel_group(ch.get("name", ""), custom_rules, foreign_name)
                if ch.get("group") != new_g:
                    ch["group"] = new_g
                    changed += 1
            if changed:
                try:
                    rows = [
                        ChannelStore._row_from_channel(ch, i, normalize_url(ch["url"]))
                        for i, ch in enumerate(self.pool)
                    ]
                    self.store.clear()
                    self.store.upsert_many(rows)
                except Exception:
                    pass
        return changed, len(self.pool)

    def get_all(self):
        with self.lock:
            return self.pool.copy()

    def update_channel(self, channel_id, **kwargs):
        with self.lock:
            for ch in self.pool:
                if ch["id"] == channel_id:
                    kwargs.pop("sources", None)
                    kwargs.pop("source_groups", None)
                    _strip_multi_fields(ch)
                    ch.update(kwargs)
                    try:
                        self.store.update_by_norm(normalize_url(ch["url"]), **kwargs)
                    except Exception:
                        pass
                    return True
            return False

    def remove_by_filter(self, filter_func):
        with self.lock:
            before = len(self.pool)
            self.pool = [ch for ch in self.pool if not filter_func(ch)]
            for idx, ch in enumerate(self.pool, 1):
                ch["id"] = idx
            self._store_rebuild()
            return before - len(self.pool)

    def clear_all(self):
        with self.lock:
            self.pool.clear()
            try:
                self.store.clear()
            except Exception:
                pass

    def toggle_check(self, channel_id):
        with self.lock:
            for ch in self.pool:
                if ch["id"] == channel_id:
                    ch["checked"] = not ch["checked"]
                    return True
            return False

    def set_check_all(self, state):
        with self.lock:
            for ch in self.pool:
                ch["checked"] = state

    def set_check_ids(self, ids, state):
        with self.lock:
            idset = set(ids)
            for ch in self.pool:
                if ch["id"] in idset:
                    ch["checked"] = state

    def get_stats(self):
        with self.lock:
            total = len(self.pool)
            online = sum(1 for ch in self.pool if ch["status"] == "在线")
            offline = sum(1 for ch in self.pool if ch["status"] == "离线")
            return total, online, offline

    def count_unchecked(self):
        with self.lock:
            return sum(1 for ch in self.pool if ch.get("status", "未检查") == "未检查")

    def get_unchecked(self):
        with self.lock:
            return [ch for ch in self.pool if ch.get("status", "未检查") == "未检查"]

    def count(self):
        try:
            return self.store.count()
        except Exception:
            with self.lock:
                return len(self.pool)

    def get_page(self, offset=0, limit=100):
        try:
            return self.store.get_page(offset, limit)
        except Exception:
            with self.lock:
                return [
                    dict(ch, id=idx)
                    for idx, ch in enumerate(self.pool[offset:offset + limit], offset + 1)
                ]

    def search(self, text, offset=0, limit=200):
        try:
            return self.store.search(text, offset, limit)
        except Exception:
            with self.lock:
                t = (text or "").lower()
                matched = [
                    ch for ch in self.pool
                    if t in ch.get("name", "").lower()
                    or t in ch.get("group", "").lower()
                    or t in ch.get("tag", "").lower()
                ]
                return [
                    dict(ch, id=idx)
                    for idx, ch in enumerate(matched[offset:offset + limit], offset + 1)
                ]

    def get_groups(self):
        try:
            return self.store.group_counts()
        except Exception:
            from collections import Counter
            with self.lock:
                c = Counter((ch.get("group", "") or "未分组") for ch in self.pool)
            return [{"group": g, "count": n} for g, n in c.most_common()]

    _DECODE_ERROR_PREFIXES = ("h264-proxy:", "probe-hls:")

    def update_health(self, channel_id=None, url=None, success=True,
                      error=None, first_frame_ms=None):
        with self.lock:
            ch = None
            if channel_id is not None:
                for c in self.pool:
                    if c["id"] == channel_id:
                        ch = c
                        break
            elif url is not None:
                norm = normalize_url(url)
                for c in self.pool:
                    if normalize_url(c["url"]) == norm:
                        ch = c
                        break
            if ch is None:
                return None
            h = ch.setdefault("health", _new_health())
            err_str = str(error) if error else ""
            if success:
                h["success"] += 1
                h["consecutive_fail"] = 0
            else:
                h["fail"] += 1
                if err_str.startswith(self._DECODE_ERROR_PREFIXES):
                    h["decode_fail"] = h.get("decode_fail", 0) + 1
                else:
                    h["consecutive_fail"] += 1
                if error:
                    h["last_error"] = err_str[:200]
            h["last_check"] = datetime.now(timezone.utc).isoformat()
            if first_frame_ms is not None:
                h["last_first_frame_ms"] = first_frame_ms
            total = h["success"] + h["fail"]
            h["score"] = (h["success"] / total) if total > 0 else None
            h["dead"] = h["consecutive_fail"] >= 3
            _decode_fail = h.get("decode_fail", 0)
            h["decode_unsupported"] = _decode_fail > 0 and _decode_fail >= h["consecutive_fail"]
            return dict(h)

    def get_health_summary(self):
        with self.lock:
            total = len(self.pool)
            dead = sum(1 for ch in self.pool if ch.get("health", {}).get("dead"))
            scored = [ch["health"]["score"] for ch in self.pool
                      if isinstance(ch.get("health", {}).get("score"), (int, float))]
            avg = (sum(scored) / len(scored)) if scored else None
            return {"total": total, "dead": dead, "avg_score": avg,
                    "scored": len(scored)}

    @staticmethod
    def _norm_url_key(u):
        if not u:
            return ""
        s = str(u).strip().lower()
        if "://" in s:
            s = s.split("://", 1)[1]
        for sep in ("#", "?"):
            if sep in s:
                s = s.split(sep, 1)[0]
        s = s.rstrip("/")
        if s.startswith("www."):
            s = s[4:]
        return s

    def _norm_name_key(self, n):
        if not n:
            return ""
        s = str(n)
        s = s.lower()
        for q in ("高清", "超清", "蓝光", "标清", "hd", "fhd", "uhd",
                  "4k", "720p", "1080p", "1080i", "sd", "vr"):
            s = s.replace(q, "")
        out = []
        for ch in s:
            if ch.isalnum() or ("一" <= ch <= "鿿") or ch in "-_":
                out.append(ch)
        return "".join(out)

    def _merge_by_key(self, key_fn):
        with self.lock:
            groups = {}
            order = []
            for ch in self.pool:
                key = key_fn(ch)
                if key == "":
                    gk = ("__uniq__", id(ch))
                    groups.setdefault(gk, []).append(ch)
                    order.append(gk)
                    continue
                gk = ("grp", key)
                if gk not in groups:
                    groups[gk] = []
                    order.append(gk)
                groups[gk].append(ch)
            new_pool = []
            merged_removed = 0
            for gk in order:
                members = groups[gk]
                if gk[0] == "__uniq__":
                    new_pool.extend(members)
                    continue
                new_pool.append(_strip_multi_fields(dict(members[0])))
                merged_removed += (len(members) - 1)
            self.pool = new_pool
            for idx, ch in enumerate(self.pool, 1):
                ch["id"] = idx
            self._store_rebuild()
            return merged_removed

    def ungroup_all(self):
        with self.lock:
            expanded = []
            split_count = 0
            for ch in self.pool:
                srcs = _normalize_sources(ch)
                from app.main import tag_db, fake_live_db
                is_multi = (ch.get("sources") and len(ch.get("sources")) > 1) or bool(ch.get("source_groups"))
                if not is_multi:
                    expanded.append(_strip_multi_fields(ch))
                    continue
                src_tags = ch.get("source_tags") or {}
                src_fl = ch.get("source_is_fake_live") or {}
                base_name = ch.get("name", "")
                base_group = ch.get("group", "")
                for i, u in enumerate(srcs):
                    row = dict(ch)
                    row["url"] = u
                    _strip_multi_fields(row)
                    row["name"] = base_name if len(srcs) == 1 else f"{base_name} #{i + 1}"
                    row["group"] = base_group
                    row["tag"] = (src_tags.get(u) or "").strip()
                    row["is_fake_live"] = bool(src_fl.get(u)) or bool(ch.get("is_fake_live"))
                    row.pop("ms", None)
                    row.pop("res", None)
                    row.pop("status", None)
                    if i == 0:
                        row["ms"] = ch.get("ms")
                        row["res"] = ch.get("res")
                        row["status"] = ch.get("status")
                    expanded.append(row)
                split_count += (len(srcs) - 1)
            self.pool = expanded
            for idx, ch in enumerate(self.pool, 1):
                ch["id"] = idx
            self._store_rebuild()
            return {"split": split_count, "total": len(self.pool)}

    def merge_duplicates(self, settings=None):
        removed_url = self._merge_by_key(lambda ch: self._norm_url_key(ch.get("url", "")))
        return {
            "removed": removed_url,
            "removed_by_url": removed_url,
            "remaining": len(self.pool),
        }

    def match_logos(self, logos_dir=None):
        if not logos_dir:
            from app.main import DATA_DIR
            logos_dir = os.path.join(DATA_DIR, "logos")
        if not os.path.isdir(logos_dir):
            return {"scanned": 0, "matched": 0, "logos_dir": logos_dir}
        exts = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")
        name_map = {}
        files = []
        for root, _dirs, fnames in os.walk(logos_dir):
            for fn in sorted(fnames):
                if fn.lower().endswith(exts):
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, logos_dir).replace("\\", "/")
                    files.append(rel)
                    base = os.path.splitext(fn)[0]
                    name_map.setdefault(self._norm_name_key(base), rel)
        matched = 0
        with self.lock:
            for ch in self.pool:
                key = self._norm_name_key(ch.get("name", ""))
                rel = name_map.get(key)
                if not rel and key:
                    for k, v in name_map.items():
                        if k and (key in k or k in key):
                            rel = v
                            break
                if rel:
                    ch["logo"] = "/logos/" + rel
                    matched += 1
        return {"scanned": len(files), "matched": matched, "logos_dir": logos_dir}

    _ONLINE_INDEX_FILE = "logos_online_index.json"
    _ONLINE_INDEX_TTL = 7 * 86400

    def _default_online_sources(self):
        return [
            {"id": "tb_zbds", "type": "pattern",
             "url": "https://tb.zbds.top/logo/{name}.png"},
            {"id": "wuji_tvlogo", "type": "pattern",
             "url": "https://www.xn--rgv465a.top/tvlogo/{name}.png"},
            {"id": "kodinerds", "type": "github",
             "repo": "jnk22/kodinerds-iptv", "branch": "master"},
            {"id": "tvufop", "type": "github",
             "repo": "daniloroxette/tvufop", "branch": "main"},
            {"id": "iseppro_img", "type": "github",
             "repo": "sumingyd/IPTV-Scanner-Editor-Pro", "branch": "main"},
            {"id": "songwh", "type": "github",
             "repo": "songwenhui239/Songwenhui239", "branch": "main"},
            {"id": "tvg", "type": "tvg"},
        ]

    def _load_github_index_cache(self):
        try:
            from app.main import DATA_DIR
            p = os.path.join(DATA_DIR, self._ONLINE_INDEX_FILE)
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_github_index_cache(self, cache):
        try:
            from app.main import DATA_DIR
            p = os.path.join(DATA_DIR, self._ONLINE_INDEX_FILE)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

    def _build_github_index(self, s, mirror):
        repo = s["repo"]
        branch = s["branch"]
        key = f"{repo}@{branch}"
        try:
            cache = self._load_github_index_cache()
            ent = cache.get(key)
            if ent and (time.time() - ent.get("ts", 0) < self._ONLINE_INDEX_TTL):
                return ent.get("index", {})
        except Exception:
            cache = {}
        index = {}
        try:
            import requests
            api = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
            r = requests.get(api, headers={"User-Agent": "Mozilla/5.0",
                                           "Accept": "application/vnd.github+json"}, timeout=25)
            if r.status_code != 200:
                return {}
            for item in r.json().get("tree", []):
                if item.get("type") != "blob":
                    continue
                p = item["path"]
                if not p.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")):
                    continue
                base = os.path.splitext(os.path.basename(p))[0]
                nk = self._norm_name_key(base)
                if not nk:
                    continue
                raw = f"https://raw.githubusercontent.com/{repo}/{branch}/{p}"
                raw = format_github_raw_url(raw, mirror)
                index.setdefault(nk, raw)
        except Exception:
            return {}
        try:
            cache[key] = {"ts": time.time(), "index": index}
            self._save_github_index_cache(cache)
        except Exception:
            pass
        return index

    @staticmethod
    def _sniff_ext(data):
        head = data[:16] if data else b""
        if head[:4] == b"\x89PNG":
            return "png"
        if head[:3] == b"\xff\xd8\xff":
            return "jpg"
        if head[:4] == b"GIF8":
            return "gif"
        if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        if head[:2] == b"BM":
            return "bmp"
        try:
            txt = data[:200].decode("utf-8", "replace").lstrip()
            low = txt[:60].lower()
            if low.startswith("<?xml") or low.startswith("<svg") or "svg" in low:
                return "svg"
        except Exception:
            pass
        return "png"

    @staticmethod
    def _fetch_logo_bytes(url, proxy, timeout):
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"} if proxy else {}
        cap = 2 * 1024 * 1024
        try:
            r = requests.get(url, headers=headers, proxies=proxies, timeout=timeout, stream=True)
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}"
            data = b""
            for chunk in r.iter_content(8192):
                if not chunk:
                    continue
                data += chunk
                if len(data) >= cap:
                    break
            if not data:
                return None, "空内容"
            head = data[:16]
            is_img = (
                head[:4] == b"\x89PNG" or head[:3] == b"\xff\xd8\xff"
                or head[:4] == b"GIF8"
                or (head[:4] == b"RIFF" and data[8:12] == b"WEBP")
                or head[:2] == b"BM"
                or data[:200].decode("utf-8", "replace").lstrip()[:4].lower() in ("<?xm", "<svg")
            )
            if not is_img:
                return None, "非图片"
            return data, None
        except Exception as e:
            return None, str(e)[:120]

    def _save_online_logo(self, source_id, nk, data, logos_dir):
        try:
            d = os.path.join(logos_dir, "_online")
            os.makedirs(d, exist_ok=True)
            ext = self._sniff_ext(data)
            fname = f"{source_id}__{nk}.{ext}"
            full = os.path.join(d, fname)
            with open(full, "wb") as f:
                f.write(data)
            return "_online/" + fname
        except Exception:
            return None

    def start_online_logos(self, settings, sources=None, only_missing=True, log=None, save_cache=None):
        srcs = sources or self._default_online_sources()
        task_id = "ol_" + uuid.uuid4().hex[:12]
        with self.lock:
            self._online_tasks[task_id] = {
                "total": 0, "done": 0, "found": 0, "downloaded": 0,
                "failed": 0, "running": True, "error": None, "done_flag": False,
            }
        t = threading.Thread(
            target=self._online_logo_worker,
            args=(task_id, srcs, only_missing, settings, log, save_cache),
            daemon=True,
        )
        t.start()
        return task_id

    def get_online_logos_status(self, task_id):
        with self.lock:
            st = self._online_tasks.get(task_id)
            return dict(st) if st else None

    def _online_logo_worker(self, task_id, sources, only_missing, settings, log, save_cache):
        status = self._online_tasks.get(task_id)
        if status is None:
            return
        try:
            from app.main import DATA_DIR
            mirror = (settings or {}).get("mirror", "不使用加速")
            proxy = (settings or {}).get("proxy", "")
            logos_dir = os.path.join(DATA_DIR, "logos")
            os.makedirs(logos_dir, exist_ok=True)

            github_index = {}
            for s in sources:
                if s.get("type") == "github":
                    idx = self._build_github_index(s, mirror)
                    if idx:
                        github_index[s["id"]] = idx

            with self.lock:
                all_channels = list(self.pool)
                candidates = [
                    ch for ch in all_channels
                    if not (only_missing and str(ch.get("logo", "")).startswith("/logos/"))
                ]
            status["total"] = len(all_channels)
            with self.lock:
                for ch in all_channels:
                    if only_missing and str(ch.get("logo", "")).startswith("/logos/"):
                        status["done"] += 1
                        status["found"] += 1

            def process(ch):
                name = ch.get("name", "")
                if not name:
                    return None
                nk = self._norm_name_key(name)
                if not nk:
                    return None
                for s in sources:
                    url = None
                    stype = s.get("type")
                    if stype == "pattern":
                        url = s["url"].format(name=urllib.parse.quote(name, safe=""))
                    elif stype == "github":
                        idx = github_index.get(s["id"])
                        if idx:
                            url = idx.get(nk)
                    elif stype == "tvg":
                        l = ch.get("logo", "")
                        if isinstance(l, str) and l.startswith("http"):
                            url = l
                    if not url:
                        continue
                    data, err = self._fetch_logo_bytes(url, proxy, 8)
                    if data:
                        rel = self._save_online_logo(s["id"], nk, data, logos_dir)
                        if rel:
                            return rel
                return None

            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
                futs = {ex.submit(process, ch): ch for ch in candidates}
                for fut in concurrent.futures.as_completed(futs):
                    rel = fut.result()
                    with self.lock:
                        ch = futs[fut]
                        if rel:
                            ch["logo"] = "/logos/" + rel
                            status["found"] += 1
                            status["downloaded"] += 1
                        else:
                            status["failed"] += 1
                        status["done"] += 1

            status["running"] = False
            status["done_flag"] = True
            if callable(save_cache):
                try:
                    save_cache(self, settings)
                except Exception:
                    pass
            if callable(log):
                try:
                    log(f"在线台标补全完成：新增下载 {status['downloaded']} 个，"
                        f"已匹配(含原有) {status['found']}，未找到 {status['failed']}")
                except Exception:
                    pass
        except Exception as e:
            status["error"] = str(e)[:300]
            status["running"] = False
            status["done_flag"] = True
            if callable(log):
                try:
                    log(f"在线台标补全异常: {e}")
                except Exception:
                    pass
