import request from './request'

export const getChannels = () => request.get('/api/channels')
export const getStats = () => request.get('/api/stats')
export const clearAll = () => request.delete('/api/channels')
export const updateChannel = (id, data) => request.put(`/api/channels/${id}`, data)
export const deleteChannel = (id) => request.delete(`/api/channels/${id}`)
export const deleteMany = (ids) => request.post('/api/channels/delete-many', ids)
export const deleteByGroup = (group) => request.post('/api/channels/delete-by-group', { group })
export const removeInvalid = () => request.delete('/api/channels/invalid')
export const setSelect = (ids, state = true, clear = true) => request.post('/api/channels/select', { ids, state, clear })
export const toggleCheck = (id) => request.post(`/api/channels/toggle/${id}`)
export const setTag = (id, tag) => request.post(`/api/channels/${id}/tag`, { tag })
export const toggleTag = (id, tag) => request.post(`/api/channels/${id}/tag-toggle`, { tag })
export const batchTagAdd = (ids, tags) => request.post('/api/channels/batch-tag-add', { ids, tags })
export const batchTagClear = (ids) => request.post('/api/channels/batch-tag-clear', { ids })
export const setFakeLive = (id, isFakeLive) => request.post(`/api/channels/${id}/fake-live`, { is_fake_live: isFakeLive })
export const batchFakeLive = (ids, isFakeLive) => request.post('/api/channels/batch-fake-live', { ids, is_fake_live: isFakeLive })
export const batchGroup = (ids, group) => request.post('/api/channels/batch-group', { ids, group })
export const saveCache = () => request.post('/api/cache/save')
export const getGroups = () => request.get('/api/channels/groups')
export const searchChannels = (q, offset = 0, limit = 200) =>
  request.get('/api/channels/search', { params: { q, offset, limit } })

export const reportHealth = (url, success, error = null, firstFrameMs = null) =>
  request.post('/api/channels/health', { url, success, error, first_frame_ms: firstFrameMs })

export const mergeDuplicates = () => request.post('/api/channels/merge-duplicates')
export const matchLogos = (logosDir = null) =>
  request.post('/api/channels/match-logos', { logos_dir: logosDir })
export const startOnlineLogos = (payload = {}) =>
  request.post('/api/channels/match-logos-online', payload)
export const getOnlineLogoTask = (taskId) =>
  request.get(`/api/channels/match-logos-online/${taskId}`)
export const reclassifyChannels = () => request.post('/api/channels/reclassify')