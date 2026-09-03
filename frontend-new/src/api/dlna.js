import request from './request'

export const discoverDevices = () => request.get('/api/dlna/devices')
export const playOnDevice = (device, url) => request.post('/api/dlna/play', { device, url })
export const stopDevice = (device) => request.post('/api/dlna/stop', { device })
