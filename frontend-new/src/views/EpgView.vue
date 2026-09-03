<template>
  <div class="epg-page">
    <!-- EPG 状态卡片 -->
    <el-card shadow="never" class="epg-status-card">
      <div class="epg-status-row">
        <div class="epg-status-info">
          <el-tag
            size="small"
            :type="statusTag.type"
            effect="light"
            class="epg-status-tag"
          >
            {{ statusTag.text }}
          </el-tag>
          <span class="epg-status-count" v-if="epgStatus.loaded">
            共 {{ epgStatus.count }} 个频道
          </span>
          <span class="epg-status-error" v-if="epgStatus.error">
            {{ epgStatus.error }}
          </span>
        </div>
        <div class="epg-actions">
          <div class="epg-urls">
            <el-select
              v-model="epgUrl"
              filterable
              allow-create
              default-first-option
              placeholder="选择或输入 EPG 地址，回车添加"
              style="width: 280px"
              @keyup.enter="addEpgSource"
            >
              <el-option v-for="u in epgHistory" :key="u" :value="u" :label="u" />
            </el-select>
            <el-button size="small" @click="addEpgSource" :disabled="!epgUrl.trim()">添加</el-button>
          </div>
          <div class="epg-source-tags" v-if="epgSources.length">
            <el-tag
              v-for="(s, idx) in epgSources"
              :key="idx"
              size="small"
              closable
              @close="removeEpgSource(idx)"
              style="margin-right:4px; margin-bottom:4px"
            >{{ s.url.length > 50 ? s.url.slice(0, 50) + '…' : s.url }}</el-tag>
          </div>
          <el-button type="primary" size="small" :loading="epgLoading" @click="loadEpg">
            加载全部 ({{ epgSources.length }} 个源)
          </el-button>
          <el-button size="small" :disabled="!epgStatus.loaded" @click="correctNames">
            校正频道名
          </el-button>
          <el-button size="small" :disabled="!epgStatus.loaded" @click="correctGroups">
            校正分组
          </el-button>
          <el-button size="small" :disabled="!epgStatus.loaded" @click="loadChannels">
            刷新频道
          </el-button>
          <el-button size="small" :disabled="!epgStatus.loaded" type="success" plain @click="showSearch = true">
            <el-icon style="margin-right:4px"><Search /></el-icon>搜索节目
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 主内容：左频道列表 / 右节目单 -->
    <div class="epg-main">
      <!-- 左侧：频道列表 -->
      <el-card shadow="never" class="epg-channels-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">频道列表</span>
            <span class="card-sub">{{ filteredChannels.length }} / {{ channels.length }}</span>
          </div>
        </template>
        <el-input
          v-model="channelKw"
          placeholder="搜索频道名"
          clearable
          size="small"
          class="channel-search"
        />
        <div class="channel-list" v-loading="channelsLoading">
          <div
            v-for="ch in filteredChannels"
            :key="ch.name"
            class="channel-item"
            :class="{ active: selectedChannel === ch.name }"
            @click="selectChannel(ch)"
          >
            <div class="channel-item-top">
              <span class="channel-name">{{ ch.name }}</span>
              <span class="channel-count" v-if="ch.count">{{ ch.count }}条</span>
            </div>
            <div class="channel-item-prog" v-if="ch.current">
              <span class="now-dot"></span>
              {{ ch.current }}
            </div>
            <div class="channel-item-prog empty" v-else>暂无节目</div>
          </div>
          <el-empty v-if="!channelsLoading && filteredChannels.length === 0" description="暂无频道" :image-size="60" />
        </div>
      </el-card>

      <!-- 右侧：节目单 -->
      <el-card shadow="never" class="epg-programs-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">{{ selectedChannel || '请选择频道' }}</span>
            <span class="card-sub" v-if="selectedChannel">今日节目单</span>
          </div>
        </template>
        <div class="program-list" v-loading="programsLoading">
          <el-empty v-if="!selectedChannel" description="在左侧选择一个频道查看节目单" :image-size="80" />
          <template v-else>
            <div
              v-for="p in programs"
              :key="p.start + p.title"
              class="program-item"
              :class="p.state"
              @dblclick="onProgramDblClick(p)"
            >
              <div class="program-time">
                <span class="program-start">{{ p.start }}</span>
                <span class="program-stop">{{ p.stop }}</span>
              </div>
              <div class="program-body">
                <div class="program-title-row">
                  <span class="program-title">{{ p.title }}</span>
                  <el-tag v-if="p.state === 'current'" size="small" type="danger" effect="dark">正在播放</el-tag>
                  <el-tag v-else-if="p.state === 'ended'" size="small" type="info" effect="plain">已结束</el-tag>
                  <span class="dblclick-hint">双击播放</span>
                </div>
                <el-progress
                  v-if="p.state === 'current'"
                  :percentage="p.progress"
                  :stroke-width="4"
                  :show-text="false"
                  class="program-progress"
                />
              </div>
            </div>
            <el-empty v-if="programs.length === 0" description="今日暂无节目" :image-size="60" />
          </template>
        </div>
      </el-card>
    </div>

    <!-- 弹窗：节目搜索 -->
    <el-dialog v-model="showSearch" title="搜索正在播放的节目" width="560px" destroy-on-close>
      <div class="search-row">
        <el-input
          v-model="searchKw"
          placeholder="输入节目名称，回车搜索（例如：新闻、电影、体育）"
          clearable
          @keyup.enter="doSearchProg"
        />
        <el-button type="primary" @click="doSearchProg" :loading="searching">搜索</el-button>
      </div>
      <el-table
        :data="searchResults"
        size="small"
        border
        max-height="380"
        style="margin-top:10px"
        @row-dblclick="searchProgPlay"
      >
        <el-table-column prop="channel" label="频道" width="180" show-overflow-tooltip />
        <el-table-column prop="title" label="节目" show-overflow-tooltip />
        <el-table-column prop="start" label="开始" width="70" />
        <el-table-column prop="stop" label="结束" width="70" />
        <el-table-column label="操作" width="70">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click.stop="searchProgPlay(row)">播放</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!searching && searched && searchResults.length === 0" description="未找到正在播放的节目" :image-size="60" />
      <template #footer>
        <el-button @click="showSearch = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as epgApi from '@/api/epg'
