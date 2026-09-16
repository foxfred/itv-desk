import request from './request'

export const nfStatus = () => request.get('/api/namefix/status')
export const nfSuggestions = (state) =>
  request.get('/api/namefix/suggestions', { params: state ? { state } : {} })
export const nfScan = (payload) => request.post('/api/namefix/scan', payload || {})
export const nfApply = (ids) => request.post('/api/namefix/apply', { ids: ids || [] })
export const nfDismiss = (ids) => request.post('/api/namefix/dismiss', { ids: ids || [] })
export const nfUndo = (batchId) => request.post('/api/namefix/undo', { batch_id: batchId || '' })
export const nfUndoList = () => request.get('/api/namefix/undo-list')
export const nfVisionTest = () => request.post('/api/namefix/vision-test', {})
export const nfClear = () => request.post('/api/namefix/clear', {})
