import request from './request'

export const getStatsReport = (days = 7) => request.get('/api/stats/report', { params: { days } })
export const takeStatsSnapshot = (force = false) =>
  request.post('/api/stats/snapshot', null, { params: { force } })
