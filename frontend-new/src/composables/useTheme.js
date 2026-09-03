import { ref, watch } from 'vue'

const STORAGE_KEY = 'iptv-theme'
const DARK_KEY = 'iptv-dark-mode'

// 预设主题色
export const PRESET_THEMES = [
  { name: '默认蓝', color: '#409EFF' },
  { name: '深邃蓝', color: '#1A365D' },
  { name: '青翠绿', color: '#16A085' },
  { name: '雅致紫', color: '#7B68EE' },
  { name: '热情橙', color: '#E67E22' },
  { name: '玫瑰红', color: '#E74C3C' },
  { name: '石墨灰', color: '#546E7A' },
  { name: '暗夜黑', color: '#2C3E50' },
]

// 内置皮肤 CSS 文件
export const BUILTIN_SKINS = [
  // 暗黑风格
  { name: '赛博朋克', file: 'dark-cyberpunk.css', type: 'dark' },
  { name: '暗夜森林', file: 'dark-forest.css', type: 'dark' },
  { name: '深海暗流', file: 'dark-ocean.css', type: 'dark' },
  { name: '暗烬余晖', file: 'dark-ember.css', type: 'dark' },
  { name: '极致暗黑', file: 'dark-monochrome.css', type: 'dark' },
  // 亮色风格
  { name: '磨砂玻璃', file: 'light-frosted-glass.css', type: 'light' },
  { name: '樱花物语', file: 'light-sakura.css', type: 'light' },
  { name: '薄荷清风', file: 'light-mint.css', type: 'light' },
  { name: '薰衣草梦', file: 'light-lavender.css', type: 'light' },
  { name: '日落暖橙', file: 'light-sunset.css', type: 'light' },
  { name: '浅色现代极简', file: 'light-modern-minimal.css', type: 'light' },
  // 原有主题
  { name: '蓝色背景', file: 'blue-bg-theme.css', type: 'light' },
  { name: 'macOS', file: 'macos-theme.css', type: 'light' },
  { name: 'Windows XP', file: 'winxp-theme.css', type: 'light' },
  { name: 'Windows 7', file: 'win7-theme.css', type: 'light' },
  { name: 'Windows 10', file: 'win10-theme.css', type: 'light' },
  { name: 'Windows 11', file: 'win11-theme.css', type: 'light' },
]

// 从 hex 生成 Element Plus 需要的色阶
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return { r, g, b }
}

function rgbToHex(r, g, b) {
  return '#' + [r, g, b].map(x => Math.round(x).toString(16).padStart(2, '0')).join('')
}

function mixColor(hex, mix, amount) {
  const c = hexToRgb(hex)
  const m = hexToRgb(mix)
  return rgbToHex(
    c.r + (m.r - c.r) * amount,
    c.g + (m.g - c.g) * amount,
    c.b + (m.b - c.b) * amount
  )
}

function generateThemeColors(primary) {
  return {
    '--el-color-primary': primary,
    '--el-color-primary-light-3': mixColor(primary, '#ffffff', 0.3),
    '--el-color-primary-light-5': mixColor(primary, '#ffffff', 0.5),
    '--el-color-primary-light-7': mixColor(primary, '#ffffff', 0.7),
    '--el-color-primary-light-8': mixColor(primary, '#ffffff', 0.8),
    '--el-color-primary-light-9': mixColor(primary, '#ffffff', 0.9),
    '--el-color-primary-dark-2': mixColor(primary, '#000000', 0.2),
  }
}

export const currentTheme = ref(loadTheme())
export const isDark = ref(loadDarkMode())

function loadTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved || '#409EFF'
  } catch { return '#409EFF' }
}

function loadDarkMode() {
  try {
    return localStorage.getItem(DARK_KEY) === 'true'
  } catch { return false }
}

export function setTheme(color) {
  currentTheme.value = color
  localStorage.setItem(STORAGE_KEY, color)
  applyTheme(color)
}

export function toggleDarkMode() {
  isDark.value = !isDark.value
  localStorage.setItem(DARK_KEY, String(isDark.value))
  applyDarkMode(isDark.value)
}

export function setDarkMode(val) {
  isDark.value = val
  localStorage.setItem(DARK_KEY, String(val))
  applyDarkMode(val)
}

function applyTheme(color) {
  const vars = generateThemeColors(color)
  const root = document.documentElement
  for (const [key, value] of Object.entries(vars)) {
    root.style.setProperty(key, value)
  }
}

