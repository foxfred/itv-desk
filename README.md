# ITV Desk

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
