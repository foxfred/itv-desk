import request from './request'

// 频道健康统计（P1-10）
export const getStatsReport = (days = 7) => request.get('/api/stats/report', { params: { days } })
export const takeStatsSnapshot = (force = false) =>
  request.post('/api/stats/snapshot', null, { params: { force } })
