import request from './request'

export const startCheck = (params) => request.post('/api/check', params)
export const stopCheck = () => request.post('/api/check/stop')
export const getCheckStatus = () => request.get('/api/check/status')