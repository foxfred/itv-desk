import { createRouter, createWebHashHistory } from 'vue-router'
import { callNative } from '@/composables/useNative'

const routes = [
  {
    path: '/',
    name: 'channels',
    component: () => import('@/views/ChannelView.vue'),
    meta: { title: '频道管理', icon: 'Monitor' }
  },
  {
    path: '/player',
    name: 'player',
    component: () => import('@/views/PlayerView.vue'),
    meta: { title: '播放器', icon: 'VideoPlay', fullscreen: true, standaloneOnly: true }
  },
  {
    path: '/epg',
    name: 'epg',
    component: () => import('@/views/EpgView.vue'),
    meta: { title: '节目单', icon: 'Calendar' }
  },
  {
    path: '/repair',
    name: 'repair',
    component: () => import('@/views/RepairView.vue'),
    meta: { title: '乱码修补', icon: 'Tools' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { title: '播放历史', icon: 'Clock' }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '系统设置', icon: 'Setting' }
  },
  {
    path: '/subscriptions',
    name: 'subscriptions',
    component: () => import('@/views/SubscriptionView.vue'),
    meta: { title: '订阅源', icon: 'Link' }
  },
  {
    path: '/scan',
    name: 'scan',
    component: () => import('@/views/ScanView.vue'),
    meta: { title: '扫描网段', icon: 'Connection' }
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// Electron 主窗路由守卫：/player 只在独立播放窗（?standalone=1）中访问；
// 主窗若误跳到 /player（drawer 浮层/手动导航），自动跳回 / 并尝试打开独立播放窗。
// 原因：主窗系统标题栏会与 PlayerView 浮层叠加（出现"白边框"错觉），
// 且独立播放窗才是 PotPlayer 极简无边框的正确载体。
router.beforeEach((to, from, next) => {
  const isStandalone = to.query.standalone === '1'
  if (to.meta?.standaloneOnly && !isStandalone) {
    // 主窗误入 /player：跳回首页，并唤起独立播放窗
    next({ path: '/', replace: true })
    try { callNative('open_player') } catch { /* ignore */ }
    return
  }
  next()
})

export default router