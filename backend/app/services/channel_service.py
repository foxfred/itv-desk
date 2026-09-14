"""频道管理服务 - 封装频道池操作（内存为实时源，SQLite 为并行镜像）"""
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
    """新频道的健康度初始结构。"""
    return {
        "success": 0,
        "fail": 0,
        "consecutive_fail": 0,
        "decode_fail": 0,    # 源可达但解码/转码失败的次数（H.265 等浏览器不支持的格式）
        "last_check": None,
        "last_error": "",
        "last_first_frame_ms": None,
        "score": None,      # 0..1，None=样本不足未知
        "dead": False,      # 连续失败 >=3 判定为死源（解码失败不计入）
        "decode_unsupported": False,  # 源可达但本机解码器不支持（H.265 等）
    }


def _normalize_sources(ch):
    """从频道数据归一化出「多源 URL 列表」（每频道多源故障转移用）。
    单源频道退化为 [url]；保证去重、非空、保留顺序。"""
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
    """清除频道上的聚合源残留字段（一源一行后这些字段不应再存在）。"""
    for f in _MULTI_FIELDS:
        ch.pop(f, None)
    return ch


def _expand_multi(items):
    """把可能带多源的频道条目展平成「一源一行」的单源条目。

    聚合源功能已彻底移除（聚合后各源无法单独检查/清除，不适合本软件）。
    此处对旧缓存/旧导出做兜底展平，保证进入频道池的每条记录只有一个 url。
    多源时名称加 #序号 便于区分，并把原先按源记录的 tag / fake-live 落到对应行。
    返回新的列表，不修改入参。
    """
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


# ==================== 清晰度折算（供健康报告等统计使用） ====================
# 实测数据形态（586 条缓存统计）：
#   res      : '-' | '1080P' | '720P' | '3840' | '1920' | '1280' | '854' | '640' | '768x576'
#   quality  : '-' | '高清' | '标清' | '低清' | '流畅' | '2160' | '1080' | '720' | '480' | '360'
#   ms       : 字符串（'3251' / '110' / '-'）
# 关键差异：res 里的裸数字是**宽度**（1280/1920），quality 里的裸数字是**高度**（720/1080）。
# 两者都按 16:9 折算成高度后再比档位，避免"1280 被当成 1080P"这类误判。
_TEXT_RANK = {
    "8k": 8, "4320p": 8, "4k": 7, "2160p": 7, "uhd": 7, "超清": 7, "蓝光": 6,
    "2k": 6, "1440p": 6, "1080p": 5, "1080i": 5, "fhd": 5, "高清": 5, "全高清": 5,
    "720p": 3, "hd": 3, "标清": 2, "576p": 2, "480p": 1, "360p": 0, "低清": 0, "流畅": 0,
}


def _rank_of(height):
    """画面高度 → 清晰度档位（0..7，未知 None → -1）

    注意 0 是合法档位（360P），不能用 `if not height` 判定未知。
    """
    if height is None:
        return -1
    for bound, rank in ((2160, 7), (1440, 6), (1080, 5), (720, 3), (576, 2), (480, 1), (360, 0)):
        if height >= bound:
            return rank
    return 0


def _num_rank(s, is_quality):
    """含数字的字段 → 档位"""
    if "x" in s:
        # 宽x高（'768x576'）：取后一个数字当高度，别把 768 当高度
        m2 = re.search(r"x\s*(\d{3,5})", s)
        if m2:
            return _rank_of(int(m2.group(1)))
    m = re.search(r"(\d{3,5})", s)
    if not m:
        return -1
    n = int(m.group(1))
    if re.search(r"[pi]$", s) or is_quality:
        return _rank_of(n)      # 带 p/i 后缀的是高度；quality 的裸数字也是高度
    return _rank_of(int(n * 9 / 16))  # res 的裸数字是宽度 → 按 16:9 折成高度


def _cue_rank(x, is_quality=False):
    """把 res / quality 字段折算成清晰度档位（越大越清晰，未知 -1）

    返回值是**档位**不是高度，可直接比较：
      res '1920' → 5（宽 1920 折算 1080）；res '1280' → 3（折算 720）
      quality '720' → 3；quality '高清' → 5；'-' → -1
    """
    if x is None:
        return -1
    s = str(x).strip().lower()
    if s in ("", "-", "none", "null", "unknown"):
        return -1
    if s in _TEXT_RANK:
        return _TEXT_RANK[s]    # 文本标签直接就是档位
    return _num_rank(s, is_quality)


