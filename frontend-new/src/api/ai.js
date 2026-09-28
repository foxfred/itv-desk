import request from './request'

export const getAiConfig = () => request.get('/api/ai/config')
export const saveAiConfig = (data) => request.post('/api/ai/config', data)

// 点击「获取模型列表」：从 /v1/models 拉取可用模型
export const listModels = (base_url = '', api_key = '') =>
  request.post('/api/ai/models', { base_url, api_key })

// 连通性测试（会真实发一次最短对话）
export const testAi = (base_url = '', api_key = '', model = '') =>
  request.post('/api/ai/test', { base_url, api_key, model })

// 智能分组：不给 mapping 时让模型分析频道名，给 mapping + apply 时落库
export const groupChannels = (payload) => request.post('/api/ai/group', payload)
export const applyGroups = (mapping) => request.post('/api/ai/apply-groups', { mapping })

// 频道名智能清洗：不给 mapping 时让模型清洗频道名，给 mapping + apply 时落库（可整批撤销）
export const namefixChannels = (payload) => request.post('/api/ai/namefix', payload)

// ---- 2026-09-28 能力扩展 ----
// #3 频道打标与自动分级（apply=true 写入 tag 体系）
export const tagChannels = (payload) => request.post('/api/ai/tags', payload)
// #4 模糊搜索同义词扩展
export const searchExpand = (payload) => request.post('/api/ai/search-expand', payload)
// #1 增强版：用名称校正的规则候选交模型裁决
export const cleanNames = (payload) => request.post('/api/ai/clean-names', payload)
// #2 源真实性核验（视觉模型读截图）
export const verifySource = (payload) => request.post('/api/ai/verify-source', payload)
// #6 多源择优排序
export const rankSources = (payload) => request.post('/api/ai/rank-sources', payload)
// #9 播放故障诊断（读 app.log）
export const diagnose = (payload) => request.post('/api/ai/diagnose', payload)
// #10 EPG 智能补齐 / 节目单摘要
export const epgSuggest = (payload) => request.post('/api/ai/epg-suggest', payload)
export const epgSummary = (payload) => request.post('/api/ai/epg-summary', payload)
// #8 自然语言操作（只解析计划，由前端确认后执行）
export const nlPlan = (payload) => request.post('/api/ai/nl', payload)
// #5 乱码智能还原
export const garbled = (payload) => request.post('/api/ai/garbled', payload)
// #7 订阅源体检
export const auditSubscription = (payload) => request.post('/api/ai/audit-subscription', payload)
// #11 频道墙智能排布
export const wallOrder = (payload) => request.post('/api/ai/wall-order', payload)
// #12 导出描述生成
export const exportDesc = (payload) => request.post('/api/ai/export-desc', payload)
// 用量与缓存
export const getUsage = () => request.get('/api/ai/usage')
export const resetUsage = () => request.post('/api/ai/usage/reset')
export const getCacheStats = () => request.get('/api/ai/cache/stats')
export const clearCache = () => request.post('/api/ai/cache/clear')
