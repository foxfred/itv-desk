# IPTV Core PRO MAX —— 交付总览（Phase 0 → 3.6）

## 交付状态
全部既定项目目标已完成并逐项验证。从 P0 正确性缺陷修复开始，按顺序完成 Phase 0/1/2 与
Phase 3.1–3.6 全部新功能，最终通过后端集成校验 + 前端生产构建。

## 本轮（收尾）完成的内容
- **Phase 2（性能/健壮性）**：`realtime.py` SSE 事件总线 + `/api/logs/stream`、`/api/events/stream`；
  连通性探测；`LOGO_DB` 外置到 `backend/app/data/logos.json`。
- **Phase 3.1**：`services/channel_store.py`（SQLite 镜像 `channels.db`，分页/搜索/分组）。
- **Phase 3.2 断点续检**：`check_service.start_check(resume=)` + `channel_service.count_unchecked()/get_unchecked()`；
  `routes/check.py` 的 `CheckReq.resume`。
- **Phase 3.3 订阅源**：`subscription_service.py`（CRUD + 去重 + 定时调度）+ `routes/subscriptions.py` + `subscriptions.json`。
- **Phase 3.4 搜索/分组树**：后端 `/search` `/groups` `/stats`；前端 `ChannelView.vue` 分组树 + 全文搜索；
  `api/channels.js` 新增 `getGroups`/`searchChannels`。
- **Phase 3.5 EPG**：`epg_service.py` 增 `save_cache/load_cache/save_source/load_source/match_channel/start_refresh_scheduler`；
  `routes/epg.py` 增 `/set-source` `/refresh`；`epg_cache.json`/`epg_source.json`。
- **Phase 3.6 DLNA 投屏**：`dlna_service.py`（SSDP 发现 + UPnP AVTransport play/stop，命名空间无关 XML 解析）
  + `routes/dlna.py`。
- **文档**：更新 `AGENTS.md`（§3/§4/§7/§8/§9 交付状态 + GUI 手动验证清单）、
  `IPTV_Core_代码分析报告.md`（§9 实施交付状态，映射原第 6/7/8 节建议落地）。
- **可复用 Skill**：新建用户级技能 `fastapi-sandbox-verify`（桩依赖 harness 验证 FastAPI 应用导入/路由注册，
  无需安装 fastapi/pydantic/sqlalchemy，含模板脚本）。

## 本轮（2026-08-18 收尾）完成的内容：增强批次 #51–#59 + 紧急修复

> 用户选定一批增强点子「先搞一下」，跨频道 EPG 搜索经核查已存在故划掉；"云同步"重定义为"本地加密备份/恢复"（零服务器）。拆成 #51–#59，分两个子批次实现并统一重打包。

