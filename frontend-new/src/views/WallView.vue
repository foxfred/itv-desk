<template>
  <div class="wall-view">
    <div class="wall-toolbar">
      <span class="wall-title">频道墙</span>
      <el-select v-model="groupFilter" placeholder="全部分组" clearable size="small" style="width:150px">
        <el-option v-for="g in groups" :key="g.group" :label="g.group + ' (' + g.count + ')'" :value="g.group" />
      </el-select>
      <el-input v-model="kw" placeholder="搜索频道名/分组" clearable size="small" style="width:180px" />
      <el-checkbox v-model="favOnly" size="small" border>只看收藏</el-checkbox>
      <el-checkbox v-model="hideDead" size="small" border>隐藏死源</el-checkbox>
      <el-select v-model="cols" size="small" style="width:104px">
        <el-option v-for="n in [3, 4, 5, 6, 7, 8]" :key="n" :label="n + ' 列'" :value="n" />
      </el-select>
      <el-button size="small" :loading="loading" @click="reload">刷新</el-button>
      <el-button size="small" type="primary" plain :loading="shotRunning" @click="captureVisible">
        抓取画面
      </el-button>
      <span v-if="shotRunning" class="wall-info">画面 {{ shotDone }}/{{ shotTotal }}</span>
      <span class="wall-count">匹配 {{ list.length }} 个</span>
    </div>

    <div class="wall-grid" :style="{ gridTemplateColumns: 'repeat(' + cols + ', minmax(0, 1fr))' }">
      <div v-for="ch in visible" :key="ch.id" class="wall-card" @click="play(ch)">
        <div class="wall-thumb">
          <img v-if="shotOf(ch) && !isLocked(ch)" :src="shotOf(ch)" :alt="ch.name" loading="lazy" />
          <div v-else-if="isLocked(ch)" class="wall-noshot">
            <el-icon :size="24"><Lock /></el-icon>
            <span>已锁定</span>
          </div>
          <div v-else class="wall-noshot">
            <el-icon :size="24"><Picture /></el-icon>
            <span>无画面</span>
          </div>
          <span class="wall-ms" :class="msClass(ch)">{{ msText(ch) }}</span>
          <span v-if="badgeOf(ch)" class="wall-badge">{{ badgeOf(ch) }}</span>
          <el-tag v-if="isFav(ch)" size="small" type="warning" effect="dark" class="wall-fav">收藏</el-tag>
          <button class="wall-star" :class="{ on: isFav(ch) }" :title="isFav(ch) ? '取消收藏' : '收藏该频道'"
                  @click.stop="toggleFav(ch)">
            <el-icon :size="13"><StarFilled v-if="isFav(ch)" /><Star v-else /></el-icon>
          </button>
        </div>
        <div class="wall-name" :title="ch.name">{{ ch.name }}</div>
        <div class="wall-meta">{{ metaText(ch) }}</div>
      </div>
    </div>

    <el-empty v-if="!visible.length && !loading" description="没有符合条件的频道" :image-size="80" />

    <div v-if="visible.length < list.length" class="wall-more">
      <el-button size="small" @click="pageSize += 120">
        加载更多（还有 {{ list.length - visible.length }} 个）
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useChannelStore } from '@/stores/channels'
import { useSettingsStore } from '@/stores/settings'
import * as shotApi from '@/api/screenshots'
import * as channelApi from '@/api/channels'
import { callNative } from '@/composables/useNative'

const store = useChannelStore()
const settingsStore = useSettingsStore()
const groupFilter = ref('')
const kw = ref('')
const favOnly = ref(false)
const hideDead = ref(false)
const cols = ref(7)
const pageSize = ref(140)
const loading = ref(false)
const shotIndex = ref({})
const shotRunning = ref(false)
const shotDone = ref(0)
const shotTotal = ref(0)
let shotTimer = null

function tagsOf(ch) {
  return String((ch && ch.tag) || '').split(',').map(s => s.trim()).filter(Boolean)
}

function isFav(ch) {
  return tagsOf(ch).includes('fav')
}

function isLocked(ch) {
  const s = settingsStore.settings || {}
  if (!s.parental_enabled || !String(s.parental_pin || '').trim()) return false
  const g = Array.isArray(s.parental_locked_groups) ? s.parental_locked_groups : []
  return g.includes(ch.group || '')
}

function badgeOf(ch) {
  const t = tagsOf(ch).filter(x => x !== 'fav')
  return t.length ? t[0] : ''
}

function msNum(ch) {
  const n = parseInt(String(ch && ch.ms != null ? ch.ms : '').replace(/[^0-9]/g, ''), 10)
  return Number.isFinite(n) ? n : -1
}

function msText(ch) {
  const n = msNum(ch)
  if (n < 0) return ch && ch.status === '未检查' ? '未检查' : '—'
  return n + ' ms'
}

function msClass(ch) {
  const n = msNum(ch)
  if (n < 0) return 'unknown'
  if (n <= 300) return 'good'
  if (n <= 800) return 'mid'
  return 'bad'
}

function metaText(ch) {
  const parts = [ch.res, ch.group, ch.stack].filter(v => v && v !== '-')
  return parts.join(' · ')
}

