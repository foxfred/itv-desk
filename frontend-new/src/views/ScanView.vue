<template>
  <div class="scan-view">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>扫描网段</span>
          <el-text type="info" size="small">从频道列表选择链接反推网段，或手动输入 IP 段模板批量探测</el-text>
        </div>
      </template>

      <el-form label-width="90px" size="default">
        <el-form-item label="选择频道">
          <el-select
            v-model="selectedUrls"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="从频道池选择 IP 源链接，自动推导 C 段模板"
            style="width: 100%"
          >
            <el-option
              v-for="ch in ipChannels"
              :key="ch.id"
              :label="`${ch.name} (${ch.url})`"
              :value="ch.url"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="deriveFromSelection" :disabled="!selectedUrls.length">反推网段</el-button>
          <el-button @click="selectedUrls = []">清空选择</el-button>
        </el-form-item>

        <el-form-item label="IP 段模板">
          <div class="template-row">
            <el-input v-model="template" placeholder="如 192.168.1.{1-254}:8080 或 192.168.1.0/24" style="flex:1" />
            <el-input v-model="path" placeholder="探测路径，默认 /" style="width:160px; margin-left:8px" />
            <el-select v-model="scheme" style="width:110px; margin-left:8px">
              <el-option label="http" value="http" />
              <el-option label="https" value="https" />
            </el-select>
          </div>
          <div class="template-hint">
            支持格式：192.168.1.{{ 1-254 }}、192.168.1.1-192.168.1.254、192.168.1.0/24、单 IP；端口写在模板末尾。
          </div>
        </el-form-item>

        <el-form-item label="扫描选项">
          <div class="option-row">
            <el-input-number v-model="timeout" :min="1" :max="60" controls-position="right" style="width:100px" />
            <span class="opt-label">超时(秒)</span>
            <el-input-number v-model="maxWorkers" :min="1" :max="200" controls-position="right" style="width:100px; margin-left:16px" />
            <span class="opt-label">并发数</span>
            <el-switch v-model="autoImport" style="margin-left:24px" />
            <span class="opt-label">自动导入在线</span>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="startScan" :loading="scanning" :disabled="!template.trim()">开始扫描</el-button>
          <el-button v-if="scanning" type="danger" plain @click="stopScan">停止</el-button>
          <el-button @click="clearResults">清空结果</el-button>
        </el-form-item>
      </el-form>

      <div v-if="derivedTemplates.length" class="derived-bar">
        <span class="derived-label">已推导模板：</span>
        <el-tag
          v-for="(t, idx) in derivedTemplates"
          :key="idx"
          type="info"
          class="derived-tag"
          @click="applyTemplate(t)"
          style="cursor:pointer"
        >
          {{ t.template }} (来自 {{ t.host }})
        </el-tag>
      </div>

      <el-alert
        v-if="scanning"
        type="info"
        :closable="false"
        show-icon
        style="margin-top:16px"
      >
        <template #title>正在扫描 {{ scanIpCount }} 个 IP:port，预计 {{ estimatedSec }} 秒……请稍候（大网段会较慢）</template>
      </el-alert>

      <el-card v-if="results.length" shadow="never" style="margin-top:16px">
        <template #header>
          <div class="result-header">
            <span>扫描结果（在线 {{ onlineCount }} / 共 {{ results.length }}）</span>
            <el-button size="small" type="primary" @click="importOnline" :disabled="!onlineCount || autoImport">导入在线结果</el-button>
          </div>
        </template>
        <el-table :data="results" size="small" max-height="460" style="width:100%" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="45" />
          <el-table-column prop="ip" label="IP" width="140" />
          <el-table-column prop="port" label="端口" width="80" />
          <el-table-column prop="url" label="探测 URL" show-overflow-tooltip />
          <el-table-column prop="status_code" label="状态码" width="90" />
          <el-table-column prop="ms" label="延迟" width="90" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.online" type="success" size="small">在线</el-tag>
              <el-tag v-else type="danger" size="small">离线</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="copyUrl(row.url)">复制</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useChannelStore } from '@/stores/channels'
import * as scanApi from '@/api/scan'
import * as channelsApi from '@/api/channels'

const store = useChannelStore()

const ipChannels = ref([])
const selectedUrls = ref([])
const derivedTemplates = ref([])
const template = ref('')
const path = ref('/')
const scheme = ref('http')
const timeout = ref(5)
const maxWorkers = ref(40)
const autoImport = ref(false)
const scanning = ref(false)
const results = ref([])
const selectedResults = ref([])

// 估算待扫描 IP 数量（用于提示，非精确）
const scanIpCount = ref(0)
const estimatedSec = computed(() => {
  if (!scanIpCount.value) return 0
  const w = Math.max(1, maxWorkers.value || 40)
  const t = Math.max(1, timeout.value || 5) + 1
  return Math.ceil((scanIpCount.value / w) * t)
})

