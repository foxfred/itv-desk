// IPTV Core PRO MAX — Electron preload
// 关键设计：暴露 window.pywebview.api 兼容垫片，方法签名与原 pywebview js_api 完全一致。
// → 前端（useNative.js / PlayerView 等）零改动即可在 Electron 下运行。
// 所有调用经 ipcRenderer.invoke 转发主进程，返回 Promise（与 pywebview 行为一致）。

const { contextBridge, ipcRenderer } = require('electron');

// 与原 run.py 的 Api / PlayerApi 方法一一对应（前端全部调用点）
const METHODS = [
  // 主窗（Api）
  'play_channel',      // 双击频道 → 转发播放窗
  'open_player',       // 打开/恢复播放窗
  'close_player',      // 关闭播放窗
  'save_text',         // 保存文本文件（原生保存对话框）
  'save_file_from',    // 复制文件到用户选择的位置
  'select_file',       // 原生打开文件对话框
  'play_external',     // 外部播放器打开
  'toggle_fullscreen', // 全屏切换（播放窗）
  // 播放窗（PlayerApi）
  'pop_pending',       // 取待播频道（轮询换台）
  'notify_main',       // 播放状态上报主窗（window.__updatePlaying）
  'set_topmost',       // 置顶
  'is_topmost',        // 查询是否置顶
  'minimize',          // 最小化播放窗
  // 自绘顶栏窗口控制（主窗 TitleBar.vue）
  'maximize_window',   // 最大化/还原切换
  'is_maximized',      // 查询是否最大化
  'close_window',      // 关闭窗口
  'move_window',       // 无边框拖拽移动
  'resize_window',     // 无边框四角缩放
  'hide_window',       // 画中画时隐藏播放窗
  'show_window',       // 退出画中画恢复播放窗
  'restore_main_window', // 恢复主窗（不抢前台）
];

const api = {};
for (const m of METHODS) {
  api[m] = (...args) => ipcRenderer.invoke('native-call', m, args);
}

// 兼容垫片：前端检测 window.pywebview?.api / api[method] 均成立
contextBridge.exposeInMainWorld('pywebview', { api });
