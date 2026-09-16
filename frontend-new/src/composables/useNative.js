
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

export async function callNative(method, ...args) {
  const api = getApi()
  if (api && typeof api[method] === 'function') {
    try {
      const r = await api[method](...args)
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

export async function toggleNativeFullscreen() {
  const r = await callNative('toggle_fullscreen')
  return r !== undefined
}

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
