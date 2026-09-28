<template>
  <div class="sub-page">
    
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button size="small" type="primary" @click="showAdd = true">
          <el-icon><Plus /></el-icon>添加订阅源
        </el-button>
        <el-button size="small" @click="openPresets">
          <el-icon><MagicStick /></el-icon>预置源
        </el-button>
        <el-button size="small" type="success" @click="doUpdateAll" :loading="updatingAll" :disabled="!subs.length">
          <el-icon><Refresh /></el-icon>全部更新
        </el-button>
        <span class="toolbar-hint">更新已启用的订阅源，增量合并到频道列表</span>
      </div>
      <div class="toolbar-right">
        <span class="sub-count">共 {{ subs.length }} 个订阅源</span>
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon class="role-alert">
      <template #title>
        订阅源 = 长期自动更新的来源：启用后按设定周期增量拉取并合并到频道池。只想一次性抓取某个网页 / 链接的频道，请用「频道管理 → 抓取配置」。两者共用同一频道池，按地址去重，不会重复。
      </template>
    </el-alert>

    <!-- 订阅源列表 -->
    <el-table :data="subs" v-loading="loading" size="small" border stripe empty-text="暂无订阅源，点击上方按钮添加" class="sub-table">
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.name || '未命名' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="url" label="地址" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">
          <el-link type="primary" :href="row.url" target="_blank" style="font-size:12px">{{ row.url }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="suffix_list" label="格式后缀" width="110" align="center" />
      <el-table-column prop="enabled" label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enabled"
            @change="(val) => doToggle(row, val)"
            :loading="row._toggling"
            size="small"
            inline-prompt
            active-text="启用"
            inactive-text="禁用"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center">
        <template #default="{ row }">
          <el-button size="small" type="primary" text @click="doUpdateOne(row)" :loading="row._updating">
            <el-icon><Refresh /></el-icon>更新
          </el-button>
          <el-button size="small" type="primary" text @click="editRow(row)">
            <el-icon><Edit /></el-icon>编辑
          </el-button>
          <el-popconfirm title="确认删除该订阅源？" @confirm="doRemove(row)">
            <template #reference>
              <el-button size="small" type="danger" text>
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="showAdd"
      :title="editingSub ? '编辑订阅源' : '添加订阅源'"
      width="520px"
      destroy-on-close
    >
      <el-form :model="form" label-width="80px" size="small" :rules="rules" ref="formRef">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="可选，用于识别" />
        </el-form-item>
        <el-form-item label="地址" prop="url">
          <el-select v-model="form.url" filterable allow-create default-first-option
            placeholder="仅接受母链（目录/播放列表地址，必填），可下拉复用扫描网址历史" style="width:100%">
            <el-option v-for="u in urlHistory" :key="u" :value="u" :label="u" />
          </el-select>
          <div class="form-tip">
            订阅源<b>只接受母链</b>（目录/播放列表地址），频道直链请用「频道管理」添加。<br>
            下拉可复用「频道管理 → 扫描网址」保存过的网址。<br>
            支持的母链：<br>
            • <b>GitHub 仓库目录</b> — 如 github.com/user/repo（更新时自动解析仓库内频道）<br>
            • <b>M3U / M3U8 / TXT 播放列表</b> — 如 raw.githubusercontent.com/.../iptv.m3u<br>
            • 示例：https://github.com/Rivens7/Livelist
          </div>
        </el-form-item>
        <el-form-item label="格式后缀" prop="suffix_list">
          <el-input v-model="form.suffix_list" placeholder="m3u,m3u8,txt" />
        </el-form-item>
        <el-form-item label="加速源">
          <el-input v-model="form.mirror" placeholder="留空则不使用加速" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false; editingSub = null">取消</el-button>
        <el-button type="primary" @click="doAdd" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 预置源弹窗 -->
    <el-dialog v-model="showPresets" title="预置订阅源" width="660px" destroy-on-close>
      <el-alert type="info" :closable="false" show-icon class="role-alert">
        <template #title>按类别分组，勾选后一键导入，导入完成自动更新拉取频道。已存在的源会自动跳过。</template>
      </el-alert>
      <div v-loading="loadingPresets" class="preset-body">
        <el-collapse v-model="presetActiveGroups">
          <el-collapse-item v-for="grp in presetGroups" :key="grp.name" :name="grp.name">
            <template #title>
              <span class="preset-group-title">{{ grp.name }}</span>
              <el-tag size="small" type="info" effect="plain" class="preset-group-tag">
                {{ grp.items.length }} 个
              </el-tag>
              <el-tag v-if="grp.addedCount" size="small" type="success" effect="plain" class="preset-group-tag">
                已添加 {{ grp.addedCount }}
              </el-tag>
            </template>
            <el-table :data="grp.items" size="small" border>
              <el-table-column width="46" align="center">
                <template #default="{ row }">
                  <el-checkbox v-model="row._checked" :disabled="row.added" />
                </template>
              </el-table-column>
              <el-table-column prop="name" label="名称" min-width="190" />
              <el-table-column prop="url" label="地址" min-width="230" show-overflow-tooltip />
              <el-table-column label="状态" width="86" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.added" type="success" size="small">已添加</el-tag>
                  <el-tag v-else type="info" size="small">未添加</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
      <template #footer>
        <el-button @click="showPresets = false">取消</el-button>
        <el-button type="primary" @click="doImportPresets" :loading="importing">导入并更新</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import * as subApi from '@/api/subscriptions'
import { getHistory, saveUrlHistory } from '@/api/export'
import { useChannelStore } from '@/stores/channels'

const loading = ref(false)
const updatingAll = ref(false)
const submitting = ref(false)
const showAdd = ref(false)
const editingSub = ref(null)
const formRef = ref()
const subs = ref([])
const urlHistory = ref([])
const showPresets = ref(false)
const loadingPresets = ref(false)
const importing = ref(false)
const presets = ref([])
const presetActiveGroups = ref([])

// 预置源按 category 分组（保持后端 PRESET_SOURCES 的类别顺序）
const presetGroups = computed(() => {
  const map = new Map()
  for (const p of presets.value) {
    const key = p.category || '其他'
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(p)
  }
  return [...map.entries()].map(([name, items]) => ({
    name,
    items,
    addedCount: items.filter(i => i.added).length,
  }))
})

const form = reactive({
  name: '',
  url: '',
  suffix_list: 'm3u,m3u8,txt',
  mirror: '不使用加速',
  enabled: true,
})

const rules = {
  url: [{ required: true, message: '请输入订阅地址', trigger: 'blur' }],
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await subApi.listSubs()
    subs.value = (data || []).map(s => ({ ...s, _toggling: false, _updating: false }))
  } catch { /* ignore */ }
  loading.value = false
}

