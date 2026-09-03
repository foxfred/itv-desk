<template>
  <!-- 自绘顶栏：图标 + ITV Desk + 虚竖线 + 中文菜单 + 窗口按钮（最小化/最大化/关闭）
       背景用 Element CSS 变量，自动跟随当前皮肤。整条可拖拽，交互元素 no-drag。 -->
  <div class="title-bar">
    <!-- 左：品牌区 -->
    <div class="tb-brand">
      <el-icon :size="16" class="tb-logo"><VideoCamera /></el-icon>
      <span class="tb-title">ITV Desk</span>
    </div>

    <!-- 虚竖线分隔（品牌 与 菜单 之间） -->
    <span class="tb-divider" />

    <!-- 中：汉化菜单 -->
    <div class="tb-menu">
      <el-dropdown
        v-for="m in MENUS"
        :key="m.label"
        trigger="click"
        popper-class="tb-menu-popper"
        @command="onCommand"
      >
        <span class="tb-menu-item">{{ m.label }}</span>
        <template #dropdown>
          <el-dropdown-menu>
            <template v-for="(it, idx) in m.items" :key="idx">
              <el-dropdown-item v-if="it.sep" divided :command="''" disabled />
              <el-dropdown-item v-else :command="it.cmd">
                <span class="tb-menu-label">{{ it.label }}</span>
                <span v-if="it.accel" class="tb-menu-accel">{{ it.accel }}</span>
              </el-dropdown-item>
            </template>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 右：窗口控制按钮 -->
    <div class="tb-controls">
      <button class="tb-btn" title="最小化" @click="onMinimize">
        <svg width="10" height="10" viewBox="0 0 10 10"><line x1="0" y1="5" x2="10" y2="5" stroke="currentColor" stroke-width="1" /></svg>
      </button>
      <button class="tb-btn" :title="isMax ? '还原' : '最大化'" @click="onMaximize">
        <svg v-if="!isMax" width="10" height="10" viewBox="0 0 10 10"><rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" stroke-width="1" /></svg>
        <svg v-else width="10" height="10" viewBox="0 0 10 10">
          <rect x="0.5" y="2.5" width="7" height="7" fill="none" stroke="currentColor" stroke-width="1" />
          <path d="M2.5 2.5 V0.5 H9.5 V7.5 H7.5" fill="none" stroke="currentColor" stroke-width="1" />
        </svg>
      </button>
      <button class="tb-btn tb-close" title="关闭" @click="onClose">
        <svg width="10" height="10" viewBox="0 0 10 10"><line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" stroke-width="1.2" /><line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" stroke-width="1.2" /></svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { callNative } from '@/composables/useNative'

const router = useRouter()
const isMax = ref(false)

const MENUS = [
  {
    label: '文件',
    items: [
      { label: '导入频道源…', cmd: 'route:/subscriptions' },
      { sep: true },
      { label: '退出', accel: 'Alt+F4', cmd: 'close' },
    ],
  },
  {
    label: '视图',
    items: [
      { label: '频道管理', accel: 'Ctrl+1', cmd: 'route:/' },
      { label: '节目单', accel: 'Ctrl+2', cmd: 'route:/epg' },
      { label: '乱码修补', accel: 'Ctrl+3', cmd: 'route:/repair' },
      { label: '播放历史', accel: 'Ctrl+4', cmd: 'route:/history' },
      { label: '订阅源', accel: 'Ctrl+5', cmd: 'route:/subscriptions' },
      { label: '扫描网段', accel: 'Ctrl+6', cmd: 'route:/scan' },
      { label: '系统设置', accel: 'Ctrl+7', cmd: 'route:/settings' },
      { sep: true },
      { label: '重新加载', accel: 'Ctrl+R', cmd: 'reload' },
      { label: '全屏', accel: 'F11', cmd: 'fullscreen' },
    ],
  },
  {
    label: '播放',
    items: [
      { label: '打开/恢复播放窗口', accel: 'Ctrl+P', cmd: 'open_player' },
      { label: '关闭播放窗口', cmd: 'close_player' },
    ],
  },
  {
    label: '窗口',
    items: [
      { label: '最小化', cmd: 'minimize' },
      { label: '最大化/还原', cmd: 'maximize' },
      { label: '始终置顶', cmd: 'topmost' },
    ],
  },
  {
    label: '帮助',
    items: [
      { label: '关于 ITV Desk', cmd: 'about' },
    ],
  },
]

async function onCommand(cmd) {
  if (!cmd) return
  if (cmd.startsWith('route:')) {
    router.push(cmd.slice(6))
    return
  }
  switch (cmd) {
    case 'close': await callNative('close_window'); break
    case 'reload': location.reload(); break
    case 'fullscreen': await callNative('toggle_fullscreen'); break
    case 'open_player': await callNative('open_player'); break
    case 'close_player': await callNative('close_player'); break
    case 'minimize': await callNative('minimize'); break
    case 'maximize': await toggleMax(); break
    case 'topmost': {
      const cur = await callNative('is_topmost')
      await callNative('set_topmost', !cur)
      break
    }
    case 'about':
      ElMessageBox.alert(
        '桌面端 IPTV 直播源整理工具\n人机共创软件（人类 × AI Agent）',
        'ITV Desk v3.0.0',
        { confirmButtonText: '确定' }
      )
      break
  }
}

async function toggleMax() {
  const r = await callNative('maximize_window')
  isMax.value = !!r
}
async function onMinimize() { await callNative('minimize') }
async function onMaximize() { await toggleMax() }
async function onClose() { await callNative('close_window') }

// 窗口尺寸变化时同步最大化图标（frameless 下双击拖拽区也会最大化）
function onResize() {
  callNative('is_maximized').then((v) => { isMax.value = !!v })
}
onMounted(() => {
  callNative('is_maximized').then((v) => { isMax.value = !!v })
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.title-bar {
  height: 34px;
  display: flex;
  align-items: stretch;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-lighter);
  -webkit-app-region: drag; /* 整条可拖拽窗口 */
  user-select: none;
  flex-shrink: 0;
}

.tb-brand {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  -webkit-app-region: no-drag;
}
.tb-logo { color: var(--el-color-primary); }
.tb-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

/* 虚竖线：品牌与菜单之间的分隔 */
.tb-divider {
  width: 0;
  border-left: 1px dashed var(--el-border-color);
  margin: 7px 2px;
  align-self: center;
  height: 20px;
}

.tb-menu {
  display: flex;
  align-items: center;
  -webkit-app-region: no-drag;
}
.tb-menu-item {
  display: inline-flex;
  align-items: center;
  height: 100%;
  padding: 0 12px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  cursor: pointer;
  outline: none;
}
.tb-menu-item:hover {
  background: var(--el-fill-color);
  color: var(--el-color-primary);
}

.tb-controls {
  margin-left: auto;
  display: flex;
  align-items: stretch;
  -webkit-app-region: no-drag;
}
.tb-btn {
  width: 44px;
  border: none;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  outline: none;
}
.tb-btn:hover { background: var(--el-fill-color); }
.tb-close:hover { background: #e81123; color: #fff; }
</style>

<style>
/* 菜单弹层 teleport 到 body，落在 drag 区上方会被 OS 拖拽吞点击 → 强制 no-drag */
.tb-menu-popper { -webkit-app-region: no-drag; }
.tb-menu-popper .tb-menu-label { min-width: 130px; display: inline-block; }
.tb-menu-popper .tb-menu-accel { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 24px; }
</style>
