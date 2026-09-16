// IPTV Core PRO MAX — Electron preload

const { contextBridge, ipcRenderer } = require('electron');

const METHODS = [
    'play_channel',      
  'open_player',       
  'close_player',      
  'save_text',         
  'save_file_from',    
  'select_file',       
  'play_external',     
  'toggle_fullscreen', 
    'pop_pending',       
  'notify_main',       
  'set_topmost',       
  'is_topmost',        
  'minimize',          
    'maximize_window',   
  'is_maximized',      
  'close_window',      
  'move_window',       
  'resize_window',     
  'hide_window',       
  'show_window',       
  'restore_main_window', 
  'install_update',    
  'apply_folder_update', 
];

const api = {};
for (const m of METHODS) {
  api[m] = (...args) => ipcRenderer.invoke('native-call', m, args);
}

contextBridge.exposeInMainWorld('pywebview', { api });
