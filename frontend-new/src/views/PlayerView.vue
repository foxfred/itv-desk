<template>
  <!-- PotPlayer 极简风：黑底、悬浮 chrome、静止淡出 -->
  <div
    class="player-page"
    :class="{ 'chrome-hidden': !showControls && !!currentUrl && !playError, 'is-mini': miniMode }"
    @mousemove="onChromeActivity"
    @mouseleave="scheduleHideControls"
  >
    <!-- 全窗口任意位置拖动：由 CSS -webkit-app-region: drag 实现（见下方样式） -->

    <!-- 视频主区 -->
    <div class="video-wrap" :class="{ 'video-mini': miniMode }">
      <!-- 等待态 -->
      <div v-if="!currentUrl" class="empty-state">
        <el-icon :size="48" color="rgba(255,255,255,0.25)"><VideoPlay /></el-icon>
        <p>等待播放…</p>
      </div>

      <template v-else>
        <!-- 视频元素（始终挂载，错误/加载遮罩叠在上层） -->
        <video
          ref="videoEl"
          class="video"
          autoplay
          :src="currentUrl"
          @error="onVideoError"
          @dblclick="toggleFullscreen"
          @timeupdate="onTimeUpdate"
          @loadedmetadata="onLoadedMeta"
          @waiting="onWaiting"
          @playing="onPlaying"
          @canplay="onPlaying"
        />

        <!-- 加载中遮罩（自绘 spinner） -->
        <div v-if="loading" class="loading-mask">
          <div class="spinner"></div>
        </div>

        <!-- 错误遮罩 -->
        <div v-if="playError" class="error-mask">
          <el-icon :size="44" color="#FB7185"><WarningFilled /></el-icon>
          <p class="error-title">播放失败：{{ currentName }}</p>
          <p class="error-hint">源可能已失效、编码不受支持，或受运行环境跨源/MSE 限制</p>
          <p v-if="lastHlsError" class="error-detail">错误详情：{{ lastHlsError }}</p>
          <div class="error-actions">
            <el-button size="small" type="primary" @click="retryPlay">重试</el-button>
            <el-button v-if="!proxyEnabled && !usingProxy" size="small" @click="retryViaProxy">经本地代理重试</el-button>
            <el-button v-if="isNative()" size="small" @click="playExternal">用外部播放器打开</el-button>
          </div>
        </div>

        <!-- 假直播提示条（极细顶部条，hover 时滑入） -->
        <div v-if="showFakeLiveBar" class="fake-live">
          <el-icon :size="13" color="#FBBF24"><WarningFilled /></el-icon>
          <span class="fl-text">{{ currentIsFakeLiveMarked ? '已标记为假直播' : '当前源疑似假直播' }}</span>
          <button v-if="!currentIsFakeLiveMarked" class="fl-btn" @click="markCurrentAsFakeLive(true)">标记</button>
          <button v-else class="fl-btn" @click="markCurrentAsFakeLive(false)">取消标记</button>
          <button v-if="isFakeLive && !currentIsFakeLiveMarked" class="fl-btn" @click="trustCurrentSource">信任</button>
          <button v-if="currentSources.length > 1" class="fl-btn" @click="cycleSource">切换源</button>
          <button class="fl-btn fl-x" @click="fakeLiveDismissed = true">×</button>
        </div>

        <!-- EPG 信息条：显示当前频道正在播放的节目 + 进度 + 接下来 -->
        <div class="player-epg-bar" v-if="epg.visible && currentUrl && !playError">
          <div class="epg-content">
            <span class="epg-badge">EPG</span>
            <template v-if="epg.matched">
              <span class="epg-now">正在播放</span>
              <span class="epg-title" :title="epg.current">{{ epg.current || '—' }}</span>
              <div class="epg-progress" v-if="epg.currentProg">
                <div class="epg-progress-bar" :style="{ width: epgProgress + '%' }"></div>
              </div>
              <span class="epg-time" v-if="epg.currentProg">{{ epgRemaining }}</span>
              <span class="epg-next" v-if="epg.next">· 接下来 {{ epg.next }}</span>
            </template>
            <span v-else class="epg-title epg-dim">未匹配到节目单</span>
          </div>
          <button class="epg-collapse" title="收起 EPG 信息条" @click="epg.visible = false">
            <el-icon :size="14"><ArrowDown /></el-icon>
          </button>
        </div>
        <button v-else-if="currentUrl && !playError" class="epg-reopen" title="显示 EPG 信息条" @click="epg.visible = true">
          <el-icon :size="14"><ArrowUp /></el-icon> EPG
        </button>
      </template>
    </div>

    <!-- 底部 chrome（PotPlayer 极简：进度条 + 极简按钮） -->
    <div v-if="currentUrl && !playError" class="chrome">
      <!-- 自绘进度条（支持拖拽 seek） -->
      <div class="progress" ref="progressTrackEl" @mousedown="onSeekMouseDown">
        <div class="progress-buffered" :style="{ width: bufferedPercent + '%' }"></div>
        <div class="progress-played" :style="{ width: Math.min(100, progressVal || 0) + '%' }"></div>
        <div class="progress-thumb" :style="{ left: Math.min(100, progressVal || 0) + '%' }"></div>
      </div>

      <!-- 按钮栏（完整功能版：PotPlayer 极简风，所有按钮用 ico-btn，禁用 el-button circle） -->
      <div class="ctrl-row">
        <!-- 上一频道 -->
        <button v-if="hasChannelNav" class="ico-btn" @click="prevChannel" title="上一个频道">
          <el-icon :size="14"><Back /></el-icon>
        </button>
        <!-- 下一频道 -->
        <button v-if="hasChannelNav" class="ico-btn" @click="nextChannel" title="下一个频道">
          <el-icon :size="14"><Right /></el-icon>
        </button>
        <!-- 暂停/播放 -->
        <button class="ico-btn" @click="togglePlay" :title="isPaused ? '播放' : '暂停'">
          <el-icon :size="18">
            <VideoPlay v-if="isPaused" />
            <VideoPause v-else />
          </el-icon>
        </button>
        <!-- 停止 -->
        <button class="ico-btn" @click="stopPlay" title="停止播放">
          <el-icon :size="14"><VideoPause /></el-icon>
        </button>
        <!-- 静音切换 -->
        <button class="ico-btn" :class="{ on: isMuted }" @click="toggleMute" :title="isMuted ? '取消静音' : '静音'">
          <el-icon :size="14"><MuteNotification v-if="isMuted" /><Notification v-else /></el-icon>
        </button>
        <!-- 音量滑条 -->
        <div class="volume-slider-wrap" ref="volumeSliderWrap" @mousedown.stop.prevent="onVolumeSliderMouseDown">
          <el-slider
            v-model="volume"
            :show-tooltip="false"
            :max="100"
            size="default"
            style="width:80px; flex-shrink:0"
            @input="onVolumeChange"
            @change="onVolumeChange"
          />
        </div>
        <span class="time">{{ timeText }}</span>
        <!-- 频道名 -->
        <span class="player-title" :title="currentUrl">{{ currentName }}</span>
        <el-tag v-if="currentUrlNote" size="small" type="info" effect="dark" class="player-note" :title="`源标签：${currentUrlNote}`">{{ currentUrlNote }}</el-tag>
        <!-- 收藏 -->
        <button v-if="currentChannelId" class="ico-btn" :class="{ on: isFav }" @click="toggleFav" :title="isFav ? '取消收藏' : '收藏该频道'">
          <el-icon :size="14"><StarFilled v-if="isFav" /><Star v-else /></el-icon>
        </button>
        <el-tag v-if="currentTag" size="small" type="warning" effect="dark" class="player-tag" :title="`标记：${currentTag}`">{{ currentTag }}</el-tag>
        <span class="spacer"></span>
        <!-- 媒体信息 -->
        <button class="ico-btn" @click="toggleVideoInfo" title="媒体信息（分辨率/帧率/音频）">
          <el-icon :size="14"><InfoFilled /></el-icon>
        </button>
        <!-- 清晰度 -->
        <button v-if="qualityOptions.length > 1" class="ico-btn" @click="onPickQuality(qualityOptions.find(q => q.selected)?.id || 'auto')" title="清晰度">
          <el-icon :size="14"><Monitor /></el-icon>
        </button>
        <!-- 倍速（下拉选择）：popper 单独标记 no-drag，修复 Electron 无边框窗拖拽区吞掉鼠标点击 -->
        <el-dropdown v-if="!miniMode" trigger="click" @command="onSpeedChange" class="speed-drop" popper-class="player-speed-popper" @visible-change="(v) => speedDropOpen = v">
          <button class="ico-btn" title="倍速">
            <span class="speed-label">{{ playbackSpeedText }}</span>
            <el-icon :size="10"><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="sp in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]" :key="sp" :command="sp">
                {{ sp }}x
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <!-- 外部播放器 -->
        <button v-if="isNative()" class="ico-btn" @click="playExternal" title="用外部播放器打开">
          <el-icon :size="14"><Link /></el-icon>
        </button>
        <!-- 画中画 -->
        <button v-if="pipSupported" class="ico-btn" :class="{ on: pipActive }" @click="togglePiP" title="画中画">
          <el-icon :size="14"><PictureFilled /></el-icon>
        </button>
        <!-- 置顶 -->
        <button class="ico-btn" :class="{ on: topmost }" @click="toggleTopmost" title="置顶">
          <el-icon :size="14"><Top /></el-icon>
        </button>
        <!-- 切换源 -->
        <button v-if="currentSources.length > 1" class="ico-btn" @click="cycleSource" title="切换源">
          <el-icon :size="14"><Refresh /></el-icon>
        </button>
        <!-- 迷你 -->
        <button class="ico-btn" :class="{ on: miniMode }" @click="toggleMiniMode" title="迷你模式">
          <el-icon :size="14"><Crop /></el-icon>
        </button>
        <!-- 最小化 -->
        <button class="ico-btn" @click="minimizeWindow" title="最小化窗口">
          <el-icon :size="14"><Minus /></el-icon>
        </button>
        <!-- 全屏 -->
        <button class="ico-btn" @click="toggleFullscreen" title="全屏">
          <el-icon :size="14"><FullScreen /></el-icon>
        </button>
        <!-- 关闭 -->
        <button class="ico-btn ico-close" @click="closePlayer" title="关闭">
          <el-icon :size="14"><Close /></el-icon>
        </button>
      </div>
    </div>

    <!-- 媒体信息浮层 -->
    <transition name="el-fade-in">
      <div v-if="videoInfoVisible && videoInfo.w" class="video-info-overlay">
        <div class="vi-row"><span class="vi-label">分辨率</span><span class="vi-value">{{ videoInfo.w }}×{{ videoInfo.h }}</span></div>
        <div class="vi-row" v-if="videoInfo.fps"><span class="vi-label">帧率</span><span class="vi-value">{{ videoInfo.fps }} fps</span></div>
        <div class="vi-row" v-if="audioInfoText"><span class="vi-label">音频</span><span class="vi-value">{{ audioInfoText }}</span></div>
        <div class="vi-row" v-if="videoInfo.codec"><span class="vi-label">编码</span><span class="vi-value">{{ videoInfo.codec }}</span></div>
        <div class="vi-row" v-if="videoInfo.engine"><span class="vi-label">引擎</span><span class="vi-value">{{ videoInfo.engine }}</span></div>
        <div class="vi-row" v-if="videoInfo.bitrate"><span class="vi-label">码率</span><span class="vi-value">{{ videoInfo.bitrate }} kbps</span></div>
        <div class="vi-row" v-if="videoInfo.protocol"><span class="vi-label">协议</span><span class="vi-value">{{ videoInfo.protocol }}</span></div>
        <div class="vi-row" v-if="videoInfo.latency"><span class="vi-label">延迟</span><span class="vi-value">{{ videoInfo.latency }} ms</span></div>
      </div>
    </transition>

    <!-- 四角缩放手柄（无外框模式） -->
    <div class="resize resize-tl" @mousedown.prevent="(e) => onResizeStart(e, 0, 'tl')"></div>
    <div class="resize resize-tr" @mousedown.prevent="(e) => onResizeStart(e, 1, 'tr')"></div>
    <div class="resize resize-br" @mousedown.prevent="(e) => onResizeStart(e, 2, 'br')"></div>
    <div class="resize resize-bl" @mousedown.prevent="(e) => onResizeStart(e, 3, 'bl')"></div>
  </div>
