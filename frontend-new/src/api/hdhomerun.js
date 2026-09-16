import request from './request'

export const getHdhrConfig = () => request.get('/api/hdhomerun/config')
export const saveHdhrConfig = (data) => request.post('/api/hdhomerun/config', data)
export const getHdhrStatus = () => request.get('/api/hdhomerun/status')
