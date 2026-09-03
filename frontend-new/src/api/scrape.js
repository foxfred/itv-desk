import request from './request'

export const scrape = (params) => request.post('/api/scrape', params)
export const scrapeBatch = (params) => request.post('/api/scrape-batch', params)
export const getScrapeStatus = () => request.get('/api/scrape/status')
export const stopScrape = () => request.post('/api/scrape-stop')
export const importUrl = (params) => request.post('/api/import-url', params)
export const importUrls = (params) => request.post('/api/import-urls', params)
export const importText = (text) => request.post('/api/import-text', { text })
export const importChannels = (channels) => request.post('/api/import-channels', { channels })
export const smartPaste = (text) => request.post('/api/smart-paste', { text })