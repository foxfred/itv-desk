# iTV Desk

桌面端 IPTV 直播源整理工具（PyWebView + FastAPI + Vue3）。

抓取 / 订阅源 / 在线检测 / 自动分组 / EPG 校正 / 乱码修补 / 导出 / **双窗口播放器**（hls.js / flv.js / mpv 可选）。

---

## ⚠️ 重要声明（AI 开发 + 合规）

- 本软件由 **AI 辅助开发**：基于用户需求，经多轮人机对话迭代生成，绝大多数源码为原创实现。
- 项目在播放器引擎选择上**参考了开源播放器 IPTVnator 的设计思路**（Web 内核按流协议自动选解码器），但**未复制其源码**，相关实现均为独立编写。
- 本仓库仅用于查看源码；**通过 Releases 分发的二进制（EXE/zip）仅供个人学习测试使用**。
- 本项目**不提供、也不包含任何频道列表 / 播放源**，也不包含破解、侵权内容。使用的直播源由使用者自行导入。

---

## 功能特性

- **抓取**：网页抓取 / 订阅源自动更新 / 通道池管理
- **检测**：在线可用性、延迟、分辨率、质量、协议栈（含 H.264 SPS 解析）
- **整理**：去重合并、重新分组、规则改名、TAG 打标、乱码修补
- **节目**：EPG 节目单、调度器自动刷新、节目搜索
- **导出**：M3U / 播放列表 / 加密备份导出
- **播放（双窗口）**：
  - 主窗口 = 频道库 / 管理（列表即唯一选源入口）
  - 独立播放窗口 = 可拖 / 缩 / 置顶；Web 内核（hls.js / flv.js）即点即播
  - 可选 mpv 独立窗原生解码（默认关闭）
  - **H.265 / HEVC 源自动转码**：Chrome / Edge 的 MSE 不支持 H.265 软解。遇到 H.265 的 HLS 源时，程序自动经后端 ffmpeg 实时重编码为 H.264 + AAC 的 HTTP-FLV 流（flv.js 播放），无需手动切换引擎。转码依赖本机 `ffmpeg`（需在系统 PATH，或通过环境变量 `IPTV_FFMPEG` 指定路径）。

---

## 技术栈与第三方依赖（版权声明）

| 组件 | 用途 | License | 来源 |
|---|---|---|---|
| Vue 3 | 前端框架 | MIT | https://github.com/vuejs/core |
| Element Plus | UI 组件库 | MIT | https://github.com/element-plus/element-plus |
| Vue Router / Pinia / Axios | 前端配套 | MIT | vuejs.org / pinia / axios |
| hls.js | HLS 播放内核 | Apache-2.0 | https://github.com/video-dev/hls.js |
| flv.js | HTTP-FLV 播放内核 | Apache-2.0 | https://github.com/bilibili/flv.js |
| dashjs | DASH 播放内核 | BSD-3-Clause | https://github.com/Dash-Industry-Forum/dash.js |
| FastAPI / Uvicorn | 后端框架 | MIT | https://github.com/fastapi/fastapi |
| SQLAlchemy | ORM | MIT | https://www.sqlalchemy.org |
| pywebview | 桌面壳 | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| **mpv** | **可选原生解码** | **GPL-v2+** | https://github.com/mpv-player/mpv |

> **⚠️ mpv GPL 版权说明：**
> iTV Desk 打包版集成 `mpv`（由 shinchiro 提供的 Windows 构建，**GPL-2.0+ 许可证**）。
> 依据 GPL 要求，Releases 分发包内已附带 `COPYING`（GPL v2 许可证全文）。
> mpv 源码：https://github.com/mpv-player/mpv
> 若你不希望使用 GPL 组件，可从本仓库源码自行构建（不集成 mpv 的包）。
>
> 其它第三方依赖均为宽松许可证（MIT / BSD / Apache-2.0），详见 `THIRD_PARTY_NOTICES.md`。

---

## 开发 / 运行

```bash
# 后端依赖
pip install -r backend/requirements.txt

# 前端
cd frontend-new && npm install

# 开发运行（启动 FastAPI 后端 + PyWebView 主窗口）
python run.py
```

## 打包

```bash
python build.py          # PyInstaller --onedir → dist/IPTVCore_Folder/
python publish.py        # (可选) 生成 release/zip + update.json + 发布 GitHub Release
```

---

## 更新机制

iTV Desk 通过 **GitHub Releases** 分发更新：
1. 程序内「设置 → 更新」读取本仓库 `release/update.json`（版本清单）。
2. 比对版本号，有新版本则从对应 Release 下载更新包（zip）。
3. 重启后由更新器完成替换；更新器**只替换程序文件，绝不改动你的数据**（`channels.db` / `settings.json` / 台标 / 分组等均保留）。

## 更新日志

### v1.0.8（2026-08-22）

| 修复 | 说明 |
|---|---|
| 播放器无外框显示 | 播放窗口去掉顶部标题栏，改为无外框无边框样式；顶部新增细窄拖拽条（悬停显示），拖动可移动整个窗口 |

### v1.0.7（2026-08-22）

| 修复 | 说明 |
|---|---|
| 假直播标记与标签列解耦 | 频道列表「标记」列优先检查 `is_fake_live` 字段（含播放器界面标记的假直播），不再漏显示 |
| 死源检测不再误杀 H.265 源 | 健康度系统新增 `decode_fail` / `decode_unsupported` 字段；H.265 等格式问题导致的转码失败不再计入连续失败，不会误标死源 |
| H.265 转码黑屏有声音修复 | H.264 转码代理增加 `scale+format=yuv420p` 像素格式归一化，兼容 yuv420p10/444 等 H.265 格式，消除视频流损坏导致的黑屏 |

### v1.0.6（2026-08-22）
- 彻底修复 WebView2 页面级缓存导致前端无法更新的问题（主窗口 URL 追加 UUID）

---

## License（自研部分）

MIT，详见 [LICENSE](https://github.com/foxfred/itv-desk/blob/master/LICENSE)。

> mpv 组件为 GPL-v2+，其许可证独立于本项目 MIT 声明，见上方说明与 `THIRD_PARTY_NOTICES.md`。