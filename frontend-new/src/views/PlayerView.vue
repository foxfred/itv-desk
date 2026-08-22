<template>
  <div class="player-page" :style="{ background: videoBg }">
    <div v-if="!currentUrl" class="player-empty">
      <el-icon :size="56" color="var(--el-text-color-disabled)"><VideoPlay /></el-icon>
      <p>等待播放...</p>
    </div>

    <div v-else class="player-container">
      <!-- 无外框模式下的窗口拖拽条：细窄、悬停显示，拖动移动整个窗口 -->
      <div class="player-drag-bar"
        @mousedown.stop.prevent="onDragStart"
        @mouseup.stop="onDragEnd">
        <span class="drag-hint">⋮⋮</span>
      </div>
      <div
        class="player-video-wrap"
        :class="{ 'player-video-wrap-mini': mini }"
        v-loading="loading"
        element-loading-text="缓冲中…"
        element-loading-background="rgba(0,0,0,0.6)"
        @mousemove="(!mini) && (showControls = true)"
        @mouseleave="(!mini) && scheduleHideControls()"
      >
        <!-- mpv 模式：隐藏 video 元素（避免 src 清空后残留上一帧造成"两窗口"视觉混淆，IPTVnator 式"先关旧再开新"）；
             用 v-show 保留 ref，避免 forceStopAll 中 videoEl 丢失。 -->
        <video
          v-show="!mpvActive"
          ref="videoEl"
          class="player-video"
          autoplay
          :src="mpvActive ? '' : currentUrl"
          @error="onVideoError"
          @dblclick="toggleFullscreen"
          @timeupdate="onTimeUpdate"
          @loadedmetadata="onLoadedMeta"
          @waiting="onWaiting"
          @playing="onPlaying"
          @canplay="onPlaying"
        />
        <!-- mpv 引擎占位：mpv 通过 --wid 嵌入主窗容器渲染画面，这里保持纯黑避免 webview 尝试解码 -->
        <div v-if="mpvActive" class="mpv-placeholder">
          <span class="mpv-badge">mpv</span>
          <span class="mpv-hint">原生解码中…（mpv 正在渲染画面）</span>
        </div>
        <!-- 播放器内 EPG 信息条：显示当前频道正在播放的节目 + 进度 + 接下来 -->
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
          <el-button size="small" text class="epg-collapse" title="收起 EPG 信息条" @click="epg.visible = false">
            <el-icon><ArrowDown /></el-icon>
          </el-button>
        </div>
        <el-button v-else-if="currentUrl && !playError" size="small" text class="epg-reopen" title="显示 EPG 信息条" @click="epg.visible = true">
          <el-icon><ArrowUp /></el-icon> EPG
        </el-button>
        <div v-if="playError" class="player-error">
          <el-icon :size="48" color="#FB7185"><WarningFilled /></el-icon>
          <p>播放失败：{{ currentName }}</p>
          <p class="player-error-hint">源可能已失效、编码不受支持，或受运行环境跨源/MSE 限制</p>
          <p v-if="lastHlsError" class="player-error-detail">错误详情：{{ lastHlsError }}</p>
          <div class="player-error-actions">
            <el-button size="small" type="primary" @click="retryPlay">重试</el-button>
            <el-button v-if="!proxyEnabled && !usingProxy" size="small" @click="retryViaProxy">经本地代理重试</el-button>
            <el-button v-if="isNative()" size="small" @click="playExternal">用外部播放器打开</el-button>
          </div>
        </div>
        <!-- 假直播提示：自动检测或用户手动标记为假直播时显示，提供切换/信任/修改标记入口 -->
        <!-- 可关闭：点击 X 关闭常驻提示；命中白名单/点“信任此源”后不再提示 -->
        <div v-if="showFakeLiveBar" class="player-fakelive-bar">
          <el-icon :size="16" color="#FBBF24"><WarningFilled /></el-icon>
          <span class="fl-text">
            {{ currentIsFakeLiveMarked ? '该频道已被你标记为「假直播」' : '当前源疑似「假直播」（点播/循环文件），并非真实直播流' }}
          </span>
          <el-button v-if="!currentIsFakeLiveMarked" size="small" type="warning" plain @click="markCurrentAsFakeLive(true)">标记为假直播</el-button>
          <el-button v-else size="small" type="success" plain @click="markCurrentAsFakeLive(false)">取消假直播标记</el-button>
          <el-button v-if="isFakeLive && !currentIsFakeLiveMarked" size="small" type="warning" plain @click="trustCurrentSource">信任此源</el-button>
          <el-button size="small" type="warning" plain @click="cycleSource">切换源</el-button>
          <el-button size="small" text circle title="关闭提示" @click="fakeLiveDismissed = true">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
        <div class="player-controls" v-show="showControls && !playError && !mini" @mouseenter="showControls = true" @mouseleave="scheduleHideControls">
          <!-- 进度条（直播流显示为实时指示） -->
          <div class="progress-wrap" v-if="duration > 0 || isLive">
            <el-slider
              v-model="progressVal"
              :show-tooltip="false"
              :min="0"
              :max="isLive ? 100 : (duration || 0)"
              size="small"
              class="progress-slider"
              @input="onSeek"
              @change="onSeekEnd"
            />
          </div>
          <div class="ctrl-row">
            <!-- 上一频道 / 下一频道 -->
            <el-button size="default" text circle title="上一个频道" @click="prevChannel" :disabled="!hasChannelNav">
              <el-icon><DArrowLeft /></el-icon>
            </el-button>
            <el-button size="default" text circle title="下一个频道" @click="nextChannel" :disabled="!hasChannelNav">
              <el-icon><DArrowRight /></el-icon>
            </el-button>
            <el-button v-if="!embedded" size="default" text circle :title="isPaused ? '播放' : '暂停'" @click="togglePlay">
              <el-icon><VideoPlay v-if="isPaused" /><VideoPause v-else /></el-icon>
            </el-button>
            <el-button v-if="!embedded" size="default" text circle title="停止播放" @click="stopPlay">
              <el-icon><VideoCamera /></el-icon>
            </el-button>
            <!-- 音量 -->
            <el-button size="default" text circle :type="isMuted ? 'warning' : ''" :title="isMuted ? '取消静音' : '静音'" @click="toggleMute">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true">
                <path v-if="!isMuted" d="M3 9v6h4l5 4V5L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
                <path v-else d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 4v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L2 14h3l7-7-4-3z" />
              </svg>
            </el-button>
            <div class="volume-slider-wrap" ref="volumeSliderWrap" @mousedown.stop.prevent="onVolumeSliderMouseDown">
              <el-slider
                v-model="volume"
                :show-tooltip="false"
                :max="100"
                size="default"
                style="width:100px; flex-shrink: 0"
                @input="onVolumeChange"
                @change="onVolumeChange"
              />
            </div>
            <span class="time-label">{{ timeText }}</span>
            <span class="player-title" :title="currentUrl">{{ currentName }}</span>
            <el-tag v-if="currentUrlNote" size="default" type="info" effect="dark" class="player-note" :title="`源标签：${currentUrlNote}`">{{ currentUrlNote }}</el-tag>
            <!-- R3: 收藏星标（tag=fav 读写，复用 channels API） -->
            <el-button v-if="currentChannelId" size="default" text circle
              :type="isFav ? 'warning' : ''"
              :title="isFav ? '取消收藏' : '收藏该频道'"
              @click="toggleFav">
              <el-icon><StarFilled v-if="isFav" /><Star v-else /></el-icon>
            </el-button>
            <el-tag v-if="currentTag" size="default" type="warning" effect="dark" class="player-tag" :title="`标记：${currentTag}`">{{ currentTag }}</el-tag>
            <!-- 播放引擎指示 + 切换（Phase 5 Track A） -->
            <el-tooltip :content="mpvActive ? '当前 mpv 原生解码，点击切回 WebView' : (mpvAvailable ? '当前 WebView 解码，点击切换到 mpv 原生' : 'mpv 未就位')" placement="top">
              <el-tag
                size="default"
                :type="mpvActive ? 'success' : 'info'"
                effect="dark"
                class="engine-tag"
                :class="{ 'engine-clickable': mpvAvailable }"
                @click="toggleEngineBtn"
              >{{ mpvActive ? 'mpv' : 'Web' }}</el-tag>
            </el-tooltip>
            <!-- P5: 媒体信息按钮（6.3 信息浮层） -->
            <el-button size="default" text circle title="媒体信息（分辨率/帧率/音频）" @click="toggleVideoInfo">
              <el-icon><InfoFilled /></el-icon>
            </el-button>
            <!-- P5: 音轨下拉（mpv 模式多音轨才显示） -->
            <el-dropdown v-if="mpvActive && audioTracks.length > 1" size="default" trigger="click" @command="onPickAudioTrack">
              <el-button size="default" text circle title="切换音轨">
                <el-icon><Headset /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="t in audioTracks" :key="t.id" :command="t.id" :class="{ 'sp-active': t.selected }">
                    <span>{{ trackLabel(t) }}</span>
                    <el-icon v-if="t.selected" class="sp-check"><Check /></el-icon>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <!-- P5: 字幕（mpv 模式：字幕轨切换 + 加载本地字幕） -->
            <el-dropdown v-if="mpvActive && (subTracks.length > 1 || true)" size="default" trigger="click" @command="onPickSubCmd">
              <el-button size="default" text circle title="字幕">
                <el-icon><DocumentAdd /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="t in subTracks" :key="t.id" :command="'track:' + t.id" :class="{ 'sp-active': t.selected }">
                    <span>{{ t.title || (t.lang || ('字幕 ' + t.id)) }}</span>
                    <el-icon v-if="t.selected" class="sp-check"><Check /></el-icon>
                  </el-dropdown-item>
                  <el-dropdown-item divided command="load-file">📂 加载本地字幕…</el-dropdown-item>
                  <el-dropdown-item v-if="subTracks.length > 1" command="off">关闭字幕</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <!-- P5: 清晰度（mpv 用 video 轨 / webview 用 hls.levels） -->
            <el-dropdown v-if="qualityOptions.length > 1" size="default" trigger="click" @command="onPickQuality">
              <el-button size="default" text circle title="清晰度">
                <el-icon><Monitor /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="(q, i) in qualityOptions" :key="q.id || i" :command="q.id === 'auto' ? 'auto' : q.id" :class="{ 'sp-active': q.selected }">
                    <span>{{ q.label }}</span>
                    <el-icon v-if="q.selected" class="sp-check"><Check /></el-icon>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <div class="spacer"></div>
            <span class="speed-label">{{ playbackSpeedText }}</span>
            <el-dropdown size="default" trigger="click" @command="onSpeedChange">
              <el-button size="default" text>
                <el-icon><CaretBottom /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="sp in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]" :key="sp" :command="sp">
                    {{ sp }}x
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button v-if="isNative()" size="default" text circle title="用外部播放器打开" @click="playExternal">
              <el-icon><VideoCamera /></el-icon>
            </el-button>
            <el-button v-if="pipSupported" size="default" text circle :type="pipActive ? 'primary' : ''" title="画中画" @click="togglePiP">
              <el-icon><Picture /></el-icon>
            </el-button>
            <el-button v-if="currentSources.length > 1" size="default" text circle :title="`切换下一个源 (${sourceIndex + 1}/${currentSources.length})`" @click="cycleSource">
              <el-icon><Refresh /></el-icon>
            </el-button>
            <el-dropdown v-if="currentSources.length > 1" size="default" trigger="click" placement="top" @command="onPickSource">
              <el-button size="default" text circle :type="isFakeLive ? 'warning' : ''" :title="`选择直播源 (${sourceIndex + 1}/${currentSources.length})`">
                <el-icon><Switch /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu class="source-picker-menu">
                  <div class="sp-menu-title">
                    选择直播源（共 {{ currentSources.length }} 个）
                    <el-tag v-if="currentTag" size="default" type="warning" effect="dark" class="sp-menu-tag" :title="`标记：${currentTag}`">{{ currentTag }}</el-tag>
                  </div>
                  <el-dropdown-item
                    v-for="(s, i) in currentSources"
                    :key="i"
                    :command="i"
                    :class="{ 'sp-active': i === sourceIndex, 'sp-fake': isFakeLive && i === sourceIndex }"
                  >
                    <span class="sp-idx">{{ i + 1 }}</span>
                    <span class="sp-url" :title="s">{{ shortUrl(s) }}</span>
                    <el-tag v-if="currentIsFakeLiveMarked" size="default" type="danger" effect="dark" class="sp-fake-tag">假直播</el-tag>
                    <el-tag v-if="groupLabelOf(s)" size="default" type="info" effect="plain" class="sp-group">{{ groupLabelOf(s) }}</el-tag>
                    <el-icon v-if="i === sourceIndex" class="sp-check"><Check /></el-icon>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button size="default" text circle title="全屏" @click="toggleFullscreen">
              <el-icon><FullScreen /></el-icon>
            </el-button>
            <el-button v-if="!embedded" style="margin-left: auto" size="default" text circle :type="topmost ? 'primary' : ''" :title="topmost ? '取消窗口置顶' : '窗口置顶'" @click="toggleTopmost">
              <el-icon><Top /></el-icon>
            </el-button>
            <el-button v-if="!embedded" size="default" text circle :type="miniMode ? 'primary' : ''" :title="miniMode ? '退出迷你模式' : '迷你模式'" @click="toggleMiniMode">
              <el-icon><Minimize /></el-icon>
            </el-button>
            <el-button v-if="!embedded" size="default" text circle title="最小化窗口" @click="minimizeWindow">
              <el-icon><Minus /></el-icon>
            </el-button>
            <el-button size="default" text circle type="danger" title="关闭窗口" @click="closePlayer">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </div>
        <!-- 无外框模式四角缩放手柄（拖动调整窗口大小） -->
        <div class="resize-handle resize-tl" @mousedown.stop.prevent="onResizeStart($event, 0, 'tl')" />
        <div class="resize-handle resize-tr" @mousedown.stop.prevent="onResizeStart($event, 1, 'tr')" />
        <div class="resize-handle resize-br" @mousedown.stop.prevent="onResizeStart($event, 2, 'br')" />
        <div class="resize-handle resize-bl" @mousedown.stop.prevent="onResizeStart($event, 3, 'bl')" />
        <!-- P5: 媒体信息浮层（6.3，右下角弹出，点击信息按钮开关） -->
        <transition name="el-fade-in">
          <div v-if="videoInfoVisible && videoInfo.w" class="video-info-overlay">
            <div class="vi-row"><span class="vi-label">分辨率</span><span class="vi-value">{{ videoInfo.w }}×{{ videoInfo.h }}</span></div>
            <div class="vi-row" v-if="videoInfo.fps"><span class="vi-label">帧率</span><span class="vi-value">{{ videoInfo.fps }} fps</span></div>
            <div class="vi-row" v-if="videoInfo.audio && videoInfo.audio.channels"><span class="vi-label">音频</span><span class="vi-value">{{ audioInfoText }}</span></div>
            <div class="vi-row" v-if="videoInfo.codec"><span class="vi-label">编码</span><span class="vi-value">{{ videoInfo.codec }}</span></div>
            <div class="vi-row" v-if="videoInfo.engine"><span class="vi-label">引擎</span><span class="vi-value">{{ videoInfo.engine }}</span></div>
            <!-- Phase 4：实时统计——码率/协议/延迟（IPTVnator 式信息面板） -->
            <div class="vi-row" v-if="videoInfo.bitrate"><span class="vi-label">码率</span><span class="vi-value">{{ videoInfo.bitrate }} kbps</span></div>
            <div class="vi-row" v-if="videoInfo.protocol"><span class="vi-label">协议</span><span class="vi-value">{{ videoInfo.protocol }}</span></div>
            <div class="vi-row" v-if="videoInfo.latency"><span class="vi-label">延迟</span><span class="vi-value">{{ videoInfo.latency }} ms</span></div>
          </div>
        </transition>
      </div>
    </div>
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
// 双窗口（Phase 1）：独立播放窗置顶状态（仅 standalone 模式可用）
const topmost = ref(false)
// 无外框模式：窗口拖拽状态（拖动顶部条移动整个窗口）
let dragState = { active: false, startX: 0, startY: 0 }
function onDragStart(e) {
  if (e.button !== 0) return
  dragState = { active: true, startX: e.clientX, startY: e.clientY }
  document.addEventListener('mousemove', onGlobalDragMove)
  document.addEventListener('mouseup', onGlobalDragEnd)
}
function onDragEnd() {
  document.removeEventListener('mousemove', onGlobalDragMove)
  document.removeEventListener('mouseup', onGlobalDragEnd)
  dragState.active = false
}
function onGlobalDragMove(e) {
  if (!dragState.active) return
  const dx = e.clientX - dragState.startX
  const dy = e.clientY - dragState.startY
  if (dx === 0 && dy === 0) return
  callNative('move_window', dx, dy).catch(() => {})
  dragState.startX = e.clientX
  dragState.startY = e.clientY
}
function onGlobalDragEnd() {
  document.removeEventListener('mousemove', onGlobalDragMove)
  document.removeEventListener('mouseup', onGlobalDragEnd)
  dragState.active = false
}

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
// Phase 5：mpv 窗口跟随播放面板（拖动/缩放时重定位覆盖视频区）
const mpvFollowPlayer = ref(true)
const playbackSpeed = ref(1.0)
const playbackSpeedText = ref('1.0x')
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

