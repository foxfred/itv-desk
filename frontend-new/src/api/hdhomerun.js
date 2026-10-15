import request from './request'

export const getHdhrStatus = () => request.get('/api/hdhomerun/status')
