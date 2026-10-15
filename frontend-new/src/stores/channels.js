import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as channelApi from '@/api/channels'

export const useChannelStore = defineStore('channels', () => {
  const channels = ref([])
  const stats = ref({ total: 0, online: 0, offline: 0 })
  const loading = ref(false)
  const loaded = ref(false)

  async function fetchChannels() {
    loading.value = true
    try {
      const { data } = await channelApi.getChannels()
      channels.value = data || []
      loaded.value = true
    } catch { /* ignore */ }
    loading.value = false
  }

  async function fetchIfNeeded() {
    if (loaded.value) {
      await fetchStats()
      return false
    }
    await fetchChannels()
    await fetchStats()
    return true
  }

  async function fetchStats() {
    try {
      const { data } = await channelApi.getStats()
      stats.value = data
    } catch { /* ignore */ }
  }

  async function refresh() {
    await Promise.all([fetchChannels(), fetchStats()])
  }

  return {
    channels, stats, loading, loaded,
    fetchChannels, fetchStats, fetchIfNeeded, refresh
  }
})