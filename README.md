# ITV Desk

> **人机共创软件声明** — 本软件从需求定义、架构设计、代码实现、Bug 修复到测试验证，全程由人类与 AI Agent 协作完成：人类负责提出需求、决策技术方向、验收结果；AI 负责编写代码、调试排错、构建打包与文档维护。仓库的每一次提交都是这种协作模式的产物。这不是一份"人写的软件加了 AI 辅助"，而是一份"人与 AI 共同孕育的软件"。

桌面端 IPTV 直播源整理工具：抓取 / 订阅 / 在线检测 / 自动分组 / EPG / 频道名校正 / 导出，内置双窗口播放器。

## 功能

- **频道管理**：网页抓取、M3U 订阅、批量导入、网段扫描（一个源一行，同名不同源独立成行）
- **健康检测**：在线状态、延迟、分辨率、真实可看性探测、播放截图验证
- **频道名自动校正**：本地 OCR 读画面台标 → 别名库 + EPG 反查 → 生成改名建议表，人工确认后应用，可一键撤销。默认**只给建议、不乱改**，非台标位置的文字（平台水印、栏目角标）一律不采纳
- **频道别名库**：内置 110 组（央视全系 / 省级卫视 / 港澳台），可在设置页增删与导入
- **统计报告**：按天记录在线率、死源数、广告台数、延迟与清晰度分布
- **自动分组 / 规则改名 / EPG 节目单 / 乱码母链修复**
- **局域网订阅网关**：手机、电视、播放器可直接订阅本机频道源
- **播放器**：HLS / FLV / RTMP，倍速、画中画、置顶、EPG 信息条
- **17 套主题皮肤，数据备份（支持加密），软件内自动更新**

## 下载

前往 [Releases](https://github.com/foxfred/itv-desk/releases) 下载：

- **安装版** `ITV-Desk-Setup-x.y.z.exe`（推荐）
- **便携版** `ITV-Desk-x.y.z.exe`（免安装）
- **文件夹版** `ITV-Desk-x.y.z-folder.zip`（解压即用）

已安装旧版时，可在软件内「设置 → 更新」直接检测升级。

> 本应用的形态是 **Electron 壳 + 系统 Python 跑后端源码**，安装包不含 Python 与后端依赖。
> 因此升级后若新增了后端依赖，需要手动补一句（见下方「开发」）。
> 没装也不影响其它功能，只是名称校正会提示「OCR 引擎不可用」。

## 开发

```bash
# 后端依赖（Python 3.12）
cd backend && pip install -r requirements.txt && cd ..

# 前端构建
cd frontend-new && npm install && npm run build && cd ..

# Electron 依赖
npm install

# 启动
npm start
```

> 频道名自动校正依赖本地 OCR（`rapidocr-onnxruntime` + `onnxruntime`，约 60~75MB），
> 已写进 `backend/requirements.txt`，跑一次 `pip install -r backend/requirements.txt` 即可。

打包：`npm run dist`（安装包）/ `npm run dist:folder`（文件夹版）。

发版：改 `backend/app/version.py` 与 `package.json` 的版本号 → 提交推送 → 打 tag `v*` 推送，GitHub Actions 会自动构建并发布到 Releases，并回填 `release/update.json` 的校验值。版本号规则见 `backend/app/version.py`。

## 技术栈

Electron + FastAPI + SQLite + Vue 3 + Element Plus

## License

开源软件，随意使用。