function resetForm() {
  form.name = ''
  form.url = ''
  form.suffix_list = 'm3u,m3u8,txt'
  form.mirror = '不使用加速'
  form.enabled = true
}

function editRow(row) {
  editingSub.value = row
  form.name = row.name || ''
  form.url = row.url || ''
  form.suffix_list = row.suffix_list || 'm3u,m3u8,txt'
  form.mirror = row.mirror || '不使用加速'
  form.enabled = row.enabled !== false
  showAdd.value = true
}

async function doAdd() {
  try {
    await formRef.value?.validate()
  } catch { return }
  submitting.value = true
  try {
    if (editingSub.value) {
            await subApi.removeSub(editingSub.value.url)
    }
    const { data } = await subApi.addSub({ ...form })
    if (data.error) { ElMessage.error(data.error); return }
    ElMessage.success(editingSub ? '已更新' : '添加成功')
        if (form.url && (editingSub ? form.url !== editingSub.url : true)) {
      pushUrlHistory(form.url)
    }
    showAdd.value = false
    editingSub.value = null
    resetForm()
    loadList()
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
  submitting.value = false
}

async function doRemove(row) {
  try {
    await subApi.removeSub(row.url)
    ElMessage.success('已删除')
    loadList()
  } catch { ElMessage.error('删除失败') }
}

async function doToggle(row, val) {
  row._toggling = true
  try {
    await subApi.toggleSub(row.url, val)
    row.enabled = val
  } catch { ElMessage.error('切换失败') }
  row._toggling = false
}

async function doUpdateOne(row) {
  row._updating = true
  try {
    const { data } = await subApi.updateOne(row.url)
    if (data.error) { ElMessage.error(data.error) }
    else {
      ElMessage.success(`「${row.name || row.url}」更新完成`)
            await useChannelStore().fetchChannels()
    }
  } catch { ElMessage.error('更新失败') }
  row._updating = false
}

async function doUpdateAll() {
  updatingAll.value = true
  try {
    const { data } = await subApi.updateAll()
    if (data.error) { ElMessage.error(data.error) }
    else {
      ElMessage.success(`全部更新完成${data.added ? `，新增 ${data.added} 个频道` : ''}`)
            await useChannelStore().fetchChannels()
    }
  } catch { ElMessage.error('全部更新失败') }
  updatingAll.value = false
}

async function openPresets() {
  showPresets.value = true
  loadingPresets.value = true
  try {
    const { data } = await subApi.listPresets()
    presets.value = (data || []).map(p => ({ ...p, _checked: !p.added }))
    presetActiveGroups.value = presetGroups.value.map(g => g.name)  // 默认展开全部类别
  } catch { ElMessage.error('获取预置源失败') }
  loadingPresets.value = false
}

async function doImportPresets() {
  const picked = presets.value.filter(p => p._checked && !p.added)
  if (!picked.length) { ElMessage.warning('没有勾选可导入的源'); return }
  importing.value = true
  try {
    const { data } = await subApi.importPresets()
    const ok = (data?.results || []).filter(r => r.status === 'ok').length
    const exists = (data?.results || []).filter(r => r.status === 'exists').length
    ElMessage.success(`导入完成：新增 ${ok} 个${exists ? `，跳过已存在 ${exists} 个` : ''}，开始更新…`)
    showPresets.value = false
    loadList()
    doUpdateAll()
  } catch { ElMessage.error('导入失败') }
  importing.value = false
}

onMounted(() => { loadList(); loadUrlHistory() })

async function loadUrlHistory() {
  try {
    const { data } = await getHistory()
    urlHistory.value = data?.url || []
  } catch { urlHistory.value = [] }
}

function pushUrlHistory(u) {
  const url = (u || '').trim()
  if (!url) return
  urlHistory.value = [url, ...urlHistory.value.filter(x => x !== url)]
  saveUrlHistory(url).catch(() => {})
}
</script>

<style scoped>
.sub-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--el-bg-color);
  border-radius: 6px;
  flex-shrink: 0;
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.sub-count {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.sub-table {
  flex: 1;
}
.role-alert {
  margin-bottom: 12px;
}
.preset-body {
  max-height: 62vh;
  overflow-y: auto;
  padding-right: 4px;
}
.preset-group-title {
  font-weight: 600;
}
.preset-group-tag {
  margin-left: 8px;
}
.form-tip {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  line-height: 1.6;
  margin-top: 4px;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
</style>
