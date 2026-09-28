# IPTV 订阅源实测清单

> 生成时间：2026-09-28 21:5x
> 测试方式：直连 raw.githubusercontent.com（走中转通道），读取响应 + 统计 `#EXTINF` 条数 + 检测台标/EPG 字段
> 说明：条数为「前 256 KB 内统计」，实际总数通常更多；所有地址均实测 HTTP 200

---

## 一、主推：大而全（1000+ 频道，带台标 + EPG + 分组）

| 项目 | 订阅地址 | 频道≈ | 台标 | EPG | 备注 |
|---|---|---|---|---|---|
| **suxuang/myIPTV** | `https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u` | 1273 | Y | Y | 典藏版，卫视最全，台标+节目预告内置 |
| **CCSH/IPTV** | `https://raw.githubusercontent.com/CCSH/IPTV/main/live_platforms.m3u` | 1447 | Y | - | 多平台聚合，频道数最多 |
| **CCSH/IPTV** | `https://raw.githubusercontent.com/CCSH/IPTV/main/live.m3u` | 1098 | Y | Y | 全量版，带 EPG |
| **Free-TV/IPTV** | `https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8` | 1179 | Y | Y | 全球源，英文台多 |
| **Guovin/iptv-api** | `https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u` | 1114 | Y | Y | 自动采集+校验+测速后的成品（注意是 `gd` 分支，master 无输出） |

## 二、中国大陆专项（央视 / 卫视 / 地方台）

| 项目 | 订阅地址 | 频道≈ | 台标 | 备注 |
|---|---|---|---|---|
| **zilong7728/Collect-IPTV** | `https://raw.githubusercontent.com/zilong7728/Collect-IPTV/main/best_sorted.m3u` | 781 | Y | 每 4 小时更新，已排序 |
| **hujingguang/ChinaIPTV** | `https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV1_ALL.m3u8` | 405 | Y | 央视 + 国内台全量 |
| **hujingguang/ChinaIPTV** | `https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/cnTV_AutoUpdate.m3u8` | 67 | Y | 央视自动更新（轻量） |
| **iptv-org/iptv** | `https://raw.githubusercontent.com/iptv-org/iptv/master/streams/cn.m3u` | 505 | - | 裸流列表，无台标无分组 |
| **iptv-org/iptv** | `https://iptv-org.github.io/iptv/countries/cn.m3u` | 145 | - | 官方分类接口（较精简） |
| **best-fan/iptv-sources** | `https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all.m3u8` | 118 | Y | 每日检测，只留有效源 |
| **best-fan/iptv-sources** | `https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_cctv.m3u8` | 40 | Y | 纯央视 |
| **best-fan/iptv-sources** | `https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_province.m3u8` | 71 | Y | 纯卫视 |

## 三、中国港澳台

| 项目 | 订阅地址 | 频道≈ | 备注 |
|---|---|---|---|
| **hujingguang/ChinaIPTV** | `https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/TaiWan.m3u8` | 20 | 中国台湾 |
| **hujingguang/ChinaIPTV** | `https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/HongKong.m3u8` | 12 | 中国香港 |
| **hujingguang/ChinaIPTV** | `https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/Macao.m3u8` | 1 | 中国澳门 |
| **iptv-org/iptv** | `https://iptv-org.github.io/iptv/countries/tw.m3u` | 26 | 中国台湾 |
| **iptv-org/iptv** | `https://iptv-org.github.io/iptv/countries/hk.m3u` | 18 | 中国香港 |
| **iptv-org/iptv** | `https://iptv-org.github.io/iptv/languages/zho.m3u` | 214 | 全部中文频道 |

## 四、IPv6 / 移动线路 / 其他

| 项目 | 订阅地址 | 频道≈ | 备注 |
|---|---|---|---|
| **suxuang/myIPTV** | `https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv6.m3u` | 862 | IPv6 专用 |
| **suxuang/myIPTV** | `https://raw.githubusercontent.com/suxuang/myIPTV/main/移动IPTV.m3u` | 124 | 移动线路 |
| **suxuang/myIPTV** | `https://raw.githubusercontent.com/suxuang/myIPTV/main/APTV手机专享.m3u` | 120 | 带 catchup 回看 |
| **ngo5/IPTV** | `https://raw.githubusercontent.com/ngo5/IPTV/main/m3u/ipv4.m3u` | 158 | IPv4/IPv6 双栈 |
| **ngo5/IPTV** | `https://raw.githubusercontent.com/ngo5/IPTV/main/m3u/ipv6Plus.m3u` | 168 | IPv6 增强 |
| **YueChan/Live** | `https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u` | 96 | 高清收集 |
| **akiralereal/iptv** | `https://raw.githubusercontent.com/akiralereal/iptv/main/IPTV.m3u` | 28 | 自托管系统的主源 |
| **SPX372928/MyIPTV** | `https://raw.githubusercontent.com/SPX372928/MyIPTV/master/咪咕视频CDN版.txt` | — | 各省移动线路，txt 格式（`频道,url`），需 URL 编码 |

---

## 五、查证结果：3 个项目无法直接当订阅源

