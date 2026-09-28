import axios from 'axios'
import request from './request'

// 进度轮询专用实例：不挂全局拦截器（轮询偶发失败不应弹错误提示）
const silent = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '', timeout: 8000 })

export const getAppVersion = () => request.get('/api/app/version')
export const checkUpdate = (url = null) => request.post('/api/app/check-update', { url })
// 下载更新包：110MB 实测走代理 40s+，必须单独放宽超时。
// 全局 axios 默认 30s，会导致「下载失败: timeout of 30000ms exceeded」。
export const downloadUpdate = (url, filename = null, sha256 = null, size = null) =>
  request.post('/api/app/download-update', { url, filename, sha256, size }, { timeout: 900000 })
// 下载进度（后端下载期间实时更新，前端轮询显示百分比）
export const downloadProgress = () => silent.get('/api/app/download-progress')
export const applyUpdate = (zipPaths) => {
    if (Array.isArray(zipPaths)) {
    return request.post('/api/app/apply-update', { zip_paths: zipPaths })
  }
  return request.post('/api/app/apply-update', { zip_path: zipPaths })
}
