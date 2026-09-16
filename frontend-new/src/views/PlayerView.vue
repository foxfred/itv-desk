<template>
  
  <div
    class="player-page"
    :class="{ 'chrome-hidden': !showControls && !!currentUrl && !playError, 'is-mini': miniMode }"
    @mousemove="onChromeActivity"
    @mouseleave="scheduleHideControls"
  >
    

    
    <div class="video-wrap" :class="{ 'video-mini': miniMode }">
      
      <div v-if="!currentUrl" class="empty-state">
        <el-icon :size="48" color="rgba(255,255,255,0.25)"><VideoPlay /></el-icon>
        <p>等待播放…</p>
      </div>

      <template v-else>
        
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

        
        <div v-if="loading" class="loading-mask">
          <div class="spinner"></div>
        </div>

        
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

        
        <div v-if="showFakeLiveBar" class="fake-live">
          <el-icon :size="13" color="#FBBF24"><WarningFilled /></el-icon>
          <span class="fl-text">{{ currentIsFakeLiveMarked ? '已标记为假直播' : '当前源疑似假直播' }}</span>
          <button v-if="!currentIsFakeLiveMarked" class="fl-btn" @click="markCurrentAsFakeLive(true)">标记</button>
          <button v-else class="fl-btn" @click="markCurrentAsFakeLive(false)">取消标记</button>
          <button v-if="isFakeLive && !currentIsFakeLiveMarked" class="fl-btn" @click="trustCurrentSource">信任</button>
          <button class="fl-btn fl-x" @click="fakeLiveDismissed = true">×</button>
        </div>

        
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
          <el-icon :size="14">
            <svg viewBox="0 0 16 16"><rect x="3.5" y="3.5" width="9" height="9" rx="1" fill="currentColor" /></svg>
          </el-icon>
        </button>
        <!-- 静音切换 -->
        <button class="ico-btn" :class="{ on: isMuted }" @click="toggleMute" :title="isMuted ? '取消静音' : '静音'">
          <el-icon :size="14">
            <!-- 静音：喇叭+叉 -->
            <svg v-if="isMuted" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
              <path d="M2 6v4h3l4 3V3L5 6H2z" fill="currentColor" stroke="none" />
              <line x1="11.5" y1="6.5" x2="15.5" y2="10.5" />
              <line x1="15.5" y1="6.5" x2="11.5" y2="10.5" />
            </svg>
            <!-- 有声：喇叭+声波 -->
            <svg v-else viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
              <path d="M2 6v4h3l4 3V3L5 6H2z" fill="currentColor" stroke="none" />
              <path d="M11.5 5.8c1.1 1.2 1.1 3.2 0 4.4" />
              <path d="M13.4 3.8c1.9 2.1 1.9 6.3 0 8.4" />
            </svg>
          </el-icon>
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
        <button class="ico-btn" :class="{ on: recording }" @click="toggleRecord" :title="recording ? '停止录制' : '录制当前频道'">
          <el-icon :size="14"><VideoCamera v-if="!recording" /><CircleClose v-else /></el-icon>
        </button>
        <button class="ico-btn" :class="{ on: timeshiftActive }" @click="toggleTimeshift" :title="timeshiftActive ? '关闭时移（回到直播）' : '开启时移缓冲（可暂停/回看）'">
          <el-icon :size="14"><RefreshLeft /></el-icon>
        </button>
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
    <div v-if="pinVisible" class="pin-mask">
      <div class="pin-box">
        <el-icon :size="30"><Lock /></el-icon>
        <div class="pin-title">家长锁</div>
        <div class="pin-sub">该频道所属分组已锁定，请输入 PIN 码解锁播放</div>
        <el-input v-model="pinInput" type="password" show-password maxlength="8"
                  placeholder="请输入 PIN 码" class="pin-input" @keyup.enter="submitPin" />
        <div v-if="pinError" class="pin-err">{{ pinError }}</div>
        <div class="pin-actions">
          <el-button size="small" @click="cancelPin">取消</el-button>
          <el-button size="small" type="primary" @click="submitPin">解锁播放</el-button>
        </div>
      </div>
    </div>

    <div class="resize resize-tl" @mousedown.prevent="(e) => onResizeStart(e, 0, 'tl')"></div>
    <div class="resize resize-tr" @mousedown.prevent="(e) => onResizeStart(e, 1, 'tr')"></div>
    <div class="resize resize-br" @mousedown.prevent="(e) => onResizeStart(e, 2, 'br')"></div>
    <div class="resize resize-bl" @mousedown.prevent="(e) => onResizeStart(e, 3, 'bl')"></div>
  </div>
