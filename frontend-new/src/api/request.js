import axios from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = import.meta.env.VITE_API_BASE_URL || ''

const request = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截：上传 FormData 时必须去掉默认的 application/json 头，
// 交给浏览器自动设置带 boundary 的 multipart/form-data，
// 否则后端 FastAPI 收不到文件字段（返回 422，导入功能失效）。
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

// 把后端错误信息规整成可安全显示的字符串。
// 关键：FastAPI 422 校验错误的 detail 是数组，直接丢给 ElMessage
// 会被当成配置对象展开，产生 '0' is not a valid attribute name 崩溃白屏。
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
