import request from './request'

export const listShots = () => request.get('/api/screenshots')
export const getShotStatus = () => request.get('/api/screenshots/status')
export const captureShot = (payload) => request.post('/api/screenshots/capture', payload)
export const captureShotBatch = (payload) => request.post('/api/screenshots/batch', payload)
export const removeShot = (url) => request.delete('/api/screenshots', { params: { url } })
