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
export const setSourceTag = (id, url, tag) => request.post(`/api/channels/${id}/source-tag`, { url, tag })
export const setSourceFakeLive = (id, url, isFakeLive) => request.post(`/api/channels/${id}/source-fake-live`, { url, is_fake_live: isFakeLive })
export const batchGroup = (ids, group) => request.post('/api/channels/batch-group', { ids, group })
export const saveCache = () => request.post('/api/cache/save')
// 服务端分组树 / 全文检索（SQLite 镜像支撑，适合大数据量与外部 API 调用）
export const getGroups = () => request.get('/api/channels/groups')
export const searchChannels = (q, offset = 0, limit = 200) =>
  request.get('/api/channels/search', { params: { q, offset, limit } })

// 播放健康度上报：播放成功/失败回写评分（失败带 error 细节）
export const reportHealth = (url, success, error = null, firstFrameMs = null) =>
  request.post('/api/channels/health', { url, success, error, first_frame_ms: firstFrameMs })

// #56 智能去重合并
export const mergeDuplicates = () => request.post('/api/channels/merge-duplicates')
// 拆解所有聚合源：还原为单源频道（聚合源使离线源无法单独清除）
export const ungroupAll = () => request.post('/api/channels/ungroup-all')
// #57 Logo 自动匹配（logosDir 为空则用默认 DATA_DIR/logos）
export const matchLogos = (logosDir = null) =>
  request.post('/api/channels/match-logos', { logos_dir: logosDir })
// #58 在线台标补全（后台任务 + 轮询进度）
export const startOnlineLogos = (payload = {}) =>
  request.post('/api/channels/match-logos-online', payload)
export const getOnlineLogoTask = (taskId) =>
  request.get(`/api/channels/match-logos-online/${taskId}`)
// #60 重新自动分组（对整个频道池按统一算法重跑分组）
export const reclassifyChannels = () => request.post('/api/channels/reclassify')