// P5: 媒体信息（6.3）+ 轨道状态
const videoInfoVisible = ref(false)
const videoInfo = reactive({ w: 0, h: 0, fps: 0, audio: null, codec: '', engine: '', bitrate: 0, protocol: '', latency: 0 })
const mpvTracks = ref([])
// P5: 并发修复状态（C1/C3/C4）
let engineSwitching = false     // C1: 引擎切换中标志
let playSession = 0             // C3: 快速换台会话 id
let _loadSeq = 0                // C4: mpv loadfile 序号

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

// mpv 引擎（Phase 5 Track A）：默认 webview（今日已验证），MPV 作为可选项 + 失败自动兜底
const engine = ref('webview')           // 'webview' | 'mpv'
// mpv 激活 = 引擎已切 mpv 且子进程就绪（此时隐藏 <video>，画面由独立 mpv 窗渲染）
const mpvActive = computed(() => engine.value === 'mpv' && mpvReady.value)
const mpvAvailable = ref(false)          // mpv 二进制是否就位
const mpvReady = ref(false)              // mpv 子进程已起 + 管道已连
const mpvLoading = ref(false)
const mpvError = ref('')                 // 最近一次 mpv 错误（前端可见，用于自动回退 webview）
let mpvStateTimer = null                 // 轮询 mpv_state

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

