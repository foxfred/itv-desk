import request from './request'

export const getAppVersion = () => request.get('/api/app/version')
export const checkUpdate = (url = null) => request.post('/api/app/check-update', { url })
export const downloadUpdate = (url, filename = null, sha256 = null, size = null) =>
  request.post('/api/app/download-update', { url, filename, sha256, size })
export const applyUpdate = (zipPaths) => {
    if (Array.isArray(zipPaths)) {
    return request.post('/api/app/apply-update', { zip_paths: zipPaths })
  }
  return request.post('/api/app/apply-update', { zip_path: zipPaths })
}
