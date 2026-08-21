import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { initTheme } from './composables/useTheme'

// 构建版本戳（由 vite define 在构建时注入）。用于与后端比对，破除 WebView2 磁盘缓存
// 导致的“改了代码却看不到更新”问题。
const LOCAL_BUILD_TIME = __BUILD_TIME__ || null

async function checkBuildVersion() {
  if (!LOCAL_BUILD_TIME) return
  try {
    const res = await fetch('/api/build-info?_=' + Date.now(), { cache: 'no-store' })
    if (!res.ok) return
    const info = await res.json()
    if (info && info.buildTime && info.buildTime !== LOCAL_BUILD_TIME) {
      console.log('[version] 检测到前端已更新，强制刷新以加载最新版本')
      location.reload(true)
    }
  } catch (e) {
    // 网络异常不阻断启动
  }
}

async function bootstrap() {
  await checkBuildVersion()
  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.use(ElementPlus, { locale: zhCn })
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }
  initTheme()
  app.mount('#app')
}

bootstrap()
