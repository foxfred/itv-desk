import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as configApi from '@/api/config'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref({})
  const loading = ref(false)
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