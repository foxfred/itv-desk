import request from './request'

export const getRules = () => request.get('/api/rules')
export const saveRule = (data) => request.post('/api/rules', data)
export const deleteRule = (index) => request.delete(`/api/rules/${index}`)