import { getHistory } from '@/api/export'
import { getChannels } from '@/api/channels'
import { callNative } from '@/composables/useNative'
import { usePlayerStore } from '@/stores/player'

const playerStore = usePlayerStore()
const epgUrl = ref('')
const epgHistory = ref([])
const epgSources = ref([])  // [{url, proxy}, ...]
const epgStatus = ref({ loading: false, loaded: false, count: 0, error: null })
const epgLoading = ref(false)

const channels = ref([])
const channelsLoading = ref(false)
const channelKw = ref('')
const selectedChannel = ref('')

const programs = ref([])
const programsLoading = ref(false)

const showSearch = ref(false)
const searchKw = ref('')
const searchResults = ref([])
const searching = ref(false)
const searched = ref(false)
const channelPool = ref([])

let statusTimer = null
let refreshTimer = null

const statusTag = computed(() => {
  if (epgStatus.value.loading) return { text: '加载中...', type: 'warning' }
  if (epgStatus.value.error) return { text: '加载失败', type: 'danger' }
  if (epgStatus.value.loaded) return { text: '已加载', type: 'success' }
  return { text: '未加载', type: 'info' }
})

const filteredChannels = computed(() => {
  const kw = channelKw.value.trim().toLowerCase()
  if (!kw) return channels.value
  return channels.value.filter(c => c.name.toLowerCase().includes(kw))
})

