import request from './request'

// #58 应用自更新（GitHub Releases：读取原 update.json + 下载 zip + 安装）
export const getAppVersion = () => request.get('/api/app/version')
export const checkUpdate = (url = null) => request.post('/api/app/check-update', { url })
export const downloadUpdate = (url, filename = null) =>
  request.post('/api/app/download-update', { url, filename })
export const applyUpdate = (zipPaths) => {
  // 支持数组（多包）或字符串（单包兼容）
  if (Array.isArray(zipPaths)) {
    return request.post('/api/app/apply-update', { zip_paths: zipPaths })
  }
  return request.post('/api/app/apply-update', { zip_path: zipPaths })
}