// ==================== P5: 轨道 / 清晰度 / 媒体信息 ====================
// 从 mpv track-list 过滤三类轨道
const audioTracks = computed(() => (mpvTracks.value || []).filter(t => t.type === 'audio'))
const subTracks = computed(() => (mpvTracks.value || []).filter(t => t.type === 'sub'))
const videoTracks = computed(() => (mpvTracks.value || []).filter(t => t.type === 'video'))

// 清晰度选项：mpv 模式用 video 轨；webview 模式用 hls.levels
const qualityOptions = computed(() => {
  if (mpvActive.value) {
    if (videoTracks.value.length > 1) {
      return videoTracks.value.map(t => ({
        id: String(t.id), label: `${t.title || '清晰度 ' + t.id}${t.selected ? '（当前）' : ''}`,
        selected: !!t.selected,
      }))
    }
    return [{ id: 'auto', label: '自动', selected: true }]
  }
  // webview：hls.js levels（L1172 已改为不强制最高）
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

function onPickAudioTrack(id) {
  callNative('mpv_set_track', 'audio', Number(id))
}

function onPickSubCmd(cmd) {
  if (cmd === 'load-file') {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.srt,.ass,.ssa,.vtt'
    input.onchange = async () => {
      const f = input.files && input.files[0]
      if (!f) return
      // 经后端原生保存对话框无法直接拿路径，改用 webkitRelativePath 或提示：
      // 桌面端用 showOpenFileDialog 原生能力选路径
      const api = window.pywebview?.api
      if (api && typeof api.select_file === 'function') {
        const path = await callNative('select_file', '选择字幕文件', '字幕文件 (*.srt;*.ass;*.ssa;*.vtt)|*.srt;*.ass;*.ssa;*.vtt')
        if (path && typeof path === 'string') {
          const r = await callNative('mpv_sub_add', path)
          if (r && r.ok) ElMessage.success('字幕已加载')
          else ElMessage.error('字幕加载失败：' + ((r && r.error) || '未知'))
        }
      } else {
        ElMessage.warning('请使用桌面客户端加载字幕文件')
      }
    }
    input.click()
    return
  }
  if (cmd === 'off') {
    callNative('mpv_set_track', 'sub', 'no')
    return
  }
  if (cmd.startsWith('track:')) {
    callNative('mpv_set_track', 'sub', Number(cmd.slice(6)))
  }
}

function onPickQuality(id) {
  if (id === 'auto') {
    if (mpvActive.value) {
      // mpv：cycle video 回自动
      callNative('mpv_cycle_track', 'video')
    } else if (hls) {
      hls.currentLevel = -1
      hls.autoLevelCapping = -1
    }
    return
  }
  if (mpvActive.value) {
    callNative('mpv_set_quality', Number(id))
  } else if (hls) {
    hls.currentLevel = Number(id)
  }
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
  if (engine.value === 'mpv' && mpvReady.value) {
    callNative('mpv_toggle_pause')
    isPaused.value = !isPaused.value
    return
  }
  const v = videoEl.value
  if (!v) return
  if (v.paused) { v.play().catch(() => {}); isPaused.value = false }
  else { v.pause(); isPaused.value = true }
}

function onSeek(val) {
  // 拖拽中不跳转（避免卡顿），只在 change（松手）时跳转
}

function onSeekEnd(val) {
  if (engine.value === 'mpv' && mpvReady.value) {
    // mpv 用 absolute 模式 seek 到百分比对应秒数（前端只拿百分比，需要 duration）
    if (isLive.value) return
    if (!duration.value) return
    const sec = (val / 100) * duration.value
    callNative('mpv_seek', sec, 'absolute')
    return
  }
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

// ==================== mpv 引擎（Phase 5 Track A）====================
async function ensureMpvAvailable() {
  if (mpvAvailable.value) return true
  const r = await callNative('mpv_available')
  if (r && r.ok) {
    mpvAvailable.value = true
    return true
  }
  // 失败：把后端探测的所有候选路径写到 mpvError（不再硬编码）
  if (r && r.candidates && r.candidates.length) {
    const detail = r.candidates
      .map(c => `${c.exists ? '✓' : '✗'} ${c.label}: ${c.path}`)
      .join('\n')
    mpvError.value = `mpv.exe 未就位（已探测：\n${detail}\n_meipass=${r.meipass || '(空)'}）`
  } else {
    mpvError.value = (r && r.reason) || 'mpv 引擎不可用'
  }
  return false
}

async function initMpv() {
  if (!isNative()) return false
  if (mpvReady.value) return true
  if (mpvLoading.value) return false
  mpvLoading.value = true
  mpvError.value = ''
  try {
    if (!(await ensureMpvAvailable())) {
      // mpvError 已在 ensureMpvAvailable 里写好（含探测路径）
      return false
    }
    const r = await callNative('mpv_init')
    if (r && r.ok) {
      mpvReady.value = true
      startMpvStatePoll()
      return true
    }
    mpvError.value = (r && r.error) || 'mpv 启动失败'
    return false
  } finally {
    mpvLoading.value = false
  }
}

function startMpvStatePoll() {
  if (mpvStateTimer) return
  mpvStateTimer = setInterval(async () => {
    if (!mpvReady.value) return
    // C1 修复：引擎切换窗口期跳过轮询，避免与 switchEngine 竞态双重 setupHls
    if (engineSwitching) return
    const s = await callNative('mpv_state')
    if (s && s.alive === false && engine.value === 'mpv') {
      // mpv 进程死了。强制 mpv 模式下不静默回退 webview（用户要求），保持 engine='mpv' 等用户操作
      mpvReady.value = false
      mpvError.value = s.last_error || 'mpv 进程退出'
      ElMessage.warning('mpv 进程已退出，请重试或切换引擎')
    } else if (s && s.state) {
      // 同步状态：暂停/进度/音量
      const st = s.state
      if (typeof st.pause === 'boolean') isPaused.value = st.pause
      if (typeof st.volume === 'number' && Math.abs(st.volume - volume.value) > 1) {
        volume.value = st.volume
      }
      // B2 修复：mpv 模式直播判定——duration 非法/为 0 且 path 是流媒体 → 直播
      const dur = st.duration
      const path = st.path || ''
      const looksLive = !(typeof dur === 'number' && isFinite(dur) && dur > 1)
        && /m3u8|m3u|mpd|flv|rtmp|rtsp|\.ts/i.test(path)
      if (looksLive) {
        isLive.value = true
        duration.value = 0
        // 直播流进度条显示循环指示
        if (typeof st.position === 'number') progressVal.value = (st.position % 86400) / 86400 * 100
      } else {
        isLive.value = false
        if (typeof dur === 'number' && dur > 0) {
          duration.value = dur
          if (typeof st.position === 'number' && dur > 0) {
            progressVal.value = st.position / dur * 100
          }
        }
      }
      // 时间文本（直播显示 elapsed / 直播）
      if (typeof st.position === 'number') {
        const ct = st.position
        timeText.value = isLive.value
          ? `${formatTime(ct)} / 直播`
          : `${formatTime(ct)} / ${formatTime(duration.value)}`
      }
      // P5: 媒体信息（6.3）+ 轨道填充
      if (st.video_w || st.video_h) {
        videoInfo.w = st.video_w || 0
        videoInfo.h = st.video_h || 0
        videoInfo.fps = st.fps || 0
        videoInfo.engine = 'mpv'
        // R4: 同步到 store 供状态栏展示
        playerStore.videoInfo = { w: videoInfo.w, h: videoInfo.h, fps: videoInfo.fps, engine: 'mpv' }
      }
      if (st.audio) videoInfo.audio = st.audio
      if (st.codec) videoInfo.codec = st.codec
      if (Array.isArray(st.tracks)) mpvTracks.value = st.tracks
      // P5: mpv 健康上报（首帧=播放成功，video_h>0 即出帧）
      if ((st.video_h || 0) > 0 && !healthReported) {
        reportPlayHealth(true)
      }
    }
  }, 1500)
}

function stopMpvStatePoll() {
  if (mpvStateTimer) {
    clearInterval(mpvStateTimer)
    mpvStateTimer = null
  }
}

async function playMpv(url) {
  if (!url) return false
  // C4 修复：loadfile 序号——连续两次 playMpv 时旧调用的异步结果丢弃
  const seq = ++_loadSeq
  // 记住进入时的引擎模式：强制 mpv 失败时不静默回退 webview（用户要求：单独用 mpv 不需要兜底）
  const origEng = engine.value
  if (!mpvReady.value) {
    const ok = await initMpv()
    if (!ok) return
    // mpv 首次启动成功后定位到参考坐标；之后用户可自由拖动 mpv 窗口（不随切台重定位，避免"不可控"）
    await positionMpv()
  }
  if (seq !== _loadSeq) return  // 已被更新的换台请求取代
  const r = await callNative('mpv_load', url)
  if (seq !== _loadSeq) return  // 加载期间又换台，丢弃
  if (!r || !r.ok) {
    const detail = (r && r.error) || 'mpv_load 失败'
    mpvError.value = detail
    reportPlayHealth(false, detail)
    await forceStopAll()
    mpvReady.value = false
    ElMessage.warning(`mpv 加载失败：${detail}`)
    if (origEng !== 'mpv') {
      // 非强制 mpv（auto/webview 过渡）：回退 webview 兜底
      engine.value = 'webview'
      playerStore.engine = 'webview'
      setupHls()
    }
    // 强制 mpv：保持 engine='mpv'，不静默回退，等用户重试或切引擎
    return false
  }
  // D3/M1 修复：20s 内未出现 video-params（首帧解码）→ 判定加载失败；强制 mpv 不回退
  if (_mpvFirstFrameTimer) { clearTimeout(_mpvFirstFrameTimer); _mpvFirstFrameTimer = null }
  const lastVideoH = _mpvLastVideoH
  const frameSeq = seq
  _mpvFirstFrameTimer = setTimeout(async () => {
    _mpvFirstFrameTimer = null
    if (frameSeq !== _loadSeq) return
    if (engine.value !== 'mpv' || !mpvReady.value) return
    const s = await callNative('mpv_state')
    const curH = s && s.state ? (s.state.video_h || 0) : 0
    if (!curH || curH === lastVideoH) {
      const detail = `首帧超时(20s)${s && s.last_error ? '：' + s.last_error : ''}`
      mpvError.value = detail
      reportPlayHealth(false, detail)
      await forceStopAll()
      mpvReady.value = false
      ElMessage.warning(`mpv 首帧超时：${detail}`)
      if (origEng !== 'mpv') {
        engine.value = 'webview'
        playerStore.engine = 'webview'
        if (!maybeFailover()) setupHls()
      }
      // 强制 mpv：不静默回退
    }
  }, 20000)
  return true
}

// D3 修复：首帧超时判定用的跨调用状态
let _mpvFirstFrameTimer = null
let _mpvLastVideoH = 0

async function positionMpv() {
  // 记录当前视频高度（首帧判定基线）
  try {
    const s0 = await callNative('mpv_state')
    if (s0 && s0.state) _mpvLastVideoH = s0.state.video_h || 0
  } catch { /* ignore */ }
  // 当前播放器窗口的 client area 在屏幕上的位置 + 视频区在 client area 内的偏移
  const wrap = document.querySelector('.player-video-wrap')
  if (!wrap) return
  const r = wrap.getBoundingClientRect()
  const hwndRect = await callNative('get_client_rect')
  if (hwndRect) {
    // hwndRect = {x, y, w, h, chrome_h}  client area 屏幕坐标
    const x = hwndRect.x + (r.left || 0)
    const y = hwndRect.y + hwndRect.chrome_h + (r.top || 0)
    const w = Math.max(100, r.width || 100)
    // Phase 2（风险 A）：mpv 只覆盖视频区上部，底部露出 Vue 控制条条带（否则控制条被 OS 窗口盖住）
    let h = Math.max(60, r.height || 60)
    const ctrlEl = wrap.querySelector('.player-controls')
    const ctrlH = ctrlEl && ctrlEl.offsetHeight > 0 ? ctrlEl.offsetHeight + 8 : 0
    h = Math.max(60, h - ctrlH)
    await callNative('mpv_set_rect', Math.round(x), Math.round(y), Math.round(w), Math.round(h))
  } else {
    // fallback: 让 mpv 浮动到屏幕中央
    await callNative('mpv_set_rect', 200, 150)
  }
}

async function switchEngine(newEngine) {
  // P1c：'auto' 作为目标时，根据当前实际状态决定去向
  if (newEngine === 'auto') {
    newEngine = mpvActive.value ? 'webview' : 'mpv'
  }
  if (newEngine === engine.value) return
  // C1 修复：引擎切换窗口期置标志，mpv 轮询跳过，避免竞态双重 setupHls
  engineSwitching = true
  try {
    if (newEngine === 'mpv') {
      // 先 forceStopAll 释放 webview 旧源（hls/flv），再启 mpv
      await forceStopAll()
      const ok = await initMpv()
      if (!ok) {
        ElMessage.warning(mpvError.value || 'mpv 启动失败，保持 WebView')
        return
      }
      engine.value = 'mpv'
      playerStore.engine = 'mpv'
      let playOk = true
      if (currentUrl.value) {
        playOk = await playMpv(currentUrl.value)
      }
      if (playOk) {
        ElMessage.success('已切换到 mpv 引擎（原生解码）')
      }
    } else {
      // 回退 webview：先 forceStopAll 释放所有源（hls/flvPlayer/mpv），避免叠加
      await forceStopAll()
      engine.value = 'webview'
      playerStore.engine = 'webview'
      if (currentUrl.value) {
        setupHls()
      }
      ElMessage.success('已切回 WebView 引擎')
    }
  } finally {
    engineSwitching = false
  }
}

// 控制条引擎标签点击切换（mpv 可用才可点）
function toggleEngineBtn() {
  if (!mpvAvailable.value && !mpvActive.value) {
    ElMessage.warning('mpv 引擎未就位（vendor/mpv/mpv.exe 缺失）')
    return
  }
  switchEngine(mpvActive.value ? 'webview' : 'mpv')
}

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
  // mpv 引擎模式直接换源（不走 webview 播放）
  if (engine.value === 'mpv' && mpvReady.value) {
    playMpv(srcs[i])
    return
  }
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
  if (engine.value === 'mpv' && mpvReady.value) {
    callNative('mpv_set_volume', nv)
    isMuted.value = false
    return
  }
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
  if (engine.value === 'mpv' && mpvReady.value) {
    if (isMuted.value) {
      // unmute：恢复 mute 前音量（若没有记录则用当前音量）
      const nv = _savedVolume != null ? _savedVolume : Math.max(volume.value, 1)
      _savedVolume = null
      callNative('mpv_set_volume', nv)
      volume.value = nv
    } else {
      _savedVolume = volume.value
      callNative('mpv_set_volume', 0)
    }
    isMuted.value = !isMuted.value
    return
  }
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
  if (engine.value === 'mpv' && mpvReady.value) {
    callNative('mpv_set_speed', sp)
    playbackSpeed.value = sp
    playbackSpeedText.value = `${sp}x`
    return
  }
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
  // mpv 引擎模式下不走 webview 播放
  if (engine.value === 'mpv' && mpvReady.value) {
    playMpv(currentUrl.value)
    return
  }
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
            case Hls.Events.MEDIA_ERROR:
              try { hls.recoverMediaError() } catch (_) { /* 尝试恢复失败 */ }
              break
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
    // Phase 5：双窗口新增项——播放窗口置顶 + mpv 跟随播放面板
    if (data.player_window_topmost != null) {
      const wantTop = !!data.player_window_topmost
      if (wantTop !== topmost.value) {
        topmost.value = wantTop
        if (wantTop) callNative('set_topmost', true)
      }
    }
    if (data.mpv_follow_player != null) mpvFollowPlayer.value = !!data.mpv_follow_player
    // 播放引擎（P1c 1.6 播放器预选）：'auto'(默认, mpv 优先失败降级) / 'mpv' / 'webview'
    const pe = data.player_engine || 'auto'
    if (pe === 'mpv' || pe === 'webview' || pe === 'auto') {
      // 问题1修复：引擎设置发生变化时，必须先释放旧音源再切换，
      // 否则旧 webview 声音悬空 + 新源 mpv = 双声叠加
      if (engine.value !== pe) {
        // 记录旧引擎，切换前彻底停旧源
        const oldEng = engine.value
        if (hls || flvPlayer || dashPlayer || mpvReady.value) {
          await forceStopAll()
        }
        engine.value = pe
        playerStore.engine = pe
        // 若当前正有频道在播且处于窗口激活态，立即按新引擎重播
        if (currentUrl.value && (oldEng === 'mpv' && mpvReady.value || oldEng === 'webview')) {
          // 避免重复 init，统一走 setupHls/playMpv 分流（embedded 时由 store watch 触发）
          queueMicrotask(async () => {
            if (pe === 'mpv') {
              const ok = await initMpv()
              if (ok && currentUrl.value) playMpv(currentUrl.value)
              else miscTimers.push(setTimeout(setupHls, 100))
            } else if (pe === 'webview') {
              setupHls()
            } else {
              // auto
              const eff = await resolveEngine(currentUrl.value)
              if (eff === 'mpv' && currentUrl.value) await playMpv(currentUrl.value)
              else miscTimers.push(setTimeout(setupHls, 100))
            }
          })
        }
      } else {
        // 引擎未变，仅更新 store 状态
        playerStore.engine = pe
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
// 否则抓取一小段清单文本，若含相关关键字则判为 h265（浏览器 MSE 不支持，需转码）。
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
          return res.text().then((t) => {
            const low = (t || '').toLowerCase()
            resolve(/h265|hevc|videocodec=h26|codec=hev1|codecs=.{0,8}hev1/.test(low))
          })
        })
        .catch(() => { if (timer) clearTimeout(timer); resolve(false) })
    } catch (e) { if (timer) clearTimeout(timer); resolve(false) }
  })
}

