<template>
  <div class="repair-view">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>乱码修补</span>
          <el-text type="info" size="small">粘贴需要修补的 M3U/TXT 文本，修复中文乱码后分类为母链与频道</el-text>
        </div>
      </template>

      <el-form label-width="70px" size="default">
        <el-form-item label="文本">
          <el-input
            v-model="repairText"
            type="textarea"
            :rows="8"
            placeholder="粘贴需要修补的 M3U/TXT 文本（支持 #genre#、name→url、name,url$备注 等格式）"
          />
        </el-form-item>
        <el-form-item label="模式">
          <el-radio-group v-model="repairMode" :disabled="!repairSaveOnly">
            <el-radio label="纯净模式">纯净模式</el-radio>
            <el-radio label="保留元数据">保留元数据</el-radio>
            <el-radio label="完整增强">完整增强</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="选项">
          <el-switch v-model="repairSaveOnly" active-text="仅保存文件" inactive-text="导入列表" />
          <el-select v-if="repairSaveOnly" v-model="repairFmt" size="default" style="width: 90px; margin-left: 12px">
            <el-option label="M3U" value="m3u" />
            <el-option label="TXT" value="txt" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doRepair" :loading="repairBusy">执行修复</el-button>
          <el-button @click="repairText = ''">清空</el-button>
        </el-form-item>
      </el-form>

      <el-card v-if="repairPreview.length" shadow="never" style="margin-top: 16px">
        <template #header><span>修复前后对照预览</span></template>
        <el-table :data="repairPreview" size="small" max-height="240" style="width: 100%">
          <el-table-column prop="before" label="修复前（原始）" show-overflow-tooltip />
          <el-table-column prop="after" label="修复后（编码修正）" show-overflow-tooltip />
        </el-table>
      </el-card>

      <el-row :gutter="16" v-if="parentLinks.length || channels.length" style="margin-top: 16px">
        <!-- 左侧：母链 -->
        <el-col :span="12">
          <el-card shadow="never" class="result-card">
            <template #header>
              <div class="result-header">
                <span>母链链接（M3U/TXT/网页）</span>
                <el-button size="small" @click="saveParents">保存母链</el-button>
              </div>
            </template>
            <el-table
              :data="parentLinks"
              size="small"
              max-height="360"
              style="width: 100%"
              @selection-change="handleParentSelectionChange"
            >
              <el-table-column type="selection" width="45" />
              <el-table-column prop="name" label="名称" show-overflow-tooltip />
              <el-table-column prop="url" label="URL" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag v-if="row.status === '成功'" type="success" size="small">成功</el-tag>
                  <el-tag v-else type="danger" size="small">失败</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="count" label="频道数" width="80" />
            </el-table>
          </el-card>
        </el-col>

        <!-- 右侧：频道 -->
        <el-col :span="12">
          <el-card shadow="never" class="result-card">
            <template #header>
              <div class="result-header">
                <span>频道链接（可直接播放）</span>
                <div>
                  <el-button size="small" type="primary" @click="importChannels">频道→导入</el-button>
                  <el-button size="small" @click="saveChannels">频道→保存</el-button>
                </div>
              </div>
            </template>
            <el-table
              :data="channels"
              size="small"
              max-height="360"
              style="width: 100%"
              @selection-change="handleChannelSelectionChange"
            >
              <el-table-column type="selection" width="45" />
              <el-table-column prop="name" label="频道名" show-overflow-tooltip />
              <el-table-column prop="group" label="分组" width="100" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag v-if="row.status === '在线'" type="success" size="small">在线</el-tag>
                  <el-tag v-else-if="row.status === '离线'" type="danger" size="small">离线</el-tag>
                  <el-tag v-else type="info" size="small">未检查</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="ms" label="延迟" width="80" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useChannelStore } from '@/stores/channels'
import { saveTextFile } from '@/composables/useNative'
import * as scrapeApi from '@/api/scrape'
import * as exportApi from '@/api/export'

const store = useChannelStore()

const repairText = ref('')
const repairMode = ref('纯净模式')
const repairSaveOnly = ref(false)
const repairFmt = ref('m3u')
const repairBusy = ref(false)
const repairPreview = ref([])
const parentLinks = ref([])
const channels = ref([])
const selectedParents = ref([])
const selectedChannels = ref([])

function downloadFile(content, filename) {
  return saveTextFile(filename, content)
}

async function doRepair() {
  if (!repairText.value.trim()) return ElMessage.warning('请输入文本')
  repairBusy.value = true
  repairPreview.value = []
  parentLinks.value = []
  channels.value = []
  try {
    const mode = repairSaveOnly.value ? repairMode.value : '完整增强'
    const resp = await exportApi.repair({
      text: repairText.value, mode: mode,
      save_only: repairSaveOnly.value, fmt: repairFmt.value
    }, repairSaveOnly.value ? 'text' : 'json')
    if (repairSaveOnly.value) {
      await downloadFile(resp.data, `修复结果.${repairFmt.value}`)
      ElMessage.success('已保存修复结果')
    } else {
      if (resp.data.error) {
        ElMessage.error(resp.data.error)
      } else {
        repairPreview.value = resp.data.preview || []
        parentLinks.value = resp.data.parent_links || []
        channels.value = resp.data.channels || []
        ElMessage.success(`已修复：母链 ${parentLinks.value.length} 条，频道 ${channels.value.length} 个`)
      }
    }
  } catch {
    ElMessage.error('修补失败')
  }
  repairBusy.value = false
}

function handleParentSelectionChange(rows) {
  selectedParents.value = rows
}

function handleChannelSelectionChange(rows) {
  selectedChannels.value = rows
}

async function importChannels() {
  const list = selectedChannels.value.length ? selectedChannels.value : channels.value
  if (!list.length) return ElMessage.warning('没有可导入的频道')
  try {
    await scrapeApi.importChannels(list)
    ElMessage.success(`已导入 ${list.length} 个频道`)
    store.refresh()
  } catch {
    ElMessage.error('导入失败')
  }
}

function buildM3u(list) {
  const lines = ['#EXTM3U']
  for (const ch of list) {
    lines.push(`#EXTINF:-1 group-title="${ch.group || '未分组'}"${ch.logo ? ` tvg-logo="${ch.logo}"` : ''},${ch.name}`)
    lines.push(`${ch.url}${ch.url_note ? '$' + ch.url_note : ''}`)
  }
  return lines.join('\n')
}

function buildTxt(list) {
  const groups = {}
  for (const ch of list) {
    const g = ch.group || '未分组'
    if (!groups[g]) groups[g] = []
    groups[g].push(`${ch.name},${ch.url}${ch.url_note ? '$' + ch.url_note : ''}`)
  }
  const lines = []
  for (const g of Object.keys(groups)) {
    lines.push(`${g},#genre#`)
    lines.push(...groups[g])
  }
  return lines.join('\n')
}

async function saveChannels() {
  const list = selectedChannels.value.length ? selectedChannels.value : channels.value
  if (!list.length) return ElMessage.warning('没有可保存的频道')
  const content = buildM3u(list)
  await downloadFile(content, '频道链接.m3u')
  ElMessage.success('已保存频道链接')
}

async function saveParents() {
  const list = selectedParents.value.length ? selectedParents.value : parentLinks.value
  if (!list.length) return ElMessage.warning('没有可保存的母链')
  const content = list.map(p => `${p.name || '母链'},${p.url}`).join('\n')
  await downloadFile(content, '母链链接.txt')
  ElMessage.success('已保存母链链接')
}
</script>

<style scoped>
.repair-view {
  max-width: 1200px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.result-card {
  min-height: 360px;
}
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
