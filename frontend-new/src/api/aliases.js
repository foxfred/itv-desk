import request from './request'

// 频道别名库（P1-9）
export const listAliases = () => request.get('/api/aliases')
export const setAliasGroup = (canon, aliases) => request.post('/api/aliases', { canon, aliases })
export const removeAliasGroup = (canon) => request.delete('/api/aliases', { params: { canon } })
export const importAliases = (text, replace = false) => request.post('/api/aliases/import', { text, replace })
export const resetAliases = () => request.post('/api/aliases/reset')
