"""乱码修补服务 - 修复UTF-8/Latin-1乱码并提取频道"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from app.utils.network import http_probe_channel, download_url, format_github_raw_url
from app.utils.m3u_parser import extract_channels, export_playlist, Parser
from app.utils.helpers import find_logo


# 乱码特征字符：UTF-8多字节序列被Latin-1误解码后的典型字符
# \u00c0-\u00ff 是Latin-1高位区域，UTF-8多字节首字节都在此范围
_GARBLED_CHARS = re.compile(r'[\u00c0-\u00ff]')

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
_URL_RE = re.compile(r'(?:https?|rtmp|rtsp|udp|mms)://[^\s,\u4e00-\u9fff]+')

# 母链扩展名：会进一步递归抓取
_PARENT_EXTS = {".M3U", ".M3U8", ".TXT", ".HTML", ".HTM"}
# 直接播放扩展名：视为频道
_CHANNEL_EXTS = {".TS", ".MP4", ".FLV", ".MKV", ".AVI", ".MOV", ".WMV"}


def _classify_url(url):
    """判断 URL 是母链（需递归抓取）还是频道链接（可直接播放）。"""
    if not url:
        return "channel"
    u = url.upper().split("?")[0].split("#")[0]
    # GitHub blob / raw 页面视为母链（会转 raw）
    if "GITHUB.COM" in url.upper() and "/BLOB/" in url.upper():
        return "parent"
    if "RAW.GITHUBUSERCONTENT.COM" in url.upper():
        # raw 内容可能是 m3u/txt 母链，也可能是 m3u8 频道；按扩展名再分
        ext = os.path.splitext(u)[1]
        if ext in _PARENT_EXTS:
            return "parent"
        return "channel"
    ext = os.path.splitext(u)[1]
    if ext in _PARENT_EXTS:
        # .m3u8 比较特殊：可能是 HLS 索引（频道），也可能是母链
        # 启发：若 URL 含 playlist / index / live 等字样，倾向频道；否则母链
        if ext == ".M3U8":
            if any(k in u for k in ["/LIVE/", "PLAYLIST", "INDEX", "/STREAM/"]):
                return "channel"
            return "parent"
        return "parent"
    if ext in _CHANNEL_EXTS:
        return "channel"
    # 无扩展名：无法直接判断，倾向于频道（直播源常无扩展名）
    return "channel"


def _count_cjk(text):
    return len(_CJK_RE.findall(text))


def _looks_garbled(text):
    """检测文本是否包含UTF-8被误解码为Latin-1的乱码"""
    if not text:
        return False
    cjk = _count_cjk(text)
    # 如果已有足够中文，不是乱码
    if cjk > len(text) * 0.05:
        return False
    # 检测Latin-1高位字符（UTF-8多字节序列被误解码的典型特征）
    return bool(_GARBLED_CHARS.search(text))


def fix_garbled_utf8(text):
    """修复UTF-8字节被误解码为Latin-1/CP1252的乱码"""
    if not text or not _looks_garbled(text):
        return text

    best = text
    best_cjk = _count_cjk(text)

    # 增强：中文编码优先修复。本工具面向中文 IPTV 源，乱码最常见来自
    # GBK/GB18030（简体）或 Big5（繁体）被误当 Latin-1/UTF-8 解码。
    # 策略：先把 Latin-1 误码还原成原始字节，依次尝试：
    #   1) 显式中文编码（gb18030 / big5）——对中文误码最稳，按 CJK 计数取最优；
    #   2) charset-normalizer 兜底其它编码（utf-8 等）；
    #   3) 经典 latin-1/cp1252 → utf-8 回退（见下方 encodings 循环）。
    # 说明：GBK 与 CP932/CP949 在高位字节区重叠，单纯按 CJK 计数可能并列，
    # 但正确的中文编码通常产出最多连贯中文，故「取 CJK 最多者」在实践中可靠。
    try:
        raw = text.encode('latin-1')
        for enc in ('gb18030', 'big5'):
            try:
                candidate = raw.decode(enc)
            except Exception:
                continue
            cjk = _count_cjk(candidate)
            if cjk > best_cjk:
                best = candidate
                best_cjk = cjk
        from charset_normalizer import from_bytes
        for guess in from_bytes(raw):
            candidate = str(guess)
            cjk = _count_cjk(candidate)
            if cjk > best_cjk:
                best = candidate
                best_cjk = cjk
    except Exception:
        pass

    encodings = ['latin-1', 'cp1252', 'iso-8859-1', 'iso-8859-15']

    for enc in encodings:
        # 先尝试严格解码
        try:
            fixed = text.encode(enc).decode('utf-8')
            fixed_cjk = _count_cjk(fixed)
            if fixed_cjk > best_cjk:
                best = fixed
                best_cjk = fixed_cjk
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            # 严格解码失败，尝试忽略无效字节的部分解码
            try:
                fixed = text.encode(enc).decode('utf-8', errors='ignore')
                fixed_cjk = _count_cjk(fixed)
                if fixed_cjk > best_cjk:
                    best = fixed
                    best_cjk = fixed_cjk
            except (UnicodeEncodeError, LookupError):
                continue

    # 如果整体修复无效，尝试逐行修复
    if best_cjk == _count_cjk(text) and '\n' in text:
        lines = text.split('\n')
        fixed_lines = []
        changed = False
        for line in lines:
            if _looks_garbled(line):
                line_best = line
                line_best_cjk = _count_cjk(line)
                for enc in encodings:
                    try:
                        fixed_line = line.encode(enc).decode('utf-8')
                        if _count_cjk(fixed_line) > line_best_cjk:
                            line_best = fixed_line
                            line_best_cjk = _count_cjk(fixed_line)
                    except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
                        try:
                            fixed_line = line.encode(enc).decode('utf-8', errors='ignore')
                            if _count_cjk(fixed_line) > line_best_cjk:
                                line_best = fixed_line
                                line_best_cjk = _count_cjk(fixed_line)
                        except (UnicodeEncodeError, LookupError):
                            continue
                if line_best_cjk > _count_cjk(line):
                    fixed_lines.append(line_best)
                    changed = True
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        if changed:
            best = '\n'.join(fixed_lines)

    return best


def clean_channel_name(name):
    """清理频道名称：移除方括号/圆括号标签、特殊字符、emoji，保留标准名称"""
    if not name:
        return "未知频道"

    name = name.replace('`', '').strip()
    # 移除方括号标签 [...]
    name = re.sub(r'\s*\[[^\]]*\]\s*', ' ', name).strip()
    # 移除圆括号标签 (...)
    name = re.sub(r'\s*\([^)]*\)\s*', ' ', name).strip()
    # 移除全角括号标签（...）
    name = re.sub(r'\s*\uff08[^\uff09]*\uff09\s*', ' ', name).strip()
    # 移除特殊字符：™ ® © 及其UTF-8乱码形式
    name = re.sub(r'[\u2122\u00ae\u00a9\u00e2\u0084\u00a2\u00c2\u00ae\u00c2\u00a9]', '', name)
    # 移除emoji（含emoji变体选择符）
    name = re.sub(r'[\U0001F300-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]', '', name)
    name = re.sub(r'[\u2600-\u27BF\uFE00-\uFEFF\u2700-\u27BF]', '', name)
    # 移除多余空白
    name = re.sub(r'\s+', ' ', name).strip()

    if not name or len(name) < 2:
        return "未知频道"

    return name


def infer_name_from_url(url):
    """从URL路径中推断频道名（当名称乱码时的兜底策略）"""
    if not url:
        return None
    try:
        p = urlparse(url)
        base = os.path.basename(p.path)
        if base:
            name = os.path.splitext(base)[0]
            # CCTV格式标准化：cctv1 → CCTV-1
            name = re.sub(r'(?i)cctv\s*[-]?(\d+)', r'CCTV-\1', name)
            name = re.sub(r'[._-]', ' ', name).strip()
            if len(name) >= 2:
                return name
    except Exception:
        pass
    return None


# 状态关键词
_STATUS_TAGS = {"在线可用", "在线稳定", "可用直播源", "可播放", "在线", "可用", "有效", "正常",
                "失效离线", "离线异常", "不可用", "失效", "离线", "无效", "异常", "错误"}

# 分辨率关键词
_RES_TAGS = {"高清1080P", "超清4K", "蓝光", "标清", "高清", "超清", "2K", "4K", "8K",
             "HD", "FHD", "UHD", "1080P", "720P", "480P", "2160P", "1440P"}

# 编码/协议标签（无对应列，直接移除）
_CODEC_TAGS = {"H.264", "H.265", "H264", "H265", "AVC", "HEVC", "MPEG", "MPEG2",
               "MPEG4", "AV1", "VP9", "FLV", "RTMP", "RTSP", "HLS", "M3U8"}

# 可转移到标记列的标签
_TAG_TAGS = {"稳定", "稳定源", "直播源", "CDN", "AWS", "直连", "中转", "代理",
             "IPv4", "IPv6", "官方", "第三方", "优选", "备用"}

# ---- 可配置规则（默认沿用上方硬编码，运行期可从设置覆盖，实现"规则可配置"）----
_DEFAULT_RULES = {
    "status": set(_STATUS_TAGS),
    "res": set(_RES_TAGS),
    "tag": set(_TAG_TAGS),
}
_RULES = {k: set(v) for k, v in _DEFAULT_RULES.items()}


def _refresh_rules():
    """从设置中读取用户自定义标签词表（若存在则覆盖默认），实现分组/标签词典可配置。

    设置项：repair_status_tags / repair_res_tags / repair_tag_tags
    （接受列表，或以英文逗号分隔的字符串）。
    """
    try:
        from app.config import Config
        for key in ("status", "res", "tag"):
            val = Config.get_setting(f"repair_{key}_tags")
            if not val:
                continue
            if isinstance(val, (list, tuple, set)):
                items = [str(s).strip() for s in val if str(s).strip()]
            else:
                items = [s.strip() for s in str(val).split(",") if s.strip()]
            if items:
                _RULES[key] = set(items)
    except Exception:
        pass


def extract_tags_from_name(name):
    """
    从频道名称中提取方括号标签，返回 (clean_name, metadata)。
    metadata 包含: status, res, tag, stack
    """
    if not name:
        return "未知频道", {}

    # 提取所有 [...] 标签
    brackets = re.findall(r'\[([^\]]*)\]', name)
    # 移除所有 [...] 标签得到干净名称
    clean = re.sub(r'\s*\[[^\]]*\]\s*', ' ', name).strip()
    clean = re.sub(r'\s+', ' ', clean)

    metadata = {"status": "", "res": "", "tag": "", "stack": ""}
    tags_found = []

    for tag in brackets:
        tag_stripped = tag.strip()
        # 状态判断
        if tag_stripped in _RULES["status"]:
            if "在线" in tag_stripped or "可用" in tag_stripped or "有效" in tag_stripped or "正常" in tag_stripped or "可播放" in tag_stripped:
                metadata["status"] = "在线"
            elif "失效" in tag_stripped or "离线" in tag_stripped or "不可用" in tag_stripped or "无效" in tag_stripped or "异常" in tag_stripped or "错误" in tag_stripped:
                metadata["status"] = "离线"
            continue

        # 分辨率判断
        if tag_stripped in _RULES["res"]:
            metadata["res"] = tag_stripped
            continue

        # 编码/协议（无对应列，丢弃）
        if tag_stripped in _CODEC_TAGS:
            continue

        # 网络栈
        if tag_stripped in ("IPv4", "IPv6"):
            metadata["stack"] = tag_stripped
            continue

        # 可转移到标记列
        if tag_stripped in _RULES["tag"]:
            tags_found.append(tag_stripped)
            continue

        # 未识别的标签，尝试智能分类
        tag_lower = tag_stripped.lower()
        if any(k in tag_lower for k in ("在线", "可用", "有效", "正常", "可播放", "online", "ok")):
            metadata["status"] = "在线"
        elif any(k in tag_lower for k in ("失效", "离线", "不可用", "无效", "异常", "错误", "offline", "down")):
            metadata["status"] = "离线"
        elif re.search(r'\d+x\d+|\d+[pPkK]|高清|超清|蓝光|标清|HD|FHD|UHD', tag_stripped):
            metadata["res"] = tag_stripped
        elif any(k in tag_lower for k in ("h.264", "h264", "h.265", "h265", "avc", "hevc", "mpeg", "rtmp", "hls")):
            continue  # 编码标签丢弃
        elif tag_stripped in ("IPv4", "IPv6"):
            metadata["stack"] = tag_stripped
        elif _looks_garbled(tag_stripped):
            # 乱码标签，跳过不处理
            continue
        else:
            tags_found.append(tag_stripped)

    if tags_found:
        metadata["tag"] = ",".join(tags_found)

    if not clean or len(clean) < 2:
        clean = "未知频道"

    return clean, metadata


def clean_url(url):
    """清理URL：移除反引号、首尾空白"""
    if not url:
        return url
    url = url.strip()
    url = url.strip('`')
    url = url.replace('`', '')
    return url.strip()


def determine_group(name, url, existing_group=""):
    """
    根据频道名和URL综合判断分组。
    优先使用M3U中已有的分组，否则使用程序分组策略。
    """
    if existing_group and existing_group != "自动分组":
        return existing_group

    name_upper = str(name).upper()
    url_upper = str(url).upper() if url else ""

    # 1. URL关键词判断（优先级最高，URL中的信息更可靠）
    if re.search(r'(?i)/cctv[-\s]*5|/cctv5', url_upper):
        return "体育竞技"
    if re.search(r'(?i)/cctv[-\s]*6|/cctv6', url_upper):
        return "影院剧场"
    if re.search(r'(?i)/cctv[-\s]*(\d+)', url_upper):
        return "央视频道"

    # 2. 频道名关键词判断
    # 港澳台
    if any(k in name_upper for k in ["HK", "TW", "MO", "香港", "台湾", "澳门", "翡翠", "明珠",
                                       "凤凰", "TVB", "中天", "纬来", "东森", "年代", "三立",
                                       "华视", "民视", "台视", "公视", "中视", "无线", "美亚", "莲花", "澳视"]):
        return "港澳台"

    # 央视
    if "CCTV" in name_upper:
        return "央视频道"

    # 卫视
    if "卫视" in name_upper:
        return "地方卫视"

    # 影院剧场
    if any(k in name_upper for k in ["电影", "影院", "剧场", "HBO", "影视", "经典影院",
                                       "CHC", "电影台", "动作", "影迷", "STAR"]):
        return "影院剧场"

    # 体育竞技
    if any(k in name_upper for k in ["体育", "足球", "五星", "NBA", "赛事", "劲爆",
                                       "高尔夫", "羽毛球", "台球", "五星体育"]):
        return "体育竞技"

    # 少儿动漫
    if any(k in name_upper for k in ["少儿", "卡通", "动漫", "儿童", "娃娃", "金鹰卡通",
                                       "哈哈炫动", "卡酷"]):
        return "少儿动漫"

    # 轮播专区
    if any(k in name_upper for k in ["NEWTV", "iHOT", "SITV", "轮播", "百视通", "咪咕", "欢腾", "求索"]):
        return "轮播专区"

    # 省市地方
    if any(k in name_upper for k in ["北京", "上海", "广东", "江苏", "浙江", "湖南", "四川",
                                       "湖北", "山东", "河南", "河北", "福建", "安徽", "辽宁",
                                       "陕西", "重庆", "天津", "深圳", "地方", "新闻综合", "都市", "生活", "公共"]):
        return "省市地方"

    # 3. URL域名关键词兜底
    if any(k in url_upper for k in ["CCTV", "CNTV"]):
        return "央视频道"
    if any(k in url_upper for k in ["SPORT", "NBA", "FOOTBALL", "足球", "体育"]):
        return "体育竞技"
    if any(k in url_upper for k in ["MOVIE", "FILM", "电影"]):
        return "影院剧场"

    return "杂项频道"


def parse_raw_text(raw_text, current_group=""):
    """
    从原始文本中提取频道名称和URL。
    支持：
      - M3U #EXTINF 格式
      - 中文 TXT #genre# 分组头 + 名称,URL$备注
      - 论坛箭头格式 name → url
      - 逗号分隔 name,url
      - 名称 + URL 分行
    返回频道字典列表，current_group 用于继承 #genre# 分组。
    """
    channels = []
    lines = raw_text.split('\n')
    i = 0
    group = current_group

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # #genre# 分组头
        genre_match = re.match(r'^#genre#\s*[:\-]?\s*(.+)$', line, re.IGNORECASE)
        if genre_match:
            group = genre_match.group(1).strip()
            i += 1
            continue

        # M3U #EXTINF 格式
        if line.startswith('#EXTINF:'):
            gm = re.search(r'group-title="([^"]+)"', line)
            if gm:
                group = gm.group(1).strip()
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            logo = logo_match.group(1) if logo_match else ''
            name = ''
            if ',' in line:
                name = line.split(',', 1)[-1].strip()
            if i + 1 < len(lines):
                url = clean_url(lines[i + 1].strip())
                if url and re.match(r'(?:https?|rtmp|rtsp|udp|mms)://', url):
                    channels.append(_make_channel(name, url, group, logo, line))
                    i += 2
                    continue
            i += 1
            continue

        if line.startswith('#EXTM3U'):
            i += 1
            continue

        # 论坛箭头格式：名称 → URL（可能含 $备注）
        arrow_match = re.match(r'^(.+?)\s*[→\->]\s*((?:https?|rtmp|rtsp|udp|mms)://\S+)$', line)
        if arrow_match:
            name = arrow_match.group(1).strip()
            url_part = arrow_match.group(2).strip()
            url, note = _split_url_note(url_part)
            channels.append(_make_channel(name, url, group, '', None, note))
            i += 1
            continue

        # 逗号分隔格式：名称,URL（可能含 $备注）
        if ',' in line:
            url_match = re.search(r'(?:https?|rtmp|rtsp|udp|mms)://[^\s,\u4e00-\u9fff]+', line)
            if url_match:
                url_start = url_match.start()
                name = line[:url_start].rstrip(',` \t')
                url_part = clean_url(line[url_start:])
                url_part = re.sub(r'[,`\s]+$', '', url_part)
                url, note = _split_url_note(url_part)
                if url and re.match(r'(?:https?|rtmp|rtsp|udp|mms)://', url):
                    channels.append(_make_channel(name, url, group, '', None, note))
                    i += 1
                    continue

        # 纯URL行（上一行可能是名称）
        if re.match(r'(?:https?|rtmp|rtsp|udp|mms)://', line):
            url, note = _split_url_note(clean_url(line))
            name = '未知频道'
            if i > 0:
                prev = lines[i - 1].strip()
                if prev and not prev.startswith('#') and not re.match(r'(?:https?|rtmp|rtsp|udp|mms)://', prev):
                    name = prev.strip().replace('`', '').strip()
            if name == '未知频道':
                inferred = infer_name_from_url(url)
                name = inferred or '未知频道'
            channels.append(_make_channel(name, url, group, '', None, note))
            i += 1
            continue

        i += 1

    return channels


def _split_url_note(url_part):
    """分离 URL 与 $备注"""
    if '$' in url_part:
        u, note = url_part.split('$', 1)
        return u.strip(), note.strip()
    return url_part.strip(), ""


def _make_channel(name, url, group, logo, raw_extinf=None, note=""):
    """构造统一频道字典"""
    clean_name = name.strip().replace('`', '').strip() if name else '未知频道'
    if not clean_name or len(clean_name) < 1:
        clean_name = '未知频道'
    return {
        'name': clean_name,
        'url': url,
        'group': group or '',
        'logo': clean_url(logo) if logo else '',
        'url_note': note,
        'raw_extinf': raw_extinf or f'#EXTINF:-1 group-title="{group or "自动分组"}",{clean_name}',
        'raw_url': url
    }


def _load_group_overrides():
    """加载按 URL 精确覆盖分组的规则表（轻量，settings.group_override_by_url）。
    规则格式：[{"url": "子串或正则", "group": "目标组"}, ...]
    """
    try:
        from app.config import Config
        rules = Config.get_setting("group_override_by_url", []) or []
        compiled = []
        for r in rules:
            if not r:
                continue
            pattern = r.get("url", "")
            group = r.get("group", "")
            if not pattern or not group:
                continue
            try:
                compiled.append((re.compile(pattern, re.IGNORECASE), group))
            except re.error:
                compiled.append((pattern.lower(), group))
        return compiled
    except Exception:
        return []


def _apply_group_override(url, group):
    """按 URL 精确覆盖分组"""
    rules = _load_group_overrides()
    if not rules:
        return group
    url_l = str(url).lower()
    for pat, grp in rules:
        if isinstance(pat, str):
            if pat in url_l:
                return grp
        else:
            if pat.search(str(url)):
                return grp
    return group


def _fetch_parent(url, proxy=None):
    """下载母链内容，返回 (text, error)。GitHub 页面会转 raw。"""
    raw_url = format_github_raw_url(url)
    content, err = download_url(raw_url, proxy=proxy)
    if err and raw_url != url:
        content, err = download_url(url, proxy=proxy)
    return content, err


class RepairService:
    """乱码修补 + 检测服务"""

    def __init__(self, log_callback=None, settings=None, data_dir=None):
        self.log_callback = log_callback or (lambda msg: None)
        self._settings = settings or {}
        self._data_dir = data_dir or os.getcwd()

    def repair(self, text, mode="纯净模式", save_only=False, fmt="m3u"):
        """
        乱码修补主流程：
        1. 修复UTF-8/Latin-1乱码
        2. 提取频道名+URL
        3. 自动分组（根据频道名+URL综合判断）
        4. 后台检测链接存活状态
        5. 保留所有频道（含离线），一并返回
        """
        raw = text.strip()
        if not raw:
            return {"error": "请输入或粘贴文本"}

        # 刷新可配置规则（标签词表可从设置覆盖）
        _refresh_rules()

        # 第一步：修复UTF-8/Latin-1乱码
        self.log_callback("正在检测并修复乱码...")
        fixed_text = fix_garbled_utf8(raw)
        if fixed_text != raw:
            self.log_callback("检测到乱码，已自动修复UTF-8编码")

        # 第二步：解析提取频道与母链
        parent_links = []
        channels = parse_raw_text(fixed_text)
        if not channels:
            channels = extract_channels(fixed_text)
        if not channels:
            urls = _URL_RE.findall(fixed_text)
            for url in urls:
                url = clean_url(url)
                p = urlparse(url)
                name = os.path.basename(p.path) or p.netloc or "未知频道"
                if name:
                    name = os.path.splitext(name)[0]
                    name = re.sub(r'[._-]', ' ', name).strip()
                if not name or len(name) < 2:
                    name = p.netloc or "未知频道"
                channels.append({
                    "name": name, "url": url, "group": "", "logo": "",
                    "raw_extinf": f'#EXTINF:-1 group-title="自动分组",{name}',
                    "raw_url": url
                })

        # 分类：把 URL 拆成母链与频道
        classified = {"parent": [], "channel": []}
        for ch in channels:
            kind = _classify_url(ch["url"])
            classified[kind].append(ch)

        # 对母链递归抓取一次（避免无限递归，仅一层）
        fetched_channels = []
        proxy = self._settings.get("proxy", "") or None
        for parent in classified["parent"]:
            url = parent["url"]
            self.log_callback(f"正在抓取母链: {url}")
            content, err = _fetch_parent(url, proxy=proxy)
            if err:
                parent_links.append({
                    "url": url, "name": parent.get("name", ""), "status": "失败",
                    "error": str(err), "count": 0
                })
                continue
            # 修复乱码后再解析
            content = fix_garbled_utf8(content)
            sub = parse_raw_text(content)
            if not sub:
                sub = extract_channels(content)
            # 过滤掉仍是母链的条目（避免递归爆炸）
            sub_channels = [c for c in sub if _classify_url(c["url"]) == "channel"]
            fetched_channels.extend(sub_channels)
            parent_links.append({
                "url": url, "name": parent.get("name", ""), "status": "成功",
                "error": "", "count": len(sub_channels)
            })

        all_channels = classified["channel"] + fetched_channels

        if not all_channels and not parent_links:
            return {"error": "未提取到任何有效频道或母链"}

        # 第三步：去重（按URL）
        seen, unique = set(), []
        for ch in all_channels:
            if ch["url"] not in seen:
                seen.add(ch["url"])
                unique.append(ch)
        self.log_callback(f"乱码修补：提取到 {len(unique)} 个频道（去重 {len(all_channels) - len(unique)} 条）")

        # 第四步：后台检测频道存活状态（始终执行）
        self.log_callback(f"开始检测 {len(unique)} 个频道的连接状态...")
        self._check_channels(unique)

        online_count = sum(1 for ch in unique if ch.get("status") == "在线")
        offline_count = sum(1 for ch in unique if ch.get("status") == "离线")
        self.log_callback(f"检测完成：在线 {online_count}，离线 {offline_count}")

        # 第五步：构建最终结果（保留所有频道，含离线）
        final = []
        for ch in unique:
            url = ch["url"]
            raw_name = ch.get("name", "")

            # 5.1 从名称中提取方括号标签（状态、分辨率等）
            clean_name, meta = extract_tags_from_name(raw_name)

            # 5.2 全面清理名称（方括号、圆括号、特殊字符、emoji）
            clean_name = clean_channel_name(clean_name)

            # 5.3 安全兜底：正则确保无残留标签
            clean_name = re.sub(r'\s*\[[^\]]*\]\s*', ' ', clean_name).strip()
            clean_name = re.sub(r'\s*\([^)]*\)\s*', ' ', clean_name).strip()
            clean_name = re.sub(r'\s+', ' ', clean_name).strip()

            # 5.4 如果名称仍为乱码/太短，从URL路径推断频道名
            if not clean_name or clean_name == "未知频道" or len(clean_name) < 2:
                inferred = infer_name_from_url(url)
                if inferred:
                    clean_name = inferred
                else:
                    p = urlparse(url)
                    clean_name = p.netloc or "未知频道"

            # 5.5 检测名称是否仍含乱码字符（无中文且含Latin-1高位字符）
            if clean_name and _looks_garbled(clean_name) and _count_cjk(clean_name) == 0:
                inferred = infer_name_from_url(url)
                if inferred:
                    clean_name = inferred

            # 自动分组：综合频道名+URL判断
            group = determine_group(clean_name, url, ch.get("group", ""))
            # 按 URL 精确覆盖分组
            group = _apply_group_override(url, group)

            # Logo
            logo = ch.get("logo", "")
            if not logo and mode == "完整增强":
                logo = find_logo(clean_name) or ""

            # 检测结果优先，标签提取结果作为补充
            status = ch.get("status", "未检查")
            if status == "未检查" and meta.get("status"):
                status = meta["status"]
            ms = ch.get("ms", "-")
            res = ch.get("res", "-")
            if res == "-" and meta.get("res"):
                res = meta["res"]
            stack = meta.get("stack", "IPv4")
            tag = meta.get("tag", "")
            note = ch.get("url_note", "")

            final.append({
                "name": clean_name,
                "url": url,
                "group": group,
                "logo": logo,
                "status": status,
                "ms": ms,
                "res": res,
                "stack": stack,
                "tag": tag,
                "url_note": note,
                "raw_extinf": f'#EXTINF:-1 group-title="{group}",{clean_name}',
                "raw_url": url
            })

        self.log_callback(f"乱码修补完成，共 {len(final)} 个频道（在线 {online_count}，离线 {offline_count}）")

        if save_only:
            fname = f"修复结果.{fmt}"
            fpath = os.path.join(self._data_dir, fname)
            success, err = export_playlist(final, fpath, fmt)
            if not success:
                raise Exception(err)
            return {"file": fpath, "filename": fname}

        # 修补历史留存（便于回溯）
        self._append_history(raw, len(unique), len(final), mode)
        # 前后对照预览：原始行 ↔ 修复编码后行
        preview = self._build_preview(raw, fixed_text, n=30)
        return {
            "channels": final,
            "parent_links": parent_links,
            "count": len(final),
            "parent_count": len(parent_links),
            "preview": preview
        }

    def _append_history(self, raw_text, src_count, out_count, mode):
        """修补历史留存：追加一条 JSONL 记录到 data_dir/repair_history.jsonl。"""
        try:
            import json
            from datetime import datetime
            path = os.path.join(self._data_dir, "repair_history.jsonl")
            rec = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "mode": mode,
                "input_chars": len(raw_text),
                "parsed": src_count,
                "output": out_count,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    @staticmethod
    def _build_preview(raw_text, fixed_text, n=30):
        """前后对照预览：按行对齐原始输入与修复编码后的文本，返回有差异的前 n 行。"""
        raw_lines = raw_text.split("\n")
        fixed_lines = fixed_text.split("\n")
        total = max(len(raw_lines), len(fixed_lines))
        pairs = []
        for i in range(min(n, total)):
            before = raw_lines[i] if i < len(raw_lines) else ""
            after = fixed_lines[i] if i < len(fixed_lines) else ""
            if before != after:
                pairs.append({"before": before[:160], "after": after[:160]})
        return pairs

    def _check_channels(self, channels):
        """并发检测频道连接状态"""
        repair_timeout = int(self._settings.get("repair_check_timeout", 5))
        repair_retries = int(self._settings.get("repair_max_retries", 1))
        repair_workers = int(self._settings.get("repair_max_workers", 10))

        def check_one(channel):
            url = channel["url"]
            start = time.time()
            try:
                online, code, elapsed, res = http_probe_channel(
                    url, timeout=repair_timeout, retries=repair_retries)
            except Exception:
                online, code, elapsed, res = False, None, int((time.time() - start) * 1000), "-"
            if online:
                channel["status"] = "在线"
            else:
                channel["status"] = "离线"
            channel["ms"] = str(elapsed)
            channel["res"] = res

        with ThreadPoolExecutor(max_workers=repair_workers) as executor:
            futures = {executor.submit(check_one, ch): ch for ch in channels}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    ch = futures[future]
                    ch["status"] = "错误"
                    ch["ms"] = "-"
                    ch["res"] = "-"