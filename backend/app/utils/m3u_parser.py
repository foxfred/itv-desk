import io
import re
from urllib.parse import urlparse
from app.utils.network import normalize_url
from app.config import Config


class Parser:
    @staticmethod
    def standardize_name(ns):
        n = str(ns).upper().strip()
        n = re.sub(r'\[.*?\]|\(.*?\)|\（.*?\）|-高清|-超清|HD|4K|1080P|BD|蓝光|综合|频道', '', n).strip()
        n = n.replace("CCTV 综合", "CCTV1").replace("CCTV 财经", "CCTV2").replace("CCTV 综艺", "CCTV3")
        n = n.replace("CCTV 体育", "CCTV5").replace("CCTV 电影", "CCTV6").replace("CCTV 新闻", "CCTV13").replace("中央", "CCTV")
        m = re.match(r'^(CCTV)(\d+)$', n)
        if m:
            n = f"{m.group(1)}-{m.group(2)}"
        return n if n else ns.strip().upper()

    FOREIGN_KEYWORDS = [
        "日本", "韩国", "朝鲜", "美国", "英国", "法国", "德国", "意大利", "西班牙",
        "俄罗斯", "印度", "泰国", "越南", "新加坡", "马来西亚", "印尼", "土耳其",
        "阿拉伯", "加拿大", "巴西", "墨西哥", "荷兰", "葡萄牙", "波兰", "乌克兰",
        "菲律宾", "澳大利亚", "新西兰", "柬埔寨", "老挝", "缅甸", "尼泊尔", "斯里兰卡",
        "巴基斯坦", "孟加拉", "哈萨克", "蒙古", "伊朗", "伊拉克", "以色列", "埃及",
        "南非", "肯尼亚", "尼日利亚", "瑞典", "挪威", "丹麦", "芬兰", "瑞士", "奥地利",
        "比利时", "爱尔兰", "希腊", "捷克", "匈牙利", "罗马尼亚",
        "JAPAN", "KOREA", "USA", "UK", "FRANCE", "GERMANY", "RUSSIA", "INDIA",
        "THAI", "SINGAPORE", "CANADA", "BRAZIL", "AUSTRALIA",
    ]

    @staticmethod
    def _has_cjk(s):
        return bool(re.search(r'[\u3400-\u9fff]', s))

    @staticmethod
    def get_channel_group(n, custom_rules=None, foreign_name="外国频道"):
        name = str(n)
        nu = name.upper()
        if custom_rules:
            for rule in custom_rules:
                if not rule:
                    continue
                if isinstance(rule, dict):
                    kw = rule.get("keyword")
                    grp = rule.get("group")
                else:
                    kw, grp = (list(rule) + [None, None])[:2]
                if not kw or not grp:
                    continue
                if str(kw).upper() in nu:
                    return grp
        if any(k in nu for k in ["香港", "台湾", "澳门", "翡翠", "明珠", "凤凰",
                                  "TVB", "中天", "纬来", "东森", "年代", "三立", "华视", "民视",
                                  "台视", "公视", "中视", "无线", "美亚", "莲花", "澳视", "PHOENIX"]):
            return "港澳台"
        import re as _re
        if _re.search(r'(^|[^A-Z])(HK|TW|MO)($|[^A-Z])', nu):
            return "港澳台"
        if "CCTV" in nu:
            return "央视频道"
        if (not Parser._has_cjk(name)) or any(k.upper() in nu for k in Parser.FOREIGN_KEYWORDS):
            return foreign_name
        if "卫视" in name:
            return "地方卫视"
        if any(k in name for k in ["北京", "上海", "广东", "江苏", "浙江", "湖南", "四川", "深圳",
                                    "天津", "重庆", "河北", "河南", "山东", "山西", "陕西", "福建",
                                    "安徽", "辽宁", "吉林", "黑龙江", "湖北", "江西", "广西", "云南",
                                    "贵州", "海南", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "西藏",
                                    "新闻综合", "都市", "生活", "公共", "经济生活"]):
            return "地方卫视"
        if any(k in nu for k in ["电影", "影院", "剧场", "HBO", "影视", "经典影院", "CH", "电影台", "动作", "影迷", "STAR"]):
            return "电影剧场"
        if any(k in nu for k in ["体育", "足球", "五星", "NBA", "赛事", "劲爆", "高尔夫", "CCTV5", "羽毛球", "台球", "五星体育"]):
            return "体育竞技"
        if any(k in nu for k in ["少儿", "卡通", "动漫", "儿童", "娃娃", "金鹰卡通", "哈哈炫动", "卡酷"]):
            return "少儿动漫"
        if any(k in nu for k in ["新闻", "资讯", "环球"]):
            return "新闻资讯"
        if any(k in nu for k in ["财经", "经济", "商业", "证券", "理财", "交易"]):
            return "财经商业"
        if any(k in nu for k in ["音乐", "戏曲", "戏剧", "歌曲", "MTV", "音乐台"]):
            return "音乐戏曲"
        if any(k in nu for k in ["纪录", "探索", "DISCOVERY", "纪实"]):
            return "纪录片"
        if any(k in nu for k in ["购物", "导购", "电视购物", "SHOP"]):
            return "购物"
        if any(k in nu for k in ["NEWTV", "IHOT", "SITV", "轮播", "百视通", "咪咕", "欢腾", "求索"]):
            return "轮播专区"
        return "其他"

    @staticmethod
    def detect_geo_and_stack(n, u):
        n_u, u_u = str(n).upper(), str(u).upper()
        g = "中国"
        if any(k in n_u for k in ["HBO", "CNN", "BBC", "DISCOVERY"]):
            g = "欧美"
        elif any(k in n_u for k in ["HK", "香港", "翡翠", "PHOENIX"]):
            g = "中国香港"
        elif any(k in n_u for k in ["TW", "台湾", "东森"]):
            g = "中国台湾"
        s = "IPv4"
        try:
            nl = urlparse(u).netloc
            if "[" in nl and "]" in nl:
                s = "IPv6"
            elif re.search(r'//\[[0-9a-fA-F:]+\]', u):
                s = "IPv6"
        except:
            pass
        return g, s

    @staticmethod
    def is_live_stream(u, cc):
        u_u = str(u).upper()
        video_exts = [".M3U8", ".M3U", ".TS", "/TS/", ".MP4", ".FLV", ".MKV", ".AVI", ".MOV", ".WMV"]
        if any(k in u_u for k in video_exts):
            return True
        if any(k in u_u for k in ["M3U8?", "PLAY?", "LIVE", "STREAM"]):
            return True
        if any(k in cc for k in ["#EXTM3U", "#EXTINF", "MPEGTS", "FLV", "FTYPMP4"]):
            return True
        if "FTYP" in cc and "MP4" in cc:
            return True
        return False

    @staticmethod
    def parse_local_file(txt):
        channels, lines = [], txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        fixed = []
        for line in lines:
            line = line.strip()
            if line.startswith("#EXTM3U") and "#EXTINF" in line:
                parts = line.split("#EXTINF", 1)
                fixed.append(parts[0].strip())
                fixed.append("#EXTINF" + parts[1].strip())
            else:
                fixed.append(line)
        lines = fixed
        if "#EXTM3U" in txt[:150]:
            name = group = ""
            for l in lines:
                l = l.strip()
                if l.startswith("#EXTINF:"):
                    gm = re.search(r'group-title="([^"]+)"', l)
                    group = gm.group(1).strip() if gm else ""
                    if "," in l:
                        name = Parser.standardize_name(l.split(",", 1)[-1].strip())
                elif (l.startswith(("http://", "https://", "rtmp://", "rtsp://"))) and name:
                    channels.append({"name": name, "url": l, "group": group})
                    name = group = ""
        else:
            for l in lines:
                l = l.strip()
                if "," in l and ("http://" in l or "https://" in l or "rtmp://" in l or "rtsp://" in l):
                    p = l.split(",", 1)
                    name = Parser.standardize_name(p[0].strip())
                    if name and p[-1].strip():
                        channels.append({"name": name, "url": p[-1].strip(), "group": ""})
        return channels


