import request from './request'

export const listRecords = () => request.get('/api/record/list')
export const startRecord = (payload) => request.post('/api/record/start', payload)
export const stopRecord = (id = '') => request.post('/api/record/stop', { id })
export const deleteRecord = (file) => request.delete(`/api/record/${encodeURIComponent(file)}`)

export const listTimeshift = () => request.get('/api/timeshift/list')
export const startTimeshift = (payload) => request.post('/api/timeshift/start', payload)
export const stopTimeshift = (id = '') => request.post('/api/timeshift/stop', { id })
