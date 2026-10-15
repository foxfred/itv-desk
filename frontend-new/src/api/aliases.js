import request from './request'

export const listAliases = () => request.get('/api/aliases')
export const importAliases = (text, replace = false) => request.post('/api/aliases/import', { text, replace })
export const resetAliases = () => request.post('/api/aliases/reset')