// 构建 h265 → h264 转码代理 URL（后端 ffmpeg 实时转码，输出 HTTP-FLV）
function h264ProxyUrl(srcUrl) {
  return '/api/h264-proxy?url=' + encodeURIComponent(srcUrl)
}

// 引擎解析：auto 时优先 mpv（全协议原生），mpv 不可用按协议回退 webview
// 返回实际生效引擎 'mpv' | 'webview'
// 问题4修复：auto 模式下 RTMP/RTSP 优先走 webview（flv.js + 后端 rtmp_proxy），
// 因为 mpv 播 RTMP 对部分源不稳（连接/超时），走成熟链路更可靠；
// 其余协议（hls/mpd/flv/ts/mp4 等）mpv 可用则用 mpv 原生解码。
async function resolveEngine(urlOverride = null) {
  if (engine.value === 'mpv') return 'mpv'
  if (engine.value === 'webview') return 'webview'
  // auto（Phase 2 起 = Web 优先，与「Web为主 + mpv独立窗可选」决策一致）：
  // 默认走 webview（hls.js/flv.js + RTMP 中继成熟可靠），mpv 仅手动/设置切换时启用。
  return 'webview'
}

// ==================== 统一播放入口（第一点修复）====================
// 修复前：mpv 仅在「手动点状态栏徽标切换引擎」时才会初始化；
// 首播、或设置了「强制 mpv」时，playRow 直接因 mpvReady===false 静默落到 WebView，
// 导致「强制使用 MPV」形同虚设、状态栏始终显示 Web。
// 这里集中做引擎分发，并在需要时主动拉起 mpv（force-mpv 必拉起；auto 非 RTMP 探测后拉起）。
// playRow / 浮层预载 / 独立窗口三处播放入口共用，避免逻辑分叉再出 bug。
async function startPlayback() {
  const url = currentUrl.value || ''
  if (!url) return
  const isRtmpLike = /^(rtmp|rtmps|rtsp):\/\//i.test(url)
  if (engine.value === 'mpv') {
    // 强制 mpv（用户明确要求：不静默回退 webview，让他加载到最后/明确报错即可）
    const ok = await initMpv()
    if (ok) {
      await playMpv(url)
    } else {
      // mpv 不可用（如 vendor/mpv/mpv.exe 缺失）：明确报错并保持 mpv 引擎状态，不自动切 web
      mpvReady.value = false
      ElMessage.error(mpvError.value || 'mpv 启动失败，请在设置中确认 mpv 可用或切换引擎')
    }
    return
  }
  if (engine.value === 'auto') {
    // auto（Phase 2 起 = Web 优先，IPTVnator 式：默认 Web 内核 hls.js/flv.js，不弹 mpv 窗）
    if (isRtmpLike) {
      setupHls()
      return
    }
    const eff = await resolveEngine(url)
    if (eff === 'mpv' && currentUrl.value) await playMpv(currentUrl.value)
    else setupHls()
    return
  }
  // 显式 webview
  setupHls()
}

