# iTV Desk

桌面端 IPTV 直播源整理工具（PyWebView + FastAPI + Vue3）。

抓取 / 订阅源 / 在线检测 / 自动分组 / EPG 校正 / 乱码修补 / 导出 / **双窗口播放器**（hls.js / flv.js 内置内核 + VLC / PotPlayer / mpv 外部播放可选）。

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
  - **H.265 / HEVC 源自动转码**：Chrome / Edge 的 MSE 不支持 H.265 软解。遇到 H.265 的 HLS 源时，程序自动经后端 ffmpeg 实时重编码为 H.264 + AAC 的 HTTP-FLV 流（flv.js 播放），无需手动切换引擎。转码依赖本机 `ffmpeg`（需在系统 PATH，或通过环境变量 `IPTV_FFMPEG` 指定路径）。
  - **外部播放器（可选）**：支持调用 VLC / PotPlayer / mpv 作为外部播放器打开当前源（在「系统设置 → 播放器」选择，需本机已安装）。

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
| VLC / PotPlayer / mpv | 外部播放器（可选，不集成） | 各自许可证 | 由用户本机安装 |

> **外部播放器说明：** 自 v1.0.17 起，mpv 不再作为内置解码引擎，降级为与 VLC / PotPlayer 同级的**可选外部播放器**。程序**不再集成**任何 GPL 组件，打包分发包体积更小、许可证更干净（仅含 MIT / BSD / Apache-2.0 依赖）。如需用 mpv 播放，请在本机自行安装，程序仅负责调用。
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

### v1.0.17（2026-08-23）

| 类别 | 说明 |
|---|---|
| **移除 mpv 内置引擎** | mpv 不再作为内置解码引擎，彻底清除前端 mpv 相关逻辑（引擎切换/状态轮询/首帧超时/窗口跟随）与后端 mpv 探测代码；播放引擎固定为 Web（hls.js / flv.js），更稳定兼容 |
| **mpv 降级为外部播放器** | 与 VLC / PotPlayer 并列，在「系统设置 → 播放器」中作为可选项；需本机自行安装，程序仅负责调用（不再集成 GPL 组件） |
| **播放器 UI 修复** | 停止按钮图标改为实心方块（原误用禁止 X 图标）；控制栏背景加深（0.85→0.92），按钮图标在深色背景下清晰可见；播放窗口白色边框根除（`WS_POPUP` 彻底去客户区边缘） |
| **设置面板精简** | 删除「播放引擎」radio（固定 Web）、删除「MPV 独立窗」「MPV 容器跟随」选项、隐藏「更新清单地址」栏、清除更新面板内所有说明文字 |
| **H.265 转码兜底增强** | 探测机制升级：主清单无 codec 时进一步抓取首个 TS 分片检测 HEVC NAL 起始码；HLS.js `MEDIA_ERROR`（parse/frag/alloc）时自动回退后端 ffmpeg 转码路径，大量 H.265 源不再因 MSE 拒绝而黑屏 |

### v1.0.12（2026-08-22）

| 修复 | 说明 |
|---|---|
| 播放窗口 WebView2 缓存根除 | 播放窗口 URL 追加 UUID 防缓存（此前仅主窗口有，播放窗口漏了），彻底解决更新后仍显示旧前端的问题 |

### v1.0.11（2026-08-22）

| 修复 | 说明 |
|---|---|
| 缩放宽度公式修复 | 左下角拖拽宽度计算修正（`corner % 2 === 0` 区分左右角） |
| 音量图标修复（v2） | 改用稳定内联 SVG，兼容 WebView2 渲染 |
| 音量滑块拖动修复（v2） | 新增鼠标级 `mousedown + document.mousemove` 拖拽处理器，WebView2 下拖动正常响应 |
| 控制栏按钮完整 | 播放/暂停、停止、最大化/还原、最小化、迷你模式按钮全部就位 |

### v1.0.10（2026-08-22）

| 修复 | 说明 |
|---|---|
| 低延迟音画同步 | flv.js 启用小量 stash 缓冲（64KB），消除 `enableStashBuffer: false` 导致的音画不同步 |
| 音量图标修复 | 替换自定义 SVG 为 Element Plus 标准 Volume/Mute 图标，不再显示为麦克风 |
| 音量滑块拖动 | 新增 `@change` 事件，确保拖动滑块和点击均触发音量变化 |
| 播放控制完善 | 右侧控制栏新增播放/暂停、停止播放按钮；新增窗口最大化/还原、最小化按钮 |
| 四角缩放修复 | `.player-container` 加 `position: relative`，缩放手柄四角小圆点常显（半透明），悬停变亮，尺寸加大到 18×18 |

### v1.0.9（2026-08-22）

| 修复 | 说明 |
|---|---|
| 播放窗口四角拖拽缩放 | 无外框模式下新增四角缩放手柄（悬停显示），支持从任意角拖拽调整窗口大小 |
| 音量滑块恢复正常 | 修复顶部拖拽条 mousemove 事件抢占导致音量滑块失效的问题 |
| 迷你模式 | 播放控制栏新增「迷你模式」按钮，一键切换 320×200 小窗，再次点击恢复 1100×680 |

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