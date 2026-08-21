import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import fs from 'fs'

// 构建时生成 build-info.json（含版本号 + 时间戳），供前后端比对以破除 WebView2 缓存
const pkg = JSON.parse(fs.readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))
const BUILD_TIME = new Date().toISOString()
const BUILD_INFO = {
  version: pkg.version,
  buildTime: BUILD_TIME,
}
// 写入 public/，vite build 会原样拷贝到 dist/build-info.json
try {
  fs.writeFileSync(
    resolve(__dirname, 'public', 'build-info.json'),
    JSON.stringify(BUILD_INFO, null, 2)
  )
} catch (e) {
  console.warn('写入 build-info.json 失败:', e)
}

export default defineConfig({
  plugins: [vue()],
  define: {
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})
