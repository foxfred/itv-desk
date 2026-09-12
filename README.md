# ITV Desk

> **人机共创软件声明** — 本软件从需求定义、架构设计、代码实现、Bug 修复到测试验证，全程由人类与 AI Agent 协作完成：人类负责提出需求、决策技术方向、验收结果；AI 负责编写代码、调试排错、构建打包与文档维护。仓库的每一次提交都是这种协作模式的产物。这不是一份"人写的软件加了 AI 辅助"，而是一份"人与 AI 共同孕育的软件"。

桌面端 IPTV 直播源整理工具。抓取网页/订阅源 → 解析去重 → 在线检测 → 自动分组 → 导出或播放。

## 版本切换说明（v3.0.0 重构版）

**v3.0.0 是架构重构版本**，与 v2.x 系列不连续兼容：

| | v2.x（旧仓库） | v3.0.0（本仓库） |
|---|---|---|
| 桌面壳 | PyWebView 5.x | **Electron** |
| 换壳原因 | PyWebView WinForms 后端 frameless 窗口存在缩放混乱/白框 bug（根源在 pywebview 自身，不可修） | Electron 双窗口稳定，兼容垫片让前端零改动 |
| 进程模型 | Python 单进程内嵌 WebView | Electron Main → spawn Python 后端子进程（FastAPI, 端口 8000）→ 双 BrowserWindow（主窗 + 独立播放窗） |
| 打包 | PyInstaller --onedir | electron-builder（NSIS + portable + folder 版） |

- 后端 FastAPI + 前端 Vue3/Element Plus 代码自 v2.0.19 完整延续，**所有功能保留**（含应用自更新：内嵌更新器，「系统设置 → 更新」自动检测升级）。
- `electron/preload.js` 提供 `window.pywebview.api` 兼容垫片（17 个桥接方法），前端业务代码一行未改即完成迁移。
- 版本号规则（semver）：大更新升 Major，新功能升 Minor，修补升 Patch。v3.0.0 之后的更新将延续 3.x 序列。

## 功能

- **频道管理** — 网页抓取、M3U 订阅、批量导入、M3U 解析
- **健康检测** — 在线/离线/延迟/分辨率/协议栈/真实可看性
- **自动分组** — 智能分类 + 规则改名 + 自定义分组规则
- **EPG 节目单** — 多源聚合，自动匹配电视节目指南
- **乱码修复** — 中文编码自动修复
- **播放器** — Electron 独立窗口，HLS/FLV/RTMP 中继，H.265 转码，ESC 快捷退出，倍速/画中画/置顶
- **订阅源** — 定时自动更新，支持母链目录
- **网段扫描** — 反推 IP 段模板，批量探测发现源
- **多主题** — 17 套内置皮肤（含 WinXP/Win7/Win10/Win11/macOS 复古与现代系列）+ 自定义皮肤导入
- **数据备份** — zip 导出/导入 + AES 加密备份与恢复
- **应用自更新** — 内嵌更新器，自动检测更新（v3.0.0 起保留）

## 快速开始

```bash
# 1. 安装后端依赖（需要 Python 3.12，含 backend/requirements.txt 依赖）
cd backend && pip install -r requirements.txt && cd ..

# 2. 安装前端依赖并构建
cd frontend-new && npm install && npm run build && cd ..

# 3. 安装 Electron 依赖
npm install

# 4. 启动桌面应用（可用 IPTVCORE_PYTHON 指定 Python 解释器）
npm start
```

浏览器访问 `http://127.0.0.1:8000` 也可使用 Web 版。

打包发布：`npm run dist`（安装包）或 `npm run dist:folder`（解压即用的文件夹版），产物在 `dist_electron/`。

## CI/CD（GitHub Actions）

本仓库内置两套流水线（`.github/workflows/`）：

| 工作流 | 触发 | 作用 |
|---|---|---|
| `ci.yml` | push / PR 到 `master` | 前端 vite build + 后端语法/导入校验 + pytest 冒烟 + Electron 自检，拦截低级错误 |
| `release.yml` | 打 tag `v*`（或手动） | 前端构建 + 后端校验 → Windows runner 上 electron-builder 打 NSIS/便携版 → 自动创建 GitHub Release 并上传安装包 |

### 发版流程（一步到位）

```bash
# 1. 改完代码推到 master
git push origin master

# 2. 打 tag（版本号与 backend/app/version.py 的 APP_VERSION 保持一致）
git tag v3.0.2
git push origin v3.0.2
```

之后：
- 在 GitHub 仓库 → **Releases** 页面等 10-15 分钟，会自动出现 `v3.0.2`，挂着 `ITV Desk Setup 3.0.2.exe`（NSIS 安装包）和 `itv-desk-3.0.2-Portable.exe`（便携版）
- 仓库内 `release/update.json` 由发版前提交时写好（`packages[].url` 指向上述 GitHub Release 资产），用户端「系统设置 → 更新」即可检测到新版并下载

### 自更新地址

- 默认更新清单：`https://raw.githubusercontent.com/foxfred/itv-desk/master/release/update.json`
- 包下载地址在 `update.json` 的 `packages[].url` 字段，**正式发版后指向 GitHub Release 资产**（`https://github.com/foxfred/itv-desk/releases/download/v3.0.2/...`）
- 用户可在「系统设置 → 更新」里覆盖为自定义清单/下载地址

## 技术栈

- **桌面壳**: Electron（双 BrowserWindow + IPC 兼容垫片）
- **后端**: FastAPI + SQLite + SQLAlchemy
- **前端**: Vue 3 + Element Plus + Vite + Pinia
- **播放器**: hls.js + flv.js + dashjs（Chromium 原生 HTML5），RTMP 经后端 HTTP-FLV 中继，H.265 经 ffmpeg 转码

## 版本历史

- **v3.0.2** (2026-09-12): **接入 GitHub Actions CI/CD**——新增 `ci.yml`（lint+test 自动校验）与 `release.yml`（打 tag 自动发布到 GitHub Release）；自更新地址正式指向 GitHub Release 资产；新增 `backend/tests/test_smoke.py`（9 用例）与 `electron/tests/self-check.js`；`README` 补充发版与自更新说明
- **v3.0.1** (2026-09-08): 主窗改自绘顶栏（去系统标题栏/英文菜单，图标+ITV Desk+虚线+中文菜单+窗口按钮，背景跟随皮肤）；播放器停止/静音图标修正
- **v3.0.0** (2026-09-03): **Electron 重构版**——桌面壳由 PyWebView 迁移至 Electron（根治 frameless 白框/缩放 bug）；双窗口架构（主窗管理 + 独立播放窗）；pywebview 兼容垫片实现前端零改动迁移；播放器新增 ESC 退出、倍速鼠标选择修复；数据备份/恢复 UI 重做（导入/导出实心按钮 + 加密导入导出）；17 套内置皮肤参数与现代控件对齐
- **v2.0.19** (2026-09-01): 播放器黑方块根因修复（前端 dist 候选顺序 RES_DIR 优先）
- **v2.0.9** (2026-09-01): 控件圆形样式迁入入口 CSS，绕过 WebView2 懒加载缓存
- **v2.0.0** (2026-08-24): 正式更名 ITV Desk
- （v1.x / v2.x 完整历史见旧仓库提交记录）

## License

个人开源，随意使用。
