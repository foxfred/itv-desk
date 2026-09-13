# ITV Desk

> **人机共创软件声明** — 本软件从需求定义、架构设计、代码实现、Bug 修复到测试验证，全程由人类与 AI Agent 协作完成：人类负责提出需求、决策技术方向、验收结果；AI 负责编写代码、调试排错、构建打包与文档维护。仓库的每一次提交都是这种协作模式的产物。这不是一份"人写的软件加了 AI 辅助"，而是一份"人与 AI 共同孕育的软件"。

桌面端 IPTV 直播源整理工具：抓取 / 订阅 / 在线检测 / 自动分组 / EPG / 导出，内置双窗口播放器。

## 功能

- 频道管理：网页抓取、M3U 订阅、批量导入
- 健康检测：在线状态、延迟、分辨率、可看性
- 自动分组、规则改名、EPG 节目单、乱码修复
- 播放器：HLS / FLV / RTMP，倍速、画中画、置顶
- 17 套主题皮肤，数据备份（支持加密）
- 软件内自动更新

## 下载

前往 [Releases](https://github.com/foxfred/itv-desk/releases) 下载：

- **安装版** `ITV-Desk-Setup-x.y.z.exe`（推荐）
- **便携版** `ITV-Desk-x.y.z.exe`（免安装）
- **文件夹版** `ITV-Desk-x.y.z-folder.zip`（解压即用）

已安装旧版时，可在软件内「设置 → 更新」直接检测升级。

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

打包：`npm run dist`（安装包）/ `npm run dist:folder`（文件夹版）。

发版：打 tag `v*` 推送后，GitHub Actions 自动构建并发布到 Releases。

## 技术栈

Electron + FastAPI + SQLite + Vue 3 + Element Plus

## License

开源软件，随意使用。
