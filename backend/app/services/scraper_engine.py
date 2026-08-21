"""抓取引擎 - 爬取网页并提取流媒体链接

增强（对应评估报告 §4.2）：
- 链接下载/解析改为线程池并发（并发数取设置 scraper_threads，默认 8）+ 全局限速；
- 内容嗅探：依据内容特征区分 M3U 播放列表 / HTML 页面 / 其它，M3U 解析内嵌变体（不同清晰度），
  HTML 二次提取链接；
- 目标类型自动识别：单页直链（url 不含 {page} 且 start==end==1）直接当播放列表解析，
  避免把 M3U 当列表页漏抓；
- 失败策略：指数退避 + 全局重试预算；
- 结果统计：实时上报 已处理/总数、成功/失败/直链 计数。
"""
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from app.utils.network import download_url, build_link_pattern, format_github_raw_url
from app.utils.m3u_parser import extract_channels
from app.config import Config


class ScraperEngine:
    """网页抓取引擎：爬取页面，提取 m3u/ts 等流媒体链接，下载并解析频道内容"""

    def __init__(self, log_cb, inject_cb, stop_event, status_cb):
        self.log = log_cb
        self.inject = inject_cb
        self.stop = stop_event
        self.status = status_cb
        self._rate_lock = threading.Lock()
        self._last_request_ts = 0.0
        self._min_interval = 0.0

    # -------------------- 工具方法（保持原行为） --------------------
    def _resolve_url(self, link, base_url):
        """将相对路径转为绝对URL"""
        if link.startswith("http://") or link.startswith("https://"):
            return link
        if link.startswith("/"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{link}"
        if link.startswith("//"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}:{link}"
        if "/" in base_url:
            base_dir = base_url.rsplit("/", 1)[0]
            return f"{base_dir}/{link}"
        return f"{base_url}/{link}"

    def _apply_mirror(self, url, mirror):
        """对GitHub链接应用加速源"""
        if not mirror or mirror == "不使用加速":
            return format_github_raw_url(url, "")
        return format_github_raw_url(url, mirror)

    def _throttle(self, min_interval):
        """全局限速：保证两次请求入口至少间隔 min_interval 秒（0 表示不限速）"""
        if min_interval <= 0:
            return
        with self._rate_lock:
            now = time.time()
            wait = min_interval - (now - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.time()

    @staticmethod
    def _link_channel(url):
        """失败/非 M3U 链接兜底：构造一个最小频道记录（名称取域名，后续可被清洗）"""
        netloc = urlparse(url).netloc or "频道"
        return {"name": netloc, "url": url, "group": "", "tag": "", "logo": ""}

    def _fetch(self, url, proxy, mirror, timeout, retries, budget):
        """带 mirror 回退 + 指数退避 + 全局重试预算的下载。返回 (content, err)。"""
        sources = []
        dl = self._apply_mirror(url, mirror)
        if dl != url:
            sources.append(dl)
        sources.append(url)  # 直连回退
        last_err = "下载失败"
        max_attempts = 1 + max(0, retries)
        for attempt in range(max_attempts):
            if self.stop and self.stop.is_set():
                return "", "用户中断"
            src = sources[min(attempt, len(sources) - 1)]
            self._throttle(self._min_interval)
            content, err = download_url(
                src, proxy=proxy or None, timeout=timeout, max_retries=1, stop_event=self.stop
            )
            if not err and content:
                return content, None
            last_err = err or "下载失败"
            # 是否还有重试额度（全局预算 + 链接级重试）
            if attempt < max_attempts - 1:
                if budget["left"] > 0:
                    budget["left"] -= 1
                    backoff = min(0.5 * (2 ** attempt), 5.0)
                    time.sleep(backoff)
                else:
                    break
        return "", last_err

    def _extract_variants(self, m3u_content, base_url):
        """从主 m3u8 提取 #EXT-X-STREAM-INF 嵌套变体链接（不同清晰度）。返回 [(url, resolution)]。

        采用逐行解析（而非单一跨行正则），稳定捕获 RESOLUTION 与变体 URI，避免
        `#EXT-X-STREAM-INF` 行被贪婪/懒惰量词吞掉导致分辨率丢失。
        """
        variants = []
        lines = m3u_content.splitlines()
        for i, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue
            res_m = re.search(r'RESOLUTION=(\d+x\d+)', line)
            res = res_m.group(1) if res_m else ""
            if i + 1 < len(lines):
                vurl = lines[i + 1].strip()
                if vurl and not vurl.startswith("#"):
                    variants.append((self._resolve_url(vurl, base_url), res))
        return variants

    def _resolve_variants(self, content, base_url, proxy, mirror, timeout, budget):
        """解析主索引 m3u8 的变体（不同清晰度），返回真实频道列表（带分辨率标签）。

        主索引 m3u8（含 #EXT-X-STREAM-INF）本身不直接包含频道，必须下载其变体再解析，
        否则 extract_channels 会把 STREAM-INF 行误当成频道名、变体 URI 当成 URL。
        """
        channels = []
        for vurl, res in self._extract_variants(content, base_url)[:10]:
            if self.stop and self.stop.is_set():
                break
            vc, ve = self._fetch(vurl, proxy, mirror, timeout, 0, budget)
            if ve or not vc:
                continue
            for c in (extract_channels(vc) or []):
                if res:
                    c["name"] = f"{c.get('name', '')} {res}".strip()
                channels.append(c)
        return channels

    @staticmethod
    def _sniff(content):
        """内容嗅探：依据特征判断类型。返回 'm3u' / 'html' / 'other'。"""
        if not content:
            return "other"
        head = content[:4000]
        if head.lstrip().startswith("#EXTM3U") or "#EXTM3U" in head:
            return "m3u"
        if re.search(r'<html|<!doctype html|<a\s|href\s*=', head, re.IGNORECASE):
            return "html"
        return "other"

    def _process_link(self, link, proxy, mirror, timeout, retries, budget, pattern, stats):
        """处理单个链接：下载 → 嗅探 → 解析。返回 (channels, kind)。"""
        if self.stop and self.stop.is_set():
            return [], "stopped"
        content, err = self._fetch(link, proxy, mirror, timeout, retries, budget)
        if err:
            stats["failed"] += 1
            return [self._link_channel(link)], "failed"
        kind = self._sniff(content)
        if kind == "m3u":
            if "#EXT-X-STREAM-INF" in content:
                channels = self._resolve_variants(content, link, proxy, mirror, timeout, budget)
            else:
                channels = list(extract_channels(content) or [])
            if not channels:
                stats["as_link"] += 1
                return [self._link_channel(link)], "other"
            stats["success"] += 1
            return channels, "m3u"
        if kind == "html":
            found = set()
            sub_links = []
            for m in pattern.finditer(content):
                l = m.group(1) or m.group(3) or m.group(5)
                if l and l not in found:
                    found.add(l)
                    sub_links.append(self._resolve_url(l, link))
            sub = []
            for nl in sub_links[:20]:
                if self.stop and self.stop.is_set():
                    break
                c2, e2 = self._fetch(nl, proxy, mirror, timeout, 0, budget)
                if e2 or not c2:
                    continue
                sub.extend(extract_channels(c2) or [])
            stats["success"] += 1
            return sub, "html"
        # other：作为直链保留
        stats["as_link"] += 1
        return [self._link_channel(link)], "other"

    def run(self, url, start, end, suffix_list, proxy, mirror):
        """执行抓取任务"""
        suffixes = [s.strip() for s in suffix_list.split(",") if s.strip()]
        if not suffixes:
            self.log("后缀列表为空")
            return

        # 读取抓取设置
        workers = max(1, int(Config.get_setting("scraper_threads", 8)))
        timeout = max(1, int(Config.get_setting("scraper_timeout", 15)))
        retries = max(0, int(Config.get_setting("scraper_retries", 2)))
        self._min_interval = float(Config.get_setting("scraper_min_interval", 0.0))
        budget = {"left": max(10, workers * 3)}  # 全局额外重试预算

        pattern = build_link_pattern(suffixes)
        is_single = ("{page}" not in url) and start == 1 and end == 1

        self.log(f"抓取引擎：并发数={workers}，超时={timeout}s，每链接重试={retries}，限速={self._min_interval}s")

        # -------------------- 类型识别：单页直链（直接播放列表） --------------------
        if is_single:
            self.log(f"检测到单页直链模式，直接解析目标: {url}")
            self.status("正在解析直链目标", 5)
            content, err = self._fetch(url, proxy, mirror, timeout, retries, budget)
            if err:
                self.log(f"直链下载失败: {err}")
                self._finish([])
                return
            kind = self._sniff(content)
            if kind == "m3u":
                if "#EXT-X-STREAM-INF" in content:
                    channels = self._resolve_variants(content, url, proxy, mirror, timeout, budget)
                else:
                    channels = list(extract_channels(content) or [])
                if not channels:
                    self.log("M3U 未解析到频道")
                    self._finish([])
                    return
                self.log(f"直链解析完成，提取 {len(channels)} 个频道")
                self._finish(channels)
                return
            if kind == "html":
                found = set()
                all_links = []
                for m in pattern.finditer(content):
                    l = m.group(1) or m.group(3) or m.group(5)
                    if l and l not in found:
                        found.add(l)
                        all_links.append(self._resolve_url(l, url))
                if not all_links:
                    self.log("直链 HTML 页面未提取到任何链接")
                    self._finish([])
                    return
                self.log(f"直链 HTML 提取 {len(all_links)} 个链接，转入并发解析")
                self._concurrent_resolve(all_links, proxy, mirror, timeout, retries, budget, pattern)
                return
            self._finish([self._link_channel(url)])
            return

        # -------------------- 多页列表页：逐页下载并收集链接（页面数通常较少，顺序即可） --------------------
        all_links = []
        total_pages = end - start + 1
        for page in range(start, end + 1):
            if self.stop and self.stop.is_set():
                self.log("抓取已中断")
                return
            raw_page_url = url.replace("{page}", str(page))
            page_url = self._apply_mirror(raw_page_url, mirror)
            self.log(f"正在抓取第 {page} 页: {page_url}")
            if page_url != raw_page_url:
                self.log(f"  (加速源: {mirror})")
            pct = int((page - start) / total_pages * 100) if total_pages > 0 else 0
            self.status(f"正在抓取第 {page} 页", pct)

            self._throttle(self._min_interval)
            content, err = download_url(
                page_url, proxy=proxy or None, timeout=timeout, max_retries=1, stop_event=self.stop
            )
            if err:
                self.log(f"第 {page} 页下载失败: {err}")
                if page_url != raw_page_url:
                    self.log(f"加速源失败，尝试直连: {raw_page_url}")
                    content, err = download_url(
                        raw_page_url, proxy=proxy or None, timeout=timeout, max_retries=1, stop_event=self.stop
                    )
                    if err:
                        self.log(f"直连也失败: {err}")
                        continue
                    page_url = raw_page_url
                else:
                    continue
            if not content:
                self.log(f"第 {page} 页内容为空")
                continue
            # 单页内容若是 M3U（罕见但仍可能），直接解析避免漏抓
            if self._sniff(content) == "m3u":
                if "#EXT-X-STREAM-INF" in content:
                    chs = self._resolve_variants(content, raw_page_url, proxy, mirror, timeout, budget)
                else:
                    chs = list(extract_channels(content) or [])
                self.log(f"第 {page} 页为 M3U 列表，直接解析 {len(chs)} 个频道")
                self._finish(chs)
                return
            found = set()
            for m in pattern.finditer(content):
                link = m.group(1) or m.group(3) or m.group(5)
                if not link or link in found:
                    continue
                found.add(link)
                abs_link = self._resolve_url(link, raw_page_url)
                all_links.append(abs_link)
                self.log(f"    发现链接: {abs_link}")
            self.log(f"第 {page} 页找到 {len(found)} 个链接")

        if not all_links:
            self.log("未找到任何有效链接")
            return

        self.log(f"共发现 {len(all_links)} 个链接，开始并发探测并解析（并发数 {workers}）...")
        self._concurrent_resolve(all_links, proxy, mirror, timeout, retries, budget, pattern)

    def _concurrent_resolve(self, all_links, proxy, mirror, timeout, retries, budget, pattern):
        """第二阶段：线程池并发下载并解析每个链接。"""
        all_channels = []
        stats = {"processed": 0, "total": len(all_links), "success": 0, "failed": 0, "as_link": 0}
        lock = threading.Lock()
        workers = max(1, int(Config.get_setting("scraper_threads", 8)))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self._process_link, link, proxy, mirror, timeout, retries, budget, pattern, stats
                ): link
                for link in all_links
            }
            for future in as_completed(futures):
                if self.stop and self.stop.is_set():
                    self.log("抓取已中断")
                    break
                link = futures[future]
                try:
                    result, kind = future.result()
                except Exception:
                    result, kind = [self._link_channel(link)], "error"
                with lock:
                    all_channels.extend(result)
                    stats["processed"] += 1
                    pct = int(stats["processed"] / stats["total"] * 100) if stats["total"] else 100
                self.status(
                    f"探测 {stats['processed']}/{stats['total']} "
                    f"成功{stats['success']} 失败{stats['failed']} 直链{stats['as_link']}",
                    pct,
                )
        self.log(
            f"探测完成：处理 {stats['processed']}/{stats['total']} 链接，"
            f"成功解析 {stats['success']}，失败 {stats['failed']}，直链保留 {stats['as_link']}，"
            f"共提取 {len(all_channels)} 个频道"
        )
        self._finish(all_channels)

    def _finish(self, all_channels):
        if all_channels:
            self.log(f"正在注入频道池...")
            self.inject(all_channels)
        else:
            self.log("未提取到任何频道")
