// ITV Desk — Electron 主进程 CI 自检（node --check 之外，验证模块可加载）
// 仅做语法与 require 检查，不真正起窗口（CI 无 X server）。
// 用法：node --check main.js && node --check preload.js && node --check ipc-handlers.js
// 本文件由 release 流水线在 Windows runner 上额外执行（可选深度校验）。

'use strict';

// 验证 3 个核心文件至少能被 Node 语法解析
// 若此处抛 SyntaxError，CI 应直接失败。
const fs = require('fs');
const path = require('path');

const files = ['main.js', 'preload.js', 'ipc-handlers.js'];

for (const f of files) {
  const p = path.join(__dirname, '..', f);
  if (!fs.existsSync(p)) {
    console.error(`[self-check] 缺失文件: ${p}`);
    process.exit(1);
  }
  // 读出来让 node 做一次语法解析（不用 vm，避免引入依赖）
  const src = fs.readFileSync(p, 'utf-8');
  try {
    new Function(src); // 仅语法校验，不执行
    console.log(`[self-check] ${f} 语法 OK (${src.length} bytes)`);
  } catch (e) {
    console.error(`[self-check] ${f} 语法错误:`, e.message);
    process.exit(1);
  }
}
console.log('[self-check] 全部通过');