def _ms_num(v):
    """延迟字段折算成数字（'3251' → 3251.0）；取不到或非正数返回 None"""
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


class ChannelService:
    """线程安全的频道池管理器。

    - pool：内存列表，作为实时数据源，所有既有读写逻辑保持不变；
    - store：SQLite 镜像（channels.db），提供分页/检索/持久化；
    - 所有 store 写操作均被 try/except 包裹，SQLite 异常绝不穿透主流程。
    """

    def __init__(self):
        self.pool = []
        self.lock = threading.RLock()
        self.clean_dup_counter = 0
        self.store = ChannelStore()
        self._online_tasks = {}  # task_id -> 进度状态(dict)

    # -------------------- 存储镜像同步（全部防御性） --------------------
    def _store_rebuild(self):
        """用当前内存池整体重建 SQLite 镜像（顺序与 pool 一致）"""
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
        """添加频道列表，返回 (added, dup)。

        origin：来源标记，用于来源追溯。取值 scrape / subscription / manual。
        调用方可显式传入；否则沿用频道自身携带的 origin，都没有则记为 manual。
        """
        # 读取分组配置（导入时按统一算法自动重分组）
        _settings = Config.load_settings()
        auto_group = _settings.get("auto_group", True)
        foreign_name = _settings.get("foreign_group_name", "外国频道")
        custom_rules = _settings.get("custom_group_rules", []) or []
        with self.lock:
            existing = {normalize_url(ch["url"]) for ch in self.pool}
            added = 0
            dup = 0
            # 一源一行：旧数据/旧导出若带多源，先展平成单源条目再入库
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
                # 导入时按持久化 tag_db/fake_live_db 还原该行的标记
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
                    "url_note": ch.get("url_note", ""),   # 1.5: $ 后标签（如「组播超高清-50fps」），透传展示
                    "health": _new_health()
                })
                added += 1
            for idx, ch in enumerate(self.pool, 1):
                ch["id"] = idx
            self.clean_dup_counter = dup
            # 增量同步 SQLite：已有行 order_idx 后移 added，新行占据 0..added-1
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
        """对整个频道池按统一算法重新分组（手动「重新分组」动作，解决历史混乱）。

        忽略 auto_group 开关——这是用户主动触发，必然按算法重分。
        返回 (changed, total)。
        """
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
                    # 一源一行：丢弃任何多源字段，避免旧前端把聚合结构写回
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
        """统计仍为「未检查」的频道数（支撑断点续检 UI）"""
        with self.lock:
            return sum(1 for ch in self.pool if ch.get("status", "未检查") == "未检查")

    def get_unchecked(self):
        """返回仍为「未检查」的频道列表（断点续检时跳过已检测项）"""
        with self.lock:
            return [ch for ch in self.pool if ch.get("status", "未检查") == "未检查"]

    # -------------------- 分页 / 检索（SQLite 优先，回退内存） --------------------
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
        """分组树数据：各分组频道数（SQLite 优先，回退内存统计）"""
        try:
            return self.store.group_counts()
        except Exception:
            from collections import Counter
            with self.lock:
                c = Counter((ch.get("group", "") or "未分组") for ch in self.pool)
            return [{"group": g, "count": n} for g, n in c.most_common()]

    # -------------------- 播放健康度评分 --------------------
    # 解码/转码类错误前缀：源可达但本机浏览器/转码器无法解码（H.265 等）
    # 这类失败不计入 consecutive_fail（源没死，是格式不支持）
    _DECODE_ERROR_PREFIXES = ("h264-proxy:", "probe-hls:")

    def update_health(self, channel_id=None, url=None, success=True,
                      error=None, first_frame_ms=None):
        """回写一次播放/检测结果，更新健康度。

        - channel_id / url 二选一定位频道（检测用 id，播放上报用 url）；
        - 维护 success/fail/consecutive_fail/decode_fail，推导 score（成功率）与 dead 标记；
        - **关键区分**：error 以 h264-proxy:/probe-hls: 开头 → 源可达但解码失败，
          计入 decode_fail 但不计入 consecutive_fail，避免 H.265 等被误判死源；
        - 其余失败 → 正常计入 consecutive_fail，3 次连续失败判死源；
        - health 随频道缓存（channels_cache.json 序列化整池）持久化，无需 SQLite 列。
        返回更新后的 health 字典；未命中返回 None。
        """
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
                # 区分：解码/转码失败 vs 源真的不可达
                if err_str.startswith(self._DECODE_ERROR_PREFIXES):
                    h["decode_fail"] = h.get("decode_fail", 0) + 1
                    # 解码失败不计入 consecutive_fail（源没死）
                else:
                    h["consecutive_fail"] += 1
                if error:
                    h["last_error"] = err_str[:200]
            h["last_check"] = datetime.now(timezone.utc).isoformat()
            if first_frame_ms is not None:
                h["last_first_frame_ms"] = first_frame_ms
            total = h["success"] + h["fail"]
            h["score"] = (h["success"] / total) if total > 0 else None
            # 死源 = 连续失败 >= 3（纯粹的网络/可达性失败）
            h["dead"] = h["consecutive_fail"] >= 3
            # 解码不支持 = 源可达但本机解码/转码失败次数超过连续失败次数
            # 兼容旧缓存：老版本 health 字典没有 decode_fail 字段
            _decode_fail = h.get("decode_fail", 0)
            h["decode_unsupported"] = _decode_fail > 0 and _decode_fail >= h["consecutive_fail"]
            return dict(h)

    def get_health_summary(self):
        """健康度汇总：总数 / 死源数 / 平均可看性评分。"""
        with self.lock:
            total = len(self.pool)
            dead = sum(1 for ch in self.pool if ch.get("health", {}).get("dead"))
            scored = [ch["health"]["score"] for ch in self.pool
                      if isinstance(ch.get("health", {}).get("score"), (int, float))]
            avg = (sum(scored) / len(scored)) if scored else None
            return {"total": total, "dead": dead, "avg_score": avg,
                    "scored": len(scored)}

    # -------------------- #56 智能去重合并 --------------------
    @staticmethod
    def _norm_url_key(u):
        """归一化 URL 用于去重：去协议/认证/查询/片段/末尾斜杠/www. 前缀。"""
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
        """归一化名称（频道名 / 台标文件名）：去画质后缀 + 仅保留字母数字与中文。

        别名归一**只用于 EPG 匹配**（只读、无副作用，见 epg_service._normalize_name），
        这里的名称归一不带别名，避免误判把频道真的删掉。
        """
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
        """按 key 函数分组去重：同组（key 相同）仅保留第一个，删除其余重复项。

        只做「去重」，不再把同组频道合并为多源聚合频道——聚合源会使各源无法
        单独检查/清除，不适合本软件。同时清理历史聚合残留字段。
        返回删除的数量。
        """
        with self.lock:
            groups = {}
            order = []
            for ch in self.pool:
                key = key_fn(ch)
                if key == "":
                    # 无 key（如缺 URL）各自独立
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
                # 去重：同 key 只留第一条（不做多源聚合）
                new_pool.append(_strip_multi_fields(dict(members[0])))
                merged_removed += (len(members) - 1)
            self.pool = new_pool
            for idx, ch in enumerate(self.pool, 1):
                ch["id"] = idx
            self._store_rebuild()
            return merged_removed

    def ungroup_all(self):
        """拆解所有聚合源：把多源/分组的聚合频道还原为每个源一个独立单源频道。

        用户反馈聚合源里各源无法单独检查/清除离线，不适合本软件。
        本方法把每个聚合频道按 sources（URL 列表）展开为多个单源频道，
        清理 sources/source_groups/source_tags/source_health 等聚数字段，
        并把每个源的 tag / fake-live 落到对应展开频道上。
        返回拆解出的频道数量（多出的行数）。
        """
        with self.lock:
            expanded = []
            split_count = 0
            for ch in self.pool:
                srcs = _normalize_sources(ch)
                from app.main import tag_db, fake_live_db
                is_multi = (ch.get("sources") and len(ch.get("sources")) > 1) or bool(ch.get("source_groups"))
                if not is_multi:
                    # 单源：仅清理可能的聚合残留字段
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
                    # 多个源时给名称加序号，便于区分；单源沿用原名
                    row["name"] = base_name if len(srcs) == 1 else f"{base_name} #{i + 1}"
                    row["group"] = base_group
                    row["tag"] = (src_tags.get(u) or "").strip()
                    row["is_fake_live"] = bool(src_fl.get(u)) or bool(ch.get("is_fake_live"))
                    # 主 url 的行保留该源自己的健康/延迟；其余源无独立检测则归零重置
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
        """去重：按 URL 归一归并重复源。返回统计。

        一源一行后**不再按频道名合并**——同名不同源的频道是正常形态（正是"一源
        一行"要保留的多行），按名合并会把其他可用源误删。
        """
        removed_url = self._merge_by_key(lambda ch: self._norm_url_key(ch.get("url", "")))
        return {
            "removed": removed_url,
            "removed_by_url": removed_url,
            "remaining": len(self.pool),
        }

    # -------------------- #57 Logo 自动匹配 --------------------
    def match_logos(self, logos_dir=None):
        """递归扫描 logos 目录树，按频道名（归一化）匹配 logo 图片，写入 ch['logo']=/logos/<相对路径>。
        支持任意层级：顶层文件（logos/湖南卫视.png）与子目录（logos/CCTV/CCTV1.png、
        logos/卫视/湖南卫视.png）均可被扫到并匹配。"""
        if not logos_dir:
            from app.main import DATA_DIR
            logos_dir = os.path.join(DATA_DIR, "logos")
        if not os.path.isdir(logos_dir):
            return {"scanned": 0, "matched": 0, "logos_dir": logos_dir}
        exts = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")
        name_map = {}  # 归一化key -> 相对 logos_dir 的路径(含子目录, 正斜杠)
        files = []
        for root, _dirs, fnames in os.walk(logos_dir):
            for fn in sorted(fnames):
                if fn.lower().endswith(exts):
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, logos_dir).replace("\\", "/")
                    files.append(rel)
                    base = os.path.splitext(fn)[0]
                    # 同名文件只保留第一个命中的（顶层优先于子目录，因 os.walk 先访问顶层）
                    name_map.setdefault(self._norm_name_key(base), rel)
        matched = 0
        with self.lock:
            for ch in self.pool:
                key = self._norm_name_key(ch.get("name", ""))
                rel = name_map.get(key)
                if not rel and key:
                    # 模糊兜底：文件名与频道名互相包含（去画质后）
                    for k, v in name_map.items():
                        if k and (key in k or k in key):
                            rel = v
                            break
                if rel:
                    ch["logo"] = "/logos/" + rel
                    matched += 1
        return {"scanned": len(files), "matched": matched, "logos_dir": logos_dir}

    # -------------------- #58 在线台标自动补全（联网下载） --------------------
    _ONLINE_INDEX_FILE = "logos_online_index.json"
    _ONLINE_INDEX_TTL = 7 * 86400  # GitHub 树索引缓存 7 天

    def _default_online_sources(self):
        """默认接入的全部在线台标源（最全面）。
        - pattern：URL 模板含 {name}（按频道名 URL 编码后填入），中文台标站；
        - github：GitHub 仓库树索引（kodinerds/tvufop 等大型共享台标库），raw 走 mirror 加速；
        - tvg：复用频道自带 tvg-logo 远程地址（下载到本地）。"""
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

    # ---- GitHub 树索引缓存（避免每次重新拉取，且离线可复用） ----
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
        """拉取 GitHub 仓库文件树，建立 归一化文件名 -> raw URL 索引；带 7 天缓存。失败返回空 dict。"""
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
                index.setdefault(nk, raw)  # 同名保留首个命中
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
        """下载 URL 内容并校验为图片，返回 (bytes, err)。"""
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
        """保存下载的台标到 logos/_online/，返回相对 logos_dir 的路径（正斜杠），失败返回 None。"""
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
        """启动在线台标补全后台任务，返回 task_id。"""
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

            # 预拉取 GitHub 树索引（联网一次，缓存复用）
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
            # 已匹配本地台标的频道直接计入 done/found（不重复下载）
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
