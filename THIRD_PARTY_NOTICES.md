# Third-Party Notices for iTV Desk

iTV Desk 自研部分使用 **MIT** 许可（见 `LICENSE`）。

本软件集成了以下第三方开源组件。此处列出其项目名称、用途、许可证与来源，以符合各自许可证的署名与再分发要求。

全部第三方依赖均为宽松许可证（MIT / BSD / Apache-2.0），或 GPL（mpv），允许随本软件再分发。

## 后端 / 桌面壳（Python）

| 组件 | 用途 | License | 来源 |
|---|---|---|---|
| pywebview | 桌面壳 / 网络视图 | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| FastAPI | Web 框架 | MIT | https://github.com/fastapi/fastapi |
| Uvicorn | ASGI 服务器 | BSD-3-Clause | https://www.uvicorn.org |
| SQLAlchemy | ORM | MIT | https://www.sqlalchemy.org |
| aiosqlite | 异步 SQLite | MIT | https://github.com/omnilib/aiosqlite |
| beautifulsoup4 | HTML/XML 解析 | MIT | https://www.crummy.com/software/BeautifulSoup/ |
| lxml | XML/XPath 加速 | BSD-3-Clause | https://lxml.de/ |
| aiohttp | 异步 HTTP | Apache-2.0 AND MIT | https://docs.aiohttp.org |
| requests | HTTP 客户端 | Apache-2.0 | https://requests.readthedocs.io |
| PySocks | SOCKS 代理 | BSD | https://github.com/Anorov/PySocks |
| python-multipart | multipart 解析 | (MIT 系) | https://github.com/Kludex/python-multipart |

## 前端（npm）

| 组件 | 用途 | License | 来源 |
|---|---|---|---|
| Vue 3 | 前端框架 | MIT | https://github.com/vuejs/core |
| Vue Router | 前端路由 | MIT | https://github.com/vuejs/router |
| Pinia | 状态管理 | MIT | https://github.com/vuejs/pinia |
| Element Plus | UI 组件库 | MIT | https://github.com/element-plus/element-plus |
| Axios | HTTP 客户端 | MIT | https://github.com/axios/axios |
| hls.js | HLS 播放内核 | Apache-2.0 | https://github.com/video-dev/hls.js |
| flv.js | HTTP-FLV 播放内核 | Apache-2.0 | https://github.com/bilibili/flv.js |
| dashjs | DASH 播放内核 | BSD-3-Clause | https://github.com/Dash-Industry-Forum/dash.js |
| Vite | 前端构建 | MIT | https://github.com/vitejs/vite |

## 二进制（打包分发时随包含）

### ⚠️ mpv — GNU GPL v2+
- **用途**：可选的本地原生视频解码引擎（默认关闭）。
- **来源**：https://github.com/mpv-player/mpv （Windows 构建由 shinchiro 提供：https://github.com/shinchiro/mpv-winbuild-cmake）
- **许可证**：**GPL-2.0-or-later**（mpv 支持 GPLv2+/LGPLv2.1+ 双许可；shinchiro 的完整构建为 GPL）。
- **合规**：依据 GPL 要求，通过 Releases 分发的包内随附 `COPYING`（GPL v2 许可证全文）。mpv 源码：[https://github.com/mpv-player/mpv](https://github.com/mpv-player/mpv)。本软件对 mpv 仅作外部进程调用，未修改其源码。

## 声明确认

- 除上述第三方依赖外，iTV Desk 的其余代码为原创（AI 辅助开发）。
- 本软件不包含任何第三方频道列表 / 播放源数据。
- 若你对许可证或归属有任何疑问，请在本仓库的 Issues 提出。

_本文件由 iTV Desk 维护。_