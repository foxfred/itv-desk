import request from './request'

export const listSubs = () => request.get('/api/subscriptions')
export const addSub = (data) => request.post('/api/subscriptions', data)
export const removeSub = (url) => request.delete('/api/subscriptions', { params: { url } })
export const toggleSub = (url, enabled) => request.post('/api/subscriptions/toggle', { url, enabled })
export const updateAll = () => request.post('/api/subscriptions/update')
export const updateOne = (url) => request.post('/api/subscriptions/update-one', { url })
