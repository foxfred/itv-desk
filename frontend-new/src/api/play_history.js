import request from './request'

export const getPlayHistory = (limit = 50) => request.get('/api/play-history', { params: { limit } })
export const recordPlay = (data) => request.post('/api/play-history', data)
export const toggleFavorite = (id) => request.post(`/api/play-history/${id}/favorite`)
export const removePlayHistory = (id) => request.delete(`/api/play-history/${id}`)
export const clearPlayHistory = () => request.delete('/api/play-history')

export const playHistoryApi = {
  list: getPlayHistory,
  record: recordPlay,
  favorite: toggleFavorite,
  remove: removePlayHistory,
  clear: clearPlayHistory,
}
