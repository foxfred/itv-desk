
const { ipcMain, dialog, BrowserWindow, app } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
const APPLY_PS1 = [
  "$ErrorActionPreference = 'Continue'",
  "$base = $PSScriptRoot",
  "$log = Join-Path $env:TEMP 'itvdesk_update.log'",
  "$ready = if ($args.Count -ge 1) { [string]$args[0] } else { 'ready.txt' }",
  "try { Set-Content -LiteralPath (Join-Path $base $ready) -Value 'ready' -Encoding ASCII -ErrorAction SilentlyContinue } catch { }",
  "function Log([string]$m) {",
  "  $line = '[' + (Get-Date).ToString('s') + '] ' + $m",
  "  try { Add-Content -LiteralPath $log -Value $line -Encoding UTF8 } catch { }",
  "  try { Add-Content -LiteralPath (Join-Path $base 'apply_trace.txt') -Value $line -Encoding UTF8 } catch { }",
  "}",
  "function Dec([string]$s) { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($s)) }",
  "Log '=== update start (powershell) ==='",
  "try {",
  "  $plan = Get-Content -LiteralPath (Join-Path $base 'plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json",
  "  $zip = Dec $plan.zip_b64",
  "  $target = Dec $plan.target_b64",
  "  $exe = Dec $plan.exe_b64",
  "  $appPid = [int]$plan.app_pid",
  "} catch { Log ('FATAL parse plan: ' + $_.Exception.Message); exit 1 }",
  "Log ('ver=' + $plan.version)",
  "Log ('zip=' + $zip)",
  "Log ('target=' + $target)",
  "$procName = [IO.Path]::GetFileNameWithoutExtension($exe)",
  "for ($i = 0; $i -lt 240; $i++) {",
  "  $byPid = Get-Process -Id $appPid -ErrorAction SilentlyContinue",
  "  $byName = Get-Process -Name $procName -ErrorAction SilentlyContinue",
  "  if ((-not $byPid) -and (-not $byName)) { break }",
  "  Start-Sleep -Milliseconds 500",
  "}",
  "Start-Sleep -Seconds 2",
  "Log 'old processes gone, extracting'",
  "$ok = $false",
  "$tar = Join-Path $env:SystemRoot 'System32\\tar.exe'",
  "for ($i = 0; $i -lt 20; $i++) {",
  "  if (Test-Path $tar) {",
  "    & $tar -xf $zip -C $target 2>$null",
  "    if ($LASTEXITCODE -eq 0) { $ok = $true; Log ('extracted by tar try ' + $i); break }",
  "    Log ('tar rc=' + $LASTEXITCODE + ' try ' + $i)",
  "  }",
  "  try {",
  "    Expand-Archive -LiteralPath $zip -DestinationPath $target -Force -ErrorAction Stop",
  "    $ok = $true",
  "    Log ('extracted by Expand-Archive try ' + $i)",
  "    break",
  "  } catch {",
  "    Log ('expand retry ' + $i + ': ' + $_.Exception.Message)",
  "    Start-Sleep -Seconds 2",
  "  }",
  "}",
  "if ($ok) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue; Log 'zip removed' } else { Log 'EXTRACT FAILED (kept old version)' }",
  "Copy-Item -LiteralPath $log -Destination (Join-Path $target 'update_apply.log') -Force -ErrorAction SilentlyContinue",
  "Start-Sleep -Milliseconds 500",
  "try { Start-Process -FilePath $exe -WorkingDirectory $target; Log 'relaunched' } catch { Log ('relaunch failed: ' + $_.Exception.Message) }",
  "# step out of my own work dir first (Windows cannot delete a dir in use as CWD)",
  "try { Set-Location -LiteralPath $env:TEMP -ErrorAction SilentlyContinue } catch { }",
  "Start-Sleep -Seconds 3",
  "Remove-Item -LiteralPath $base -Recurse -Force -ErrorAction SilentlyContinue",
  "",
].join("\r\n");