</template>

<script setup>
// P1b 组件化：支持 mini prop（画中画小窗模式，只渲染视频+最小控制）。
// P2 embedded prop：组件模式（主窗口浮层）——从 store 读频道、watch store 触发播放、
// 不启动 pop_pending/__iptvPlay（那是独立播放器窗口模式专属）。
const props = defineProps({
  mini: { type: Boolean, default: false },   // 画中画小窗模式
  embedded: { type: Boolean, default: false }, // 主窗口浮层组件模式
})
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import Hls from 'hls.js'
import flvjs from 'flv.js'
if (typeof window !== 'undefined') window.flvjs = flvjs
import dashjs from 'dashjs'
import { callNative, isNative } from '@/composables/useNative'
import { playHistoryApi } from '@/api/play_history'
import { reportHealth, setFakeLive as channelApiSetFakeLive, setTag as setChannelTag } from '@/api/channels'
import { getEpgMatch } from '@/api/epg'
import * as configApi from '@/api/config'
import { useSettingsStore } from '@/stores/settings'
import { usePlayerStore } from '@/stores/player'

const route = useRoute()
const playerStore = usePlayerStore()
const videoEl = ref(null)
const volumeSliderWrap = ref(null)
const currentUrl = ref('')
const currentName = ref('')
// 1.5: $ 后源标签（如「组播超高清-50fps」），标题栏展示
const currentUrlNote = ref('')
const volume = ref(75)
const isMuted = ref(false)
const showControls = ref(true)
const progressTrackEl = ref(null)

// PotPlayer 风格：缓冲进度（来自 videoEl.buffered）
const bufferedPercent = computed(() => {
  const v = videoEl.value
  if (!v || !v.buffered || !v.buffered.length || duration.value <= 0) return 0
  try {
    return Math.min(100, v.buffered.end(v.buffered.length - 1) / duration.value * 100)
  } catch { return 0 }
})

// chrome 激活：鼠标移动时显示并刷新隐藏计时器
function onChromeActivity() {
  if (miniMode.value) return
  showControls.value = true
  scheduleHideControls()
}

// 拖拽 seek（PotPlayer 自绘进度条）
function onSeekMouseDown(e) {
  const track = e.currentTarget
  if (!track) return
  const r = track.getBoundingClientRect()
  const ratio = (clientX) => Math.max(0, Math.min(1, (clientX - r.left) / r.width))
  const apply = (clientX) => {
    const p = ratio(clientX) * 100
    progressVal.value = p
    if (duration.value > 0) {
      videoEl.value && (videoEl.value.currentTime = p / 100 * duration.value)
    }
  }
  apply(e.clientX)
  const move = (ev) => apply(ev.clientX)
  const up = () => {
    document.removeEventListener('mousemove', move)
    document.removeEventListener('mouseup', up)
  }
  document.addEventListener('mousemove', move)
  document.addEventListener('mouseup', up)
}
// 双窗口（Phase 1）：独立播放窗置顶状态（仅 standalone 模式可用）
const topmost = ref(false)
// 全屏拖动由 CSS .player-page { -webkit-app-region: drag } 实现（见下方样式），
// 交互控件（按钮/进度条/音量滑条等）加 -webkit-app-region: no-drag。
// 不再需要 JS 拖拽逻辑。

// 无外框模式：四角缩放手柄拖拽逻辑
let resizeState = { active: false, corner: null, startW: 0, startH: 0, startX: 0, startY: 0 }
function onResizeStart(e, corner, pos) {
  if (e.button !== 0) return
  const w = window.innerWidth, h = window.innerHeight
  resizeState = { active: true, corner, startW: w, startH: h, startX: e.clientX, startY: e.clientY }
  document.addEventListener('mousemove', onGlobalResizeMove)
  document.addEventListener('mouseup', onGlobalResizeEnd)
}
function onGlobalResizeMove(e) {
  if (!resizeState.active) return
  const dx = e.clientX - resizeState.startX
  const dy = e.clientY - resizeState.startY
  // 左角（0=tl, 3=bl）拖右→收窄（-dx）；右角（1=tr, 2=br）拖右→变宽（+dx）
  const isLeft = resizeState.corner === 0 || resizeState.corner === 3
  const newW = Math.max(320, resizeState.startW + (isLeft ? -dx : dx))
  const newH = Math.max(200, resizeState.startH + (resizeState.corner < 2 ? -dy : dy))
  callNative('resize_window', newW, newH, resizeState.corner).catch(() => {})
}
function onGlobalResizeEnd() {
  document.removeEventListener('mousemove', onGlobalResizeMove)
  document.removeEventListener('mouseup', onGlobalResizeEnd)
  resizeState.active = false
}

// 无外框模式：迷你模式（小窗固定 320×200 放右下角）
const miniMode = ref(false)
function toggleMiniMode() {
  if (miniMode.value) {
    callNative('resize_window', 1100, 680, 0).catch(() => {})
  } else {
    callNative('resize_window', 320, 200, 2).catch(() => {})
  }
  miniMode.value = !miniMode.value
}

// 窗口最小化 / 停止播放
function minimizeWindow() {
  callNative('minimize').catch(() => {})
}
async function stopPlay() {
  // 停止所有播放引擎并清空当前频道
  await forceStopAll()
  currentUrl.value = ''
  currentName.value = ''
  isPaused.value = false
  loading.value = false
}
const playbackSpeed = ref(1.0)
const playbackSpeedText = ref('1.0x')
const speedDropOpen = ref(false)  // 倍速下拉是否展开（展开时 ESC 先关下拉，不退出播放器）
const timeText = ref('00:00 / 00:00')

// 播放状态
const isPaused = ref(false)
const duration = ref(0)
const progressVal = ref(0)
const isLive = ref(false)

// 频道导航（上一/下一频道）
const hasChannelNav = ref(false)
let channelIndex = -1
let channelList = []  // [{url, name, group}] 当前视图的频道列表快照

// P5: 媒体信息（6.3）
const videoInfoVisible = ref(false)
const videoInfo = reactive({ w: 0, h: 0, fps: 0, audio: null, codec: '', engine: '', bitrate: 0, protocol: '', latency: 0 })
// C3: 快速换台会话 id
let playSession = 0

// 由设置驱动的状态（默认值与 config.DEFAULTS 对齐）
const loading = ref(false)
const playError = ref(false)
const hideDelay = ref(3000)
const seekStep = ref(5000)
const volStep = ref(5)
const keyboardEnabled = ref(true)
const videoBg = ref('#000000')
const externalPath = ref('')
const externalPathManual = ref('')
const externalPref = ref('vlc')
let pollInterval = 500

// 本地后端流中继（绕过 WebView 跨源/MSE 限制）：proxyEnabled 来自设置，
// usingProxy 为「直接播放致命失败后自动回退一次」的运行期标志。
const proxyEnabled = ref(false)
let usingProxy = false
const lastHlsError = ref('')
let healthReported = false   // 每次换台仅上报一次播放结果（成功或失败）

let hls = null
let flvPlayer = null
let dashPlayer = null  // P5: DASH (mpd) 播放器实例
let playingStarted = false  // 原生播放是否已启动（探测兜底时避免重复启动）
let errorCount = 0
let errorTimer = null
let hideTimer = null
let historyRecorded = false
let pendingTimer = null
// 统一管理的 setTimeout 引用（A4 修复：换台/卸载时清理，防误触发）
let miscTimers = []

// 播放器内 EPG 信息条：随当前频道名匹配节目单，显示正在播放/进度/接下来
const epg = reactive({ visible: true, loading: false, matched: null, current: '', currentProg: null, next: '' })
const nowTick = ref(Date.now())
let epgTimer = null        // 每秒刷新进度
let epgRefreshTimer = null // 每 60 秒重新拉取节目单（节目边界切换）

// 画中画（PiP）：仅当前环境支持时显示按钮（WebView2/Chromium 支持）
const pipSupported = ref(typeof document !== 'undefined' && !!document.pictureInPictureEnabled)
const pipActive = ref(false)

// 多源故障转移：当前频道的全部源 + 当前源下标 + 已尝试失败的源集合
const currentSources = ref([])
const sourceIndex = ref(0)
let triedSources = new Set()

// 假直播检测：当前源疑似点播/循环文件时为 true（用于醒目提示与切换入口）
const isFakeLive = ref(false)
// 当前频道是否被用户手动标记为假直播（独立字段，不污染 tag）
const currentIsFakeLiveMarked = ref(false)
let looksLikeLiveNow = false

// 播放引擎（v1.0.17 起固定为 webview；mpv 已降级为外部播放器，与 VLC/PotPlayer 同级）
const engine = ref('webview')

// 提示条关闭状态：每次换台/换源重置，避免“常驻播放器”影响观看
const fakeLiveDismissed = ref(false)
// 用户“信任此源”白名单（会话内有效，可持久化到 settings.fake_live_whitelist）
const trustedSources = ref(new Set())
// 当前频道的聚合分组（source_groups：[{label, members:[url...]}]），用于源选择器标注
const currentSourceGroups = ref([])
// 当前频道的用户标记（tag，逗号分隔），用于源选择器/标题栏展示（修复：聚合后标记不显示）
const currentTag = ref('')
// R3: 收藏星标状态
const currentChannelId = ref(null)
const isFav = computed(() => (currentTag.value || '').split(',').map(s => s.trim()).includes('fav'))

async function toggleFav() {
  if (!currentChannelId.value) return
  try {
    const newTag = isFav.value ? 'fav' : ''
    // 切换 fav 标签：读取当前 tag 列表，增/删 fav
    const tags = (currentTag.value || '').split(',').map(s => s.trim()).filter(Boolean)
    if (isFav.value) {
      const i = tags.indexOf('fav')
      if (i >= 0) tags.splice(i, 1)
    } else {
      tags.push('fav')
    }
    const { data } = await setChannelTag(currentChannelId.value, tags.join(','))
    currentTag.value = (data && data.tag) || tags.join(',')
    ElMessage.success(isFav.value ? '已取消收藏' : '已收藏')
  } catch {
    ElMessage.error('收藏操作失败')
  }
}
const settingsStore = useSettingsStore()
function _wlMatch(url, w) {
  if (!w) return false
  try { return new RegExp(w).test(url) } catch { return String(url).includes(w) }
}
// 白名单：命中则不判为假直播（修复真实直播链接被误判）
function isWhitelisted(url) {
  if (!url) return false
  const wls = (settingsStore.get('fake_live_whitelist', []) || []).concat(Array.from(trustedSources.value))
  return wls.some(w => _wlMatch(url, w))
}
// 返回某源所属的聚合分组标签（空串表示未聚合）
function groupLabelOf(url) {
  for (const g of currentSourceGroups.value || []) {
    if ((g.urls || []).includes(url)) return g.name || '聚合'
  }
  return ''
}
// 是否显示假直播提示条：自动检测命中 或 用户手动标记了当前频道
const showFakeLiveBar = computed(() => {
  if (playError.value) return false
  if (currentSources.value.length <= 1 && !currentIsFakeLiveMarked.value) return false
  if (fakeLiveDismissed.value && !currentIsFakeLiveMarked.value) return false
  return isFakeLive.value || currentIsFakeLiveMarked.value
})