</template>

<script setup>
const props = defineProps({
  mini: { type: Boolean, default: false },   
  embedded: { type: Boolean, default: false }, 
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
import * as recordApi from '@/api/record'
import { useSettingsStore } from '@/stores/settings'
import { usePlayerStore } from '@/stores/player'

const route = useRoute()
const playerStore = usePlayerStore()
const videoEl = ref(null)
const volumeSliderWrap = ref(null)
const currentUrl = ref('')
const currentName = ref('')
const currentUrlNote = ref('')
const volume = ref(75)
const isMuted = ref(false)
const showControls = ref(true)
const progressTrackEl = ref(null)

const bufferedPercent = computed(() => {
  const v = videoEl.value
  if (!v || !v.buffered || !v.buffered.length || duration.value <= 0) return 0
  try {
    return Math.min(100, v.buffered.end(v.buffered.length - 1) / duration.value * 100)
  } catch { return 0 }
})

function onChromeActivity() {
  if (miniMode.value) return
  showControls.value = true
  scheduleHideControls()
}

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
const topmost = ref(false)

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

const miniMode = ref(false)
function toggleMiniMode() {
  if (miniMode.value) {
    callNative('resize_window', 1100, 680, 0).catch(() => {})
  } else {
    callNative('resize_window', 320, 200, 2).catch(() => {})
  }
  miniMode.value = !miniMode.value
}

function minimizeWindow() {
  callNative('minimize').catch(() => {})
}
async function stopPlay() {
    await forceStopAll()
  currentUrl.value = ''
  currentName.value = ''
  isPaused.value = false
  loading.value = false
}
const playbackSpeed = ref(1.0)
const playbackSpeedText = ref('1.0x')
const speedDropOpen = ref(false)  
const timeText = ref('00:00 / 00:00')

const isPaused = ref(false)
const duration = ref(0)
const progressVal = ref(0)
const isLive = ref(false)

const hasChannelNav = ref(false)
let channelIndex = -1
let channelList = []  

const videoInfoVisible = ref(false)
const videoInfo = reactive({ w: 0, h: 0, fps: 0, audio: null, codec: '', engine: '', bitrate: 0, protocol: '', latency: 0 })
let playSession = 0

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

const proxyEnabled = ref(false)
let usingProxy = false
const lastHlsError = ref('')
let healthReported = false   

let hls = null
let flvPlayer = null
let dashPlayer = null  
let playingStarted = false  
let errorCount = 0
let errorTimer = null
let hideTimer = null
let historyRecorded = false
let pendingTimer = null
let miscTimers = []

const epg = reactive({ visible: true, loading: false, matched: null, current: '', currentProg: null, next: '' })
const nowTick = ref(Date.now())
let epgTimer = null        
let epgRefreshTimer = null 

const pipSupported = ref(typeof document !== 'undefined' && !!document.pictureInPictureEnabled)
const pipActive = ref(false)


const isFakeLive = ref(false)
const currentIsFakeLiveMarked = ref(false)
let looksLikeLiveNow = false

const engine = ref('webview')

const fakeLiveDismissed = ref(false)
const trustedSources = ref(new Set())
const currentTag = ref('')
const currentChannelId = ref(null)
const isFav = computed(() => (currentTag.value || '').split(',').map(s => s.trim()).includes('fav'))

async function toggleFav() {
  if (!currentChannelId.value) return
  try {
    const newTag = isFav.value ? 'fav' : ''
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
function isWhitelisted(url) {
  if (!url) return false
  const wls = (settingsStore.get('fake_live_whitelist', []) || []).concat(Array.from(trustedSources.value))
  return wls.some(w => _wlMatch(url, w))
}
const showFakeLiveBar = computed(() => {
  if (playError.value) return false
  if (fakeLiveDismissed.value && !currentIsFakeLiveMarked.value) return false
  return isFakeLive.value || currentIsFakeLiveMarked.value
})

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
    if (isLive.value || !isFinite(dur)) {
    progressVal.value = (ct % 86400) / 86400 * 100  
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
  }

function onSeekEnd(val) {
  const v = videoEl.value
  if (!v || !isFinite(v.duration)) return
  if (isLive.value) return  
  v.currentTime = (val / 100) * v.duration
}

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
        currentTag.value = ch.tag || ''
    currentIsFakeLiveMarked.value = !!ch.is_fake_live
    refreshEpg(currentName.value)
    nextTick(() => setupHls())
  }
}


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

function isContainerFileUrl(url) {
  return /\.(mp4|mkv|avi|mov|wmv|m4v|webm|mp3|m4a)(\?[^#]*)?$/i.test(url || '')
}

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

function recomputeFakeLive() {
  const url = currentUrl.value
  if (!url) { isFakeLive.value = false; return }
    if (isWhitelisted(url)) { isFakeLive.value = false; return }

  const lower = url.toLowerCase()
  const isHls = lower.includes('.m3u8') || lower.includes('.m3u')
  const isFlv = lower.includes('.flv') || lower.includes('.flv?')
  const isContainer = isContainerFileUrl(url)

    if (isHls && hls && hls.levels && hls.currentLevel >= 0) {
    const lv = hls.levels[hls.currentLevel]
    if (lv && lv.details) {
      if (lv.details.live === false) { isFakeLive.value = true; return }
      if (lv.details.live === true) { isFakeLive.value = false; return }
    }
  }
    if (isFlv) { isFakeLive.value = false; return }
    if (isContainer && !looksLikeLiveNow) { isFakeLive.value = true; return }
    isFakeLive.value = false
}

async function markCurrentAsFakeLive(isFake) {
  const u = currentUrl.value
  if (!u) return
  currentIsFakeLiveMarked.value = isFake
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

function maybeFailover() {
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
        if (v.videoWidth && v.videoHeight) {
      videoInfo.w = v.videoWidth
      videoInfo.h = v.videoHeight
      videoInfo.engine = 'Web'
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

let _savedVolume = null

function toggleMute() {
  const v = videoEl.value
  if (!v) return
  if (v.muted) {
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
      return `/api/stream-proxy?url=${encodeURIComponent(target)}`
}

function buildRtmpProxyUrl(target) {
    return `/api/rtmp-proxy?url=${encodeURIComponent(target)}`
}

const recording = ref(false)
const recordJobId = ref('')
const timeshiftActive = ref(false)
const timeshiftId = ref('')
const timeshiftPlaylist = ref('')
const timeshiftBackupUrl = ref('')
let recordTimer = null

function stopRecordPoll() {
  if (recordTimer) { clearInterval(recordTimer); recordTimer = null }
}

function startRecordPoll() {
  stopRecordPoll()
  recordTimer = setInterval(async () => {
    try {
      const { data } = await recordApi.listRecords()
      const active = (data && data.active) || []
      if (!active.some(j => j.id === recordJobId.value)) {
        recording.value = false
        recordJobId.value = ''
        stopRecordPoll()
        ElMessage.info('录制已结束')
      }
    } catch { /* ignore */ }
  }, 5000)
}

async function toggleRecord() {
  if (recording.value) {
    const { data } = await recordApi.stopRecord(recordJobId.value)
    if (data && data.ok) ElMessage.success('已停止录制')
    else ElMessage.warning((data && data.error) || '停止录制失败')
    stopRecordPoll()
    recording.value = false
    recordJobId.value = ''
    return
  }
  if (!currentUrl.value) { ElMessage.warning('当前没有正在播放的频道'); return }
  const { data } = await recordApi.startRecord({ name: currentName.value, url: currentUrl.value })
  if (data && data.ok) {
    recording.value = true
    recordJobId.value = data.id || ''
    ElMessage.success('开始录制：' + (data.file || ''))
    startRecordPoll()
  } else {
    ElMessage.error((data && data.error) || '录制启动失败')
  }
}

async function toggleTimeshift() {
  if (timeshiftActive.value) {
    timeshiftActive.value = false
    const sid = timeshiftId.value
    const back = timeshiftBackupUrl.value
    timeshiftId.value = ''
    timeshiftPlaylist.value = ''
    timeshiftBackupUrl.value = ''
    if (sid) recordApi.stopTimeshift(sid).catch(() => {})
    if (back) {
      currentUrl.value = back
      await setupHls()
    }
    ElMessage.info('已关闭时移缓冲，回到直播')
    return
  }
  if (!currentUrl.value) { ElMessage.warning('当前没有正在播放的频道'); return }
  const { data } = await recordApi.startTimeshift({ url: currentUrl.value })
  if (data && data.ok && data.url_path) {
    timeshiftBackupUrl.value = currentUrl.value
    timeshiftId.value = data.id || ''
    timeshiftPlaylist.value = data.url_path
    timeshiftActive.value = true
    currentUrl.value = data.url_path
    await setupHls()
    ElMessage.success('时移已开启：可暂停、可拖动进度条回看')
  } else {
    ElMessage.error((data && data.error) || '时移启动失败')
  }
}

watch(currentUrl, (val) => {
  if (timeshiftActive.value && val !== timeshiftPlaylist.value) {
    const sid = timeshiftId.value
    timeshiftActive.value = false
    timeshiftId.value = ''
    timeshiftPlaylist.value = ''
    timeshiftBackupUrl.value = ''
    if (sid) recordApi.stopTimeshift(sid).catch(() => {})
  }
})

const pinVisible = ref(false)
const pinInput = ref('')
const pinError = ref('')
let pendingPlay = null

function parentalCfg() {
  const s = (settingsStore && settingsStore.settings) || {}
  const groups = Array.isArray(s.parental_locked_groups) ? s.parental_locked_groups : []
  return { on: !!s.parental_enabled, pin: String(s.parental_pin || '').trim(), groups }
}

function needsPin(group) {
  const c = parentalCfg()
  if (!c.on || !c.pin || !c.groups.length) return false
  return c.groups.includes(group || '')
}

function submitPin() {
  const c = parentalCfg()
  if (String(pinInput.value || '').trim() === c.pin) {
    pinVisible.value = false
    pinError.value = ''
    const p = pendingPlay
    pendingPlay = null
    if (p) playRow(p.row, p.list, p.idx)
  } else {
    pinError.value = 'PIN 码错误，请重试'
  }
}

function cancelPin() {
  pinVisible.value = false
  pinInput.value = ''
  pinError.value = ''
  pendingPlay = null
}

function reportPlayHealth(success, error = null, firstFrameMs = null) {
  if (healthReported) return
  healthReported = true
  reportHealth(currentUrl.value, success, error, firstFrameMs).catch(() => {})
}

async function setupHls() {
  const v = videoEl.value
  if (!v || !currentUrl.value) return
    const sid = ++playSession
    miscTimers.forEach(t => clearTimeout(t))
  miscTimers = []
    if (dashPlayer) { try { dashPlayer.reset() } catch (_) {}; dashPlayer = null }
  const url = currentUrl.value
    v.addEventListener('enterpictureinpicture', () => {
    pipActive.value = true
        callNative('hide_window')
  })
  v.addEventListener('leavepictureinpicture', () => {
    pipActive.value = false
            callNative('restore_main_window')
    callNative('show_window')
  })
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
    miscTimers.push(setTimeout(recomputeFakeLive, 2000))

  const lower = url.toLowerCase()

      const isRtmp = lower.startsWith('rtmp://') || lower.startsWith('rtmps://')
  if (isRtmp) {
    const flvUrl = buildRtmpProxyUrl(url)
            if (flvjs.isSupported()) {
      flvPlayer = flvjs.createPlayer({
        type: 'flv',
        url: flvUrl,
        isLive: true,
        hasAudio: true,
        hasVideo: true,
        enableWorker: true,
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
            loading.value = false
      playError.value = true
      ElMessage.warning('该源使用 RTMP 协议，当前环境不支持 FLV 播放，请使用外部播放器（VLC/PotPlayer）打开')
      return
    }
  }

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
        if (await probeHlsIsH265(url)) {
      playH264Proxy(url, src, sid, looksLikeLive)
      return recordHistory()
    }
    if (typeof Hls !== 'undefined' && Hls.isSupported()) {
      hls = new Hls({
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
                        startLevel: 0,
        autoStartLoad: true,
        defaultAudioCodec: undefined,
        xhrSetup: (xhr) => { xhr.withCredentials = false },
                fetchSetup: (_ctx, init) => { try { init.referrerPolicy = 'no-referrer'; return init } catch { return init } },
      })
      hls.loadSource(src)
      hls.attachMedia(v)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
                if (sid !== playSession) return
        v.play().catch(() => {})
      })
      hls.on(Hls.Events.LEVEL_LOADED, (_evt, data) => {
        if (sid !== playSession) return
                        if (data && data.details) {
          if (data.details.live === false && !isWhitelisted(currentUrl.value)) isFakeLive.value = true
          else if (data.details.live === true) isFakeLive.value = false
                    if (data.details.bitrate) videoInfo.bitrate = Math.round(data.details.bitrate / 1000)
          if (hls && hls.liveLatency !== undefined && isFinite(hls.liveLatency)) {
            videoInfo.latency = Math.max(0, Math.round(hls.liveLatency * 1000))
          }
        }
        recomputeFakeLive()
      })
      hls.on(Hls.Events.LEVEL_SWITCHED, (_evt, data) => {
                if (sid !== playSession) return
                const lv = data && data.level !== undefined ? hls.levels[data.level] : hls.levels[hls.currentLevel]
        if (lv) {
          videoInfo.w = lv.width || videoInfo.w
          videoInfo.h = lv.height || videoInfo.h
          videoInfo.engine = 'Web'
        }
      })
      hls.on(Hls.Events.ERROR, (event, data) => {
                if (!hls) return
                if (sid !== playSession) return
        console.warn('[HLS] error:', data.type, data.details, data.fatal)
        lastHlsError.value = `${data.type || ''}/${data.details || ''}`
        if (data.fatal) {
          switch (data.type) {
            case Hls.Events.NETWORK_ERROR:
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
                                          const detail = (data.details || '').toLowerCase()
              if (/parse|frag|alloc/.test(detail) && !usingProxy) {
                console.warn('[HLS] media parse error，疑似 H.265，转 h264-proxy:', detail)
                cleanupHls()
                playH264Proxy(url, src, sid, looksLikeLive)
                return
              }
              try { hls.recoverMediaError() } catch (_) {  }
              break
            }
            default:
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
            v.src = url
      v.play().catch(() => {})
      return recordHistory()
    }
  }

  // ====== DASH (.mpd) ======
  if (isDash) {
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
        ElMessage.info('检测到 DASH 格式，尝试原生播放。若失败建议使用外部播放器')
    v.src = url
    v.play().catch(() => {})
    return recordHistory()
  }

        if (!/\.(mp4|mkv|avi|mov|wmv|m4v|webm|mp3|m4a|flac|wav)(\?|#|$)/i.test(url)) {
    probeContentType(src).then((ct) => {
      if (sid !== playSession) return
      if (isHlsContentType(ct)) {
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
        miscTimers.push(setTimeout(() => { if (sid === playSession && !hls && !flvPlayer && !playingStarted) nativeFallback(v, url, src, looksLikeLive) }, 4500))
    recordHistory()
    return
  }
  nativeFallback(v, url, src, looksLikeLive)
  recordHistory()
}

function nativeFallback(v, url, src, looksLikeLive) {
  if (!v) return
    v.src = src
  playingStarted = true
  v.play().then(() => {
    if (looksLikeLive) isLive.value = true
  }).catch((e) => {
    console.warn('[native] play failed:', e)
  })
}

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
  } catch {  }
}

function onVideoError() {
  errorCount++
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
    usingProxy = true
  playError.value = false
  errorCount = 0
  nextTick(() => setupHls())
}

async function toggleFullscreen() {
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
        window.close()
  }
}

async function toggleTopmost() {
  const r = await callNative('set_topmost', !topmost.value)
  if (r === true) {
    topmost.value = !topmost.value
  } else if (r === false) {
    ElMessage.warning('置顶操作失败')
  }
}

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
        if (data.player_window_topmost != null) {
      const wantTop = !!data.player_window_topmost
      if (wantTop !== topmost.value) {
        topmost.value = wantTop
        if (wantTop) callNative('set_topmost', true)
      }
    }
  } catch { /* ignore */ }
}

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

function isHlsContentType(ct) {
  return /mpegurl|mp2t|x-mpegurl|vnd\.apple\.mpegurl/.test(ct || '')
}

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
                    return probeTsSegmentH265(url, text)
            .then((segResult) => resolve(segResult))
            .catch(() => resolve(false))
        })
        .catch(() => { if (timer) clearTimeout(timer); resolve(false) })
    } catch (e) { if (timer) clearTimeout(timer); resolve(false) }
  })
}

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
                    const len = Math.min(bytes.length, 32 * 1024)
          for (let i = 0; i < len - 2; i++) {
                        const nalType = (bytes[i] >> 1) & 0x3f
            if (nalType >= 16 && nalType <= 40) {
              resolve(true); return
            }
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

function h264ProxyUrl(srcUrl) {
  return '/api/h264-proxy?url=' + encodeURIComponent(srcUrl)
}

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
      window.__iptvPlay = playRow
    window.__iptvCleanup = () => {
    if (hls) { hls.destroy(); hls = null }
    if (flvPlayer) { flvPlayer.destroy(); flvPlayer = null }
  }
  window.addEventListener('keydown', onKeyDown)

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

    await loadPlayerConfig()
    try { await settingsStore.fetchSettings() } catch { /* ignore */ }
  if (currentUrl.value) applyPlayerDefaults()

  if (currentUrl.value) {
    await startPlayback()
  }

      startPendingPolling()

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
  if (needsPin(row.group)) {
    pendingPlay = { row, list, idx }
    pinInput.value = ''
    pinError.value = ''
    pinVisible.value = true
    return
  }
    if (hls || flvPlayer || dashPlayer) {
    await forceStopAll()
  }
    const meta = (row.__channelList && row.__index !== undefined)
    ? { list: row.__channelList, index: row.__index }
    : null
  if (meta) {
    list = meta.list; idx = meta.index
  }

  currentUrl.value = row.url
  currentName.value = row.name || '未知频道'
  currentUrlNote.value = row.url_note || ''
    videoInfo.protocol = detectProtocol(currentUrl.value).toUpperCase()
  refreshEpg(currentName.value)
    if (list && Array.isArray(list) && list.length > 0) {
    channelList = list.map(ch => ({
      id: ch.id,
      url: ch.url, name: ch.name || '未知频道', group: ch.group || '',
      tag: ch.tag || '',
      is_fake_live: !!ch.is_fake_live,
      url_note: ch.url_note || '',
    }))
    hasChannelNav.value = true
    channelIndex = idx >= 0 ? idx : (channelList.findIndex(ch => ch.url === row.url))
  }
    const oldUrl = currentUrl.value
  const same = row.url === oldUrl
    currentTag.value = row.tag || ''
  currentChannelId.value = row.id != null ? row.id : null  
  currentIsFakeLiveMarked.value = !!row.is_fake_live
  fakeLiveDismissed.value = false
  if (!same) {
    nextTick(() => startPlayback())
  } else if (!hls && videoEl.value) {
    setupHls()
  }
}

function resetPlayState() {
  playError.value = false
  loading.value = false
  isPaused.value = false
  duration.value = 0
  progressVal.value = 0
  errorCount = 0
  healthReported = false
  isFakeLive.value = false
    videoInfo.w = 0
  videoInfo.h = 0
  videoInfo.fps = 0
  videoInfo.codec = ''
  videoInfo.bitrate = 0
  videoInfo.latency = 0
  playerStore.videoInfo = { w: 0, h: 0, fps: 0, engine: '' }
}

async function forceStopAll() {
    if (hls) { try { hls.destroy() } catch (_) {} ; hls = null }
    if (flvPlayer) { try { flvPlayer.destroy() } catch (_) {} ; flvPlayer = null }
  if (dashPlayer) { try { dashPlayer.reset() } catch (_) {} ; dashPlayer = null }
  const v = videoEl.value
  if (v) {
    try { v.pause() } catch (_) {}
    try { v.removeAttribute('src') } catch (_) {}
    try { v.load() } catch (_) {}
  }
    resetPlayState()
}

onUnmounted(() => {
  stopRecordPoll()
  if (timeshiftActive.value && timeshiftId.value) recordApi.stopTimeshift(timeshiftId.value).catch(() => {})
    if (window.__iptvPlay === playRow) delete window.__iptvPlay
  if (window.__iptvCleanup) delete window.__iptvCleanup
  window.removeEventListener('keydown', onKeyDown)
    forceStopAll()
  if (pendingTimer) { clearInterval(pendingTimer); pendingTimer = null }
  if (epgTimer) { clearInterval(epgTimer); epgTimer = null }
  if (epgRefreshTimer) { clearInterval(epgRefreshTimer); epgRefreshTimer = null }
})

</script>

<style>

html, body, #app { background: #000 !important; margin: 0 !important; padding: 0 !important; }

.player-speed-popper { -webkit-app-region: no-drag; }
.player-speed-popper .el-dropdown-menu__item { cursor: pointer; }
</style>

<style scoped>


.player-page {
  height: 100%; background: #000; position: relative; overflow: hidden;
  user-select: none;
  
  -webkit-app-region: drag;
}


.video-wrap {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: #000;
  -webkit-app-region: drag;  
}
.video {
  width: 100%; height: 100%; object-fit: contain; outline: none;
  background: #000;  
}


.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; color: rgba(255,255,255,0.4); font-size: 13px;
}


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


.chrome {
  position: absolute; left: 0; right: 0; bottom: 0; z-index: 5;
  padding: 0 14px 10px;
  background: linear-gradient(to top, rgba(0,0,0,0.78), rgba(0,0,0,0));
  opacity: 1; transition: opacity .3s ease;
  -webkit-app-region: no-drag;
}
.player-page.chrome-hidden .chrome { opacity: 0; pointer-events: none; }


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


.volume-slider-wrap { width: 80px; flex-shrink: 0; cursor: pointer; -webkit-app-region: no-drag; }
.volume-slider-wrap :deep(.el-slider__runway) { background-color: rgba(255,255,255,0.2); height: 3px; }
.volume-slider-wrap :deep(.el-slider__bar) { background-color: #60a5fa; height: 3px; }
.volume-slider-wrap :deep(.el-slider__button) { width: 10px; height: 10px; border: 2px solid #fff; }


.player-title { font-size: 12px; color: rgba(255,255,255,0.8); margin-left: 6px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.player-note { font-size: 11px; margin-left: 4px; }
.player-tag { font-size: 11px; margin-left: 4px; }


.speed-label { font-size: 11px; color: rgba(255,255,255,0.8); font-weight: 600; }


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


.player-page.is-mini .chrome { padding: 0 6px 4px; background: transparent; }
.player-page.is-mini .fake-live { display: none; }
.player-page.is-mini .ico-btn { width: 24px; height: 24px; }
.player-page.is-mini .ico-btn:not(.ico-close):not(.ico-btn) { display: none; }  


.video-mini {  }
.pin-mask {
  position: absolute;
  inset: 0;
  z-index: 40;
  background: rgba(0, 0, 0, 0.86);
  display: flex;
  align-items: center;
  justify-content: center;
}
.pin-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #fff;
  padding: 24px 28px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
}
.pin-title { font-size: 16px; font-weight: 600; }
.pin-sub { font-size: 12px; color: rgba(255, 255, 255, 0.7); }
.pin-input { width: 200px; }
.pin-err { font-size: 12px; color: #ff7875; }
.pin-actions { display: flex; gap: 8px; margin-top: 4px; }

</style>
