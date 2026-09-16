
const { app, BrowserWindow } = require('electron');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');
const net = require('net');
const { registerIpcHandlers } = require('./ipc-handlers');

const BACKEND_PORT = Number(process.env.IPTVCORE_PORT) || 8000;
const BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const PYTHON_EXE = process.env.IPTVCORE_PYTHON || 'python';

const APP_ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

let mainWindow = null;
let playerWindow = null;
let backendProcess = null;

let pendingPlay = null;
let lastChannel = null;


async function ensurePortFree(port, timeoutMs = 4000) {
  return new Promise((resolve) => {
    const sock = new net.Socket()
    let done = false
    const finish = (result) => { if (!done) { done = true; sock.destroy(); resolve(result) } }
    sock.setTimeout(timeoutMs)
    sock.on('connect', () => finish({ busy: true }))
    sock.on('timeout', () => finish({ busy: false, reason: 'timeout' }))
    sock.on('error', (e) => {
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
                if (line.match(new RegExp(`\\s0\\.0\\.0\\.0:${port}\\s.*LISTENING\\s+(\\d+)`)) ||
            line.match(new RegExp(`\\s127\\.0\\.0\\.1:${port}\\s.*LISTENING\\s+(\\d+)`))) {
          const m = line.match(/LISTENING\s+(\d+)\s*$/)
          if (m) pids.add(parseInt(m[1]))
        }
      }
      if (pids.size === 0) { resolve({ killed: 0, pids: [] }); return }
            const killed = []
      for (const pid of pids) {
        try {
          process.kill(pid, 'SIGTERM')
          killed.push(pid)
        } catch (e) {
                  }
      }
      resolve({ killed: killed.length, pids: killed })
    })
  })
}

function startBackend() {
  const backendMain = path.join(APP_ROOT, 'backend', 'main.py');
          const DATA_DIR = app.isPackaged ? path.dirname(process.execPath) : APP_ROOT;
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


function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    frame: false, 
    show: false,
    title: 'ITV Desk',
    backgroundColor: '#ffffff',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.setMenu(null); 
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
      let x = null, y = null
  if (mainWindow && !mainWindow.isDestroyed()) {
    const { screen } = require('electron')
    const mBounds = mainWindow.getBounds()
    const display = screen.getDisplayMatching(mBounds)
    const wa = display.workArea
    x = Math.round(wa.x + (wa.width - 1100) / 2)
    y = Math.round(wa.y + (wa.height - 680) / 2)
  } else {
        x = null; y = null
  }
  playerWindow = new BrowserWindow({
    width: 1100,
    height: 680,
    minWidth: 420,
    minHeight: 260,
    x, y,
    frame: false, 
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


const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
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
            const portCheck = await ensurePortFree(BACKEND_PORT)
    if (portCheck.busy) {
      const kill = await killOccupyingPort(BACKEND_PORT)
      if (kill.killed > 0) {
        console.log(`[main] 8000 端口被占用，已精准清理 ${kill.killed} 个孤儿进程 (PID: ${kill.pids.join(', ')})`)
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
        app.quit();
  });

  app.on('will-quit', () => {
    stopBackend();
  });

  app.on('activate', () => {
    if (mainWindow === null) createMainWindow();
  });
}