function onWaiting() { loading.value = true }
function onPlaying() { loading.value = false; playError.value = false; isPaused.value = false; reportPlayHealth(true) }

function onKeyDown(e) {
  if (!keyboardEnabled.value) return
  const tag = (e.target && e.target.tagName) || ''
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag)) return
  // P5: mpv 模式键盘路由到 mpv_*（不碰 videoEl）
  if (engine.value === 'mpv' && mpvReady.value) {
    switch (e.key) {
      case ' ':
      case 'Spacebar':
        e.preventDefault()
        callNative('mpv_toggle_pause')
        break
      case 'ArrowLeft':
        e.preventDefault()
        callNative('mpv_seek', -(seekStep.value / 1000), 'relative')
        break
      case 'ArrowRight':
        e.preventDefault()
        callNative('mpv_seek', seekStep.value / 1000, 'relative')
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
    return
  }
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
      path = externalPref.value === 'potplayer' ? data.pot : data.vlc
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

// 状态栏联动（R4 + 第一点修复）：本地 mpvReady / engine 是唯一数据源，
// 必须同步到 playerStore，否则主窗状态栏 playerStore.mpvActive 永远为 false → 始终显示「Web」。
// 之前只同步 playerStore.engine（switchEngine/loadPlayerConfig），漏掉 playerStore.mpvReady，
// 导致 mpv 真在播时状态栏仍显示 Web。
watch(mpvReady, (v) => { playerStore.mpvReady = v })
watch(engine, (v) => { playerStore.engine = v })

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
    stopMpvStatePoll()
    if (mpvReady.value) {
      callNative('mpv_quit')
      mpvReady.value = false
    }
  }
  // Phase 5：mpv 窗口跟随播放面板——后端 events.moved/resized 触发本回调重定位 mpv
  window.__repositionMpv = () => {
    if (mpvFollowPlayer.value && mpvActive.value) positionMpv()
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
  // 第一点修复：主动探测 mpv 可用性，使状态栏徽标/点击切换可正确反映真实状态
  ensureMpvAvailable()
  // 读取全局设置：获取 fake_live_whitelist（真实直播链接白名单，修复误判）
  try { await settingsStore.fetchSettings() } catch { /* ignore */ }
  if (currentUrl.value) applyPlayerDefaults()

  if (currentUrl.value) {
    // 引擎分流（P1c 1.6 + 第一点修复）：统一走 startPlayback()，强制 mpv 也会主动拉起引擎
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
  // P5-C5 修复：mpv 模式换台不 quit（loadfile replace 天然换源），仅重置状态，
  // 避免 quit→重 init→load 重启风暴；hls/flvPlayer/webview 仍走 forceStopAll
  if (engine.value === 'mpv' && mpvReady.value) {
    resetPlayState()
    // 释放 webview 侧残留（若有）
    if (hls) { try { hls.destroy() } catch (_) {}; hls = null }
    if (flvPlayer) { try { flvPlayer.destroy() } catch (_) {}; flvPlayer = null }
    if (dashPlayer) { try { dashPlayer.reset() } catch (_) {}; dashPlayer = null }
  } else if (hls || flvPlayer || dashPlayer || mpvReady.value) {
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
    // 引擎分流换台（P1c 1.6 + 问题4修复 + 第一点修复）：
    // 统一走 startPlayback()，由它按 engine 决定 mpv/webview 并主动拉起 mpv，
    // 解决「强制 mpv 却静默走 webview / 状态栏恒显 Web」的问题。
    nextTick(() => startPlayback())
  } else if (!hls && videoEl.value) {
    setupHls()
  }
}

// BUG3 修复：统一释放所有播放源，避免多音频流叠加
// 切台/切引擎/关闭时调用，确保旧源彻底停止
// P5-C5 修复：轻量状态重置（不碰引擎进程），mpv 换台时复用，避免 quit 重启风暴
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

// BUG3 修复：统一释放所有播放源（hls/flvPlayer/mpv），避免多音频流叠加
// 切台/切引擎/关闭时调用，确保旧源彻底停止
// 问题1修复：改为 async，mpv_quit 用 mpvQuitSafe await 确认退出后再继续，杜绝叠加
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
  // 3) 退出 mpv（如果运行中）——await 确认退出，避免 mpv 与 webview 双声短暂叠加
  if (mpvReady.value) {
    mpvReady.value = false
    if (engine.value === 'mpv' || engine.value === 'auto') {
      await mpvQuitSafe()
    } else {
      // 静默退出（非 mpv 模式也确保干净）
      await mpvQuitSafe()
    }
  }
  // 4) 清首帧超时计时器
  if (_mpvFirstFrameTimer) { clearTimeout(_mpvFirstFrameTimer); _mpvFirstFrameTimer = null }
  // 5) 重置状态
  resetPlayState()
}

