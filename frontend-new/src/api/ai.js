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
