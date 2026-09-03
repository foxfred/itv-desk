import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as channelApi from '@/api/channels'

export const useChannelStore = defineStore('channels', () => {
  const channels = ref([])
  const stats = ref({ total: 0, online: 0, offline: 0 })
  const loading = ref(false)
  const loaded = ref(false)
  const selectedIds = ref(new Set())

  const selectedChannels = computed(() =>
    channels.value.filter(c => selectedIds.value.has(c.id))
  )

  async function fetchChannels() {
    loading.value = true
    try {
      const { data } = await channelApi.getChannels()
      channels.value = data || []
      loaded.value = true
    } catch { /* ignore */ }
    loading.value = false
  }

  // 已有数据则跳过全量刷新（切页快速显示）
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

  function toggleSelect(id) {
    const s = new Set(selectedIds.value)
    if (s.has(id)) s.delete(id)
    else s.add(id)
    selectedIds.value = s
  }

  function selectAll() {
    selectedIds.value = new Set(channels.value.map(c => c.id))
  }

  function invertSelect() {
    const all = new Set(channels.value.map(c => c.id))
    const inv = new Set([...all].filter(id => !selectedIds.value.has(id)))
    selectedIds.value = inv
  }

  function clearSelect() {
    selectedIds.value = new Set()
  }

  return {
    channels, stats, loading, loaded, selectedIds, selectedChannels,
    fetchChannels, fetchStats, fetchIfNeeded, refresh,
    toggleSelect, selectAll, invertSelect, clearSelect
  }
})