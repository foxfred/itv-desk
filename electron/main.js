// ITV Desk — Electron 主进程
// 职责：启动 FastAPI 后端子进程 → 等就绪 → 双窗口（主窗 + 独立播放窗）+ IPC 经纪人。
// 架构见 ELECTRON_MIGRATION.md：Vue 前端与 FastAPI 后端零改动，只换壳。

const { app, BrowserWindow } = require('electron');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const net = require('net');
const { registerIpcHandlers } = require('./ipc-handlers');

const BACKEND_PORT = Number(process.env.IPTVCORE_PORT) || 8000;
const BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const PYTHON_EXE = process.env.IPTVCORE_PYTHON || 'python';

// 路径自适应：打包版（app.isPackaged）backend/前端 dist 在 process.resourcesPath 下，
// 且数据文件落盘到 resources/（= 程序目录，随文件夹整体移动，与旧版 EXE 同级语义一致）；
// 开发版使用仓库根。
const APP_ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

let mainWindow = null;
let playerWindow = null;
let backendProcess = null;

// 播放窗跨窗状态：待播频道队列（播放窗未就绪时排队，onMounted/轮询 pop_pending 取走）
let pendingPlay = null;
// 上次播放的频道（关闭后重开播放窗时恢复）
let lastChannel = null;

// ==================== FastAPI 后端子进程 ====================

// ==================== 端口预检：8000 被占用 ====================
// 启动新后端前先检测 8000 端口：若已被占用（很可能是上次 TaskStop 强杀留下的孤儿进程），
// 给用户提示并自动清理。绝不批量杀 python.exe（会误杀 8799 代理等其他服务）——只精准按 PID 杀。
async function ensurePortFree(port, timeoutMs = 4000) {
  return new Promise((resolve) => {
    const sock = new net.Socket()
    let done = false
    const finish = (result) => { if (!done) { done = true; sock.destroy(); resolve(result) } }
    sock.setTimeout(timeoutMs)
    sock.on('connect', () => finish({ busy: true }))
    sock.on('timeout', () => finish({ busy: false, reason: 'timeout' }))
    sock.on('error', (e) => {
      // ECONNREFUSED = 端口空闲
      if (e.code === 'ECONNREFUSED') finish({ busy: false, reason: 'refused' })
      else finish({ busy: false, reason: e.code })
    })
    sock.connect(port, '127.0.0.1')
  })
}

async function killOccupyingPort(port) {
  return new Promise((resolve) => {
    const cmd = spawn('netstat', ['-ano'], { stdio: ['ignore', 'pipe', 'ignore'] })
    let out = ''
    cmd.stdout.on('data', (d) => out += d.toString())
    cmd.on('exit', () => {
      const lines = out.split(/\r?\n/)
      const pids = new Set()
      for (const line of lines) {
        // 匹配 0.0.0.0:8000 或 127.0.0.1:8000 LISTENING 状态
        if (line.match(new RegExp(`\\s0\\.0\\.0\\.0:${port}\\s.*LISTENING\\s+(\\d+)`)) ||
            line.match(new RegExp(`\\s127\\.0\\.0\\.1:${port}\\s.*LISTENING\\s+(\\d+)`))) {
          const m = line.match(/LISTENING\s+(\d+)\s*$/)
          if (m) pids.add(parseInt(m[1]))
        }
      }
      if (pids.size === 0) { resolve({ killed: 0, pids: [] }); return }
      // 精准按 PID 杀（绝不用 -IM python.exe，避免误杀 8799 代理）
      const killed = []
      for (const pid of pids) {
        try {
          process.kill(pid, 'SIGTERM')
          killed.push(pid)
        } catch (e) {
          // 权限不足或进程不存在，跳过
        }
      }
      resolve({ killed: killed.length, pids: killed })
    })
  })
}

