import request from './request'

export const getGatewayInfo = () => request.get('/api/gateway')
export const rotateGatewayToken = () => request.post('/api/gateway/token')
