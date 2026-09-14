import request from './request'

// 局域网订阅网关（P1-6）
export const getGatewayInfo = () => request.get('/api/gateway')
export const rotateGatewayToken = () => request.post('/api/gateway/token')
