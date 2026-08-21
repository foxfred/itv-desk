import request from './request'

export const loadEpg = (url) => request.post('/api/epg/load', { url })
export const getEpgStatus = () => request.get('/api/epg/status')
export const correctNames = (data) => request.post('/api/epg/correct-names', data)
export const updateGroups = (data) => request.post('/api/epg/update-groups', data)
export const searchProgram = (keyword) => request.post('/api/epg/search', { keyword })
export const getProgram = (params) => request.get('/api/epg/program', { params })
export const getChannels = () => request.get('/api/epg/channels')
export const getPrograms = (params) => request.get('/api/epg/programs', { params })
export const getEpgMatch = (name) => request.get('/api/epg/match', { params: { name } })