onUnmounted(() => {
  // embedded 模式不注册 __iptvPlay/__iptvCleanup（那是独立窗口模式专属）
  if (window.__iptvPlay === playRow) delete window.__iptvPlay
  if (window.__iptvCleanup) delete window.__iptvCleanup
  window.removeEventListener('keydown', onKeyDown)
  // BUG3：统一释放所有源（hls/flvPlayer/mpv）+ timer + EPG，避免残留
  forceStopAll()
  if (pendingTimer) { clearInterval(pendingTimer); pendingTimer = null }
  if (epgTimer) { clearInterval(epgTimer); epgTimer = null }
  if (epgRefreshTimer) { clearInterval(epgRefreshTimer); epgRefreshTimer = null }
  stopMpvStatePoll()
})

// A1 修复：异步确认 mpv 退出（onUnmounted 非 async，抽成独立函数）
async function mpvQuitSafe() {
  try {
    await Promise.race([
      callNative('mpv_quit'),
      new Promise(resolve => setTimeout(resolve, 3000)),
    ])
  } catch { /* ignore */ }
}
</script>

<style scoped>
.player-page { height: 100%; background: #000; border: 0 !important; margin: 0; padding: 0; }

.player-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 16px; color: var(--el-text-color-secondary);
}

.player-container { height: 100%; display: flex; flex-direction: column; position: relative; }