async function loadEpg() {
  if (!epgSources.value.length && !epgUrl.value.trim()) return ElMessage.warning('请添加 EPG 地址')
  // 先将输入框内容加入源列表
  if (epgUrl.value.trim()) addEpgSource()
  if (!epgSources.value.length) return ElMessage.warning('请添加 EPG 地址')
  try {
    epgLoading.value = true
    const sources = epgSources.value.map(s => ({ url: s.url }))
    await epgApi.loadEpgBatch(sources)
    ElMessage.info('EPG 多源加载中...')
    startStatusPolling()
    startAutoRefresh()
  } catch (e) {
    ElMessage.error('EPG 加载失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    epgLoading.value = false
  }
}

// 添加 EPG 源到列表
function addEpgSource() {
  const url = epgUrl.value.trim()
  if (!url) return
  if (epgSources.value.some(s => s.url === url)) {
    ElMessage.warning('该地址已在列表中')
    return
  }
  epgSources.value.push({ url })
  epgUrl.value = ''
}

// 移除 EPG 源
function removeEpgSource(idx) {
  epgSources.value.splice(idx, 1)
}

function startStatusPolling() {
  stopStatusPolling()
  statusTimer = setInterval(async () => {
    try {
      const { data } = await epgApi.getEpgStatus()
      epgStatus.value = data
      if (!data.loading) {
        stopStatusPolling()
        if (data.error) {
          ElMessage.error('EPG 加载失败: ' + data.error)
        } else {
          ElMessage.success(`EPG 加载完成，共 ${data.count} 个频道`)
          await loadChannels()
        }
      }
    } catch { /* ignore */ }
  }, 1000)
}

function stopStatusPolling() {
  if (statusTimer) { clearInterval(statusTimer); statusTimer = null }
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = setInterval(refreshCurrent, 60000)
}

function stopAutoRefresh() {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
}

async function loadChannels() {
  channelsLoading.value = true
  try {
    const { data } = await epgApi.getChannels()
    if (data.error) return ElMessage.warning(data.error)
    channels.value = data.channels || []
    if (selectedChannel.value) {
      const exists = channels.value.find(c => c.name === selectedChannel.value)
      if (!exists) {
        selectedChannel.value = ''
        programs.value = []
      }
    }
  } catch (e) {
    ElMessage.error('获取频道列表失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    channelsLoading.value = false
  }
}

async function selectChannel(ch) {
  selectedChannel.value = ch.name
  await loadPrograms(ch.name)
}

async function loadPrograms(name) {
  programsLoading.value = true
  try {
    const { data } = await epgApi.getPrograms({ name })
    programs.value = data.programs || []
  } catch (e) {
    ElMessage.error('获取节目单失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    programsLoading.value = false
  }
}

async function refreshCurrent() {
  if (!epgStatus.value.loaded) return
  if (selectedChannel.value) await loadPrograms(selectedChannel.value)
  const kw = channelKw.value.trim().toLowerCase()
  if (kw) return
  const { data } = await epgApi.getChannels()
  if (data.channels) channels.value = data.channels
}

async function correctNames() {
  try {
    const { data } = await epgApi.correctNames({})
    if (data.error) return ElMessage.warning(data.error)
    ElMessage.success(`已校正 ${data.corrected} 个频道名`)
  } catch (e) {
    ElMessage.error('校正失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function correctGroups() {
  try {
    const { data } = await epgApi.updateGroups({})
    if (data.error) return ElMessage.warning(data.error)
    ElMessage.success(`已更新 ${data.updated} 个频道的分组`)
  } catch (e) {
    ElMessage.error('校正失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function loadChannelPool() {
  try {
    const { data } = await getChannels()
    channelPool.value = data || []
  } catch { /* ignore */ }
}

async function doSearchProg() {
  const kw = searchKw.value.trim()
  if (!kw) return ElMessage.warning('请输入节目名称')
  searching.value = true
  searched.value = true
  try {
    const { data } = await epgApi.searchProgram(kw)
    if (data.error) return ElMessage.warning(data.error)
    searchResults.value = data.results || []
    if (searchResults.value.length === 0) ElMessage.info('未找到正在播放的节目')
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    searching.value = false
  }
}

function onProgramDblClick(p) {
  playChannel(selectedChannel.value)
  if (p.state === 'ended') {
    ElMessage.info('该节目已结束，正在播放频道直播（回放需源支持时移）')
  } else {
    ElMessage.success(`正在播放 ${selectedChannel.value}`)
  }
}

async function playChannel(channelName) {
  const match = channelPool.value.find(ch =>
    ch.name && (ch.name === channelName || ch.name.includes(channelName) || channelName.includes(ch.name))
  )
  if (!match || !match.url) {
    return ElMessage.warning(`未在频道列表中找到「${channelName}」的播放地址`)
  }
  // 双窗口（Phase 1）：EPG 节目播放走经纪人，打开独立播放窗（列表即选源入口）
  const api = window.pywebview?.api
  if (api && typeof api.play_channel === 'function') {
    await callNative('play_channel', {
      url: match.url, name: match.name, group: match.group || '',
    })
    playerStore.currentChannel = { url: match.url, name: match.name, group: match.group || '' }
    if (playerStore.state === 'hidden') playerStore.state = 'drawer'
    return
  }
  // 退化：浏览器环境
  playerStore.open({ url: match.url, name: match.name, group: match.group || '' }, null, -1)
  if (playerStore.state === 'hidden') playerStore.setState('drawer')
  else playerStore.exitPip()
}

function searchProgPlay(row) {
  playChannel(row.channel)
  showSearch.value = false
}

async function fetchHistory() {
  try {
    const { data } = await getHistory()
    if (data.epg && data.epg.length) {
      epgHistory.value = data.epg
      if (!epgUrl.value) epgUrl.value = data.epg[0]
    }
  } catch { /* ignore */ }
}

async function initStatus() {
  try {
    const { data } = await epgApi.getEpgStatus()
    epgStatus.value = data
    if (data.loaded) await loadChannels()
  } catch { /* ignore */ }
}

onMounted(async () => {
  await fetchHistory()
  await initStatus()
  await loadChannelPool()
})

onUnmounted(() => {
  stopStatusPolling()
  stopAutoRefresh()
})
</script>

<style scoped>
.epg-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.epg-status-card { flex-shrink: 0; }
.epg-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}
.epg-status-info { display: flex; align-items: center; gap: 10px; }
.epg-status-tag { font-weight: 600; }
.epg-status-count { font-size: 13px; color: var(--el-text-color-secondary); }
.epg-status-error { font-size: 12px; color: var(--el-color-danger); max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.epg-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.epg-main {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
}

.epg-channels-card {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.epg-channels-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
}
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 14px; font-weight: 600; }
.card-sub { font-size: 12px; color: var(--el-text-color-secondary); }
.channel-search { margin-bottom: 10px; flex-shrink: 0; }

.channel-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.channel-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  transition: all 0.15s;
}
.channel-item:hover { background: var(--el-fill-color-light); }
.channel-item.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
}
.channel-item-top { display: flex; align-items: center; justify-content: space-between; }
.channel-name { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.channel-count { font-size: 11px; color: var(--el-text-color-secondary); flex-shrink: 0; }
.channel-item-prog {
  font-size: 12px;
  color: var(--el-color-primary);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.channel-item-prog.empty { color: var(--el-text-color-placeholder); }
.now-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-danger);
  margin-right: 5px;
  animation: blink 1s infinite;
}
@keyframes blink { 50% { opacity: 0.3; } }

.epg-programs-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.epg-programs-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
}
.program-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}
.program-item {
  display: flex;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  border: 1px solid var(--el-border-color-lighter);
  transition: all 0.15s;
}
.program-item.current {
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-5);
}
.program-item.ended { opacity: 0.55; }
.program-time {
  width: 92px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
}
.program-start { font-size: 15px; font-weight: 700; color: var(--el-text-color-primary); }
.program-item.current .program-start { color: var(--el-color-danger); }
.program-stop { font-size: 12px; color: var(--el-text-color-secondary); }
.program-body { flex: 1; display: flex; flex-direction: column; gap: 6px; justify-content: center; min-width: 0; }
.program-title-row { display: flex; align-items: center; gap: 8px; }
.program-title { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dblclick-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}
.program-item:hover .dblclick-hint { opacity: 1; }
.program-progress { width: 100%; }

.search-row { display: flex; gap: 8px; }
.search-row .el-input { flex: 1; }
</style>
