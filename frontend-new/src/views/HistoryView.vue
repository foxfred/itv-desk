<template>
  <div class="history-view">
    
    <el-card shadow="never" class="report-card">
      <template #header>
        <div class="card-header">
          <span class="report-title">频道健康报告</span>
          <div class="header-actions">
            <el-select v-model="reportDays" size="small" style="width:110px" @change="loadReport">
              <el-option label="近 7 天" :value="7" />
              <el-option label="近 30 天" :value="30" />
              <el-option label="近 90 天" :value="90" />
            </el-select>
            <el-button size="small" :loading="reportLoading" @click="loadReport">刷新</el-button>
            <el-button size="small" type="primary" :loading="snapLoading" @click="takeSnapshot">
              记录今天的快照
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="reportLoading">
        <div class="metric-row" v-if="report.current">
          <div class="metric">
            <div class="metric-num">{{ fmtPct(report.current.online_rate) }}</div>
            <div class="metric-label">在线率</div>
          </div>
          <div class="metric">
            <div class="metric-num">{{ report.current.online }}<span class="metric-sub">/{{ report.current.total }}</span></div>
            <div class="metric-label">在线 / 总数</div>
          </div>
          <div class="metric">
            <div class="metric-num">{{ fmtMs(report.current.avg_ms) }}</div>
            <div class="metric-label">平均延迟</div>
          </div>
          <div class="metric">
            <div class="metric-num" :class="{ warn: report.current.dead > 0 }">{{ report.current.dead }}</div>
            <div class="metric-label">死源</div>
          </div>
          <div class="metric">
            <div class="metric-num" :class="{ warn: report.current.ad_suspect > 0 }">{{ report.current.ad_suspect }}</div>
            <div class="metric-label">疑似广告台</div>
          </div>
        </div>

        <el-divider content-position="left">在线率趋势（按天快照，共 {{ report.trend.length }} 天）</el-divider>
        <el-table v-if="report.trend.length" :data="report.trend" size="small" border max-height="220">
          <el-table-column prop="date" label="日期" width="110" />
          <el-table-column label="在线率" width="110">
            <template #default="{ row }">{{ fmtPct(row.online_rate) }}</template>
          </el-table-column>
          <el-table-column label="在线/总数" width="120">
            <template #default="{ row }">{{ row.online }}/{{ row.total }}</template>
          </el-table-column>
          <el-table-column label="平均延迟" width="110">
            <template #default="{ row }">{{ fmtMs(row.avg_ms) }}</template>
          </el-table-column>
          <el-table-column prop="dead" label="死源" width="70" />
          <el-table-column label="清晰度分布" show-overflow-tooltip>
            <template #default="{ row }">{{ fmtRes(row.resolution) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="还没有快照。点右上角「记录今天的快照」，或在频道页跑完一次检测后会自动记录" :image-size="60" />

        <el-divider content-position="left">延迟分布（当前）</el-divider>
        <div class="bar-list">
          <div v-for="b in latencyBars" :key="b.name" class="bar-row">
            <span class="bar-name">{{ b.name }}</span>
            <el-progress :percentage="b.pct" :stroke-width="14" :show-text="false" style="flex:1" />
            <span class="bar-val">{{ b.count }} 个</span>
          </div>
        </div>

        <el-divider content-position="left">失效 Top（死源 / 离线 / 高延迟，最多 20 条）</el-divider>
        <el-table :data="report.top_failing" size="small" border max-height="300" v-if="report.top_failing.length">
          <el-table-column prop="name" label="频道" min-width="150" show-overflow-tooltip />
          <el-table-column prop="group" label="分组" width="110" show-overflow-tooltip />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.dead" size="small" type="danger" effect="dark">死源</el-tag>
              <el-tag v-else size="small" type="warning" effect="plain">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="延迟" width="90" align="center">
            <template #default="{ row }">{{ fmtMs(row.ms) }}</template>
          </el-table-column>
          <el-table-column prop="consecutive_fail" label="连续失败" width="90" align="center" />
          <el-table-column prop="last_error" label="最近错误" min-width="200" show-overflow-tooltip />
        </el-table>
        <el-empty v-else description="没有失效频道，挺好" :image-size="60" />
      </div>
    </el-card>

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
import * as statsApi from '@/api/stats'
import { callNative } from '@/composables/useNative'
import { usePlayerStore } from '@/stores/player'

const report = ref({ trend: [], current: null, top_failing: [], latency_buckets: [] })
const reportDays = ref(7)
const reportLoading = ref(false)
const snapLoading = ref(false)

const latencyBars = computed(() => {
  const cur = report.value.current
  if (!cur || !cur.latency) return []
  const total = cur.total || 1
  return Object.entries(cur.latency).map(([name, count]) => ({
    name,
    count,
    pct: Math.round((count / total) * 100),
  }))
})

function fmtPct(v) {
  return v == null ? '-' : (v * 100).toFixed(1) + '%'
}
function fmtMs(v) {
  const n = Number(v)
  if (!v || Number.isNaN(n) || n <= 0) return '-'
  return n >= 1000 ? (n / 1000).toFixed(1) + 's' : Math.round(n) + 'ms'
}
function fmtRes(dist) {
  if (!dist) return '-'
  return Object.entries(dist)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => `${k} ${n}`)
    .join(' / ')
}

async function loadReport() {
  reportLoading.value = true
  try {
    const { data } = await statsApi.getStatsReport(reportDays.value)
    report.value = data
  } catch {
    ElMessage.error('健康报告加载失败')
  } finally {
    reportLoading.value = false
  }
}

async function takeSnapshot() {
  snapLoading.value = true
  try {
    const { data } = await statsApi.takeStatsSnapshot(true)
    ElMessage.success(`已记录 ${data.date} 的快照（在线 ${data.online}/${data.total}）`)
    await loadReport()
  } catch {
    ElMessage.error('记录快照失败')
  } finally {
    snapLoading.value = false
  }
}

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

onMounted(() => {
  loadReport()
  load()
})
</script>

<style scoped>
.history-view {
  max-width: 1100px;
}

.report-card { margin-bottom: 12px; }
.report-title { font-weight: 600; font-size: 14px; }
.metric-row {
  display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 4px;
}
.metric {
  flex: 1 1 110px; text-align: center; padding: 10px 6px;
  border: 1px solid var(--el-border-color-lighter); border-radius: 6px;
  background: var(--el-fill-color-blank);
}
.metric-num { font-size: 20px; font-weight: 600; line-height: 1.3; }
.metric-num.warn { color: var(--el-color-danger); }
.metric-sub { font-size: 12px; font-weight: 400; color: var(--el-text-color-secondary); }
.metric-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.bar-list { padding: 0 4px; }
.bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.bar-name { width: 100px; font-size: 12px; color: var(--el-text-color-regular); flex-shrink: 0; }
.bar-val { width: 70px; text-align: right; font-size: 12px; color: var(--el-text-color-secondary); flex-shrink: 0; }
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