function startBackend() {
  const backendMain = path.join(APP_ROOT, 'backend', 'main.py');
  // 数据目录 = exe 所在目录（打包版: win-unpacked/ 即 exe 同级；开发版: 仓库根）。
  // 通过环境变量传给后端，后端 main.py 优先读取 ITV_DATA_DIR，
  // 保证所有运行时数据（settings.json/channels.db/channels_cache.json 等）
  // 只落在"exe 所在目录"。exe 拷到哪，数据就生成在哪。
  const DATA_DIR = app.isPackaged ? path.dirname(process.execPath) : APP_ROOT;
  // 前端静态资源目录（打包版: resources/frontend-new/dist；开发版: 仓库 frontend-new/dist）。
  // 与数据目录分开传，避免后端误把前端也定位到 exe 同级目录。
  const FRONTEND_DIR = path.join(APP_ROOT, 'frontend-new', 'dist');
  backendProcess = spawn(PYTHON_EXE, [backendMain], {
    cwd: DATA_DIR,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    env: {
      ...process.env,
      ITV_DATA_DIR: DATA_DIR,
      ITV_FRONTEND_DIR: FRONTEND_DIR,
    },
  });
  const tag = '[backend]';
  backendProcess.stdout.on('data', (d) => process.stdout.write(`${tag} ${d}`));
  backendProcess.stderr.on('data', (d) => process.stderr.write(`${tag} ${d}`));
  backendProcess.on('exit', (code) => {
    console.log(`${tag} exited with code ${code}`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (backendProcess) {
    try { backendProcess.kill(); } catch { /* ignore */ }
    backendProcess = null;
  }
}

// 轮询后端直到就绪（首页 200），超时 60s
function waitBackend(timeoutMs = 60000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const req = http.get(`${BASE_URL}/api/stats`, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) return resolve(true);
        retry();
      });
      req.on('error', retry);
      req.setTimeout(2000, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) return reject(new Error('后端启动超时'));
      setTimeout(tryOnce, 300);
    };
    tryOnce();
  });
}

// ==================== 窗口 ====================

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    frame: true, // 系统标题栏（规避 pywebview frameless 白框/缩放 bug 的根因）
    show: false,
    title: 'ITV Desk',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // 转发 renderer 控制台错误到主进程 stdout（便于沙箱/无 devtools 环境诊断）
  mainWindow.webContents.on('console-message', (_e, level, msg, line, source) => {
    const tag = ['log', 'warn', 'error'][level] || 'log'
    console.log(`[renderer:${tag}] ${msg}${source ? ` (${source}:${line})` : ''}`)
  })
  mainWindow.webContents.on('render-process-gone', (_e, details) => {
    console.error('[renderer] CRASH:', details)
  })
  if (process.env.IPTVCORE_DEVTOOLS) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }
  mainWindow.loadURL(BASE_URL + '/');
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
}

