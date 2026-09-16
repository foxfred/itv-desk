<template>
  
  <router-view v-if="isStandalonePlayer" />

  
  <div v-else class="app-shell">
    
    <TitleBar />
    <el-container class="app-layout">
    
    <el-aside :width="sidebarCollapsed ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <el-icon :size="24" color="var(--el-color-primary)"><VideoCamera /></el-icon>
        <span v-show="!sidebarCollapsed" class="logo-text">ITV Desk</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="sidebarCollapsed"
        :collapse-transition="false"
        router
        class="app-menu"
      >
        <el-menu-item index="/" title="频道总览：手动导入、一次性抓取、检测与筛选（频道池主入口）">
          <el-icon><Monitor /></el-icon>
          <span>频道管理</span>
        </el-menu-item>
        <el-menu-item index="/wall" title="频道墙：图标式预览全部频道，一眼看完画面与延迟，点击直接播放">
          <el-icon><Grid /></el-icon>
          <span>频道墙</span>
        </el-menu-item>
        <el-menu-item index="/epg" title="电视节目单">
          <el-icon><Calendar /></el-icon>
          <span>节目单</span>
        </el-menu-item>
        <el-menu-item index="/repair" title="修复中文乱码并导入频道">
          <el-icon><Tools /></el-icon>
          <span>乱码修补</span>
        </el-menu-item>
        <el-menu-item index="/history" title="播放与收藏记录">
          <el-icon><Clock /></el-icon>
          <span>播放历史</span>
        </el-menu-item>
        <el-menu-item index="/subscriptions" title="长期自动更新的源：按设定周期增量拉取并合并（非一次性抓取，区别于「频道管理→抓取配置」）">
          <el-icon><Link /></el-icon>
          <span>订阅源</span>
        </el-menu-item>
        <el-menu-item index="/scan" title="从频道链接反推 IP 段，扫描相邻网段发现新源">
          <el-icon><Connection /></el-icon>
          <span>扫描网段</span>
        </el-menu-item>
        <el-menu-item index="/record" title="录制与回放：把正在看的频道录下来，随时回看">
          <el-icon><VideoCamera /></el-icon>
          <span>录像管理</span>
        </el-menu-item>
        <el-menu-item index="/settings" title="全局设置">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    
    <el-container class="app-main">
      
      <el-header class="app-header" height="48px">
        <div class="header-left">
          <el-button text @click="sidebarCollapsed = !sidebarCollapsed">
            <el-icon :size="18"><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          
          <el-button
            text
            :type="playerStore.currentChannel ? 'primary' : ''"
            title="打开/恢复播放窗口（也可在列表中双击频道）"
            @click="reopenPlayer"
          >
            <el-icon :size="16"><VideoPlay /></el-icon>
            <span class="header-label">播放窗口</span>
          </el-button>
          
          <el-dropdown trigger="click" @command="setTheme">
            <el-button text>
              <el-icon :size="16"><Brush /></el-icon>
              <span class="header-label">主题</span>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  v-for="t in PRESET_THEMES"
                  :key="t.color"
                  :command="t.color"
                  :class="{ active: currentTheme === t.color }"
                >
                  <span class="theme-dot" :style="{ background: t.color }" />
                  {{ t.name }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <!-- 暗色模式 -->
          <el-button text @click="toggleDarkMode">
            <el-icon :size="16"><Sunny v-if="isDark" /><Moon v-else /></el-icon>
          </el-button>
        </div>
      </el-header>

      <!-- 主内容（频道列表等主视图）—— 始终满尺寸，不被播放器挤压 -->
      <el-main class="app-content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>

      <!-- 状态栏 -->
      <el-footer v-if="playerStore.currentChannel" class="app-statusbar" height="26px">
        <span class="sb-engine">Web</span>
        <span class="sb-sep">|</span>
        <span class="sb-name" :title="playerStore.currentUrl || ''">{{ playerStore.currentChannel?.name || '未播放' }}</span>
        <span v-if="playerStore.currentUrlNote" class="sb-note">{{ playerStore.currentUrlNote }}</span>
        <span v-if="playerStore.videoInfo?.w" class="sb-sep">|</span>
        <span v-if="playerStore.videoInfo?.w" class="sb-res">{{ playerStore.videoInfo.w }}×{{ playerStore.videoInfo.h }}<template v-if="playerStore.videoInfo?.fps"> @ {{ playerStore.videoInfo.fps }}fps</template><template v-if="playerStore.videoInfo?.bitrate"> · {{ playerStore.videoInfo.bitrate }}k</template></span>
      </el-footer>
    </el-container>
  </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  currentTheme, isDark, PRESET_THEMES,
  setTheme, toggleDarkMode
} from '@/composables/useTheme'
import { usePlayerStore } from '@/stores/player'
import { callNative } from '@/composables/useNative'
import TitleBar from '@/components/TitleBar.vue'

const route = useRoute()
const sidebarCollapsed = ref(true)
const playerStore = usePlayerStore()

const isStandalonePlayer = computed(() => route.query.standalone === '1')

async function reopenPlayer() {
  await callNative('open_player')
}

window.__updatePlaying = (p) => {
  if (!p) return
  const cur = playerStore.currentChannel || {}
  if (p.name || p.url) {
    playerStore.currentChannel = { ...cur, name: p.name || cur.name, url: p.url || cur.url }
  }
  if (p.url) playerStore.currentUrl = p.url
  if (p.note != null) playerStore.currentUrlNote = p.note
  if (p.engine) {
    playerStore.videoInfo.engine = p.engine
  }
  if (p.w) {
    playerStore.videoInfo = { w: p.w, h: p.h || 0, fps: p.fps || 0, engine: p.engine || 'Web', bitrate: p.bitrate || 0 }
  }
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #app {
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-layout {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
}

.app-aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  transition: width 0.2s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.app-menu {
  flex: 1;
  border-right: none !important;
  overflow-y: auto;
  overflow-x: hidden;
}

.app-menu:not(.el-menu--collapse) {
  width: 219px;
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 0 16px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-label {
  margin-left: 4px;
  font-size: 13px;
}

.theme-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 8px;
  vertical-align: middle;
}

.app-content {
  flex: 1;
  padding: 16px;
  overflow: auto;
  background: var(--el-bg-color-page);
}


.app-statusbar {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
  padding: 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.sb-engine { font-weight: 600; color: var(--el-color-info); }
.sb-sep { opacity: 0.4; }
.sb-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 40%; }
.sb-note { color: var(--el-color-info); font-size: 11px; }
.sb-res { font-family: 'Consolas', monospace; color: var(--el-text-color-secondary); font-size: 11px; }


::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-thumb { background: var(--el-border-color-dark); border-radius: 3px; }
::-webkit-scrollbar-track { background: transparent; }
</style>
