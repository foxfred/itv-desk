import request from './request'

export const exportChannels = (params, responseType = 'text') =>
  request.post('/api/export', params, { responseType })
export const exportDirect = (params) => request.post('/api/export-direct', params)
export const repair = (params, responseType = 'json') =>
  request.post('/api/repair', params, { responseType })
export const findReplace = (params) => request.post('/api/find-replace', params)
export const getPlayers = () => request.get('/api/players')
export const playExternal = (player, url) => request.post('/api/play-external', { player, url })
export const getLogs = (since = 0) => request.get(`/api/logs?since=${since}`)
export const clearLogs = () => request.post('/api/logs/clear')
export const getHistory = () => request.get('/api/history')
export const saveUrlHistory = (url) => request.post('/api/history/url', { url })
export const saveMirrorHistory = (url) => request.post('/api/history/mirror', { url })
export const saveMirrorHistoryBatch = (urls) => request.post('/api/history/mirror-batch', { urls })
export const saveEpgHistory = (url) => request.post('/api/history/epg', { url })
export const saveEpgHistoryBatch = (urls) => request.post('/api/history/epg-batch', { urls })
export const saveUrlHistoryBatch = (urls) => request.post('/api/history/url-batch', { urls })

export const exportBackupFile = () => request.get('/api/backup/export-file')
export const exportBackup = () =>
  request.get('/api/backup/export', { responseType: 'blob' })
export const importBackup = (file, mode = 'overwrite') => {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', mode)
  return request.post('/api/backup/import', form)
}

// #59 本地加密备份 / 恢复（AES 口令保护，零服务器）
export const exportEncryptedBackup = (passphrase) =>
  request.post('/api/backup/export-encrypted', { passphrase })
export const importEncryptedBackup = (file, passphrase) => {
  const form = new FormData()
  form.append('file', file)
  form.append('passphrase', passphrase)
  return request.post('/api/backup/import-encrypted', form)
}

export const exportApi = {
  exportChannels, exportDirect, repair, findReplace, getPlayers, playExternal,
  getLogs, clearLogs, getHistory, saveUrlHistory, saveMirrorHistory,
  saveMirrorHistoryBatch, saveEpgHistory, saveEpgHistoryBatch, saveUrlHistoryBatch,
  exportBackup, exportBackupFile, importBackup,
  exportEncryptedBackup, importEncryptedBackup,
}