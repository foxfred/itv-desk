import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as configApi from '@/api/config'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref({})
  const loading = ref(false)
  // C6 修复：saveSettings 串行队列——连续保存基于最新状态合并，避免丢字段
  let saveQueue = Promise.resolve()

  async function fetchSettings() {
    loading.value = true
    try {
      const { data } = await configApi.getConfig()
      settings.value = data || {}
    } catch { /* ignore */ }
    loading.value = false
  }

  function saveSettings(data) {
    // 串行化：上一次保存完成后才执行本次，且基于最新 settings 合并
    saveQueue = saveQueue.then(async () => {
      await configApi.saveConfig(data)
      settings.value = { ...settings.value, ...data }
    })
    return saveQueue
  }

  function get(key, fallback) {
    return settings.value[key] ?? fallback
  }

  return { settings, loading, fetchSettings, saveSettings, get }
})