import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import fs from 'fs'


const pkg = JSON.parse(fs.readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))
const BUILD_TIME = new Date().toISOString()
const BUILD_INFO = {
  version: pkg.version,
  buildTime: BUILD_TIME,
}

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
