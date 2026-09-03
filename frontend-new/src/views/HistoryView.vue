<template>
  <div class="history-view">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <el-radio-group v-model="tab" size="small">
            <el-radio-button value="all">全部 ({{ items.length }})</el-radio-button>
            <el-radio-button value="fav">收藏 ({{ favCount }})</el-radio-button>
          </el-radio-group>
          <div class="header-actions">
            <el-button size="small" :disabled="!filtered.length" @click="onClear">
              {{ tab === 'fav' ? '清空收藏' : '清空全部' }}
            </el-button>
            <el-button size="small" :loading="loading" @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="filtered" v-loading="loading" size="small" stripe>
        <el-table-column label="名称" min-width="220">
          <template #default="{ row }">
            <span class="name-text">{{ row.name }}</span>
            <el-tag v-if="row.is_favorite" size="small" type="warning" effect="plain" class="fav-tag">收藏</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="group" label="分组" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.group" class="group-text">{{ row.group }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column label="播放次数" width="90" align="center">
          <template #default="{ row }">{{ row.play_count || 1 }}</template>
        </el-table-column>
        <el-table-column label="上次播放" width="180" align="center">
          <template #default="{ row }">{{ formatTime(row.played_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="190" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="play(row)">播放</el-button>
            <el-button size="small" text :type="row.is_favorite ? 'warning' : 'info'" @click="toggleFav(row)">
              {{ row.is_favorite ? '取消收藏' : '收藏' }}
            </el-button>
            <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!filtered.length && !loading" :description="tab === 'fav' ? '暂无收藏记录' : '暂无播放记录'" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { playHistoryApi } from '@/api/play_history'
import { callNative } from '@/composables/useNative'
import { usePlayerStore } from '@/stores/player'

const items = ref([])
const tab = ref('all')
const loading = ref(false)
const playerStore = usePlayerStore()

const favCount = computed(() => items.value.filter(i => i.is_favorite).length)
const filtered = computed(() => tab.value === 'fav' ? items.value.filter(i => i.is_favorite) : items.value)

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '-'
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function load() {
  loading.value = true
  try {
    const { data } = await playHistoryApi.list(500)
    items.value = data.items || []
  } catch { /* ignore */ }
  loading.value = false
}

async function play(row) {
  // 双窗口（Phase 1）：历史记录播放走经纪人，打开独立播放窗（列表即选源入口）
  if (!row || !row.url) return
  const api = window.pywebview?.api
  if (api && typeof api.play_channel === 'function') {
    await callNative('play_channel', {
      url: row.url, name: row.name, group: row.group || '',
    })
    playerStore.currentChannel = { id: row.id, url: row.url, name: row.name, group: row.group || '' }
    if (playerStore.state === 'hidden') playerStore.state = 'drawer'
    return
  }
  // 退化：浏览器环境
  playerStore.open({ id: row.id, url: row.url, name: row.name, group: row.group || '' }, null, -1)
  if (playerStore.state === 'hidden') playerStore.setState('drawer')
  else playerStore.exitPip()
}

async function toggleFav(row) {
  try {
    const { data } = await playHistoryApi.favorite(row.id)
    row.is_favorite = data.is_favorite
    ElMessage.success(data.is_favorite ? '已收藏' : '已取消收藏')
  } catch { ElMessage.error('操作失败') }
}

async function remove(row) {
  try {
    await playHistoryApi.remove(row.id)
    items.value = items.value.filter(i => i.id !== row.id)
  } catch { ElMessage.error('删除失败') }
}

async function onClear() {
  const label = tab.value === 'fav' ? '全部收藏' : '全部播放记录'
  try {
    await ElMessageBox.confirm(`确定清空${label}吗？此操作不可恢复`, '确认', { type: 'warning' })
  } catch { return }
  if (tab.value === 'fav') {
    // 收藏页：逐个取消收藏标记
    for (const row of items.value.filter(i => i.is_favorite)) {
      try { await playHistoryApi.favorite(row.id) } catch { /* continue */ }
    }
    load()
  } else {
    try {
      await playHistoryApi.clear()
      items.value = []
    } catch { ElMessage.error('清空失败') }
  }
}

onMounted(load)
</script>

<style scoped>
.history-view {
  max-width: 1100px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.name-text {
  font-weight: 500;
}
.fav-tag {
  margin-left: 8px;
}
.group-text {
  color: var(--el-text-color-regular);
}
.empty-text {
  color: var(--el-text-color-placeholder);
}
</style>
