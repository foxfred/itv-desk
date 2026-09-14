import request from './request'

// 扫描进度 + 建议表统计
export const nfStatus = () => request.get('/api/namefix/status')
// 改名建议表（state 可选：pending/ambiguous/unresolved/unreachable/junk/no_text/consistent）
export const nfSuggestions = (state) =>
  request.get('/api/namefix/suggestions', { params: state ? { state } : {} })
// 启动扫描（后台执行，前端轮询 nfStatus）。ids 为空则全量
export const nfScan = (payload) => request.post('/api/namefix/scan', payload || {})
// 应用建议（ids 为空则应用所有待确认项）；改名前自动备份，可整批撤销
export const nfApply = (ids) => request.post('/api/namefix/apply', { ids: ids || [] })
// 忽略建议
export const nfDismiss = (ids) => request.post('/api/namefix/dismiss', { ids: ids || [] })
// 撤销一批改名（不传 batch_id 则撤销最近一批）
export const nfUndo = (batchId) => request.post('/api/namefix/undo', { batch_id: batchId || '' })
export const nfUndoList = () => request.get('/api/namefix/undo-list')
// 视觉兜底通道自测
export const nfVisionTest = () => request.post('/api/namefix/vision-test', {})
// 清空建议表（不动频道数据）
export const nfClear = () => request.post('/api/namefix/clear', {})
