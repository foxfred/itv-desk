import axios from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

const request = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

request.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    const h = config.headers
    if (h && typeof h.delete === 'function') {
      h.delete('Content-Type')
    } else if (h) {
      delete h['Content-Type']
      delete h['content-type']
    }
  }
  return config
})

function extractErrMsg(data, fallback) {
  let msg = data && data.detail !== undefined ? data.detail : data
  if (msg && typeof msg === 'object') {
    try {
      if (Array.isArray(msg)) {
        msg = msg.map((it) => (it && (it.msg || it.detail)) || JSON.stringify(it)).join('；')
      } else {
        msg = JSON.stringify(msg)
      }
    } catch {
      msg = String(msg)
    }
  }
  const s = msg == null ? '' : String(msg)
  return (s || fallback).slice(0, 200)
}

request.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = extractErrMsg(err.response?.data, err.message || '请求失败')
    ElMessage.error(msg)
    return Promise.reject(err)
  }
)

export default request
