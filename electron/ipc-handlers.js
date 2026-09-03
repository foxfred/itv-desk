// IPTV Core PRO MAX — IPC 处理器
// 单通道 'native-call'：(method, args[]) → 对应窗口/系统操作。
// 窗口类操作（移动/缩放/置顶/全屏…）作用于「发起调用的窗口」（event.sender），
// 与原 pywebview 双窗口 js_api 语义一致。

const { ipcMain, dialog, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

function registerIpcHandlers(ctx) {
  const {
    getMainWindow, getPlayerWindow, createPlayerWindow,
    getPending, setPending, getLastChannel, setLastChannel,
  } = ctx;

  const senderWindow = (event) => BrowserWindow.fromWebContents(event.sender);

  // pywebview 风格过滤器 'Executable Files (*.exe)|All Files (*.*)' → electron filters
  function parseFilters(filter) {
    if (!filter || typeof filter !== 'string') return undefined;
    return filter.split('|').map((seg) => {
      const m = seg.match(/^(.*?)\s*\((.*)\)$/);
      const name = (m ? m[1] : seg).trim() || 'Files';
      const exts = (m ? m[2] : '*').split(',').map((e) => e.trim().replace(/^\*\.?/, '') || '*');
      return { name, extensions: exts };
    });
  }

  const handlers = {
    // ---------- 频道播放（主窗/任意视图发起） ----------
    play_channel(args) {
      const payload = args[0] || {};
      setLastChannel(payload);
      const pw = getPlayerWindow();
      if (pw && !pw.isDestroyed()) {
        // 播放窗已就绪：直接推送换台（与旧 run.py evaluate_js 行为一致，即时生效）
        pw.focus();
        pw.webContents.executeJavaScript(
          `window.__iptvPlay && window.__iptvPlay(${JSON.stringify(payload)})`
        ).catch(() => {
          // 页面尚未挂载完成 → 排队，播放窗轮询 pop_pending 兜底
          setPending(payload);
        });
      } else {
        setPending(payload);
        createPlayerWindow();
      }
      return 'OK';
    },

    open_player() {
      const pw = getPlayerWindow();
      if (pw && !pw.isDestroyed()) {
        if (pw.isMinimized()) pw.restore();
        pw.show();
        pw.focus();
      } else {
        // 恢复上次频道（若有）
        const last = getLastChannel();
        if (last && last.url) setPending(last);
        createPlayerWindow();
      }
      return 'OK';
    },

    close_player() {
      const pw = getPlayerWindow();
      if (pw && !pw.isDestroyed()) pw.destroy();
      return 'OK';
    },

    // ---------- 播放窗轮询 ----------
    pop_pending() {
      const p = getPending();
      setPending(null);
      return p; // null 或 {url, name, group, id, ...}
    },

    // ---------- 播放窗状态上报主窗 ----------
    notify_main(args) {
      const mw = getMainWindow();
      const payloadJson = String(args[0] || '{}');
      if (mw && !mw.isDestroyed()) {
        mw.webContents.executeJavaScript(
          `window.__updatePlaying && window.__updatePlaying(${payloadJson})`
        ).catch(() => {});
      }
      return 'OK';
    },

    // ---------- 文件对话框 ----------
    async save_text(args, event) {
      const [name, content] = args;
      const win = senderWindow(event);
      const opts = { defaultPath: name || 'export.txt' };
      const r = await (win ? dialog.showSaveDialog(win, opts) : dialog.showSaveDialog(opts));
      if (r.canceled || !r.filePath) return null;
      try {
        fs.writeFileSync(r.filePath, String(content ?? ''), 'utf8');
        return r.filePath;
      } catch (e) {
        return `ERROR: ${e.message}`;
      }
    },

    async save_file_from(args, event) {
      const [srcPath, defaultName] = args;
      const win = senderWindow(event);
      const opts = { defaultPath: defaultName || path.basename(srcPath || 'file') };
      const r = await (win ? dialog.showSaveDialog(win, opts) : dialog.showSaveDialog(opts));
      if (r.canceled || !r.filePath) return null;
      try {
        fs.copyFileSync(srcPath, r.filePath);
        return r.filePath;
      } catch (e) {
        return `ERROR: ${e.message}`;
      }
    },

    async select_file(args, event) {
      const [title, filter] = args;
      const win = senderWindow(event);
      const opts = { title: title || '选择文件', properties: ['openFile'] };
      const filters = parseFilters(filter);
      if (filters) opts.filters = filters;
      const r = await (win ? dialog.showOpenDialog(win, opts) : dialog.showOpenDialog(opts));
      if (r.canceled || !r.filePaths || !r.filePaths.length) return null;
      return r.filePaths[0];
    },

    // ---------- 外部播放器 ----------
    play_external(args) {
      const [url, playerPath] = args;
      if (!playerPath) return false;
      try {
        const child = spawn(playerPath, [url], { detached: true, stdio: 'ignore' });
        child.unref();
        return true;
      } catch {
        return false;
      }
    },

    // ---------- 窗口操作（作用于发起调用的窗口 = 播放窗） ----------
    set_topmost(args, event) {
      const win = senderWindow(event);
      if (win) win.setAlwaysOnTop(!!args[0]);
      return 'OK';
    },

    toggle_fullscreen(_args, event) {
      const win = senderWindow(event);
      if (win) win.setFullScreen(!win.isFullScreen());
      return true; // 前端据返回值判断已用原生全屏
    },

    minimize(_args, event) {
      const win = senderWindow(event);
      if (win) win.minimize();
      return 'OK';
    },

    move_window(args, event) {
      const win = senderWindow(event);
      if (!win) return 'OK';
      const [dx, dy] = args;
      const [x, y] = win.getPosition();
      win.setPosition(x + (dx || 0), y + (dy || 0));
      return 'OK';
    },

    resize_window(args, event) {
      const win = senderWindow(event);
      if (!win) return 'OK';
      const [w, h, corner] = args;
      const b = win.getBounds();
      const nb = { x: b.x, y: b.y, width: Math.max(320, w | 0), height: Math.max(200, h | 0) };
      // corner: 0=tl 1=tr 2=br 3=bl（前端约定）——左角拖拽需反向补偿窗口原点
      if (corner === 0 || corner === 3) nb.x = b.x + (b.width - nb.width);
      if (corner === 0 || corner === 1) nb.y = b.y + (b.height - nb.height);
      win.setBounds(nb);
      return 'OK';
    },

    hide_window(_args, event) {
      const win = senderWindow(event);
      if (win) win.hide();
      return 'OK';
    },

    show_window(_args, event) {
      const win = senderWindow(event);
      if (win) { win.show(); win.focus(); }
      return 'OK';
    },

    restore_main_window() {
      const mw = getMainWindow();
      if (mw && !mw.isDestroyed() && mw.isMinimized()) mw.restore();
      return 'OK';
    },
  };

  ipcMain.handle('native-call', (event, method, args) => {
    const fn = handlers[method];
    if (!fn) {
      console.warn(`[ipc] 未知方法: ${method}`);
      return undefined;
    }
    try {
      return fn(args || [], event);
    } catch (e) {
      console.error(`[ipc] ${method} 执行失败:`, e);
      return `ERROR: ${e.message}`;
    }
  });
}

module.exports = { registerIpcHandlers };