- **#51 健康度评分 + 死源标记**：`channel_service` 增 `health` 结构（`score`/`dead`=连续失败≥3），频道 dict 加 `health` 字段随缓存持久化；`checker_engine` 检测回写；`ChannelView` 状态格显示健康度色点/死源红标/「隐藏死源」开关。
- **#52 真实可看性探测**：`checker_engine` 旧逻辑 HEAD 200 即判在线会放过假源，改为实际 GET 拉媒体数据校验（`_probe_watchable`/`_looks_like_media`/`_probe_hls`），回写 `first_frame_ms`；假源(200 但 HTML 错误页)正确判离线。
- **#53 播放器内 EPG 信息条**：`PlayerView` 叠加 EPG 条（节目名/进度/剩余/接下来），每秒刷新+每60s重拉；`api/epg.js` 加 `getEpgMatch`。
- **#54 画中画 PiP**：`PlayerView` 加 `togglePiP`（不支持浏览器自动隐藏按钮）。
- **#55 每频道多源故障转移**：`sources` 字段（零 schema 变更）、`ChannelUpdate.sources` 可写多源；播放器 `switchSource`/`maybeFailover` 自动切备用源；`checker_engine` 逐源聚合 `source_health`。
- **#56 智能去重合并**：`channel_service` 加 `_norm_url_key`/`_norm_name_key`/`_merge_by_key`/`merge_duplicates`（先 URL 归并再名称归并、聚合 sources）；`POST /api/channels/merge-duplicates` + `ChannelView`「更多 ▸ 智能去重合并」。
- **#57 Logo 自动匹配**：`channel_service.match_logos`（扫 `DATA_DIR/logos` 按频道名匹配写 `logo`）；`POST /api/channels/match-logos`；`main.py` `/logos` 静态挂载；`ChannelView` 缩略图。
- **#58 应用自更新（零服务器）**：新增 `routes/app.py`（`APP_VERSION="7.0.1"` + `/version`/`/check-update`/`/download-update`，读 `settings.update_url` 清单比对版本、下载到 `update_staging/`）；`SettingsView`「更新」tab + `ChannelView` 关于版本动态化。
- **#59 本地加密备份/恢复（AES，零服务器）**：`routes/backup.py` 用 `cryptography` Fernet + PBKDF2 导出 `.enc`、导入凭口令解密（错口令 `InvalidToken` 被拒）；`SettingsView`「数据」tab 加密导出/恢复；`build.py` 加 `cryptography` hidden-import。
- **紧急修复（Phase 4.2）**：`routes/app.py` 漏 import `Depends` 导致 `main.py` 加载全部路由 `NameError`、EXE/`run.py` 无法启动；补 `from fastapi import ... Depends` 并重打包。`dist/IPTVCore_Folder/IPTVCore/IPTVCore.exe` 已含修复、用户数据已恢复。
- **分组重构批次 #60（Phase 4.3）**：统一分组算法 `Parser.get_channel_group`（命中即止优先级链：自定义规则 → 港澳台(含 HK/TW/MO 边界正则防 NHK/BTW 误判) → CCTV → 外国频道统一(纯外文/命中 FOREIGN_KEYWORDS 收口为「外国频道」) → 地方卫视(卫视+省市地方并入) → 电影剧场/体育竞技/少儿动漫/新闻资讯/财经商业/音乐戏曲/纪录片/购物/轮播专区 → 其他），`config.py` 新增 `auto_group`/`foreign_group_name`/`custom_group_rules`；`channel_service.add_channels` 导入时按算法重分、`reclassify_all()` 整池重分；新增 `POST /api/channels/reclassify`；`epg_service.update_groups` 复用同算法保证外国频道一致；前端「更多 ▸ 重新自动分组」+「设置 ▸ 分组」tab（auto_group 开关/外国组名/自定义规则/立即重分）。
- **同批次小 bug 修复**：① 加密导出点击无反应——`SettingsView.vue` 漏 `import { ElMessageBox }`（`exportEncrypted()` 调 `ElMessageBox.prompt` 抛 `TypeError` 静默失败），已补；② 音量按钮仍是麦克风图标——`PlayerView.vue` 将 `<Mute/>` 改为内联 SVG 喇叭（未静音=喇叭+声波，静音=喇叭+X）。
- **ISEP 能力借鉴批次 Phase 4.4（2026-08-18，紧随 #60）**：① 网段扫描——左侧边栏新增「扫描网段」入口（`ScanView.vue`），从频道池 IP 源一键反推 C 段模板（`POST /api/scan/derive`，后端 `scan_service.derive_templates`）或手动输入模板（`x.x.x.{1-254}`/`x.x.x.0/24`/`x.x.x.1-254` 等），复用 `network.http_probe_channel` 经 `ThreadPoolExecutor` 并发探测（并发 `scan_max_workers`/超时 `scan_timeout` 从 `settings` 读，不 hardcode），**可扫公网 IP**，在线结果经 `add_channels` 单一权威缓存一键导入（`POST /api/scan/import`）；后端 `services/scan_service.py`+`routes/scan.py`（`/api/scan/derive`/`/scan`/`/scan/import`）。② 乱码修补分类显示+解析增强——`RepairView.vue` 改左右双栏（左母链/右频道，对应 ISEP 截图）；`repair_service._classify_url` 母链/频道自动分类 + 一层递归抓取（GitHub `/blob/`→raw，`_fetch_parent`，过滤仍属母链项防爆炸）；`parse_raw_text` 支持 `#genre#` TXT 分组头 / 中文论坛 `name→url` 箭头 / `name,url$备注`；`config.group_override_by_url` 按 URL 精确覆盖分组（轻量，不照搬 ISEP 五张散落 JSON 覆盖表）。
- **文档**：本次同步更新 `AGENTS.md`（§3/§4/§6/§7/§9 全量补 #51–#59 + `/logos`/`app` 路由 + GUI 清单 9–22 + Phase 4.3 #60 + Phase 4.4）、`IPTV_Core_评估报告_20260817.md`（§2.1 侧边栏增至 7 项、§5 结论第 7 点、新增 §6.5 Phase 4.4）、本交付总览。

