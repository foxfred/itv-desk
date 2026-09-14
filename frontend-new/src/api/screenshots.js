import request from './request'

// 截图索引（{源URL: 静态路径}）+ 批量任务状态
export const listShots = () => request.get('/api/screenshots')
export const getShotStatus = () => request.get('/api/screenshots/status')
// 单个抓帧（同步，2-8 秒）
export const captureShot = (payload) => request.post('/api/screenshots/capture', payload)
// 批量抓帧（后台执行，前端轮询 /status）
export const captureShotBatch = (payload) => request.post('/api/screenshots/batch', payload)
export const removeShot = (url) => request.delete('/api/screenshots', { params: { url } })