function shotOf(ch) {
  if (!ch || !ch.url) return ''
  return shotIndex.value[ch.url] || ''
}

const groups = computed(() => {
  const map = new Map()
  for (const c of store.channels) {
    const g = c.group || '未分组'
    map.set(g, (map.get(g) || 0) + 1)
  }
  return [...map.entries()]
    .map(([group, count]) => ({ group, count }))
    .sort((a, b) => b.count - a.count)
})

const list = computed(() => {
  let arr = store.channels
  if (groupFilter.value) arr = arr.filter(c => (c.group || '未分组') === groupFilter.value)
  if (favOnly.value) arr = arr.filter(c => isFav(c))
  if (hideDead.value) arr = arr.filter(c => !(c.health && c.health.dead))
  const k = kw.value.trim().toLowerCase()
  if (k) {
    arr = arr.filter(c => [c.name, c.group].some(v => String(v || '').toLowerCase().includes(k)))
  }
  return arr
})

const visible = computed(() => list.value.slice(0, pageSize.value))

async function loadShots() {
  try {
    const { data } = await shotApi.listShots()
    shotIndex.value = data.index || {}
    const st = data.status || {}
    if (st.running) {
      shotRunning.value = true
      shotDone.value = st.done || 0
      shotTotal.value = st.total || 0
      pollShots()
    }
  } catch { /* ignore */ }
}

function pollShots() {
  if (shotTimer) clearInterval(shotTimer)
  shotTimer = setInterval(async () => {
    try {
      const { data } = await shotApi.getShotStatus()
      shotDone.value = data.done || 0
      shotTotal.value = data.total || 0
      if (!data.running) {
        clearInterval(shotTimer)
        shotTimer = null
        shotRunning.value = false
        await loadShots()
        ElMessage.success('画面抓取完成')
      }
    } catch { /* ignore */ }
  }, 1500)
}

async function captureVisible() {
  const pending = visible.value.filter(c => c.url && !shotOf(c))
  if (!pending.length) {
    ElMessage.info('当前显示的频道都已有画面')
    return
  }
  try {
    const { data } = await shotApi.captureShotBatch({ urls: pending.map(c => c.url), only_missing: false })
    if (data && data.started) {
      shotRunning.value = true
      shotDone.value = 0
      shotTotal.value = data.total || pending.length
      pollShots()
    } else {
      ElMessage.warning((data && data.error) || '抓帧启动失败')
    }
  } catch { /* ignore */ }
}

async function reload() {
  loading.value = true
  await store.refresh()
  await loadShots()
  loading.value = false
}

async function toggleFav(ch) {
  const tags = tagsOf(ch)
  const on = tags.includes('fav')
  if (on) {
    const i = tags.indexOf('fav')
    if (i >= 0) tags.splice(i, 1)
  } else {
    tags.push('fav')
  }
  const next = tags.join(',')
  try {
    const { data } = await channelApi.setTag(ch.id, next)
    ch.tag = (data && data.tag !== undefined) ? data.tag : next
    ElMessage.success(on ? '已取消收藏' : '已收藏')
  } catch {
    ElMessage.error('收藏操作失败')
  }
}

function play(ch) {
  if (!ch || !ch.url) return
  callNative('play_channel', { name: ch.name, url: ch.url, group: ch.group || '' })
}

onMounted(async () => {
  loading.value = true
  await store.fetchIfNeeded()
  await loadShots()
  loading.value = false
})
</script>

<style scoped>
.wall-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: auto;
}
.wall-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 12px;
}
.wall-title {
  font-size: 15px;
  font-weight: 600;
  margin-right: 4px;
}
.wall-info,
.wall-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.wall-count {
  margin-left: auto;
}
.wall-grid {
  display: grid;
  gap: 12px 10px;
}
.wall-card {
  cursor: pointer;
  border-radius: 6px;
  padding: 4px;
  transition: background 0.15s;
}
.wall-card:hover {
  background: var(--el-fill-color-light);
}
.wall-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}
.wall-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.wall-noshot {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.45);
  font-size: 11px;
}
.wall-ms {
  position: absolute;
  top: 4px;
  right: 4px;
  font-size: 11px;
  line-height: 1;
  padding: 3px 5px;
  border-radius: 3px;
  color: #fff;
  background: rgba(0, 0, 0, 0.6);
}
.wall-ms.good {
  background: rgba(56, 161, 105, 0.9);
}
.wall-ms.mid {
  background: rgba(214, 158, 46, 0.9);
}
.wall-ms.bad {
  background: rgba(229, 62, 62, 0.9);
}
.wall-badge,
.wall-fav {
  position: absolute;
  left: 4px;
  font-size: 11px;
  line-height: 1;
  padding: 3px 5px;
  border-radius: 3px;
  color: #fff;
}
.wall-badge {
  top: 4px;
  background: rgba(43, 125, 233, 0.9);
}
.wall-fav {
  bottom: 4px;
  background: rgba(230, 162, 60, 0.95);
}
.wall-star {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.wall-star.on {
  color: var(--el-color-warning);
}
.wall-name {
  margin-top: 5px;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wall-meta {
  margin-top: 2px;
  font-size: 11px;
  text-align: center;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wall-more {
  display: flex;
  justify-content: center;
  padding: 14px 0;
}
</style>