const APPLY_PY = [
  "import base64, ctypes, json, os, shutil, subprocess, sys, time, zipfile",
  "base = os.path.dirname(os.path.abspath(__file__))",
  "log = os.path.join(os.environ.get('TEMP', base), 'itvdesk_update.log')",
  "trace = os.path.join(base, 'apply_trace.txt')",
  "ready = sys.argv[1] if len(sys.argv) > 1 else 'ready.txt'",
  "",
  "def L(m):",
  "    line = '[%s] %s' % (time.strftime('%Y-%m-%dT%H:%M:%S'), m)",
  "    for p in (log, trace):",
  "        try:",
  "            f = open(p, 'a', encoding='utf-8')",
  "            f.write(line + chr(10))",
  "            f.close()",
  "        except Exception:",
  "            pass",
  "",
  "try:",
  "    open(os.path.join(base, ready), 'w', encoding='ascii').write('ready')",
  "except Exception:",
  "    pass",
  "",
  "L('=== update start (python fallback) ===')",
  "",
  "def dec(s):",
  "    return base64.b64decode(s).decode('utf-8')",
  "",
  "try:",
  "    plan = json.load(open(os.path.join(base, 'plan.json'), encoding='utf-8'))",
  "    zp = dec(plan['zip_b64'])",
  "    target = dec(plan['target_b64'])",
  "    exe = dec(plan['exe_b64'])",
  "    app_pid = int(plan['app_pid'])",
  "except Exception as e:",
  "    L('FATAL parse plan: %r' % e)",
  "    sys.exit(1)",
  "",
  "L('zip=%s' % zp)",
  "L('target=%s' % target)",
  "",
  "k32 = ctypes.windll.kernel32",
  "",
  "def alive(pid):",
  "    h = k32.OpenProcess(0x1000, False, pid)",
  "    if not h:",
  "        return False",
  "    code = ctypes.c_ulong()",
  "    k32.GetExitCodeProcess(h, ctypes.byref(code))",
  "    k32.CloseHandle(h)",
  "    return code.value == 259",
  "",
  "for _ in range(240):",
  "    if not alive(app_pid):",
  "        break",
  "    time.sleep(0.5)",
  "time.sleep(2)",
  "L('old process gone, extracting')",
  "",
  "ok = False",
  "for i in range(20):",
  "    try:",
  "        z = zipfile.ZipFile(zp)",
  "        z.extractall(target)",
  "        z.close()",
  "        ok = True",
  "        L('extracted try %d' % i)",
  "        break",
  "    except Exception as e:",
  "        L('extract retry %d: %r' % (i, e))",
  "        time.sleep(2)",
  "",
  "if ok:",
  "    try:",
  "        os.remove(zp)",
  "        L('zip removed')",
  "    except Exception as e:",
  "        L('remove zip failed: %r' % e)",
  "else:",
  "    L('EXTRACT FAILED (kept old version)')",
  "",
  "try:",
  "    shutil.copyfile(log, os.path.join(target, 'update_apply.log'))",
  "except Exception:",
  "    pass",
  "",
  "try:",
  "    subprocess.Popen([exe], cwd=target, close_fds=True)",
  "    L('relaunched')",
  "except Exception as e:",
  "    L('relaunch failed: %r' % e)",
  "",
  "try:",
  "    os.chdir(os.environ.get('TEMP', base))",
  "except Exception:",
  "    pass",
  "time.sleep(3)",
  "shutil.rmtree(base, ignore_errors=True)",
  "",
].join("\n");

const LAUNCH_CMD = [
  "@echo off",
  "start \"\" /min %*",
  "exit /b 0",
  "",
].join("\r\n");

