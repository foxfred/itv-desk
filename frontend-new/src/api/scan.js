import request from './request'

export const deriveScanTemplates = (urls) => request.post('/api/scan/derive', { urls })
export const scanRange = (params) => request.post('/api/scan', params, { timeout: 600000 })
export const importScanResults = (results) => request.post('/api/scan/import', { results })