def extract_channels(raw_text):
    lines = raw_text.splitlines()
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("#EXTINF:"):
            group_match = re.search(r'group-title="([^"]+)"', line)
            group = group_match.group(1) if group_match else ""
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            logo = logo_match.group(1) if logo_match else ""
            tag_match = re.search(r'tvg-tag="([^"]+)"', line)
            tag_val = tag_match.group(1) if tag_match else ""
            tag_parts = [p.strip() for p in tag_val.split(",") if p.strip()]
            is_fake_live = "假直播" in tag_parts
            normal_tags = [p for p in tag_parts if p != "假直播"]
            tag = ",".join(normal_tags)
            if "," in line:
                name = line.split(",", 1)[-1].strip()
            else:
                name = "未知频道"
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if any(url.startswith(p) for p in ["http://", "https://", "rtmp://", "rtsp://"]):
                    channels.append({
                        "name": name,
                        "url": url,
                        "group": group,
                        "logo": logo,
                        "tag": tag,
                        "is_fake_live": is_fake_live,
                        "raw_extinf": line,
                        "raw_url": url
                    })
                    i += 2
                    continue
            i += 1
            continue
        if "," in line and any(proto in line for proto in ["http://", "https://", "rtmp://", "rtsp://"]):
            parts = line.split(",", 1)
            name = parts[0].strip()
            url = parts[1].strip()
            url_clean = url
            url_note = ""
            if "$" in url:
                url_parts = url.split("$", 1)
                url_clean = url_parts[0]
                if len(url_parts) > 1:
                    url_note = url_parts[1]
            channels.append({
                "name": name,
                "url": url_clean,
                "group": Config.get_setting("default_group_name", "自动分组"),
                "logo": "",
                "url_note": url_note,
                "raw_extinf": f'#EXTINF:-1 group-title="{Config.get_setting("default_group_name", "自动分组")}",{name}',
                "raw_url": url
            })
            i += 1
            continue
        if i + 2 < len(lines):
            name_line = line
            status_line = lines[i + 1].strip()
            url_line = lines[i + 2].strip()
            if status_line in ["可用", "失效", "可播放", "不可用"] and any(url_line.startswith(p) for p in ["http://", "https://", "rtmp://", "rtsp://"]):
                url_clean = url_line
                url_note = ""
                if "$" in url_line:
                    parts = url_line.split("$", 1)
                    url_clean = parts[0]
                    if len(parts) > 1:
                        url_note = parts[1]
                channels.append({
                    "name": name_line.strip(),
                    "url": url_clean,
                    "group": Config.get_setting("default_group_name", "自动分组"),
                    "logo": "",
                    "url_note": url_note,
                    "raw_extinf": f'#EXTINF:-1 group-title="{Config.get_setting("default_group_name", "自动分组")}",{name_line.strip()}',
                    "raw_url": url_line
                })
                i += 3
                continue
        if any(line.startswith(p) for p in ["http://", "https://", "rtmp://", "rtsp://"]):
            if i > 0:
                prev = lines[i - 1].strip()
                if prev and not any(prev.startswith(p) for p in ["http://", "https://", "rtmp://", "rtsp://"]):
                    url_clean = line
                    url_note = ""
                    if "$" in line:
                        parts = line.split("$", 1)
                        url_clean = parts[0]
                        if len(parts) > 1:
                            url_note = parts[1]
                    channels.append({
                        "name": prev,
                        "url": url_clean,
                        "group": Config.get_setting("default_group_name", "自动分组"),
                        "logo": "",
                        "url_note": url_note,
                        "raw_extinf": f'#EXTINF:-1 group-title="{Config.get_setting("default_group_name", "自动分组")}",{prev}',
                        "raw_url": line
                    })
            i += 1
            continue
        i += 1
    return channels


