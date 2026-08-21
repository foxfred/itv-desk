// PlayerStore —— 全局播放器状态（P1 单窗口融合，唯一数据源 R1）
// 所有视图（ChannelView/PlayerView/搜索/历史/EPG）只读写本 store，不直接互相调用。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePlayerStore = defineStore('player', () => {
  // ===== 布局状态（P2 App.vue 单窗口浮层使用）=====
  // 状态机：hidden → drawer(右浮层) → pip(右下角小窗) / full(全屏)
  const state = ref('hidden')     // 'hidden' | 'drawer' | 'pip' | 'full'
  const width = ref(480)          // 播放器浮层宽度（可拖拽，320-720）
  const miniWidth = ref(360)     // 画中画小窗宽度（BUG2 修复：容纳"展开"文字按钮）
  // 问题2/3修复：浮层可自由拖动定位（drawer 与 pip 共用，x/y 为主窗内相对坐标）
  // 初始：drawer 靠右，pip 靠右下角；null 表示用默认位置（CSS 决定）
  const drawerPos = ref(null)    // {x, y} 或 null（首次用默认 right 布局）
  const pipPos = ref(null)       // {x, y} 或 null

  // ===== 播放状态（唯一数据源）=====
  const currentChannel = ref(null) // 当前频道对象 {id,url,name,group,sources,source_groups,tag,is_fake_live,url_note,...}
  const channelList = ref([])      // 当前视图频道列表快照（上/下一频道导航）
  const channelIndex = ref(-1)     // 当前频道在列表中的下标
  const currentUrl = ref('')       // 实际播放地址（已剥离 $ 后缀）
  const currentUrlNote = ref('')   // $ 后标签（如「组播超高清-50fps」）
  const engine = ref('auto')       // 'auto' | 'mpv' | 'webview'（auto=mpv 优先失败降级）
  const mpvReady = ref(false)      // mpv 子进程是否就绪
  const mpvActive = computed(() => engine.value === 'mpv' && mpvReady.value)
  // R4: 媒体信息（状态栏展示，PlayerView 同步写入）
  const videoInfo = ref({ w: 0, h: 0, fps: 0, engine: '' })

  // ===== 动作 =====
  function open(channel, list = null, idx = -1) {
    if (!channel || !channel.url) return
    const sameChannel = channel.url === currentUrl.value
    currentChannel.value = channel
    currentUrl.value = channel.url
    currentUrlNote.value = channel.url_note || ''
    if (list && Array.isArray(list) && list.length > 0) {
      channelList.value = list
      channelIndex.value = idx >= 0 ? idx : list.findIndex(ch => ch.url === channel.url)
    }
    // 布局联动：打开即进入 drawer 态（P2 生效；P1 阶段前端尚未集成浮层，此字段先记录）
    if (state.value === 'hidden') state.value = 'drawer'
    return { sameChannel, changed: !sameChannel }
  }

  function next() {
    if (channelIndex.value < 0 || !channelList.value.length) return null
    if (channelIndex.value >= channelList.value.length - 1) return null
    channelIndex.value++
    const ch = channelList.value[channelIndex.value]
    if (ch && ch.url) {
      open(ch, channelList.value, channelIndex.value)
      return ch
    }
    return null
  }

  function prev() {
    if (channelIndex.value <= 0 || !channelList.value.length) return null
    channelIndex.value--
    const ch = channelList.value[channelIndex.value]
    if (ch && ch.url) {
      open(ch, channelList.value, channelIndex.value)
      return ch
    }
    return null
  }

  function setState(s) {
    if (['hidden', 'drawer', 'pip', 'full'].includes(s)) state.value = s
  }

  function enterPip() {
    if (state.value === 'drawer' || state.value === 'full') state.value = 'pip'
  }

  function exitPip() {
    if (state.value === 'pip') state.value = 'drawer'
  }

  function close() {
    state.value = 'hidden'
    mpvReady.value = false
    // 保留 currentChannel/currentUrl 供再次打开快速恢复？不——关闭即清空（R5 会话级）
    currentChannel.value = null
    currentUrl.value = ''
    currentUrlNote.value = ''
  }

  return {
    // state
    state, width, miniWidth, drawerPos, pipPos,
    currentChannel, channelList, channelIndex,
    currentUrl, currentUrlNote,
    engine, mpvReady, mpvActive,
    videoInfo,
    // actions
    open, next, prev, setState, enterPip, exitPip, close,
  }
})