// ==================== P5: 清晰度 / 媒体信息 ====================
// 清晰度选项：webview 模式用 hls.levels
const qualityOptions = computed(() => {
  if (hls && hls.levels && hls.levels.length > 1) {
    return [
      { id: 'auto', label: '自动', selected: hls.currentLevel === -1 || hls.autoLevelEnabled },
      ...hls.levels.map((lv, i) => ({
        id: String(i), label: `${lv.height || lv.width || '?'}p${lv.bitrate ? ' ' + Math.round(lv.bitrate / 1000) + 'k' : ''}`,
        selected: hls.currentLevel === i,
      })),
    ]
  }
  return [{ id: 'auto', label: '自动', selected: true }]
})

const audioInfoText = computed(() => {
  const a = videoInfo.audio
  if (!a) return ''
  const ch = a.channels ? a.channels + 'ch' : ''
  const khz = a.samplerate ? Math.round(a.samplerate / 1000) + 'kHz' : ''
  return [a.codec, ch, khz].filter(Boolean).join(' ')
})

function trackLabel(t) {
  const parts = []
  if (t.title) parts.push(t.title)
  if (t.lang) parts.push(`[${t.lang}]`)
  if (t.codec) parts.push(t.codec)
  return parts.join(' ') || `轨道 ${t.id}`
}

function toggleVideoInfo() {
  videoInfoVisible.value = !videoInfoVisible.value
}

function onPickQuality(id) {
  if (id === 'auto') {
    if (hls) { hls.currentLevel = -1; hls.autoLevelCapping = -1 }
    return
  }
  if (hls) hls.currentLevel = Number(id)
}

