
const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn } = require('child_process');
const net = require('net');
const { registerIpcHandlers } = require('./ipc-handlers');

const BACKEND_PORT = Number(process.env.IPTVCORE_PORT) || 8000;
const BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`;

const APP_ROOT = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');

// 解析 Python 解释器：随包内置运行时优先（用户无需自行安装 Python），
// 其次环境变量显式指定（开发/调试），最后才退回系统 PATH。
function resolvePython() {
  if (process.env.IPTVCORE_PYTHON) {
    return { exe: process.env.IPTVCORE_PYTHON, source: 'env' };
  }
  const win = process.platform === 'win32';
  const candidates = win
    ? [path.join(APP_ROOT, 'python', 'python.exe'),
       path.join(APP_ROOT, 'python-runtime', 'python.exe')]
    : [path.join(APP_ROOT, 'python', 'bin', 'python3'),
       path.join(APP_ROOT, 'python-runtime', 'bin', 'python3')];
  for (const p of candidates) {
    try { if (fs.existsSync(p)) return { exe: p, source: 'bundled' }; } catch { /* ignore */ }
  }
  return { exe: win ? 'python' : 'python3', source: 'system' };
}

const PYTHON = resolvePython();
const PYTHON_EXE = PYTHON.exe;

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

const STDERR_TAIL_LINES = 40;
let backendStderrTail = [];
let backendSpawnError = null;

function pushStderrTail(text) {
  for (const line of String(text).split(/\r?\n/)) {
    if (!line.trim()) continue;
    backendStderrTail.push(line);
  }
  if (backendStderrTail.length > STDERR_TAIL_LINES) {
    backendStderrTail = backendStderrTail.slice(-STDERR_TAIL_LINES);
  }
}

function startBackend() {
  const backendMain = path.join(APP_ROOT, 'backend', 'main.py');
  const DATA_DIR = app.isPackaged ? path.dirname(process.execPath) : APP_ROOT;
  const FRONTEND_DIR = path.join(APP_ROOT, 'frontend-new', 'dist');
  backendSpawnError = null;
  backendStderrTail = [];
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
  // 关键：监听 error，否则解释器不存在（ENOENT）时会被静默吞掉，
  // 最终只表现为「启动超时」，掩盖真实原因。
  backendProcess.on('error', (err) => {
    backendSpawnError = err;
    console.error(`${tag} 进程启动失败: ${err.code || ''} ${err.message}`);
  });
  backendProcess.stdout.on('data', (d) => process.stdout.write(`${tag} ${d}`));
  backendProcess.stderr.on('data', (d) => {
    process.stderr.write(`${tag} ${d}`);
    pushStderrTail(d.toString());
  });
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


const REQUIRED_IMPORTS = 'fastapi, uvicorn, sqlalchemy, aiosqlite, bs4, lxml, aiohttp, requests';

let lastPreflight = null;

// 启动前预检：区分「找不到解释器」「缺依赖」「其他异常」，避免笼统地报「启动超时」。
// 用异步 spawn 而非 spawnSync —— spawnSync 在 Windows 上可能抛 EBUSY。
// 预检只用于改善错误提示，不阻断启动（除非明确找不到解释器）。
function preflightPython() {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (r) => { if (!settled) { settled = true; resolve(r); } };
    let child;
    try {
      child = spawn(PYTHON_EXE, ['-c', `import ${REQUIRED_IMPORTS}`], {
        windowsHide: true,
        stdio: ['ignore', 'ignore', 'pipe'],
      });
    } catch (e) {
      finish({ ok: false, kind: 'spawn-error', detail: e.message });
      return;
    }
    let stderr = '';
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    child.on('error', (e) => {
      if (e.code === 'ENOENT') {
        finish({ ok: false, kind: 'no-python', detail: `找不到可执行文件：${PYTHON_EXE}` });
      } else {
        finish({ ok: false, kind: 'spawn-error', detail: `${e.code || ''} ${e.message}`.trim() });
      }
    });
    child.on('close', (code) => {
      if (code === 0) return finish({ ok: true });
      const tail = stderr.trim().split(/\r?\n/).filter(Boolean).slice(-4).join('\n');
      finish({ ok: false, kind: 'missing-deps', detail: tail || `退出码 ${code}` });
    });
    setTimeout(() => {
      try { child.kill(); } catch { /* ignore */ }
      finish({ ok: false, kind: 'spawn-error', detail: '预检超时' });
    }, 25000);
  });
}

function pythonSourceLabel() {
  if (PYTHON.source === 'bundled') return '随包内置运行时';
  if (PYTHON.source === 'env') return '环境变量 IPTVCORE_PYTHON 指定';
  return '系统 PATH 中的 Python';
}

function showPreflightError(pre) {
  const head = pre.kind === 'no-python'
    ? '未找到可用的 Python 解释器，后端服务无法启动。'
    : pre.kind === 'missing-deps'
      ? 'Python 解释器可用，但缺少后端所需的依赖库。'
      : '启动 Python 解释器时发生错误。';
  const hint = PYTHON.source === 'bundled'
    ? '安装包内置的运行时可能已损坏，建议重新下载安装本软件。'
    : '开发/调试环境下请安装 Python 3.12 并执行 pip install -r backend/requirements.txt，'
      + '或用环境变量 IPTVCORE_PYTHON 指定解释器路径。';
  const body = [
    head,
    '',
    `解释器：${PYTHON_EXE}`,
    `来源：${pythonSourceLabel()}`,
    '',
    '详情：',
    pre.detail || '(无)',
    '',
    hint,
  ].join('\n');
  console.error('[main] 预检失败:', head, pre.detail);
  dialog.showErrorBox('后端启动失败', body);
}

function showTimeoutError(err) {
  const tail = backendStderrTail.slice(-20).join('\n');
  const body = [
    `后端服务在 ${BACKEND_PORT} 端口启动超时。`,
    '',
    `解释器：${PYTHON_EXE}`,
    `来源：${pythonSourceLabel()}`,
  ];
  if (backendSpawnError) {
    body.push(`进程错误：${backendSpawnError.code || ''} ${backendSpawnError.message}`);
  }
  if (lastPreflight && !lastPreflight.ok) {
    body.push(`预检结果：${lastPreflight.kind} — ${lastPreflight.detail}`);
  }
  body.push('', '后端输出（末尾 20 行）：', tail || '(无输出)');
  console.error('[main] 后端启动超时:', err.message);
  dialog.showErrorBox('后端启动失败', body.join('\n'));
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
    const pre = await preflightPython();
    lastPreflight = pre;
    // 只有「明确找不到解释器」才阻断启动；其余预检异常（如环境导致的 spawn 失败）
    // 不阻断，交给 waitBackend 判定，避免预检自身的问题挡掉正常流程。
    if (!pre.ok && pre.kind === 'no-python') {
      showPreflightError(pre);
      app.quit();
      return;
    }
    startBackend();
    try {
      await waitBackend();
    } catch (e) {
      console.error('[main] 后端启动失败:', e.message);
      showTimeoutError(e);
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
