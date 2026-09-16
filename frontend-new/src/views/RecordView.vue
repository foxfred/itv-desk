<template>
  <div class="record-view">
    <el-card shadow="never" class="rv-card">
      <template #header>
        <div class="rv-head">
          <span class="rv-title">录像管理</span>
          <div class="rv-actions">
            <el-tag v-if="activeRows.length" type="danger" effect="dark" size="small">
              正在录制 {{ activeRows.length }} 路
            </el-tag>
            <el-tag v-if="sessions.length" type="warning" effect="dark" size="small">
              时移缓冲 {{ sessions.length }} 路
            </el-tag>
            <el-button size="small" type="danger" plain :disabled="!activeRows.length" @click="stopAll">
              停止全部录制
            </el-button>
            <el-button size="small" :loading="loading" @click="load">
              <el-icon><Refresh /></el-icon>
              <span>刷新</span>
            </el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="activeRows.length" type="warning" :closable="false" class="rv-alert">
        <template #title>
          <span class="rv-alert-text">
            录制中：
            <b v-for="j in activeRows" :key="j.id" class="rv-live">{{ j.name }}</b>
          </span>
        </template>
      </el-alert>

      <el-table :data="records" size="small" stripe height="calc(100vh - 300px)" empty-text="暂无录像">
        <el-table-column prop="file" label="文件名" min-width="380" show-overflow-tooltip />
        <el-table-column prop="size_text" label="大小" width="110" />
        <el-table-column prop="mtime" label="录制时间" width="170" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="preview(row)">预览</el-button>
            <el-button link type="primary" size="small" @click="sendToPlayer(row)">播放器打开</el-button>
            <el-button link type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="previewVisible" :title="previewName" width="70%" top="6vh" destroy-on-close>
      <video v-if="previewUrl" :src="previewUrl" controls autoplay class="rv-video"></video>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as recordApi from '@/api/record'
import { callNative } from '@/composables/useNative'

const records = ref([])
const activeRows = ref([])
const sessions = ref([])
const loading = ref(false)
const previewVisible = ref(false)
const previewUrl = ref('')
const previewName = ref('')
let timer = null

async function load() {
  loading.value = true
  try {
    const { data } = await recordApi.listRecords()
    records.value = (data && data.records) || []
    activeRows.value = (data && data.active) || []
    const ts = await recordApi.listTimeshift()
    sessions.value = (ts.data && ts.data.sessions) || []
  } catch {
    /* interceptor already surfaced the error */
  }
  loading.value = false
}

async function stopAll() {
  try {
    await recordApi.stopRecord('')
    ElMessage.success('已停止全部录制')
    await load()
  } catch {
    /* ignore */
  }
}

function preview(row) {
  previewName.value = row.file
  previewUrl.value = row.url_path
  previewVisible.value = true
}

function sendToPlayer(row) {
  callNative('play_channel', { name: row.file, url: row.url_path })
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除录像「${row.file}」？`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  const { data } = await recordApi.deleteRecord(row.file)
  if (data && data.ok) {
    ElMessage.success('已删除')
    await load()
  } else {
    ElMessage.error((data && data.error) || '删除失败')
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 5000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.record-view {
  height: 100%;
}
.rv-card {
  height: 100%;
}
.rv-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rv-title {
  font-size: 15px;
  font-weight: 600;
}
.rv-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rv-alert {
  margin-bottom: 10px;
}
.rv-live {
  margin-right: 10px;
}
.rv-video {
  width: 100%;
  max-height: 70vh;
  background: #000;
}
</style>