## 最终验证结果（沙箱，无 PyWebView 图形界面）
- 后端 49 个 `.py` 模块全部 `py_compile` 通过（含新增 `scan_service.py`/`routes/scan.py`）。
- `app.main` 在桩依赖（fastapi/pydantic/sqlalchemy/uvicorn/webview）下导入成功：**18 个路由模块全部注册**
  （含新增 `app`/`stream_proxy`/`rtmp_proxy`/`scan`），`channel_service` 实例化正常，
  `DlnaService.discover()` 无设备时不崩溃。
- 前端 `vite build` 通过（1691 模块，仅 chunk 体积告警，不影响功能）。
- 分组分类冒烟测试 **33 用例全绿**（覆盖 CCTV/卫视/省市/各内容类/港澳台/NHK-BTW 边界/纯外文外国/带国名外国/自定义规则覆盖等），其中 NHK 边界正则修复后原先误判「港澳台」的用例改判正确。
- 网段扫描模板解析 `_parse_template` **5 用例全绿**；母链/频道分类 `_classify_url` + `parse_raw_text` 解析增强（`#genre#`/`name→url` 箭头/`$备注`）**6 用例全绿**。
- 冻结确认：`dist/IPTVCore_Folder/IPTVCore/_internal` 内 `routes/scan.py`/`scan_service.py`/`main.py`(scan 路由)、`repair_service.py`(含 `_classify_url`/`parent_links`/`#genre#`/`group_override_by_url`) 均存在，前端 `ScanView`/`RepairView` chunk 已生成 → Phase 4.4 已冻结进包。

## 仍需用户在桌面环境点验（GUI 手动验证清单，见 AGENTS.md §9）
1. `python run.py` 主窗口加载；2. 抓取/导入 M3U 入池、统计正确；3. 检查 + 断点续检；
4. 分组树过滤 + 全文搜索；5. EPG 设置源/匹配/定时刷新；6. 订阅源增量更新去重；
7. DLNA 设备发现 + 投屏播放/停止；8. 播放历史/收藏持久化（`channels.db`）。
9. 健康度/死源色点 +「隐藏死源」；10. 假源判离线(non_media)；11. 播放器内 EPG 条；12. 画中画；
13. 多源故障转移自动切源；14. 智能去重合并；15. Logo 自动匹配+缩略图；
16. 应用自更新（填清单→检查→下载暂存）；17. 加密备份导出/恢复（错口令被拒）。
18. 分组重构：「更多 ▸ 重新自动分组」后散乱外国频道收口为单一「外国频道」组、省市地方并入地方卫视、分组树呈现 11 类+港澳台+外国频道；
19. 设置 ▸ 分组：auto_group 开关 / foreign_group_name / 自定义规则增删 /「立即重新分组」生效并刷新；
20. 加密导出弹窗正常（ElMessageBox 修复）、播放器音量按钮为喇叭图标（SVG 修复）。
21. 网段扫描：侧边栏「扫描网段」→ 选频道池 IP 源「反推网段模板」或手动输入模板 → 扫描相邻网段（公网也可）→ 在线结果勾选「导入」进频道池（并发/超时随设置生效）。
22. 乱码修补左右双栏：左栏母链表（名称/URL/状态/频道数，可保存母链）、右栏频道表（频道名/分组/状态/延迟，可「频道→导入」/「频道→保存」）；`#genre#`/`name→url`/`$备注` 解析、母链递归抓取、按 URL 精确覆盖分组生效。

## 交付产物
- 完整可运行工程（backend + frontend-new/dist + 运行期数据文件均在仓库根，DATA_DIR = 仓库根）。
- 当前可启动 EXE：`dist/IPTVCore_Folder/IPTVCore/IPTVCore.exe`（已含 #51–#59 + 紧急修复 + #60 分组重构 + 两个小 bug 修复 + Phase 4.4 网段扫描与乱码修补分类双栏，用户数据已恢复）。
- 更新后的 `AGENTS.md`、`IPTV_Core_评估报告_20260817.md`、`delivery_overview.md`。
- 安装的新技能 `fastapi-sandbox-verify`（用户级，跨项目可用）。