| 原始清单写的 | 实际情况 |
|---|---|
| `FGBLH/EHR663433` | 仓库名有误，**实际是 `FGBLH/EHR663`**（442★）。其 `ok海豚常规996`、`Web鱼壳海豚常规997` 是 **JSON 格式**（首行 `{`），订阅解析器吃不了；仅 `安博.txt` 是标准 TXT 格式（含中国台湾频道）可用 |
| `kimcrowing/IPTV` | **该账号已注销/改名**，GitHub 搜不到任何同名仓库，无可用替代 |
| `yuanzl77/IPTV` | 是**纯脚本工具**（`main.py`/`check.py`），仓库内**没有现成 m3u 输出**；GitHub Pages（`yuanzl77.github.io`）也返回 404，必须自己跑脚本才能产出源 |

---

## 六、使用建议

> **2026-09-28 更新**：以下优质源已全部内置到软件「订阅源 → 预置源」弹窗（共 13 条，按 4 类分组展示），
> 无需手工复制地址；勾选「导入并更新」即可。软件已支持**线路自动切换**（直连失败自动依次尝试镜像，
> 见 `scraper_engine._mirror_chain`），`raw.githubusercontent.com` 直连不通时会自动走加速通道。

- **综合聚合**：`iptv-org 中国频道` + `iptv-org 中文频道全集` + `Free-TV` + `Guovin` —— 覆盖面最广。
- **中国大陆专项**：`myIPTV 典藏版` + `CCSH 多平台聚合` + `Collect-IPTV 优选` + `ChinaIPTV 央视卫视全量` + `YanG-1989` + `vbskycn`。
- **中国港澳台**：`ChinaIPTV 中国香港频道`（12）+ `ChinaIPTV 中国台湾频道`（20），比大杂烩干净。
- **每日检测优选**：`best-fan 每日检测`（只保留当日有效源）。
- **IPv6 源慎加**：`suxuang/ipv6`、`ngo5/ipv6*` 需要你的网络支持 IPv6，否则会全部检测失败。
- **TVBox 格式源**（`kakaxi-1`、`Supprise0901` 等）现已支持 `#genre#` 分组，导入后自动按源内分组归类。

---

## 七、liyou12345 收藏页全量检测（2026-09-28 二轮）

> 来源：`https://github.com/liyou12345?tab=stars`（两页共 45 个仓库）
> 方法：`gh api` 列仓库结构 → 定位 m3u/m3u8/txt → 走中转通道真实下载 → 统计 `#EXTINF`

### 7.1 新增可用订阅源（本轮实测 OK，已入选预置源）

| 仓库 | star | 文件 | 频道≈ | 特征 |
|---|---|---|---|---|
| **YanG-1989/m3u** | 11440 | `Gather.m3u` | 123 | 咪咕/游戏/影视轮播，带分组 |
| **vbskycn/iptv** | 8318 | `tv/iptv4.m3u` | 544 | 综合源，带台标 + EPG |
| **doms9/iptv** | 250 | `M3U8/TV.m3u8` | 576 | 带台标 + EPG + 分组 |
| **judy-gotv/iptv** | 743 | `LGTV.m3u` | 769 | 港台向（`4gtv.m3u` 197 亦可用） |
| **reysc/M3U8** | 374 | `all.m3u` | 1476 | 量大，无台标 |
| **skddyj/iptv** | 417 | `IPTV.m3u` | 82 | 精简，带台标 + EPG |
| **zwc456baby/iptv_alive** | 711 | `live.m3u` | 31 | 含 4K 点播源 |
| **wlcyywys/aptv-cn-playlist** | 1 | `aptv-cn.m3u` | 74 | 央视+卫视+港澳台精简版 |
| **Supprise0901/TVBox_live** | 1023 | `live.txt` | 306 | TVBox `#genre#` 格式 |
| **kakaxi-1/IPTV** | 518 | `iptv.txt` | 740 | TVBox `#genre#` 格式，神源收集站 |

### 7.2 工具 / 软件类（非订阅源，仅供能力对标）

| 仓库 | star | 类型 | 与本软件的关系 |
|---|---|---|---|
| `iptv-org/iptv` | 139733 | 源库 | 已作预置源 |
| `Guovin/iptv-api` | 25320 | 采集+测速 | 已作预置源 |
| `iptv-org/awesome-iptv` | 12567 | 资源清单 | 可作选源参考 |
| `laoma2053/awesome-zhuiju-free` | 10507 | 追剧资源指南 | 非直播源 |
| `HerbertHe/iptv-sources` | 8993 | Docker 自部署 | 输出需自建容器，**不能直连** |
| `4gray/iptvnator` | 7218 | Electron 桌面播放器 | 同类桌面壳，可对标 UI |
| `dongyubin/IPTV` | 4455 | Markdown 教程站 | 非源 |
| `zhimin-dev/iptv-checker` | 2034 | Docker 检测工具 | 与本软件检测模块同类 |
| `creazyboyone/FastGithub` | 1522 | GitHub 加速 | 与本软件「加速源」同思路 |

### 7.3 不收录

| 仓库 | 原因 |
|---|---|
| `hayatiptv/iptv` (247★) | 土耳其语为主，与中文场景无关 |
| `atsushi444/iptv` (287★) | 含大量成人内容，不适配 |
| `ChiSheng9/iptv` (177★) | 101 个 64 字节占位文件，无实际内容 |
| `FGBLH/EHR663` (442★) | 主文件是 JSON 格式，订阅解析器吃不了 |
| `kimcrowing/IPTV` | 账号已注销 |
| `yuanzl77/IPTV` (2122★) | 纯脚本，仓库内无现成 m3u 输出 |
