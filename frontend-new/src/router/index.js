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

router.beforeEach((to, from, next) => {
  const isStandalone = to.query.standalone === '1'
  if (to.meta?.standaloneOnly && !isStandalone) {
        next({ path: '/', replace: true })
    try { callNative('open_player') } catch { /* ignore */ }
    return
  }
  next()
})

export default router