function createPlayerWindow() {
  if (playerWindow && !playerWindow.isDestroyed()) {
    if (playerWindow.isMinimized()) playerWindow.restore();
    playerWindow.show();
    playerWindow.focus();
    return playerWindow;
  }
  // 位置：首次创建时屏幕工作区居中（对齐旧版 run.py _center_and_raise 语义）。
  // 复用已存在窗口（换台）不移动位置——"拖到哪停哪"。
  let x = null, y = null
  if (mainWindow && !mainWindow.isDestroyed()) {
    const { screen } = require('electron')
    const mBounds = mainWindow.getBounds()
    const display = screen.getDisplayMatching(mBounds)
    const wa = display.workArea
    x = Math.round(wa.x + (wa.width - 1100) / 2)
    y = Math.round(wa.y + (wa.height - 680) / 2)
  } else {
    // 无主窗兜底：Electron 默认居中
    x = null; y = null
  }
  playerWindow = new BrowserWindow({
    width: 1100,
    height: 680,
    minWidth: 420,
    minHeight: 260,
    x, y,
    frame: false, // 播放窗无边框：前端自带拖拽条/四角缩放（move_window/resize_window IPC）
    resizable: true,
    backgroundColor: '#000000',
    show: false,
    title: 'IPTV Player',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  console.log(`[player-window] 创建无边框播放窗: 1100x680 @${x},${y}, frame=false`);
  playerWindow.on('ready-to-show', () => {
    playerWindow.show();
    console.log('[player-window] 已显示 (ready-to-show)');
  });
  playerWindow.on('show', () => console.log('[player-window] show event'));
  playerWindow.on('closed', () => { playerWindow = null; });
  playerWindow.webContents.on('did-fail-load', (_e, code, desc, url) => {
    console.error(`[player-window] did-fail-load: code=${code} desc=${desc} url=${url}`);
  });
  playerWindow.webContents.on('did-finish-load', () => {
    console.log('[player-window] did-finish-load 加载完成');
  });
  const targetUrl = `${BASE_URL}/#/player?standalone=1`;
  console.log(`[player-window] loadURL: ${targetUrl}`);
  playerWindow.loadURL(targetUrl);
  // 独立窗根容器黑底兜底：semantic-base.css + element-plus 会让 body 浅色，
  // 此处通过注入 CSS 强制根容器黑底（不影响主窗/管理页）。
  // 同时移除 themes/semantic-base.css 链接（独立窗是黑底播放器，不需要浅色基座）。
  playerWindow.webContents.on('did-finish-load', async () => {
    try {
      await playerWindow.webContents.insertCSS(`
        html, body, #app { background: #000 !important; }
        .player-page, .video-wrap { background: #000 !important; }
        video { background: #000 !important; }
      `);
      await playerWindow.webContents.executeJavaScript(`
        (function(){
          try {
            document.querySelectorAll('link[rel="stylesheet"][href*="themes/semantic-base.css"]').forEach(function(n){ n.parentNode.removeChild(n); });
          } catch(e) {}
        })();
      `);
    } catch (e) {
      console.warn('[player-window] 注入黑底 CSS 失败:', e.message);
    }
  });
  return playerWindow;
}

// ==================== IPC 经纪人 ====================

registerIpcHandlers({
  getMainWindow: () => mainWindow,
  getPlayerWindow: () => playerWindow,
  createPlayerWindow,
  getPending: () => pendingPlay,
  setPending: (v) => { pendingPlay = v; },
  getLastChannel: () => lastChannel,
  setLastChannel: (v) => { lastChannel = v; },
  baseUrl: BASE_URL,
});

// ==================== 应用生命周期 ====================

// 单实例：二次启动聚焦已有主窗
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  // 沙箱/虚拟机/无显卡环境：设 IPTVCORE_NO_GPU=1 禁用 GPU（真机不需要，保持硬解）
  if (process.env.IPTVCORE_NO_GPU) {
    app.commandLine.appendSwitch('disable-gpu');
    app.commandLine.appendSwitch('disable-gpu-compositing');
    app.commandLine.appendSwitch('use-gl', 'swiftshader');
    app.commandLine.appendSwitch('no-sandbox');
  }

  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    // 启动前端口预检：8000 被占用通常是上次 TaskStop 强杀留下的孤儿后端
    // 精准按 PID 杀（绝不用 -IM python.exe，避免误杀 8799 retry-proxy 等其他服务）
    const portCheck = await ensurePortFree(BACKEND_PORT)
    if (portCheck.busy) {
      const kill = await killOccupyingPort(BACKEND_PORT)
      if (kill.killed > 0) {
        console.log(`[main] 8000 端口被占用，已精准清理 ${kill.killed} 个孤儿进程 (PID: ${kill.pids.join(', ')})`)
        // 等端口释放
        await new Promise((r) => setTimeout(r, 800))
      } else {
        const { dialog } = require('electron')
        dialog.showErrorBox('后端端口被占用',
          `端口 ${BACKEND_PORT} 已被其他程序占用，且自动清理失败（PID: ${kill.pids.join(', ') || '未知'}）。\n` +
          `请手动关闭占用该端口的程序后重试。\n\n` +
          `查询命令: netstat -ano | findstr ":${BACKEND_PORT}"`)
        app.quit()
        return
      }
    }
    startBackend();
    try {
      await waitBackend();
    } catch (e) {
      console.error('[main] 后端启动失败:', e.message);
      const { dialog } = require('electron');
      dialog.showErrorBox('后端启动失败', `FastAPI 后端在 ${BACKEND_PORT} 端口启动超时。\n请确认 Python 环境可用：${PYTHON_EXE}`);
      app.quit();
      return;
    }
    createMainWindow();
  });

  app.on('window-all-closed', () => {
    // 主窗+播放窗全关 → 退出（退出时杀后端子进程）
    app.quit();
  });

  app.on('will-quit', () => {
    stopBackend();
  });

  app.on('activate', () => {
    if (mainWindow === null) createMainWindow();
  });
}