function powershellExe() {
  const root = process.env.SystemRoot || 'C:\\Windows';
  const abs = path.join(root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
  return fs.existsSync(abs) ? abs : 'powershell.exe';
}

function pythonExe() {
    return process.env.IPTVCORE_PYTHON || 'python';
}

function sha256File(p) {
  const h = crypto.createHash('sha256');
  h.update(fs.readFileSync(p));
  return h.digest('hex');
}

function registerIpcHandlers(ctx) {
  const {
    getMainWindow, getPlayerWindow, createPlayerWindow,
    getPending, setPending, getLastChannel, setLastChannel,
  } = ctx;

  const senderWindow = (event) => BrowserWindow.fromWebContents(event.sender);

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
        play_channel(args) {
      const payload = args[0] || {};
      setLastChannel(payload);
      const pw = getPlayerWindow();
      if (pw && !pw.isDestroyed()) {
                pw.focus();
        pw.webContents.executeJavaScript(
          `window.__iptvPlay && window.__iptvPlay(${JSON.stringify(payload)})`
        ).catch(() => {
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

        pop_pending() {
      const p = getPending();
      setPending(null);
      return p; 
    },

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

        set_topmost(args, event) {
      const win = senderWindow(event);
      if (win) win.setAlwaysOnTop(!!args[0]);
      return 'OK';
    },

    is_topmost(_args, event) {
      const win = senderWindow(event);
      return !!(win && win.isAlwaysOnTop());
    },

    toggle_fullscreen(_args, event) {
      const win = senderWindow(event);
      if (win) win.setFullScreen(!win.isFullScreen());
      return true; 
    },

    minimize(_args, event) {
      const win = senderWindow(event);
      if (win) win.minimize();
      return 'OK';
    },

            maximize_window(_args, event) {
      const win = senderWindow(event);
      if (!win) return false;
      if (win.isMaximized()) { win.unmaximize(); return false; }
      win.maximize(); return true;
    },

    is_maximized(_args, event) {
      const win = senderWindow(event);
      return !!(win && win.isMaximized());
    },

        close_window(_args, event) {
      const win = senderWindow(event);
      if (win) win.close();
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

                    install_update(args) {
      const [exePath] = args;
      if (!exePath || !fs.existsSync(exePath)) return 'ERROR: 更新包不存在: ' + exePath;
      try {
                const cmdExe = process.env.ComSpec || 'cmd.exe';
        const child = spawn(cmdExe, ['/d', '/c', 'start', 'ITV Desk Update', exePath], {
          detached: true,
          stdio: 'ignore',
          cwd: path.dirname(exePath),
          windowsHide: true,
        });
        child.on('error', () => {  });
        child.unref();
      } catch (e) {
        return 'ERROR: ' + e.message;
      }
      setTimeout(() => {
        try { app.quit(); } catch { /* ignore */ }
      }, 500);
      return 'OK';
    },

        // args: [zipPath, expectedSha256, expectedSize, version]
                //
                            async apply_folder_update(args) {
      const [zipPath, expectedSha256, expectedSize, version] = args || [];
      if (!zipPath || !fs.existsSync(zipPath)) return 'ERROR: 更新包不存在: ' + zipPath;
      if (!/\.zip$/i.test(String(zipPath))) return 'ERROR: 不是文件夹版更新包: ' + zipPath;
      if (!app.isPackaged) return 'ERROR: 开发模式下不执行覆盖更新（请用 npm start 运行，或手动更新）';

            try {
        const st = fs.statSync(zipPath);
        if (expectedSize && Number(expectedSize) > 0 && st.size !== Number(expectedSize)) {
          return `ERROR: 更新包不完整（${st.size} / ${expectedSize} 字节），已中止更新，请重新下载`;
        }
        if (expectedSha256 && sha256File(zipPath) !== String(expectedSha256).trim().toLowerCase()) {
          return 'ERROR: 更新包校验失败（文件损坏），已中止更新，请重新下载';
        }
      } catch (e) {
        return 'ERROR: 校验更新包失败: ' + e.message;
      }

      const exePath = process.execPath;              // H:\...\ITV Desk.exe
      const targetDir = path.dirname(exePath);       
      const workDir = path.join(os.tmpdir(), `itvdesk_update_${process.pid}_${Date.now()}`);
      const b64 = (p) => Buffer.from(String(p), 'utf8').toString('base64');
      const ps1Path = path.join(workDir, 'apply.ps1');
      const pyPath = path.join(workDir, 'apply_upd.py');
      const launcher = path.join(workDir, 'launch.cmd');
      const READY_PS = 'ready_ps.txt';
      const READY_PY = 'ready_py.txt';
      try {
        fs.mkdirSync(workDir, { recursive: true });
        fs.writeFileSync(path.join(workDir, 'plan.json'), JSON.stringify({
          zip_b64: b64(zipPath),
          target_b64: b64(targetDir),
          exe_b64: b64(exePath),
          app_pid: process.pid,
          version: String(version || ''),
        }, null, 2), 'ascii');
        fs.writeFileSync(ps1Path, APPLY_PS1, 'ascii');
        fs.writeFileSync(pyPath, APPLY_PY, 'ascii');
        fs.writeFileSync(launcher, LAUNCH_CMD, 'ascii');
      } catch (e) {
        return 'ERROR: 写入更新脚本失败: ' + e.message;
      }

            const cmdExe = process.env.ComSpec || 'cmd.exe';
      const launchAndWait = (label, readyName, program, programArgs) => new Promise((resolve) => {
        let spawnErr = null;
        try {
          const child = spawn(cmdExe, ['/d', '/c', launcher, program, ...programArgs], {
            detached: true, stdio: 'ignore', cwd: os.tmpdir(), windowsHide: true,
          });
          child.on('error', (e) => { spawnErr = e; });
          child.unref();
        } catch (e) {
          spawnErr = e;
        }
        const t0 = Date.now();
        const tick = () => {
          if (fs.existsSync(path.join(workDir, readyName))) {
            console.log(`[update] ${label} 已启动（握手成功）`);
            return resolve(true);
          }
          if (spawnErr) {
            console.warn(`[update] ${label} 启动失败: ${spawnErr.message}`);
            return resolve(false);
          }
          if (Date.now() - t0 > 9000) {
            console.warn(`[update] ${label} 9 秒内未握手，判定为启动失败`);
            return resolve(false);
          }
          setTimeout(tick, 250);
        };
        tick();
      });

      let started = await launchAndWait('powershell', READY_PS, powershellExe(),
        ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', ps1Path, READY_PS]);
      if (!started) {
                started = await launchAndWait('python', READY_PY, pythonExe(), ['-u', pyPath, READY_PY]);
      }
      if (!started) {
        return 'ERROR: 更新脚本未能启动（可能是安全软件拦截了脚本执行），程序已保持运行、未做任何改动。\n'
          + '请改用「手动更新」：把下载好的压缩包解压覆盖到程序目录。\n'
          + `诊断目录：${workDir}`;
      }

      console.log(`[update] 文件夹版覆盖更新已就绪: ${zipPath} -> ${targetDir}`);
      setTimeout(() => {
        try { app.quit(); } catch { /* ignore */ }
      }, 400);
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