def _write_m3u_channel(f, ch, with_tvg_name=False):
    grp = ch.get("group", Config.get_setting("unknown_group_name", "未分组"))
    logo = ch.get("logo")
    tag = ch.get("tag") or ""
    if ch.get("is_fake_live") and "假直播" not in tag:
        tag = (tag + ",假直播").strip(",")
    note = ch.get("url_note")
    u = (ch.get("url") or "").strip()
    if not u:
        return
    name = ch.get("name", "")
    parts = [f'#EXTINF:-1 group-title="{grp}"']
    if with_tvg_name and name:
        parts.append(f'tvg-name="{name}"')
    if logo:
        parts.append(f'tvg-logo="{logo}"')
    if tag:
        parts.append(f'tvg-tag="{tag}"')
    f.write(" ".join(parts) + f',{name}\n')
    if note:
        f.write(f'{u}${note}\n')
    else:
        f.write(f'{u}\n')


def _write_txt_channel(f, ch):
    u = (ch.get("url") or "").strip()
    if not u:
        return
    f.write(f'{ch.get("name", "")},{u}\n')


def _write_xml_channel(f, ch):
    u = (ch.get("url") or "").strip()
    if not u:
        return
    grp = ch.get("group", Config.get_setting("unknown_group_name", "未分组"))
    f.write('  <channel>\n')
    f.write(f'    <name>{ch.get("name", "")}</name>\n')
    f.write(f'    <url>{u}</url>\n')
    f.write(f'    <group>{grp}</group>\n')
    if ch.get("logo"):
        f.write(f'    <logo>{ch["logo"]}</logo>\n')
    if ch.get("status"):
        f.write(f'    <status>{ch["status"]}</status>\n')
    if ch.get("ms"):
        f.write(f'    <ms>{ch["ms"]}</ms>\n')
    if ch.get("res"):
        f.write(f'    <res>{ch["res"]}</res>\n')
    f.write('  </channel>\n')


def _write_playlist(f, channels, format="m3u", url_tvg="", with_tvg_name=False):
    if format in ["m3u", "m3u8"]:
        header = "#EXTM3U"
        if url_tvg:
            header += f' url-tvg="{url_tvg}"'
        f.write(header + "\n")
        for ch in channels:
            _write_m3u_channel(f, ch, with_tvg_name=with_tvg_name)
    elif format == "txt":
        for ch in channels:
            _write_txt_channel(f, ch)
    elif format == "json":
        import json
        json.dump(channels, f, ensure_ascii=False, indent=Config.get_setting("json_indent", 2))
    elif format == "xml":
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<channels>\n')
        for ch in channels:
            _write_xml_channel(f, ch)
        f.write('</channels>\n')
    else:
        for ch in channels:
            _write_txt_channel(f, ch)


def render_playlist(channels, format="m3u", url_tvg="", with_tvg_name=False):
    buf = io.StringIO()
    _write_playlist(buf, channels, format, url_tvg=url_tvg, with_tvg_name=with_tvg_name)
    return buf.getvalue()


def export_playlist(channels, filepath, format="m3u"):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            _write_playlist(f, channels, format)
        return True, None
    except Exception as e:
        return False, str(e)