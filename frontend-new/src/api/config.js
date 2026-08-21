import request from './request'

export const getConfig = () => request.get('/api/config')
export const saveConfig = (data) => request.post('/api/config/save', data)
export const resetConfig = () => request.post('/api/config/reset')
export const getPlayers = () => request.get('/api/players')