const onlineCount = computed(() => results.value.filter(r => r.online).length)

onMounted(async () => {
  await store.refresh()
  // 只显示 host 为 IP 的频道
  ipChannels.value = store.channels.filter(ch => {
    try {
      const u = new URL(ch.url)
      return /^\d+\.\d+\.\d+\.\d+$/.test(u.hostname)
    } catch { return false }
  })
})

function applyTemplate(t) {
  template.value = t.template
  path.value = t.path || '/'
  scheme.value = t.scheme || 'http'
}

async function deriveFromSelection() {
  if (!selectedUrls.value.length) return
  try {
    const resp = await scanApi.deriveScanTemplates(selectedUrls.value)
    derivedTemplates.value = resp.data.templates || []
    if (derivedTemplates.value.length) {
      applyTemplate(derivedTemplates.value[0])
      ElMessage.success(`已推导 ${derivedTemplates.value.length} 个网段模板`)
    } else {
      ElMessage.warning('未从选中链接推导出 IP 段模板（仅支持 host 为 IP 的链接）')
    }
  } catch {
    ElMessage.error('反推失败')
  }
}

async function startScan() {
  if (!template.value.trim()) return ElMessage.warning('请输入 IP 段模板')
  scanning.value = true
  results.value = []
  selectedResults.value = []
  scanIpCount.value = estimateIpCount(template.value)
  try {
    const resp = await scanApi.scanRange({
      template: template.value,
      path: path.value || '/',
      scheme: scheme.value,
      timeout: timeout.value,
      max_workers: maxWorkers.value,
    })
    results.value = resp.data.results || []
    ElMessage.success(`扫描完成：在线 ${resp.data.online} / 共 ${resp.data.total}`)
    if (autoImport.value && onlineCount.value) {
      await importOnline()
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '扫描失败'
    ElMessage.error('扫描失败: ' + msg)
  }
  scanning.value = false
  scanIpCount.value = 0
}

// 停止扫描：后端扫描是同步阻塞请求，这里只是结束等待（后端线程池仍会跑完，但不阻塞界面）
function stopScan() {
  scanning.value = false
  scanIpCount.value = 0
  ElMessage.info('已停止等待（后端扫描可能仍在后台完成）')
}

// 粗略估算模板展开的 IP 数量
function estimateIpCount(tpl) {
  const s = (tpl || '').trim()
  if (!s) return 0
  // 花括号: 192.168.1.{1-254}
  const brace = s.match(/\{(\d+)-(\d+)\}/)
  if (brace) return Math.max(0, parseInt(brace[2]) - parseInt(brace[1]) + 1)
  // CIDR: 192.168.1.0/24
  const cidr = s.match(/\/(\d+)/)
  if (cidr) return Math.max(0, Math.pow(2, 32 - parseInt(cidr[1])) - 2)
  // 双点范围: a.b.c.d-a.b.c.d
  const dash = s.match(/(\d+)\.(\d+)\.(\d+)\.(\d+)-(\d+)\.(\d+)\.(\d+)\.(\d+)/)
  if (dash) {
    const d1 = parseInt(dash[4]), d2 = parseInt(dash[8])
    return Math.max(0, d2 - d1 + 1)
  }
  // 短范围: 192.168.1.1-254
  const shortDash = s.match(/(\d+)\.(\d+)\.(\d+)\.(\d+)-(\d+)/)
  if (shortDash) return Math.max(0, parseInt(shortDash[5]) - parseInt(shortDash[4]) + 1)
  return 1
}

function handleSelectionChange(rows) {
  selectedResults.value = rows
}

async function importOnline() {
  const toImport = selectedResults.value.length
    ? selectedResults.value.filter(r => r.online)
    : results.value.filter(r => r.online)
  if (!toImport.length) return ElMessage.warning('没有可导入的在线结果')
  try {
    const resp = await scanApi.importScanResults(toImport)
    ElMessage.success(`导入 ${resp.data.added} 个频道，重复 ${resp.data.dup} 个`)
    store.refresh()
  } catch {
    ElMessage.error('导入失败')
  }
}

function clearResults() {
  results.value = []
  selectedResults.value = []
  derivedTemplates.value = []
}

function copyUrl(url) {
  navigator.clipboard.writeText(url).then(() => ElMessage.success('已复制'))
}
</script>

<style scoped>
.scan-view {
  max-width: 1200px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.template-row {
  display: flex;
  width: 100%;
}
.template-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
}
.option-row {
  display: flex;
  align-items: center;
}
.opt-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-left: 6px;
}
.derived-bar {
  margin-top: 16px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.derived-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.derived-tag {
  user-select: none;
}
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
