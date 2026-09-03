// WebView 原生能力桥接（pywebview js_api）
// 桌面端(window.pywebview.api)存在时使用原生能力，否则回退到浏览器行为

function getApi() {
  try {
    if (typeof window !== 'undefined' && window.pywebview?.api) {
      return window.pywebview.api
    }
  } catch { /* ignore */ }
  return null
}

export function isNative() {
  return !!getApi()
}

// 调用原生 API（存在才调用），返回 Promise 或 undefined
// D1 修复：原生异常/返回 ERROR 时返回 { ok:false, error } 结构化错误；无原生环境仍返回 undefined
export async function callNative(method, ...args) {
  const api = getApi()
  if (api && typeof api[method] === 'function') {
    try {
      const r = await api[method](...args)
      // pywebview 后端异常通常以 "ERROR: xxx" 字符串返回，统一转结构化错误
      if (typeof r === 'string' && r.startsWith('ERROR:')) {
        return { ok: false, error: r.slice(6).trim() }
      }
      return r
    } catch (e) {
      console.warn(`原生调用 ${method} 失败:`, e)
      return { ok: false, error: e?.message || String(e) }
    }
  }
  return undefined
}

// 原生全屏切换（pywebview 窗口级），无原生时回退浏览器全屏
export async function toggleNativeFullscreen() {
  const r = await callNative('toggle_fullscreen')
  return r !== undefined
}

// 保存文本文件：优先弹原生保存对话框（WebView 中 Blob 下载会失效），否则回退 Blob 下载
export async function saveTextFile(filename, content) {
  const api = getApi()
  if (api && typeof api.save_text === 'function') {
    try {
      const path = await api.save_text(filename, content)
      return { ok: !!path, path, usedNative: true }
    } catch (e) {
      console.warn('原生保存失败，回退浏览器下载:', e)
    }
  }
  downloadBlob(content, filename)
  return { ok: true, path: null, usedNative: false }
}

export function downloadBlob(content, filename) {
  const blob = new Blob([content], { type: 'application/octet-stream' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