/* 无外框模式：窗口拖拽条——细窄、悬停显示、拖动时高亮 */
.player-drag-bar {
  height: 16px; cursor: grab;
  display: flex; align-items: center; justify-content: center;
  background: transparent;
  border-bottom: 1px solid transparent;
  transition: background .15s, border-color .15s;
  user-select: none; flex-shrink: 0;
}
.player-drag-bar:hover { background: rgba(255,255,255,0.06); border-bottom-color: rgba(255,255,255,0.12); }
.player-drag-bar:active { cursor: grabbing; }
.drag-hint { font-size: 11px; color: rgba(255,255,255,0.25); letter-spacing: 2px; }
.volume-slider-wrap { width: 100px; flex-shrink: 0; cursor: pointer; }

/* 四角缩放手柄（无外框模式）：四角小圆点，悬停时变亮 */
.resize-handle {
  position: absolute; width: 20px; height: 20px; z-index: 50;
  opacity: 0; transition: none;
  pointer-events: auto; border-radius: 4px;
}
.resize-tl { top: -4px; left: -4px; cursor: nw-resize; background: transparent; }
.resize-tr { top: -4px; right: -4px; cursor: ne-resize; background: transparent; }
.resize-br { bottom: -4px; right: -4px; cursor: se-resize; background: transparent; }
.resize-bl { bottom: -4px; left: -4px; cursor: sw-resize; background: transparent; }


