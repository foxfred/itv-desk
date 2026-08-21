import request from './request'

// #58 应用自更新（零服务器：用户自建更新清单 + 新包地址）
export const getAppVersion = () => request.get('/api/app/version')
export const checkUpdate = (url = null) => request.post('/api/app/check-update', { url })
export const downloadUpdate = (url, filename = null) =>
  request.post('/api/app/download-update', { url, filename })