function applyDarkMode(dark) {
  const root = document.documentElement
  if (dark) {
    root.classList.add('dark')
    root.style.setProperty('color-scheme', 'dark')
    // Element Plus 暗色模式 CSS 变量
    root.style.setProperty('--el-bg-color', '#141414')
    root.style.setProperty('--el-bg-color-page', '#0a0a0a')
    root.style.setProperty('--el-bg-color-overlay', '#1d1e1f')
    root.style.setProperty('--el-text-color-primary', '#e5eaf3')
    root.style.setProperty('--el-text-color-regular', '#cfd3dc')
    root.style.setProperty('--el-text-color-secondary', '#a3a6ad')
    root.style.setProperty('--el-text-color-placeholder', '#8d9095')
    root.style.setProperty('--el-border-color', '#363637')
    root.style.setProperty('--el-border-color-light', '#2b2b2c')
    root.style.setProperty('--el-border-color-lighter', '#262727')
    root.style.setProperty('--el-border-color-extra-light', '#1d1d1e')
    root.style.setProperty('--el-border-color-dark', '#4c4d4f')
    root.style.setProperty('--el-fill-color', '#262727')
    root.style.setProperty('--el-fill-color-light', '#2b2b2c')
    root.style.setProperty('--el-fill-color-lighter', '#363637')
    root.style.setProperty('--el-fill-color-blank', '#141414')
    root.style.setProperty('--el-box-shadow', '0 2px 12px 0 rgba(0,0,0,.4)')
    root.style.setProperty('--el-mask-color', 'rgba(0,0,0,.8)')
    root.style.setProperty('--el-bg-color', '#141414')
  } else {
    root.classList.remove('dark')
    root.style.removeProperty('color-scheme')
    // 清除暗色变量，恢复默认
    const darkVars = [
      '--el-bg-color', '--el-bg-color-page', '--el-bg-color-overlay',
      '--el-text-color-primary', '--el-text-color-regular', '--el-text-color-secondary',
      '--el-text-color-placeholder', '--el-border-color', '--el-border-color-light',
      '--el-border-color-lighter', '--el-border-color-extra-light', '--el-border-color-dark',
      '--el-fill-color', '--el-fill-color-light', '--el-fill-color-lighter',
      '--el-fill-color-blank', '--el-box-shadow', '--el-mask-color'
    ]
    darkVars.forEach(v => root.style.removeProperty(v))
  }
}

// 外部导入的皮肤（Element Plus theme CSS）
let _externalStyleEl = null

export function importThemeCss(cssText) {
  // 移除旧的外部皮肤
  if (_externalStyleEl) {
    _externalStyleEl.remove()
    _externalStyleEl = null
  }
  // 注入新的皮肤 CSS
  _externalStyleEl = document.createElement('style')
  _externalStyleEl.id = 'iptv-external-theme'
  _externalStyleEl.textContent = cssText
  document.head.appendChild(_externalStyleEl)
  // 标记为自定义皮肤
  localStorage.setItem(STORAGE_KEY, '__custom__')
  currentTheme.value = '__custom__'
}

export function importThemeFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        importThemeCss(e.target.result)
        resolve()
      } catch (err) { reject(err) }
    }
    reader.onerror = () => reject(new Error('读取文件失败'))
    reader.readAsText(file)
  })
}

export function clearCustomTheme() {
  if (_externalStyleEl) {
    _externalStyleEl.remove()
    _externalStyleEl = null
  }
  localStorage.removeItem(STORAGE_KEY)
  currentTheme.value = '#409EFF'
  applyTheme('#409EFF')
}

// 加载内置皮肤 CSS 文件
export async function loadBuiltinSkin(skinFile) {
  try {
    const resp = await fetch(`/themes/${skinFile}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const cssText = await resp.text()
    importThemeCss(cssText)
    localStorage.setItem('iptv-builtin-skin', skinFile)
    return true
  } catch (e) {
    console.error('加载内置皮肤失败:', e)
    throw e
  }
}

// 获取当前内置皮肤文件名
export function getBuiltinSkinName() {
  try {
    return localStorage.getItem('iptv-builtin-skin') || ''
  } catch { return '' }
}

export function initTheme() {
  const saved = currentTheme.value
  if (saved === '__custom__') {
    // 尝试恢复内置皮肤
    const builtinSkin = getBuiltinSkinName()
    if (builtinSkin) {
      loadBuiltinSkin(builtinSkin).catch(() => {
        currentTheme.value = '#409EFF'
        applyTheme('#409EFF')
      })
    } else {
      currentTheme.value = '#409EFF'
      applyTheme('#409EFF')
    }
  } else {
    applyTheme(saved)
  }
  applyDarkMode(isDark.value)
}