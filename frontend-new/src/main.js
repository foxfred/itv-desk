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
// 导致的"改了代码却看不到更新"问题。
const LOCAL_BUILD_TIME = __BUILD_TIME__ || null

// 版本自检：仅记录前后端版本，不再触发 location.reload。
// 原因：Electron 下后端 _serve_index 已对 /assets 注入唯一 UUID 强制破除缓存，
// 新构建会被自动加载；旧版用 build-info.json 比对会触发无限 reload（该文件在沙箱被锁无法更新），
// 故改为仅日志，避免右侧空白/刷屏。
async function checkBuildVersion() {
  if (!LOCAL_BUILD_TIME) return
  try {
    const res = await fetch('/api/build-info?_=' + Date.now(), { cache: 'no-store' })
    if (!res.ok) return
    const info = await res.json()
    if (info && info.buildTime) {
      const t1 = new Date(info.buildTime).getTime()
      const t2 = new Date(LOCAL_BUILD_TIME).getTime()
      if (Number.isFinite(t1) && Number.isFinite(t2) && Math.abs(t1 - t2) > 2000) {
        console.warn('[version] 前端构建时间与后端不一致（dist 可能非本次构建），但已通过 UUID 强制缓存破除，无需手动刷新')
      }
    }
  } catch (e) {
    // 网络异常不阻断启动
  }
}

async function bootstrap() {
  try {
    await checkBuildVersion()
  } catch (e) {
    console.error('[bootstrap] checkBuildVersion 失败:', e)
  }
  let app
  try {
    app = createApp(App)
    app.use(createPinia())
    app.use(router)
    app.use(ElementPlus, { locale: zhCn })
    for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
      app.component(key, component)
    }
    initTheme()
  } catch (e) {
    console.error('[bootstrap] Vue 初始化失败:', e)
    return
  }
  try {
    app.mount('#app')
  } catch (e) {
    console.error('[bootstrap] app.mount 失败:', e)
  }
}

bootstrap()