function formatTime(s) {
  if (!isFinite(s) || s < 0) s = 0
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  const h = Math.floor(m / 60)
  if (h > 0) return `${String(h).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function onTimeUpdate() {
  const v = videoEl.value
  if (!v) return
  const ct = v.currentTime || 0
  const dur = v.duration || 0
  timeText.value = `${formatTime(ct)} / ${formatTime(dur)}`
  duration.value = isFinite(dur) ? dur : 0
  // 直播流 duration 为 Infinity，显示为实时进度
  if (isLive.value || !isFinite(dur)) {
    progressVal.value = (ct % 86400) / 86400 * 100  // 循环指示
    isLive.value = true
  } else {
    progressVal.value = dur > 0 ? (ct / dur * 100) : 0
  }
}

function togglePlay() {
  const v = videoEl.value
  if (!v) return
  if (v.paused) { v.play().catch(() => {}); isPaused.value = false }
  else { v.pause(); isPaused.value = true }
}

function onSeek(val) {
  // 拖拽中不跳转（避免卡顿），只在 change（松手）时跳转
}

function onSeekEnd(val) {
  const v = videoEl.value
  if (!v || !isFinite(v.duration)) return
  if (isLive.value) return  // 直播流不支持 seek
  v.currentTime = (val / 100) * v.duration
}

// ==================== 频道导航（上一/下一）====================
// Phase 3：选源由主窗列表驱动（列表即控制器），播放窗不再维护频道列表导航；
// channelList 仅在旧 __channelList 推送时存在（兼容），无则按钮禁用。
async function prevChannel() {
  if (!hasChannelNav.value || channelIndex <= 0) return
  channelIndex--
  await playChannelAtIndex(channelIndex)
}

async function nextChannel() {
  if (!hasChannelNav.value || channelList.length === 0 || channelIndex >= channelList.length - 1) return
  channelIndex++
  await playChannelAtIndex(channelIndex)
}

async function playChannelAtIndex(idx) {
  if (idx < 0 || idx >= channelList.length) return
  const ch = channelList[idx]
  if (ch && ch.url) {
    currentUrl.value = ch.url
    currentName.value = ch.name || '未知频道'
    currentUrlNote.value = ch.url_note || ''
    const srcs = (ch.sources && ch.sources.length) ? ch.sources : [ch.url]
    // B1 修复：主 url 不在 sources 时补到头部，保证 index=0 即主源，避免静默用错源
    const mainIdx = srcs.indexOf(ch.url)
    if (mainIdx === -1) srcs.unshift(ch.url)
    currentSources.value = srcs
    sourceIndex.value = Math.max(0, mainIdx === -1 ? 0 : mainIdx)
    // 捕获聚合分组（source_groups），用于源选择器标注
    currentSourceGroups.value = Array.isArray(ch.source_groups)
      ? ch.source_groups.filter(g => g && Array.isArray(g.urls) && g.urls.length)
      : []
    // 捕获用户标记（tag）与手动假直播标记，用于源选择器/标题栏展示
    currentTag.value = ch.tag || ''
    currentIsFakeLiveMarked.value = !!ch.is_fake_live
    triedSources = new Set()
    refreshEpg(currentName.value)
    nextTick(() => setupHls())
  }
}

// v1.0.17：mpv 已降级为外部播放器（与 VLC/PotPlayer 同级），不再作为内置引擎。
// 以下 mpv 相关代码已删除，保留注释段标记以便未来如需恢复可定位。

// ==================== 播放器内 EPG 信息条 ====================
function parseEpgDate(s) {
  if (!s || s.length < 14) return null
  const y = +s.slice(0, 4), mo = +s.slice(4, 6) - 1, d = +s.slice(6, 8)
  const h = +s.slice(8, 10), mi = +s.slice(10, 12), se = +s.slice(12, 14)
  return new Date(y, mo, d, h, mi, se)
}

async function refreshEpg(name) {
  if (!name) return
  epg.loading = true
  try {
    const { data } = await getEpgMatch(name)
    if (data && data.matched) {
      epg.matched = data.matched
      epg.current = data.current || ''
      epg.currentProg = (data.programs || []).find(p => p.state === 'current') || null
      const upcoming = (data.programs || []).filter(p => p.state === 'upcoming')
      epg.next = upcoming.length ? upcoming[0].title : ''
    } else {
      epg.matched = null
      epg.current = ''
      epg.currentProg = null
      epg.next = ''
    }
  } catch {
    epg.matched = null
  } finally {
    epg.loading = false
  }
}

const epgProgress = computed(() => {
  const cur = epg.currentProg
  const s = parseEpgDate(cur && cur.start)
  const e = parseEpgDate(cur && cur.stop)
  if (!s || !e) return 0
  const now = nowTick.value
  if (now <= s.getTime()) return 0
  if (now >= e.getTime()) return 100
  return Math.min(100, Math.round((now - s.getTime()) / (e.getTime() - s.getTime()) * 100))
})

const epgRemaining = computed(() => {
  const cur = epg.currentProg
  const e = parseEpgDate(cur && cur.stop)
  if (!e) return ''
  const ms = e.getTime() - nowTick.value
  if (ms <= 0) return '即将结束'
  const m = Math.floor(ms / 60000)
  if (m >= 60) return `剩 ${Math.floor(m / 60)}h${m % 60}m`
  return `剩 ${m}m`
})

// ==================== 多源故障转移 ====================
function switchSource(toIndex) {
  const srcs = currentSources.value
  if (!srcs.length) return
  const n = srcs.length
  const i = ((toIndex % n) + n) % n
  if (srcs[i] === currentUrl.value && i === sourceIndex.value) return
  sourceIndex.value = i
  currentUrl.value = srcs[i]
  errorCount = 0
  healthReported = false
  triedSources = new Set()   // B4 修复：手动换源时清空已尝试集合，避免故障转移跳过本可用源
  isFakeLive.value = false
  fakeLiveDismissed.value = false
  // 切换时先停止当前源播放，再加载所选源（A3 修复：先 destroy 旧实例，防回调交叉）
  if (hls) { hls.destroy(); hls = null }
  if (flvPlayer) { flvPlayer.destroy(); flvPlayer = null }
  const v = videoEl.value
  if (v) { try { v.pause() } catch (_) { /* ignore */ } }
  nextTick(() => setupHls())
}

// 从下拉列表中选择指定源切换（停止当前源、加载所选源）
function onPickSource(i) {
  switchSource(i)
}

// 容器型文件扩展名（点播/文件型，对“频道”而言大多为假直播）。
// 注意：刻意排除 .ts/.m2ts —— 它们是 IPTV 直播切片型后缀，绝大多数真实直播即为 .ts，
// 此前把它们算作“静态文件”是真实直播被误判为假直播的主因。
function isContainerFileUrl(url) {
  return /\.(mp4|mkv|avi|mov|wmv|m4v|webm|mp3|m4a)(\?[^#]*)?$/i.test(url || '')
}

// 缩短展示源地址：host + 末段路径
function shortUrl(u) {
  try {
    const m = String(u || '').match(/^https?:\/\/([^/]+)(.*)$/i)
    if (m) {
      const seg = (m[2] || '').split('?')[0].split('/').filter(Boolean).pop() || ''
      return seg ? `${m[1]}/${seg}` : m[1]
    }
  } catch (_) { /* ignore */ }
  const s = String(u || '')
  return s.length > 48 ? s.slice(0, 48) + '…' : s
}

// 假直播判定（修复真实直播被误判）：
//  - 白名单（用户信任 + 全局 fake_live_whitelist）命中 => 永不判假
//  - HLS 权威标记：清单 live=false 即点播；live=true 即真实直播（解除）
//  - FLV 直播由 flv.js isLive 处理，不在此判假
//  - 容器型文件（mp4/mkv/avi/...）且无直播关键词 => 点播/循环文件
//  - .ts/.m2ts 等直播切片型、带直播关键词的地址 => 不轻易判假
function recomputeFakeLive() {
  const url = currentUrl.value
  if (!url) { isFakeLive.value = false; return }
  // 白名单：信任的源永不判假直播
  if (isWhitelisted(url)) { isFakeLive.value = false; return }

  const lower = url.toLowerCase()
  const isHls = lower.includes('.m3u8') || lower.includes('.m3u')
  const isFlv = lower.includes('.flv') || lower.includes('.flv?')
  const isContainer = isContainerFileUrl(url)

  // 1) HLS 权威标记
  if (isHls && hls && hls.levels && hls.currentLevel >= 0) {
    const lv = hls.levels[hls.currentLevel]
    if (lv && lv.details) {
      if (lv.details.live === false) { isFakeLive.value = true; return }
      if (lv.details.live === true) { isFakeLive.value = false; return }
    }
  }
  // 2) FLV 直播不在此判假（避免真实 FLV 直播被误伤）
  if (isFlv) { isFakeLive.value = false; return }
  // 3) 容器型文件且无直播关键词 => 点播/循环文件（假直播）
  if (isContainer && !looksLikeLiveNow) { isFakeLive.value = true; return }
  // 4) 其它（.ts 直播切片 / 带直播关键词等）：不轻易判假
  isFakeLive.value = false
}

function cycleSource() {
  switchSource(sourceIndex.value + 1)
}

// 信任当前源：加入白名单（会话内 + 持久化到 settings.fake_live_whitelist），
// 既关闭提示条，又长期避免该真实直播链接被误判为假直播。
async function markCurrentAsFakeLive(isFake) {
  const u = currentUrl.value
  if (!u) return
  currentIsFakeLiveMarked.value = isFake
  // 找到当前频道 id 并回写后端（通过 channelList 中的匹配项）
  const ch = channelList.find(c => c.url === u)
  if (ch && ch.id) {
    try {
      await channelApiSetFakeLive(ch.id, isFake)
      ch.is_fake_live = isFake
      ElMessage.success(isFake ? '已标记为假直播' : '已取消假直播标记')
    } catch (e) {
      ElMessage.error('操作失败：' + (e?.message || e))
    }
  } else {
    ElMessage.warning('未找到对应频道，无法持久化标记')
  }
}

async function trustCurrentSource() {
  const u = currentUrl.value
  if (!u) return
  const next = new Set(trustedSources.value)
  next.add(u)
  trustedSources.value = next
  isFakeLive.value = false
  fakeLiveDismissed.value = true
  try {
    const cur = settingsStore.get('fake_live_whitelist', []) || []
    if (!cur.includes(u)) {
      await settingsStore.saveSettings({ fake_live_whitelist: cur.concat(u) })
    }
    ElMessage.success('已将当前源加入信任列表（长期生效）')
  } catch {
    ElMessage.success('已信任此源（本次会话生效）')
  }
}

// 主源致命失败时自动切到下一个未尝试过的备用源；无可切换则返回 false（由调用方显示错误）
function maybeFailover() {
  const srcs = currentSources.value
  if (srcs.length <= 1) return false
  for (let i = 0; i < srcs.length; i++) {
    const idx = (sourceIndex.value + 1 + i) % srcs.length
    if (!triedSources.has(srcs[idx]) && srcs[idx] !== currentUrl.value) {
      triedSources.add(currentUrl.value)            // 标记当前源已失败
      reportPlayHealth(false, 'source_failover')   // 回写失败源健康度
      ElMessage.info(`源 ${sourceIndex.value + 1} 失败，切换备用源 (${idx + 1}/${srcs.length})`)
      switchSource(idx)
      return true
    }
  }
  return false
}

function applyPlayerDefaults() {
  const v = videoEl.value
  if (!v) return
  v.volume = volume.value / 100
  v.playbackRate = playbackSpeed.value
  v.muted = isMuted.value
}

function onLoadedMeta() {
  applyPlayerDefaults()
  const v = videoEl.value
  if (v) {
    isPaused.value = v.paused
    const dur = v.duration
    if (!isFinite(dur) || dur > 86400) {
      isLive.value = true
      duration.value = 0
    } else {
      duration.value = dur || 0
    }
    // P5: webview 媒体信息（分辨率/引擎）
    if (v.videoWidth && v.videoHeight) {
      videoInfo.w = v.videoWidth
      videoInfo.h = v.videoHeight
      videoInfo.engine = 'Web'
      // R4: 同步到 store 供状态栏展示
      playerStore.videoInfo = { w: videoInfo.w, h: videoInfo.h, fps: 0, engine: 'Web' }
    }
  }
  recomputeFakeLive()
}

function setVolume(val) {
  const nv = Math.min(100, Math.max(0, Math.round(val)))
  volume.value = nv
  const v = videoEl.value
  if (v) { v.volume = nv / 100; v.muted = false }
  isMuted.value = false
}

function onVolumeChange(val) {
  setVolume(val)
}

// WebView2 兼容：鼠标拖动音量条时手动计算音量（el-slider 在 WebView2 中 @input 可能不响应拖拽）
let _volumeDragActive = false
function onVolumeSliderMouseDown(e) {
  if (e.button !== 0) return
  _volumeDragActive = true
  const handleMouseMove = (ev) => {
    if (!_volumeDragActive) return
    const wrap = volumeSliderWrap.value
    if (!wrap) return
    const rect = wrap.getBoundingClientRect()
    const pct = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width))
    volume.value = Math.round(pct * 100)
    setVolume(volume.value)
  }
  const handleMouseUp = () => {
    _volumeDragActive = false
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

// B3 修复：跨引擎统一静音——mute 前保存当前音量，unmute 时恢复（两引擎行为一致）
let _savedVolume = null

function toggleMute() {
  const v = videoEl.value
  if (!v) return
  if (v.muted) {
    // unmute：恢复 mute 前音量（若没有记录则用当前音量）
    const nv = _savedVolume != null ? _savedVolume : Math.max(volume.value, 1)
    _savedVolume = null
    v.volume = nv / 100
    volume.value = nv
  } else {
    _savedVolume = volume.value
    v.volume = 0
  }
  v.muted = !v.muted
  isMuted.value = v.muted
}

function onSpeedChange(sp) {
  const v = videoEl.value
  if (!v) return
  v.playbackRate = sp
  playbackSpeed.value = sp
  playbackSpeedText.value = `${sp}x`
}

function scheduleHideControls() {
  clearTimeout(hideTimer)
  hideTimer = setTimeout(() => {
    if (!videoEl.value || videoEl.value.paused) return
    showControls.value = false
  }, hideDelay.value)
}

function buildProxyUrl(target) {
  // 经本地后端中继（/api/stream-proxy 会同源返回并把内部地址改写），
  // 用于绕过 WebView 跨源 / MSE 边界限制（PotPlayer 能放、内置报错的同类源）。
  return `/api/stream-proxy?url=${encodeURIComponent(target)}`
}

function buildRtmpProxyUrl(target) {
  // RTMP → HTTP-FLV 中继：后端 ffmpeg 实时转码，前端 flv.js 播放。
  return `/api/rtmp-proxy?url=${encodeURIComponent(target)}`
}

// 回写播放健康度：每次换台仅上报一次（首次成功或首次致命失败），避免暂停/续播重复计数
function reportPlayHealth(success, error = null, firstFrameMs = null) {
  if (healthReported) return
  healthReported = true
  reportHealth(currentUrl.value, success, error, firstFrameMs).catch(() => {})
}

async function setupHls() {
  const v = videoEl.value
  if (!v || !currentUrl.value) return
  // C3 修复：会话 id——快速换台时旧 setupHls 的异步回调全部作废
  const sid = ++playSession
  // 清理上一轮未决的杂项 timer（A4 修复：防止旧 timer 误触发）
  miscTimers.forEach(t => clearTimeout(t))
  miscTimers = []
  // 清理上一轮 dashPlayer（防叠加）
  if (dashPlayer) { try { dashPlayer.reset() } catch (_) {}; dashPlayer = null }
  const url = currentUrl.value
  // 绑定画中画状态监听（仅在元素可用时）
  v.addEventListener('enterpictureinpicture', () => {
    pipActive.value = true
    // 进入系统画中画后隐藏播放器窗口，仅保留浮层（修复：主播放器窗口未隐藏）
    callNative('hide_window')
  })
  v.addEventListener('leavepictureinpicture', () => {
    pipActive.value = false
    // 退出画中画：先恢复可能已最小化的主应用窗口（不抢前台），
    // 再由 show_window 把播放器窗口强制置顶到前台，避免被主窗口盖住导致“滞留后台”。
    callNative('restore_main_window')
    callNative('show_window')
  })
  // 每个频道重置代理状态：仅当用户开启「本地代理播放」时预启用；
  // 致命失败时的自动回退会在本次播放内把 usingProxy 置真，不污染其它频道。
  usingProxy = !!proxyEnabled.value
  healthReported = false
  const src = usingProxy ? buildProxyUrl(url) : url
  if (hls) { hls.destroy(); hls = null }
  if (flvPlayer) { flvPlayer.destroy(); flvPlayer = null }
  playError.value = false
  loading.value = true
  errorCount = 0
  isPaused.value = false
  isLive.value = false
  isFakeLive.value = false
  fakeLiveDismissed.value = false
  duration.value = 0
  progressVal.value = 0
  // 部分原生/FLV 流在 loadedmetadata 时时长尚未就绪，2s 后再判一次假直播（纳入统一 timer 管理）
  miscTimers.push(setTimeout(recomputeFakeLive, 2000))

  const lower = url.toLowerCase()

  // ====== 协议/格式检测（更宽容的匹配）======
  // RTMP / RTMPS → 后端 ffmpeg 转为 HTTP-FLV，由 flv.js 播放
  const isRtmp = lower.startsWith('rtmp://') || lower.startsWith('rtmps://')
  if (isRtmp) {
    const flvUrl = buildRtmpProxyUrl(url)
    // 用转码后的 HTTP-FLV URL 替代原始 RTMP URL，走下方 flv.js 分支
    // （flv.js 已集成且支持 HTTP-FLV 直播流）
    if (flvjs.isSupported()) {
      flvPlayer = flvjs.createPlayer({
        type: 'flv',
        url: flvUrl,
        isLive: true,
        hasAudio: true,
        hasVideo: true,
        enableWorker: true,
        // 对齐 IPTVnator：禁用 stash + 低初始缓冲，首帧更快
        enableStashBuffer: true,
        stashInitialSize: 64 * 1024,
        lazyLoad: false,
        deferLoadAfterSourceOpen: false,
        autoCleanupSourceBuffer: true,
        autoCleanupMaxBackwardDuration: 12,
        autoCleanupMinBackwardDuration: 4,
      })
      if (flvPlayer) {
        flvPlayer.attachMediaElement(v)
        flvPlayer.on(flvjs.Events.ERROR, (_eventType, _errorDetail, _error) => {
          console.warn('[RTMP→FLV] error:', _eventType, _error)
          // RTMP 转码失败时提示用户可用外部播放器
          if (_errorDetail === flvjs.Errors.MEDIA_ERROR) {
            loading.value = false
            if (!maybeFailover()) {
              playError.value = true
              reportPlayHealth(false, `flv:${_errorDetail}`)
              ElMessage.warning('RTMP 转码失败，该源可能已离线或编码不支持，建议使用外部播放器')
            }
          }
        })
        try { flvPlayer.load(); flvPlayer.play() } catch (e) { /* ignore */ }
      } else {
        v.src = flvUrl
        v.play().catch(() => {})
      }
      return recordHistory()
    } else {
      // flv.js 不支持时降级提示外部播放器
      loading.value = false
      playError.value = true
      ElMessage.warning('该源使用 RTMP 协议，当前环境不支持 FLV 播放，请使用外部播放器（VLC/PotPlayer）打开')
      return
    }
  }

  // RTSP：HTML5 video 不支持，引导用外部播放器
  if (lower.startsWith('rtsp://')) {
    loading.value = false
    playError.value = true
    ElMessage.warning('该源使用 RTSP 协议，内置播放器不支持，请使用外部播放器（VLC/PotPlayer）打开')
    return
  }

  const isFlv = lower.includes('.flv') || lower.includes('.flv?')
  const isM3u8 = lower.endsWith('.m3u8') || lower.endsWith('.m3u') || lower.includes('.m3u8') || lower.includes('.m3u?') || lower.includes('m3u8')
  const isDash = lower.endsWith('.mpd') || lower.includes('.mpd')
  const isTs = lower.endsWith('.ts') || lower.includes('.ts?')
  // 直播流特征：含 live/realtime/stream 等关键词，或常见直播路径模式
  const looksLikeLive = /\/live\/|\/stream\/|\/realtime|\/iptv|\/proxy\//i.test(url)
  looksLikeLiveNow = looksLikeLive

  // ====== HTTP-FLV ======
  if (isFlv && flvjs.isSupported()) {
    flvPlayer = flvjs.createPlayer({
      type: 'flv',
      url: url,
      isLive: true,
      hasAudio: true,
      hasVideo: true,
      enableWorker: true,
      // 对齐 IPTVnator(mpegts.js)：禁用 stash 缓冲 + 快速呈现首帧，避免慢源缓冲滞后
      enableStashBuffer: true,
      stashInitialSize: 64 * 1024,
      lazyLoad: false,
      deferLoadAfterSourceOpen: false,
      autoCleanupSourceBuffer: true,
      autoCleanupMaxBackwardDuration: 12,
      autoCleanupMinBackwardDuration: 4,
    })
    if (flvPlayer) {
      flvPlayer.attachMediaElement(v)
      flvPlayer.on(flvjs.Events.ERROR, (_eventType, _errorDetail, _error) => {
        console.warn('[FLV] error:', _eventType, _error)
        // 网络错误 mpegts/flv 会自动重试，这里不切引擎，避免"播不出来"误判
      })
      try { flvPlayer.load(); flvPlayer.play() } catch (e) { /* ignore */ }
    } else {
      v.src = url
      v.play().catch(() => {})
    }
    return recordHistory()
  }

  // ====== HLS (m3u8) ======
  if (isM3u8) {
    // H.265 HLS 浏览器 MSE 无法硬解，先探测编码；是 H.265 则走后端 ffmpeg 转 FLV
    if (await probeHlsIsH265(url)) {
      playH264Proxy(url, src, sid, looksLikeLive)
      return recordHistory()
    }
    if (typeof Hls !== 'undefined' && Hls.isSupported()) {
      hls = new Hls({
        // 注意：不要对普通 /live/ 路径强制 LL-HLS 模式（仅真实 LL-HLS 才需要），
        // 否则非 LL 直播流会被误判为落后而持续丢帧，反而导致播放不稳定甚至报错。
        lowLatencyMode: false,
        backBufferLength: looksLikeLive ? 30 : 90,
        maxBufferLength: looksLikeLive ? 10 : 30,
        maxMaxBufferLength: 60,
        liveSyncDurationCount: looksLikeLive ? 2 : 3,
        liveMaxLatencyDurationCount: looksLikeLive ? 9 : 10,
        maxLiveSyncPlaybackRate: 1.5,
        enableWorker: true,
        fragLoadingTimeOut: 20000,
        manifestLoadingTimeOut: 15000,
        levelLoadingTimeOut: 15000,
        fragLoadingMaxRetry: 6,
        manifestLoadingMaxRetry: 3,
        levelLoadingMaxRetry: 3,
        fragLoadingRetryDelay: 1000,
        manifestLoadingRetryDelay: 1000,
        levelLoadingRetryDelay: 1000,
        // 对齐 IPTVnator：startLevel=0 从最低分层起播（先出画面再自适提升），
        // 避免高码率/慢源因 auto 挑最高层而卡在加载导致"播不出来"
        startLevel: 0,
        autoStartLoad: true,
        defaultAudioCodec: undefined,
        xhrSetup: (xhr) => { xhr.withCredentials = false },
        // 对齐 IPTVnator：无 referer 头，规避部分源带 referer 校验返回 403
        fetchSetup: (_ctx, init) => { try { init.referrerPolicy = 'no-referrer'; return init } catch { return init } },
      })
      hls.loadSource(src)
      hls.attachMedia(v)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        // C3：旧会话回调作废（快速换台防串台）
        if (sid !== playSession) return
        v.play().catch(() => {})
      })
      hls.on(Hls.Events.LEVEL_LOADED, (_evt, data) => {
        if (sid !== playSession) return
        // HLS 层级清单明确标记 live=false => 点播（假直播），反之 live=true 解除标记；
        // 白名单（用户信任/全局配置）命中时永不判假直播
        if (data && data.details) {
          if (data.details.live === false && !isWhitelisted(currentUrl.value)) isFakeLive.value = true
          else if (data.details.live === true) isFakeLive.value = false
          // Phase 4：实时统计——码率(bps→kbps) / 直播延迟(liveLatency)
          if (data.details.bitrate) videoInfo.bitrate = Math.round(data.details.bitrate / 1000)
          if (hls && hls.liveLatency !== undefined && isFinite(hls.liveLatency)) {
            videoInfo.latency = Math.max(0, Math.round(hls.liveLatency * 1000))
          }
        }
        recomputeFakeLive()
      })
      hls.on(Hls.Events.LEVEL_SWITCHED, (_evt, data) => {
        // C3：旧会话回调作废
        if (sid !== playSession) return
        // P5：不再强制最高画质（用户经清晰度下拉选择）；此处仅填充 webview 媒体信息
        const lv = data && data.level !== undefined ? hls.levels[data.level] : hls.levels[hls.currentLevel]
        if (lv) {
          videoInfo.w = lv.width || videoInfo.w
          videoInfo.h = lv.height || videoInfo.h
          videoInfo.engine = 'Web'
        }
      })
      hls.on(Hls.Events.ERROR, (event, data) => {
        // A3 修复：destroy 后已排队的旧回调直接忽略，避免操作新实例
        if (!hls) return
        // C3：旧会话回调作废
        if (sid !== playSession) return
        console.warn('[HLS] error:', data.type, data.details, data.fatal)
        lastHlsError.value = `${data.type || ''}/${data.details || ''}`
        if (data.fatal) {
          switch (data.type) {
            case Hls.Events.NETWORK_ERROR:
              // 网络错误：若尚未走代理，先经本地后端中继重试一次（绕过 WebView 取流限制）；
              // 已走代理仍失败则按原逻辑重试加载。
              if (!usingProxy) {
                usingProxy = true
                loading.value = true
                playError.value = false
                nextTick(() => setupHls())
              } else {
                miscTimers.push(setTimeout(() => { if (hls) hls.startLoad() }, 1000))
              }
              break
            case Hls.Events.MEDIA_ERROR: {
              // H.265 源探测失效兜底：HLS.js 能拉清单但 MSE 解析不出画面 → detail 包含 parse/frag/alloc 关键字，
              // 此时说明是浏览器不支持该编码（典型：H.265 HEVC），切到后端 ffmpeg 转码路径。
              const detail = (data.details || '').toLowerCase()
              if (/parse|frag|alloc/.test(detail) && !usingProxy) {
                console.warn('[HLS] media parse error，疑似 H.265，转 h264-proxy:', detail)
                cleanupHls()
                playH264Proxy(url, src, sid, looksLikeLive)
                return
              }
              try { hls.recoverMediaError() } catch (_) { /* 尝试恢复失败 */ }
              break
            }
            default:
              // 其他致命错误：若尚未走代理，先回退到本地中继重试一次；否则标记失败让用户看到
              if (!usingProxy) {
                usingProxy = true
                loading.value = true
                playError.value = false
                nextTick(() => setupHls())
              } else {
                if (!maybeFailover()) {
                  loading.value = false
                  playError.value = true
                  reportPlayHealth(false, `${data.type || ''}/${data.details || ''}`)
                }
              }
              break
          }
        }
      })
      return recordHistory()
    } else if (v.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari 原生 HLS 支持
      v.src = url
      v.play().catch(() => {})
      return recordHistory()
    }
  }

  // ====== DASH (.mpd) ======
  if (isDash) {
    // P5 补：DASH (mpd) 用 dashjs 播放（设计 6.2.1，替代原"尝试原生播放"）
    try {
      if (typeof dashjs !== 'undefined' && dashjs.MediaPlayer) {
        const dp = dashjs.MediaPlayer().create()
        dashPlayer = dp
        dp.initialize(v, url, true)
        dp.on(dashjs.MediaPlayer.events.ERROR, (ev) => {
          if (sid !== playSession) return
          console.warn('[DASH] error:', ev && ev.error)
        })
        return recordHistory()
      }
    } catch (e) {
      console.warn('[DASH] dashjs init failed:', e)
    }
    // 兜底：原生播放尝试
    ElMessage.info('检测到 DASH 格式，尝试原生播放。若失败建议使用外部播放器')
    v.src = url
    v.play().catch(() => {})
    return recordHistory()
  }

  // ====== 原生 MPEG-TS / 直接视频流 ======
  // 无扩展名/未知协议的 HTTP 源：先探测 Content-Type，若实为 HLS 清单则用 hls.js
  // （修复内网 HLS 源如 http://host:1905/xxx 被误判原生播放导致黑屏/有声无图）。
  if (!/\.(mp4|mkv|avi|mov|wmv|m4v|webm|mp3|m4a|flac|wav)(\?|#|$)/i.test(url)) {
    probeContentType(src).then((ct) => {
      if (sid !== playSession) return
      if (isHlsContentType(ct)) {
        // HLS：再探测是否为 H.265。若是 → 后端 ffmpeg 转码为 H.264 FLV（flv.js 播）；
        // 否则直接 hls.js 播放。
        probeHlsIsH265(url).then((is265) => {
          if (sid !== playSession) return
          if (is265) {
            playH264Proxy(url, src, sid, looksLikeLive)
          } else {
            playHls(url, src, sid, looksLikeLive)
          }
        })
        return
      }
      nativeFallback(v, url, src, looksLikeLive)
    })
    // 兜底：探测失败（超时/被拒）时也尝试原生播放，避免卡死无响应
    miscTimers.push(setTimeout(() => { if (sid === playSession && !hls && !flvPlayer && !playingStarted) nativeFallback(v, url, src, looksLikeLive) }, 4500))
    recordHistory()
    return
  }
  nativeFallback(v, url, src, looksLikeLive)
  recordHistory()
}

function nativeFallback(v, url, src, looksLikeLive) {
  if (!v) return
  // 部分 IPTV 源直接返回 TS 或 fMP4 流，浏览器可能支持
  v.src = src
  playingStarted = true
  v.play().then(() => {
    if (looksLikeLive) isLive.value = true
  }).catch((e) => {
    console.warn('[native] play failed:', e)
  })
}

// 用 hls.js 播放 HLS 流（供 setupHls 内探测到 Content-Type 为 HLS 时调用）
function playHls(url, src, sid, looksLive) {
  const v = videoEl.value
  playingStarted = true
  if (!v || typeof Hls === 'undefined' || !Hls.isSupported()) {
    nativeFallback(v, url, src, false)
    return
  }
  if (hls) { hls.destroy(); hls = null }
  loading.value = true
  hls = new Hls({
    lowLatencyMode: false,
    backBufferLength: looksLive ? 30 : 90,
    maxBufferLength: 10,
    maxMaxBufferLength: 60,
    liveSyncDurationCount: looksLive ? 2 : 3,
    liveMaxLatencyDurationCount: looksLive ? 9 : 10,
    maxLiveSyncPlaybackRate: 1.5,
    enableWorker: true,
    fragLoadingTimeOut: 20000,
    manifestLoadingTimeOut: 15000,
    levelLoadingTimeOut: 15000,
    defaultAudioCodec: undefined,
    xhrSetup: (x) => { x.withCredentials = false },
    fetchSetup: (_ctx, init) => { try { init.referrerPolicy = 'no-referrer'; return init } catch { return init } },
  })
  hls.loadSource(src)
  hls.attachMedia(v)
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    if (sid !== playSession) return
    loading.value = false
    v.play().catch(() => {})
  })
  hls.on(Hls.Events.ERROR, (_evt, data) => {
    if (sid !== playSession || !hls) return
    console.warn('[probe-hls] error:', data.type, data.details)
    if (data.fatal) {
      // H.265 视频 MSE 不支持等致命错误：提示用户改用 mpv/外部播放器
      loading.value = false
      if (!maybeFailover()) {
        playError.value = true
        const hint = (data.type || '') + '/' + (data.details || '')
        if (/codec|decoder|mediasource/i.test(hint)) {
          lastHlsError.value = '视频编码浏览器不支持（H.265？），请切换 mpv 或外部播放器'
        } else {
          lastHlsError.value = hint
        }
        reportPlayHealth(false, 'probe-hls:' + hint)
      }
    }
  })
  recordHistory()
}

// 走后端 h264 转码代理（源为 H.265/HLS → 后端 ffmpeg 实时转 H.264/FLV → flv.js 播放）
function playH264Proxy(url, src, sid, looksLikeLive) {
  const v = videoEl.value
  if (sid !== playSession) return
  if (!v || typeof flvjs === 'undefined' || !flvjs.isSupported()) {
    nativeFallback(v, url, src, looksLikeLive)
    return
  }
  const proxyUrl = h264ProxyUrl(url)
  const flv = flvjs.createPlayer(
    { type: 'flv', isLive: !!looksLikeLive, url: proxyUrl },
    {
      enableStashBuffer: true,
      stashInitialSize: 64 * 1024,
      lazyLoad: false,
      deferLoadAfterSourceOpen: false,
      autoCleanupSourceBuffer: true,
      autoCleanupMaxBackwardDuration: 12,
      autoCleanupMinBackwardDuration: 4,
    }
  )
  flv.attachMediaElement(v)
  flvPlayer = flv
  playingStarted = true
  flv.on(flvjs.Events.ERROR, (e, h) => {
    if (sid !== playSession) return
    console.warn('[h264-proxy] flv error', e, h)
    lastHlsError.value = '转码播放失败：' + (h?.msg || e)
    reportPlayHealth(false, 'h264-proxy:' + e)
    nativeFallback(v, url, src, looksLikeLive)
  })
  flv.on(flvjs.Events.LOADING_COMPLETE, () => {
    if (sid !== playSession) return
    reportPlayHealth(true, 'h264-proxy')
  })
  flv.load()
  flv.play().catch((err) => {
    console.warn('[h264-proxy] play rejected', err)
  })
}

async function recordHistory() {
  if (historyRecorded || !currentUrl.value) return
  historyRecorded = true
  try {
    await playHistoryApi.record({
      name: currentName.value,
      url: currentUrl.value,
      group: route.query.group || '',
    })
  } catch { /* 记录失败不影响播放 */ }
}

function onVideoError() {
  errorCount++
  // 直播源偶发瞬时错误，累计到阈值再判定为致命失败，避免误报
  if (errorCount >= 2) {
    if (!maybeFailover()) {
      loading.value = false
      playError.value = true
      ElMessage.error(`播放失败：${currentName.value || '该频道'}（源可能失效或编码不受支持）`)
    }
    clearTimeout(errorTimer)
    errorTimer = setTimeout(() => { errorCount = 0 }, 1500)  }
}

function retryPlay() {
  playError.value = false
  errorCount = 0
  nextTick(() => setupHls())
}

function retryViaProxy() {
  // 手动经本地后端中继重试（绕过 WebView 跨源/MSE 限制）
  usingProxy = true
  playError.value = false
  errorCount = 0
  nextTick(() => setupHls())
}

async function toggleFullscreen() {
  // 原生窗口级系统全屏（覆盖整个屏幕），无原生时回退浏览器全屏
  const usedNative = await callNative('toggle_fullscreen')
  if (usedNative === true) return
  const video = videoEl.value
  if (!document.fullscreenElement) {
    if (video && video.requestFullscreen) {
      video.requestFullscreen()
    } else {
      document.documentElement.requestFullscreen()
    }
  } else {
    document.exitFullscreen()
  }
}

async function togglePiP() {
  const v = videoEl.value
  if (!v) return
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture()
    } else {
      await v.requestPictureInPicture()
    }
  } catch {
    ElMessage.warning('当前环境不支持画中画，或视频尚未就绪')
  }
}

async function closePlayer() {
  const ok = await callNative('close_player')
  if (ok === undefined) {
    // 非原生环境（浏览器）直接关闭窗口
    window.close()
  }
}

// 双窗口（Phase 1）：切换独立播放窗置顶（📌）。仅 standalone 模式有效。
async function toggleTopmost() {
  const r = await callNative('set_topmost', !topmost.value)
  if (r === true) {
    topmost.value = !topmost.value
  } else if (r === false) {
    ElMessage.warning('置顶操作失败')
  }
}

// ==================== 设置驱动 / 键盘 / 外部播放 ====================
async function loadPlayerConfig() {
  try {
    const { data } = await configApi.getConfig()
    if (data.default_volume != null) volume.value = Math.min(100, Math.max(0, Number(data.default_volume) || 75))
    if (data.default_playback_speed != null) {
      playbackSpeed.value = Number(data.default_playback_speed) || 1.0
      playbackSpeedText.value = `${playbackSpeed.value}x`
    }
    if (data.player_hide_controls_delay_ms != null) hideDelay.value = Number(data.player_hide_controls_delay_ms) || 3000
    if (data.player_seek_step_ms != null) seekStep.value = Number(data.player_seek_step_ms) || 5000
    if (data.player_keyboard_volume_step != null) volStep.value = Number(data.player_keyboard_volume_step) || 5
    if (data.player_keyboard_enabled != null) keyboardEnabled.value = !!data.player_keyboard_enabled
    if (data.player_update_interval_ms != null) pollInterval = Number(data.player_update_interval_ms) || 500
    if (data.color_video_bg) videoBg.value = data.color_video_bg
    if (data.external_player) externalPref.value = data.external_player
    if (data.external_player_path) externalPathManual.value = data.external_player_path
    if (data.player_stream_proxy != null) proxyEnabled.value = !!data.player_stream_proxy
    // 双窗口新增项——播放窗口置顶
    if (data.player_window_topmost != null) {
      const wantTop = !!data.player_window_topmost
      if (wantTop !== topmost.value) {
        topmost.value = wantTop
        if (wantTop) callNative('set_topmost', true)
      }
    }
  } catch { /* ignore */ }
}

// ==================== 1.6 播放器预选（按协议自动选引擎）====================
// 协议识别：返回 { kind } —— 'rtmp'|'rtsp'|'hls'|'dash'|'flv'|'ts'|'file'|'native'
function detectProtocol(url) {
  const lower = String(url || '').toLowerCase()
  if (lower.startsWith('rtmp://') || lower.startsWith('rtmps://')) return 'rtmp'
  if (lower.startsWith('rtsp://')) return 'rtsp'
  if (lower.includes('.mpd') || lower.includes('.mpd?')) return 'dash'
  if (lower.endsWith('.m3u8') || lower.endsWith('.m3u') || lower.includes('m3u8') || lower.includes('.m3u?')) return 'hls'
  if (lower.includes('.flv') || lower.includes('.flv?')) return 'flv'
  if (lower.endsWith('.ts') || lower.includes('.ts?') || lower.endsWith('.m2ts')) return 'ts'
  if (/\.(mp4|mkv|avi|mov|wmv|m4v|webm|mp3|m4a|flac|wav)(\?|$)/i.test(url)) return 'file'
  return 'native'
}

// 探测 HTTP(S) 源的真实 Content-Type：用于无扩展名 URL（如内网 HLS 源
// http://host:port/12345）识别实际协议，避免被误判为原生播放而黑屏/无声。
// 返回 Promise<string>；失败返回 ''。
function probeContentType(url, timeoutMs = 4000) {
  return new Promise((resolve) => {
    let timer = null
    try {
      const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null
      if (ctrl && timeoutMs) timer = setTimeout(() => ctrl.abort(), timeoutMs)
      fetch(url, { method: 'GET', cache: 'no-store', redirect: 'follow',
                   headers: { 'Range': 'bytes=0-1024', 'User-Agent': 'Mozilla/5.0' },
                   signal: ctrl ? ctrl.signal : undefined })
        .then((res) => {
          if (timer) clearTimeout(timer)
          const ct = (res.headers.get('content-type') || '').toLowerCase()
          resolve(ct)
        })
        .catch(() => { if (timer) clearTimeout(timer); resolve('') })
    } catch (e) { if (timer) clearTimeout(timer); resolve('') }
  })
}

// 判断 Content-Type 是否为 HLS 清单
function isHlsContentType(ct) {
  return /mpegurl|mp2t|x-mpegurl|vnd\.apple\.mpegurl/.test(ct || '')
}

// 探测 HLS 主清单是否 H.265 编码：URL 自身含 h265/hevc/videocodec=h26 标记直接判定；
// 否则抓取主清单文本做关键字匹配；主清单不含 codec 信息时进一步抓取首个 TS 分片头字节，
// 检测 HEVC NAL 单元起始码（0x42 之后 NAL 类型 0x1E-0x21 为 HEVC）→ 这是最可靠的判据。
// 返回 Promise<boolean>。
function probeHlsIsH265(url, timeoutMs = 5000) {
  const u = (url || '').toLowerCase()
  if (/h265|hevc|videocodec=h26|codec=hev1|codecs=hev1/.test(u)) return Promise.resolve(true)
  return new Promise((resolve) => {
    let timer = null
    try {
      const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null
      if (ctrl && timeoutMs) timer = setTimeout(() => ctrl.abort(), timeoutMs)
      fetch(url, { method: 'GET', cache: 'no-store',
                   headers: { 'User-Agent': 'Mozilla/5.0' },
                   signal: ctrl ? ctrl.signal : undefined })
        .then((res) => {
          if (timer) clearTimeout(timer)
          if (!res.ok) { resolve(false); return }
          return res.arrayBuffer()
        })
        .then((buf) => {
          const text = decodeText(buf)
          const low = text.toLowerCase()
          if (/h265|hevc|videocodec=h26|codec=hev1|codecs=.{0,8}hev1/.test(low)) {
            resolve(true); return
          }
          // 主清单没标注 codec，取首个 TS 分片头检测 HEVC NAL
          return probeTsSegmentH265(url, text)
            .then((segResult) => resolve(segResult))
            .catch(() => resolve(false))
        })
        .catch(() => { if (timer) clearTimeout(timer); resolve(false) })
    } catch (e) { if (timer) clearTimeout(timer); resolve(false) }
  })
}

// 从 HLS 清单里抽出相对/绝对路径的第一个 TS 分片，取前 32KB 检测 HEVC NAL
function probeTsSegmentH265(baseUrl, manifestText) {
  return new Promise((resolve) => {
    try {
      const lines = manifestText.split(/\r?\n/)
      let firstTsUrl = null
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim()
        if (line && !line.startsWith('#') && /\.(ts|TS|m2ts|M2TS|mp4|MP4|mp4s|M4S)(\?|#|$)/i.test(line)) {
          firstTsUrl = line
          break
        }
        // 兼容 EXT-X-MEDIA:URI="xxx.ts" 或 EXT-X-MAP:URI
        const m = line.match(/URI="([^"]+\.(?:ts|m2ts|mp4|mp4s))[^"]*"/i)
        if (m && !firstTsUrl) firstTsUrl = m[1]
      }
      if (!firstTsUrl) { resolve(false); return }
      const segUrl = resolveUrl(baseUrl, firstTsUrl)
      const segCtrl = typeof AbortController !== 'undefined' ? new AbortController() : null
      let segTimer = setTimeout(() => segCtrl && segCtrl.abort(), 4000)
      fetch(segUrl, { method: 'GET', cache: 'no-store',
                       headers: { 'User-Agent': 'Mozilla/5.0' },
                       signal: segCtrl ? segCtrl.signal : undefined })
        .then((res) => {
          if (segTimer) clearTimeout(segTimer)
          if (!res.ok) { resolve(false); return }
          return res.arrayBuffer().then((b) => new Uint8Array(b))
        })
        .then((bytes) => {
          // 检查前 32KB 里是否有 HEVC NAL 起始码
          const len = Math.min(bytes.length, 32 * 1024)
          for (let i = 0; i < len - 2; i++) {
            // HEVC NAL header：Type = (nalu_type >> 1) & 63，HEVC 类型范围 16..40（含 IDR/WRD/BLA/CRA/...）
            const nalType = (bytes[i] >> 1) & 0x3f
            if (nalType >= 16 && nalType <= 40) {
              resolve(true); return
            }
            // 也接受 H264 起始码后跟 HEVC NAL 头（0x00 0x00 0x01 或 0x00 0x00 0x00 0x01 后字节）
            if (i + 4 < len && bytes[i] === 0 && bytes[i + 1] === 0 && bytes[i + 2] === 1) {
              const t = (bytes[i + 3] >> 1) & 0x3f
              if (t >= 16 && t <= 40) { resolve(true); return }
            }
          }
          resolve(false)
        })
        .catch(() => { if (segTimer) clearTimeout(segTimer); resolve(false) })
    } catch (e) { resolve(false) }
  })
}

function decodeText(buf) {
  try {
    return new TextDecoder('utf-8', { fatal: false }).decode(buf)
  } catch { return '' }
}

function resolveUrl(base, relative) {
  try {
    return new URL(relative, base).href
  } catch {
    return relative
  }
}

// 构建 h265 → h264 转码代理 URL（后端 ffmpeg 实时转码，输出 HTTP-FLV）
function h264ProxyUrl(srcUrl) {
  return '/api/h264-proxy?url=' + encodeURIComponent(srcUrl)
}

// ==================== 统一播放入口 ====================
// 引擎固定 webview（v1.0.17 起 mpv 已降级为外部播放器，与 VLC/PotPlayer 同级）。
async function startPlayback() {
  const url = currentUrl.value || ''
  if (!url) return
  setupHls()
}

function onWaiting() { loading.value = true }
function onPlaying() { loading.value = false; playError.value = false; isPaused.value = false; reportPlayHealth(true) }

function onKeyDown(e) {
  const tag = (e.target && e.target.tagName) || ''
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag)) return
  // ESC 退出播放器：倍速下拉展开时先交给下拉关闭；全屏时先退全屏；否则关窗
  if (e.key === 'Escape' || e.key === 'Esc') {
    if (speedDropOpen.value) return
    if (document.fullscreenElement) { document.exitFullscreen(); return }
    e.preventDefault()
    closePlayer()
    return
  }
  if (!keyboardEnabled.value) return
  const v = videoEl.value
  if (!v) return
  switch (e.key) {
    case ' ':
    case 'Spacebar':
      e.preventDefault()
      if (v.paused) { v.play().catch(() => {}); isPaused.value = false }
      else { v.pause(); isPaused.value = true }
      break
    case 'ArrowLeft':
      e.preventDefault()
      v.currentTime = Math.max(0, (v.currentTime || 0) - seekStep.value / 1000)
      break
    case 'ArrowRight':
      e.preventDefault()
      v.currentTime = (v.currentTime || 0) + seekStep.value / 1000
      break
    case 'ArrowUp':
      e.preventDefault()
      setVolume(volume.value + volStep.value)
      break
    case 'ArrowDown':
      e.preventDefault()
      setVolume(volume.value - volStep.value)
      break
    case 'm': case 'M':
      toggleMute()
      break
    case 'f': case 'F':
      toggleFullscreen()
      break
  }
}

async function playExternal() {
  if (!currentUrl.value) return
  let path = externalPath.value
  // 优先使用设置中手动指定的路径
  if (!path && externalPathManual.value) {
    path = externalPathManual.value
  }
  if (!path) {
    try {
      const { data } = await configApi.getPlayers()
      path = externalPref.value === 'potplayer' ? data.pot
        : externalPref.value === 'mpv' ? data.mpv : data.vlc
    } catch { /* ignore */ }
  }
  if (!path) {
    ElMessage.warning('未检测到 VLC / PotPlayer，请先安装或在「系统设置→播放器」中手动指定路径')
    return
  }
  externalPath.value = path
  const ok = await callNative('play_external', currentUrl.value, path)
  if (ok === undefined) ElMessage.info('仅桌面版支持外部播放')
}

// Phase 3：跨窗口状态上报——播放窗把 引擎/频道/分辨率 推给主窗状态栏。
// Pinia store 不跨窗口共享，主窗状态栏只能靠 Python 经纪人（PlayerApi.notify_main）转发。
watch(
  [engine, () => currentName.value, () => currentUrl.value, () => currentUrlNote.value, () => videoInfo.w, () => videoInfo.h, () => videoInfo.fps, () => videoInfo.bitrate],
  () => {
    callNative('notify_main', JSON.stringify({
      engine: engine.value,
      name: currentName.value,
      url: currentUrl.value,
      note: currentUrlNote.value,
      w: videoInfo.w || 0,
      h: videoInfo.h || 0,
      fps: videoInfo.fps || 0,
      bitrate: videoInfo.bitrate || 0,
    }))
  },
  { deep: true }
)

onMounted(async () => {
  // ===== 独立播放器窗口模式（双窗口架构，Phase 1+）=====
  // 全局 push 入口：后端 open_player 通过 evaluate_js 直接推送新频道，换台即时生效
  window.__iptvPlay = playRow
  // D4 修复：后端 close_player destroy 前调用的资源清理入口（标题栏 X 兜底）
  window.__iptvCleanup = () => {
    if (hls) { hls.destroy(); hls = null }
    if (flvPlayer) { flvPlayer.destroy(); flvPlayer = null }
  }
  window.addEventListener('keydown', onKeyDown)

  // 优先从原生 API 取待播放频道（open_player 传入），否则用路由参数
  try {
    if (isNative()) {
      const pending = await callNative('pop_pending')
      if (pending && pending.url) {
        currentUrl.value = pending.url
        currentName.value = pending.name || '未知频道'
      }
    }
  } catch { /* ignore */ }

  if (!currentUrl.value && route.query.url) {
    currentUrl.value = route.query.url
    currentName.value = route.query.name || '未知频道'
  }

  // 读取播放器设置（音量/倍速/隐藏延时/快捷键步长等）
  await loadPlayerConfig()
  // 读取全局设置：获取 fake_live_whitelist（真实直播链接白名单，修复误判）
  try { await settingsStore.fetchSettings() } catch { /* ignore */ }
  if (currentUrl.value) applyPlayerDefaults()

  if (currentUrl.value) {
    await startPlayback()
  }

  // 持续轮询待播频道：每次 open_player 换台都会把新频道放入 _pending，
  // 轮询不能因 currentUrl 已有值而停止，否则只播放第一个频道无法换台
  startPendingPolling()

  // EPG 信息条：每秒更新进度，每 60 秒重新拉取节目单（捕捉节目边界切换）
  epgTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
  epgRefreshTimer = setInterval(() => { if (currentName.value) refreshEpg(currentName.value) }, 60000)
})

function startPendingPolling() {
  if (!isNative()) return
  clearInterval(pendingTimer)
  pendingTimer = setInterval(async () => {
    try {
      const pending = await callNative('pop_pending')
      if (pending && pending.url) {
        playRow(pending)
      }
    } catch { /* ignore */ }
  }, pollInterval)
}

async function playRow(row, list = null, idx = -1) {
  if (!row || !row.url) return
  // 切台前清理上一播放源，避免多音频流叠加（BUG3）
  if (hls || flvPlayer || dashPlayer) {
    await forceStopAll()
  }
  // row 可能携带 __channelList / __index（run.py open_player 附加的元数据）
  const meta = (row.__channelList && row.__index !== undefined)
    ? { list: row.__channelList, index: row.__index }
    : null
  if (meta) {
    list = meta.list; idx = meta.index
  }

  currentUrl.value = row.url
  currentName.value = row.name || '未知频道'
  currentUrlNote.value = row.url_note || ''
  // Phase 4：协议识别（统计面板展示，HLS/RTMP/FLV/MP4...）
  videoInfo.protocol = detectProtocol(currentUrl.value).toUpperCase()
  refreshEpg(currentName.value)
  // 接收频道列表快照用于上/下一频道
  if (list && Array.isArray(list) && list.length > 0) {
    channelList = list.map(ch => ({
      id: ch.id,
      url: ch.url, name: ch.name || '未知频道', group: ch.group || '',
      sources: (ch.sources && ch.sources.length) ? ch.sources : [ch.url],
      source_groups: Array.isArray(ch.source_groups) ? ch.source_groups : [],
      tag: ch.tag || '',
      is_fake_live: !!ch.is_fake_live,
      url_note: ch.url_note || '',
    }))
    hasChannelNav.value = true
    channelIndex = idx >= 0 ? idx : (channelList.findIndex(ch => ch.url === row.url))
  }
  // 多源故障转移：记录当前频道全部源与当前源下标
  const srcs = (row.sources && row.sources.length) ? row.sources : [row.url]
  // B1/B5 修复：主 url 不在 sources 时补到头部；same 判定带 source 维度（新旧 url+index 双对比）
  const oldUrl = currentUrl.value
  const oldSourceIndex = sourceIndex.value
  const mainIdx = srcs.indexOf(row.url)
  if (mainIdx === -1) srcs.unshift(row.url)
  currentSources.value = srcs
  sourceIndex.value = Math.max(0, mainIdx === -1 ? 0 : mainIdx)
  const same = row.url === oldUrl && sourceIndex.value === oldSourceIndex
  // 捕获聚合分组（source_groups），用于源选择器标注
  currentSourceGroups.value = Array.isArray(row.source_groups)
    ? row.source_groups.filter(g => g && Array.isArray(g.urls) && g.urls.length)
    : []
  // 捕获用户标记（tag）与手动假直播标记，用于源选择器/标题栏展示
  currentTag.value = row.tag || ''
  currentChannelId.value = row.id != null ? row.id : null  // R3: 收藏星标需要 id
  currentIsFakeLiveMarked.value = !!row.is_fake_live
  fakeLiveDismissed.value = false
  triedSources = new Set()
  if (!same) {
    nextTick(() => startPlayback())
  } else if (!hls && videoEl.value) {
    setupHls()
  }
}

// BUG3 修复：轻量状态重置（切台/切源时清零，防旧状态残留）
function resetPlayState() {
  playError.value = false
  loading.value = false
  isPaused.value = false
  duration.value = 0
  progressVal.value = 0
  errorCount = 0
  healthReported = false
  isFakeLive.value = false
  triedSources = new Set()
  // H修复：换台/切源时清零媒体信息，防旧分辨率残留状态栏
  videoInfo.w = 0
  videoInfo.h = 0
  videoInfo.fps = 0
  videoInfo.codec = ''
  videoInfo.bitrate = 0
  videoInfo.latency = 0
  playerStore.videoInfo = { w: 0, h: 0, fps: 0, engine: '' }
}

// BUG3 修复：统一释放所有播放源（hls/flvPlayer），避免多音频流叠加
// 切台/关闭时调用，确保旧源彻底停止
async function forceStopAll() {
  // 1) 销毁 hls.js
  if (hls) { try { hls.destroy() } catch (_) {} ; hls = null }
  // 2) 销毁 flv.js + dash.js + 清空 <video> src
  if (flvPlayer) { try { flvPlayer.destroy() } catch (_) {} ; flvPlayer = null }
  if (dashPlayer) { try { dashPlayer.reset() } catch (_) {} ; dashPlayer = null }
  const v = videoEl.value
  if (v) {
    try { v.pause() } catch (_) {}
    try { v.removeAttribute('src') } catch (_) {}
    try { v.load() } catch (_) {}
  }
  // 3) 重置状态
  resetPlayState()
}

onUnmounted(() => {
  // embedded 模式不注册 __iptvPlay/__iptvCleanup（那是独立窗口模式专属）
  if (window.__iptvPlay === playRow) delete window.__iptvPlay
  if (window.__iptvCleanup) delete window.__iptvCleanup
  window.removeEventListener('keydown', onKeyDown)
  // BUG3：统一释放所有源（hls/flvPlayer）+ timer + EPG，避免残留
  forceStopAll()
  if (pendingTimer) { clearInterval(pendingTimer); pendingTimer = null }
  if (epgTimer) { clearInterval(epgTimer); epgTimer = null }
  if (epgRefreshTimer) { clearInterval(epgRefreshTimer); epgRefreshTimer = null }
})

</script>

<style>
/* 全局压底色：播放器窗口任何时刻不露白底（含 WebView2 加载前/首帧前的纯色背景） */
html, body, #app { background: #000 !important; margin: 0 !important; padding: 0 !important; }
/* 倍速下拉弹层 teleport 到 body，悬浮在 -webkit-app-region:drag 区上方时
   鼠标点击会被 Electron 窗口拖拽吞掉（键盘可选、鼠标点不动的根因）。
   必须显式 no-drag 才能恢复鼠标。 */
.player-speed-popper { -webkit-app-region: no-drag; }
.player-speed-popper .el-dropdown-menu__item { cursor: pointer; }
</style>

<style scoped>
/* =========================================================
   PotPlayer 极简风：黑底铺满、悬浮 chrome、静止 3s 淡出
   ========================================================= */

.player-page {
  height: 100%; background: #000; position: relative; overflow: hidden;
  user-select: none;
  /* 全屏任意位置拖动（Electron 无边框窗）：等价旧版 pywebview easy_drag=True。
     可交互控件需加 -webkit-app-region: no-drag 才能正常点击（见 .ico-btn 等） */
  -webkit-app-region: drag;
}

/* 视频主区（铺满，object-fit: contain 由 video 元素负责） */
.video-wrap {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: #000;
  -webkit-app-region: drag;  /* 视频区域按住可拖动整窗（等价 easy_drag） */
}
.video {
  width: 100%; height: 100%; object-fit: contain; outline: none;
  background: #000;  /* 防 letterbox 留白（部分浏览器默认白底） */
}

/* 等待态（极简居中） */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; color: rgba(255,255,255,0.4); font-size: 13px;
}

/* 加载中遮罩（自绘 spinner，无依赖） */
.loading-mask {
  position: absolute; inset: 0; z-index: 3;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.35);
  pointer-events: none;
}
.spinner {
  width: 38px; height: 38px; border-radius: 50%;
  border: 3px solid rgba(255,255,255,0.15);
  border-top-color: rgba(255,255,255,0.85);
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 错误遮罩（居中卡片） */
.error-mask {
  position: absolute; inset: 0; z-index: 5;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; padding: 24px; text-align: center; color: #fff;
  background: rgba(0,0,0,0.78);
}
.error-mask p { margin: 0; }
.error-title { font-size: 15px; font-weight: 600; }
.error-hint { font-size: 12px; color: #bbb; max-width: 480px; }
.error-detail { font-size: 11px; color: #888; max-width: 520px; word-break: break-all; margin-top: 4px; }
.error-actions { display: flex; gap: 10px; margin-top: 12px; -webkit-app-region: no-drag; }
.error-actions :deep(.el-button) {
  color: #fff; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
}
.error-actions :deep(.el-button:hover) { background: rgba(255,255,255,0.2); }
.error-actions :deep(.el-button--primary) {
  background: var(--el-color-primary); border-color: var(--el-color-primary);
}

/* 假直播提示条（顶部极细） */
.fake-live {
  position: absolute; top: 14px; left: 14px; right: 14px; z-index: 6;
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: 6px;
  background: rgba(120, 53, 15, 0.92); color: #fff;
  font-size: 12px; backdrop-filter: blur(8px);
  animation: slideDown .2s ease-out;
  -webkit-app-region: no-drag;
}
@keyframes slideDown { from { transform: translateY(-10px); opacity: 0; } to { transform: none; opacity: 1; } }
.fake-live .fl-text { flex: 1; }
.fake-live .fl-btn {
  background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.18);
  color: #fff; padding: 2px 8px; font-size: 11px; border-radius: 4px;
  cursor: pointer; transition: background .15s;
}
.fake-live .fl-btn:hover { background: rgba(255,255,255,0.25); }
.fake-live .fl-x { padding: 2px 7px; }

/* ====== EPG 信息条 ====== */
.player-epg-bar {
  position: absolute; top: 0; left: 0; right: 0; z-index: 6;
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; color: #fff;
  background: linear-gradient(to bottom, rgba(0,0,0,0.8), rgba(0,0,0,0));
  font-size: 13px;
  -webkit-app-region: no-drag;
}
.epg-content { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.epg-badge {
  flex-shrink: 0; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
  background: var(--el-color-primary); color: #fff; border-radius: 4px; padding: 2px 6px;
}
.epg-now { flex-shrink: 0; color: #cbd5e1; font-size: 12px; }
.epg-title {
  flex-shrink: 0; max-width: 30%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 600;
}
.epg-dim { color: #94a3b8; font-weight: 400; }
.epg-progress {
  flex: 1; min-width: 60px; height: 4px; border-radius: 2px;
  background: rgba(255,255,255,0.22); overflow: hidden;
}
.epg-progress-bar {
  height: 100%; background: var(--el-color-primary); border-radius: 2px;
  transition: width 1s linear;
}
.epg-time { flex-shrink: 0; font-size: 12px; color: #cbd5e1; font-family: 'Consolas', monospace; }
.epg-next {
  flex-shrink: 0; max-width: 25%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: #94a3b8; font-size: 12px;
}
.epg-collapse { color: #fff; flex-shrink: 0; border: 0; background: transparent; cursor: pointer; }
.epg-collapse:hover { color: var(--el-color-primary); }
.epg-reopen {
  position: absolute; top: 10px; right: 14px; z-index: 6; color: #fff;
  background: rgba(0,0,0,0.5); border-radius: 4px; border: 0; cursor: pointer;
  padding: 2px 8px; font-size: 12px; display: inline-flex; align-items: center; gap: 4px;
  -webkit-app-region: no-drag;
}
.epg-reopen:hover { color: var(--el-color-primary); }

/* ===== 底部 chrome（PotPlayer 极简） ===== */
.chrome {
  position: absolute; left: 0; right: 0; bottom: 0; z-index: 5;
  padding: 0 14px 10px;
  background: linear-gradient(to top, rgba(0,0,0,0.78), rgba(0,0,0,0));
  opacity: 1; transition: opacity .3s ease;
  -webkit-app-region: no-drag;
}
.player-page.chrome-hidden .chrome { opacity: 0; pointer-events: none; }

/* 自绘进度条 */
.progress {
  position: relative; height: 16px; cursor: pointer; margin: 0 0 6px;
  display: flex; align-items: center;
  -webkit-app-region: no-drag;
}
.progress-buffered {
  position: absolute; left: 0; top: 50%; transform: translateY(-50%);
  height: 3px; border-radius: 2px; background: rgba(255,255,255,0.22);
  pointer-events: none; transition: width .4s;
}
.progress-played {
  position: absolute; left: 0; top: 50%; transform: translateY(-50%);
  height: 3px; border-radius: 2px;
  background: linear-gradient(to right, #60a5fa, #38bdf8);
  pointer-events: none; box-shadow: 0 0 6px rgba(56,189,248,0.45);
}
.progress-thumb {
  position: absolute; top: 50%; transform: translate(-50%, -50%);
  width: 11px; height: 11px; border-radius: 50%;
  background: #fff; box-shadow: 0 0 4px rgba(0,0,0,0.5);
  opacity: 0; transition: opacity .15s, transform .15s;
}
.progress:hover .progress-thumb { opacity: 1; }
.progress:hover .progress-played { height: 4px; }
.progress:hover .progress-buffered { height: 4px; }

/* 按钮栏 */
.ctrl-row {
  display: flex; align-items: center; gap: 6px; color: #fff;
}
.ico-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 4px; border: 0; padding: 0;
  background: transparent; color: rgba(255,255,255,0.85); cursor: pointer;
  transition: background .15s, color .15s;
  -webkit-app-region: no-drag;
}
.ico-btn:hover { background: rgba(255,255,255,0.13); color: #fff; }
.ico-btn.on { color: #38bdf8; }
.ico-btn.ico-close:hover { background: rgba(220,38,38,0.7); color: #fff; }
.time {
  font-size: 12px; color: rgba(255,255,255,0.75);
  font-family: 'Consolas', 'Cascadia Mono', 'Menlo', monospace;
  margin-left: 4px; letter-spacing: 0.5px; font-variant-numeric: tabular-nums;
}
.spacer { flex: 1; }

/* 音量滑条 */
.volume-slider-wrap { width: 80px; flex-shrink: 0; cursor: pointer; -webkit-app-region: no-drag; }
.volume-slider-wrap :deep(.el-slider__runway) { background-color: rgba(255,255,255,0.2); height: 3px; }
.volume-slider-wrap :deep(.el-slider__bar) { background-color: #60a5fa; height: 3px; }
.volume-slider-wrap :deep(.el-slider__button) { width: 10px; height: 10px; border: 2px solid #fff; }

/* 频道信息 */
.player-title { font-size: 12px; color: rgba(255,255,255,0.8); margin-left: 6px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.player-note { font-size: 11px; margin-left: 4px; }
.player-tag { font-size: 11px; margin-left: 4px; }

/* 倍速标签 */
.speed-label { font-size: 11px; color: rgba(255,255,255,0.8); font-weight: 600; }

/* 媒体信息浮层 */
.video-info-overlay {
  position: absolute; right: 20px; bottom: 80px; z-index: 20;
  background: rgba(8, 10, 14, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px; padding: 14px 18px; font-size: 13px;
  min-width: 220px; box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6);
  -webkit-app-region: no-drag;
}
.vi-row { display: flex; justify-content: space-between; gap: 20px; padding: 4px 0; align-items: center; }
.vi-label { color: #94a3b8; font-size: 12px; }
.vi-value { color: #f1f5f9; font-size: 13px; font-family: 'Consolas', monospace; font-weight: 600; }

/* ===== 四角缩放手柄 ===== */
.resize {
  position: absolute; width: 16px; height: 16px; z-index: 6;
  pointer-events: auto; opacity: 0; transition: opacity .2s;
  -webkit-app-region: no-drag;
}
.resize-tl { top: 0; left: 0; cursor: nw-resize; }
.resize-tr { top: 0; right: 0; cursor: ne-resize; }
.resize-br { bottom: 0; right: 0; cursor: se-resize; }
.resize-bl { bottom: 0; left: 0; cursor: sw-resize; }
.player-page:hover .resize { opacity: 0.5; }
.player-page:hover .resize:hover { opacity: 1; }

/* 迷你模式：透明、极小、屏蔽 chrome（仅留视频 + 关闭按钮） */
.player-page.is-mini .chrome { padding: 0 6px 4px; background: transparent; }
.player-page.is-mini .fake-live { display: none; }
.player-page.is-mini .ico-btn { width: 24px; height: 24px; }
.player-page.is-mini .ico-btn:not(.ico-close):not(.ico-btn) { display: none; }  /* 迷你模式仅显示关闭 */

/* 兼容旧类名引用（保留 player-video-wrap-mini 等以防外部 CSS 引用） */
.video-mini { /* 等同迷你 */ }
</style>