.player-video-wrap {
  flex: 1; display: flex; align-items: center; justify-content: center;
  position: relative; overflow: hidden;
}
.player-video { width: 100%; height: 100%; object-fit: contain; }

/* mpv 引擎占位：纯黑背景 + 顶部小徽标，画面在独立 mpv 窗 */
.mpv-placeholder {
  position: absolute; inset: 0; z-index: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; background: #000; color: #666;
}
.mpv-badge {
  font-size: 11px; letter-spacing: 1px; color: #4ade80;
  border: 1px solid #4ade80; border-radius: 4px; padding: 2px 8px;
}
.mpv-hint { font-size: 12px; color: #888; }

.player-error {
  position: absolute; inset: 0; z-index: 5;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; padding: 24px; text-align: center; color: #fff;
  background: rgba(0,0,0,0.7);
}
.player-error p { margin: 0; font-size: 14px; }
.player-error-hint { font-size: 12px; color: #bbb; }
.player-error-detail { font-size: 11px; color: #888; max-width: 520px; word-break: break-all; margin-top: 4px; }
.player-error-actions { display: flex; gap: 10px; margin-top: 8px; }

.player-controls {
  position: absolute; left: 0; right: 0; bottom: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.85), rgba(0,0,0,0));
  padding: 24px 16px 10px; display: flex; flex-direction: column;
}
.progress-wrap { width: 100%; margin-bottom: 6px; padding: 0 4px; }
.progress-wrap :deep(.el-slider__runway) { background-color: rgba(255,255,255,0.2); height: 3px; }
.progress-wrap :deep(.el-slider__bar) { background-color: var(--el-color-primary); height: 3px; }
.progress-wrap :deep(.el-slider__button) { width: 10px; height: 10px; border: 2px solid #fff; }
.ctrl-row { display: flex; align-items: center; gap: 8px; width: 100%; color: #fff; padding: 0 6px; }
.ctrl-row :deep(.el-button) {
  color: #fff; min-width: 34px; height: 34px; padding: 6px;
  background: transparent !important; border: 1px solid transparent !important;
  border-radius: 6px;
}
.ctrl-row :deep(.el-button:hover) {
  color: var(--el-color-primary);
  background: rgba(255,255,255,0.1) !important;
}
.ctrl-row :deep(.el-button.is-active) {
  color: var(--el-color-primary);
  background: rgba(255,255,255,0.12) !important;
}
.ctrl-row :deep(.el-button .el-icon) { font-size: 17px; }
.ctrl-row :deep(.el-button--default),
.ctrl-row :deep(.el-button--primary),
.ctrl-row :deep(.el-button--danger) { border-color: transparent !important; }
.time-label { font-size: 12px; color: #ccc; font-family: 'Consolas', monospace; }
.speed-label { font-size: 12px; color: #ccc; }
.spacer { flex: 1; }
.player-title {
  font-size: 13px; color: #fff; max-width: 40%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.player-tag {
  flex-shrink: 0; max-width: 30%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.engine-tag { margin-left: 6px; flex-shrink: 0; cursor: default; user-select: none; }
.engine-clickable { cursor: pointer; }

/* ====== 播放器内 EPG 信息条 ====== */
.player-epg-bar {
  position: absolute; top: 0; left: 0; right: 0; z-index: 6;
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; color: #fff;
  background: linear-gradient(to bottom, rgba(0,0,0,0.8), rgba(0,0,0,0));
  font-size: 13px;
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
.epg-collapse { color: #fff; flex-shrink: 0; }
.epg-collapse:hover { color: var(--el-color-primary); }
.epg-reopen {
  position: absolute; top: 10px; right: 14px; z-index: 6; color: #fff;
  background: rgba(0,0,0,0.5); border-radius: 4px;
}
.epg-reopen:hover { color: var(--el-color-primary); }

/* ====== 假直播提示条 ====== */
.player-fakelive-bar {
  position: absolute; left: 0; right: 0; bottom: 72px; z-index: 7;
  display: flex; align-items: center; gap: 10px;
  margin: 0 16px; padding: 8px 14px; border-radius: 8px;
  background: rgba(120, 53, 15, 0.92); color: #fff;
  box-shadow: 0 2px 10px rgba(0,0,0,0.4);
}
.player-fakelive-bar .fl-text { flex: 1; font-size: 13px; }
.player-fakelive-bar .el-button { flex-shrink: 0; }

/* ====== 直播源选择下拉 ====== */
.source-picker-menu { max-height: 320px; overflow-y: auto; padding: 4px; }
.source-picker-menu .sp-menu-title {
  padding: 6px 12px; font-size: 12px; color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter); margin-bottom: 4px;
}
.source-picker-menu .sp-menu-tag {
  margin-left: 6px; font-weight: 600; vertical-align: middle;
}
.source-picker-menu .el-dropdown-menu__item {
  display: flex; align-items: center; gap: 8px; max-width: 380px;
}
.source-picker-menu .sp-idx {
  flex-shrink: 0; min-width: 18px; text-align: center; font-size: 12px;
  color: var(--el-text-color-secondary);
}
.source-picker-menu .sp-url {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px;
  font-family: 'Consolas', monospace;
}
.source-picker-menu .sp-check { color: var(--el-color-primary); flex-shrink: 0; }
.source-picker-menu .sp-group { flex-shrink: 0; margin-left: 4px; }
.source-picker-menu .sp-fake-tag { flex-shrink: 0; margin-left: 4px; }
.source-picker-menu .sp-active { background: var(--el-color-primary-light-9); font-weight: 600; }
.source-picker-menu .sp-fake { color: #d97706; }

/* P1b mini 模式（画中画小窗）：视频区无圆角、无边框，填满容器 */
.player-video-wrap-mini {
  border-radius: 0 !important;
  border: none !important;
}
.player-video-wrap-mini video {
  border-radius: 0 !important;
}
.player-video-wrap-mini .player-epg-bar,
.player-video-wrap-mini .player-fakelive-bar,
.player-video-wrap-mini .epg-reopen {
  display: none !important;
}

/* P5: 媒体信息浮层（6.3）——右下角弹出，非常驻 */
.video-info-overlay {
  position: absolute;
  right: 20px;
  bottom: 80px;
  z-index: 20;
  background: rgba(8, 10, 14, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  padding: 14px 18px;
  font-size: 13px;
  min-width: 220px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.6);
}
.vi-row {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 4px 0;
  align-items: center;
}
.vi-label { color: #94a3b8; font-size: 12px; }
.vi-value { color: #f1f5f9; font-size: 13px; font-family: 'Consolas', monospace; font-weight: 600; }
</style>
