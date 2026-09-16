<template>
  <div class="channel-page">
    
    <el-row v-if="statsCardVisible" :gutter="12" class="stats-row" v-show="statsCardPosition === '顶部'">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-val">{{ store.stats.total }}</div>
          <div class="stat-label">总频道</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card stat-online">
          <div class="stat-val" style="color:var(--el-color-success)">{{ store.stats.online }}</div>
          <div class="stat-label">在线</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card stat-offline">
          <div class="stat-val" style="color:var(--el-color-danger)">{{ store.stats.offline }}</div>
          <div class="stat-label">离线</div>
        </el-card>
      </el-col>
    </el-row>

    
    <div v-if="checkRunning" class="check-progress-bar">
      <div class="progress-info">
        <span class="progress-label">检查进度</span>
        <span class="progress-text">{{ checkProcessed }} / {{ checkTotal }} ({{ checkPercent }}%)</span>
        <span class="progress-status">{{ checkStatus }}</span>
      </div>
      <el-progress
        :percentage="checkPercent"
        :stroke-width="6"
        :status="checkPercent === 100 ? 'success' : ''"
        :striped="checkPercent < 100"
        :striped-flow="checkPercent < 100"
      />
    </div>

    
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button size="small" type="primary" @click="checkAll" :disabled="checkRunning">检查全部</el-button>
        <el-button size="small" type="primary" @click="checkSelected" :disabled="checkRunning">检查选中</el-button>
        <el-button size="small" type="warning" @click="checkResume" :disabled="checkRunning">断点续检</el-button>
        <el-button size="small" type="warning" @click="stopCheck" :disabled="!checkRunning">停止</el-button>
        <el-button size="small" type="danger" plain @click="clearInvalid">清除失效</el-button>
        <el-button size="small" type="danger" plain @click="clearAllChannels">清空列表</el-button>
        <el-button size="small" @click="exportSelected">导出选中</el-button>
        <el-button size="small" @click="exportAll">导出全部</el-button>
      </div>
      <div class="toolbar-right">
        <el-button size="small" @click="selectAll">全选</el-button>
        <el-button size="small" @click="invertSelect">反选</el-button>
        <el-button size="small" @click="smartPaste">
          <el-icon><CopyDocument /></el-icon>粘贴
        </el-button>
        <el-dropdown trigger="click">
          <el-button size="small">更多</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="showImport = true">导入文件</el-dropdown-item>
              <el-dropdown-item @click="showRepair = true">乱码修补</el-dropdown-item>
              <el-dropdown-item @click="showFindReplace = true">查找替换</el-dropdown-item>
              <el-dropdown-item @click="showRules = true">规则管理</el-dropdown-item>
              <el-dropdown-item @click="showGroupTree = !showGroupTree">{{ showGroupTree ? '隐藏分组树' : '显示分组树' }}</el-dropdown-item>
              <el-dropdown-item @click="openDlna()">DLNA 投屏</el-dropdown-item>
              <el-dropdown-item divided @click="doMatchLogos">Logo 自动匹配</el-dropdown-item>
              <el-dropdown-item @click="doOnlineLogos">在线台标补全</el-dropdown-item>
              <el-dropdown-item @click="doReclassify">重新自动分组</el-dropdown-item>
              <el-dropdown-item divided @click="showLogs = true">查看日志</el-dropdown-item>
              <el-dropdown-item @click="showShortcuts = true">快捷键</el-dropdown-item>
              <el-dropdown-item @click="showAbout = true">关于</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-area">
      <!-- 左侧面板 -->
      <div class="left-panel" v-show="showLeftPanel">
        <el-card shadow="never" class="config-card">
          <template #header><span class="card-title">抓取配置</span></template>
          <el-form label-width="70px" size="small" class="scrape-form">
            <el-form-item label="扫描网址">
              <el-select v-model="cfgUrl" filterable allow-create default-first-option style="flex:1">
                <el-option v-for="u in urlHistory" :key="u" :value="u" :label="u" />
              </el-select>
            </el-form-item>
            <el-form-item label="页码范围">
              <div class="form-row">
                <el-input-number v-model="pageStart" :min="1" :controls="false" size="small" style="width:40px" />
                <span class="mx-1">到</span>
                <el-input-number v-model="pageEnd" :min="1" :controls="false" size="small" style="width:40px" />
                <span class="mx-1">页</span>
                <div class="btn-group">
                  <el-button size="small" @click="doSingleUrl">单网址</el-button>
                  <el-button size="small" @click="showUrlPool = true">多网址</el-button>
                </div>
              </div>
            </el-form-item>
            <el-form-item label="格式后缀">
              <el-input v-model="cfgSuffix" placeholder="m3u,m3u8,txt" />
            </el-form-item>
            <el-form-item label="网络代理">
              <div class="form-row">
                <el-switch v-model="useProxy" size="small" />
                <span class="mx-1" style="font-size:12px;color:var(--el-text-color-secondary)">使用代理</span>
              </div>
            </el-form-item>
            <el-form-item v-if="useProxy" label="代理地址">
              <el-input v-model="cfgProxy" placeholder="127.0.0.1:10808" />
            </el-form-item>
            <el-form-item v-else label="加速源">
              <el-select v-model="cfgMirror" filterable allow-create>
                <el-option v-for="m in mirrorHistory" :key="m" :value="m" :label="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="EPG地址">
              <div class="form-row">
                <el-select v-model="cfgEpg" filterable allow-create style="flex:1">
                  <el-option v-for="e in epgHistory" :key="e" :value="e" :label="e" />
                </el-select>
                <el-button size="small" style="margin-left:4px;flex-shrink:0" @click="loadEpg">加载</el-button>
              </div>
            </el-form-item>
            <el-form-item class="scrape-btn-item" label=" ">
              <div class="scrape-btn-wrapper">
                <el-button v-if="!scraping" type="primary" class="scrape-btn" @click="toggleScrape" :loading="scraping">
                  开始抓取
                </el-button>
                <el-button v-else type="danger" class="scrape-btn" @click="toggleScrape">
                  停止抓取
                </el-button>
              </div>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card shadow="never" class="log-card">
          <template #header>
            <span class="card-title">执行日志</span>
            <span class="log-header-actions">
              <el-button size="small" text type="primary" @click="copyLogs">复制日志</el-button>
              <el-button size="small" text @click="clearLogs">清空</el-button>
            </span>
          </template>
          <div class="log-box" ref="logBox" @click="selectLogText">{{ logText }}</div>
        </el-card>
      </div>

      <!-- 左侧开关 -->
      <div class="panel-toggle" @click="showLeftPanel = !showLeftPanel">
        <el-icon><ArrowLeft v-if="showLeftPanel" /><ArrowRight v-else /></el-icon>
      </div>

      <!-- 分组树（可视化分组 + 一键过滤） -->
      <div class="group-tree" v-show="showGroupTree">
        <div class="gt-header">
          <span class="card-title">频道分组</span>
          <el-tooltip content="收起分组树" placement="top">
            <el-icon class="gt-collapse" @click="showGroupTree = false"><Close /></el-icon>
          </el-tooltip>
        </div>
        <el-input v-model="groupKw" placeholder="筛选分组名" clearable size="small" class="gt-search" />
        <div class="gt-list">
          <div class="gt-node" :class="{ active: activeGroup === null }" @click="activeGroup = null">
            <span class="gt-name">全部频道</span>
            <span class="gt-count">{{ store.channels.length }}</span>
          </div>
          <div
            v-for="g in filteredGroups"
            :key="g.group"
            class="gt-node"
            :class="{ active: activeGroup === g.group }"
            :title="g.group"
            @click="activeGroup = g.group"
            @contextmenu.stop="onGroupCtx(g, $event)"
          >
            <span class="gt-name">{{ g.group }}</span>
            <span class="gt-count">{{ g.count }}</span>
          </div>
          <div v-if="!filteredGroups.length" class="gt-empty">暂无分组</div>
        </div>
      </div>

      <!-- 右侧表格 -->
      <div class="right-panel">
        <!-- 过滤器 -->
        <div class="filter-bar">
          <el-button v-if="!showGroupTree" size="small" type="success" @click="showGroupTree = true">
            <el-icon><Menu /></el-icon>分组树
          </el-button>
          <el-input v-model="searchKw" placeholder="搜索频道名称/分组/地址" clearable size="small" style="width:240px" />
          <el-select v-model="filterStatus" placeholder="状态" clearable size="small" style="width:100px">
            <el-option label="在线" value="在线" />
            <el-option label="离线" value="离线" />
            <el-option label="未检查" value="未检查" />
          </el-select>
          <el-select v-model="filterStack" placeholder="网络栈" clearable size="small" style="width:100px">
            <el-option label="IPv4" value="IPv4" />
            <el-option label="IPv6" value="IPv6" />
          </el-select>
          <el-checkbox v-model="hideDead" size="small" border>隐藏死源</el-checkbox>
          <el-checkbox v-model="favoriteOnly" size="small" border>只看收藏</el-checkbox>
          <span class="filter-info">共 {{ filtered.length }} 条</span>
          <el-button size="small" :loading="shotRunning" @click="captureShotsBatch">批量抓帧</el-button>
          <span v-if="shotRunning" class="filter-info">画面 {{ shotDone }}/{{ shotTotal }}</span>
          <el-button size="small" type="primary" plain :loading="nfRunning" @click="openNamefix">名称校正</el-button>
          <span v-if="nfRunning" class="filter-info">校正 {{ nfDone }}/{{ nfTotal }}</span>
          <el-button size="small" type="primary" plain :loading="aiRunning" @click="openAiGroup">AI 智能分组</el-button>
          <el-button size="small" text style="margin-left:auto" @click="showColumnSettings = true">列设置</el-button>
        </div>

        <!-- AI 智能分组 -->
        <el-dialog v-model="showAiGroup" title="AI 智能分组" width="720px" append-to-body>
          <el-alert v-if="!aiReady" type="warning" :closable="false" show-icon style="margin-bottom:10px"
                    title="尚未启用或未填写 AI 模型，请先到「设置 → AI 智能」配置 API 地址与 Key" />
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px">
            <span class="filter-info">分析条数</span>
            <el-input-number v-model="aiLimit" :min="10" :max="400" :step="50" size="small" />
            <el-input v-model="aiExtra" size="small" style="flex:1"
                      placeholder="附加要求（可选），例如：体育频道统一归到「体育」" />
            <el-button size="small" type="primary" :loading="aiRunning" @click="runAiGroup">开始分析</el-button>
          </div>
          <div v-if="aiSummary" class="filter-info" style="margin-bottom:8px">{{ aiSummary }}</div>
          <el-table :data="aiRows" height="340" size="small" v-loading="aiRunning">
            <el-table-column prop="name" label="频道" min-width="240" show-overflow-tooltip />
            <el-table-column label="分组（可改）" width="240">
              <template #default="{ row }">
                <el-input v-model="row.group" size="small" />
              </template>
            </el-table-column>
          </el-table>
          <template #footer>
            <el-button @click="showAiGroup = false">取消</el-button>
            <el-button type="primary" :disabled="!aiRows.length" :loading="aiApplying" @click="applyAiGroup">
              应用到 {{ aiRows.length }} 个频道
            </el-button>
          </template>
        </el-dialog>

        <!-- 频道表格 -->
        <el-table
          :data="displayed"
          v-loading="store.loading"
          size="small"
          height="100%"
          row-key="id"
          border
          stripe
          highlight-current-row
          @row-contextmenu="onRowCtx"
          @row-dblclick="handleRowDblClick"
          @row-click="onRowClick"
          @header-contextmenu="onHeaderCtx"
          @sort-change="onSortChange"
          @header-dragend="onHeaderDragEnd"
          :default-sort="sortState"
          :row-class-name="rowClassName"
          ref="tableRef"
          class="channel-table"
        >
          <el-table-column prop="id" label="#" width="50" sortable="custom" align="center" />
          <el-table-column label="收藏" width="56" align="center">
            <template #default="{ row }">
              <el-button link size="small" class="fav-btn" :class="{ on: isFavRow(row) }"
                         :title="isFavRow(row) ? '取消收藏' : '收藏该频道'"
                         @click.stop="toggleFavRow(row)">
                <el-icon :size="14"><StarFilled v-if="isFavRow(row)" /><Star v-else /></el-icon>
              </el-button>
            </template>
          </el-table-column>
          <el-table-column
            v-for="col in visibleCols"
            :key="col.key"
            :prop="col.prop"
            :label="col.defLabel || col.label"
            :width="col.width"
            :min-width="col.minWidth"
            :sortable="col.sortable !== false ? 'custom' : false"
            :align="col.align || 'center'"
            :show-overflow-tooltip="col.key !== 'screenshot'"
          >
            <template #default="{ row }">
              
              <template v-if="col.key === 'screenshot'">
                <el-image
                  v-if="shotOf(row)"
                  :src="shotOf(row)"
                  :preview-src-list="[shotOf(row)]"
                  preview-teleported
                  fit="cover"
                  class="shot-thumb"
                  :title="row.name + ' 的实时画面'"
                />
                <el-button
                  v-else
                  size="small"
                  text
                  :loading="shotBusy === row.url"
                  @click.stop="captureShotOne(row)"
                >抓帧</el-button>
              </template>
              <template v-else-if="col.key === 'status'">
                <div class="status-cell">
                  <el-tag :type="row.status === '在线' ? 'success' : row.status === '离线' ? 'danger' : 'info'" size="small" effect="dark">
                    {{ row.status }}
                  </el-tag>
                  <span v-if="row.health && row.health.dead" class="health-dead">死源</span>
                  <span v-else-if="row.health && row.health.score != null"
                        class="health-dot" :class="healthClass(row.health.score)"
                        :title="`可看性 ${(row.health.score * 100).toFixed(0)}%`"></span>
                </div>
              </template>
              <template v-else-if="col.key === 'group'">
                <el-tag size="small" effect="plain">{{ row.group }}</el-tag>
              </template>
              <template v-else-if="col.key === 'name'">
                <span class="name-cell">
                  <img v-if="row.logo" :src="row.logo" class="ch-logo" :alt="row.name"
                       @error="onLogoError" />
                  <span class="ch-name">{{ row.name }}</span>
                </span>
              </template>
              <template v-else-if="col.key === 'tag'">
                
                <el-tooltip v-if="adReason(row)" :content="adReason(row)" placement="top">
                  <el-tag size="small" effect="dark" type="danger" style="margin-right:4px">疑似广告</el-tag>
                </el-tooltip>
                
                <el-tag v-if="row.tag" size="small" effect="dark" type="warning">{{ row.tag }}</el-tag>
                <el-tag v-else-if="row.is_fake_live" size="small" effect="dark" type="warning">假直播</el-tag>
                <span v-else class="cell-empty">-</span>
              </template>
              <template v-else>{{ row[col.prop] }}</template>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <el-pagination
          class="pager"
          size="small"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="filtered.length"
          :page-sizes="[50, 100, 200, 500]"
          v-model:current-page="page"
          v-model:page-size="pageSize"
          @size-change="page = 1"
        />
      </div>
    </div>

    <!-- 底部统计卡片 -->
    <el-row v-if="statsCardVisible" :gutter="12" class="stats-row" v-show="statsCardPosition === '底部'">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-val">{{ store.stats.total }}</div>
          <div class="stat-label">总频道</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card stat-online">
          <div class="stat-val" style="color:var(--el-color-success)">{{ store.stats.online }}</div>
          <div class="stat-label">在线</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card stat-offline">
          <div class="stat-val" style="color:var(--el-color-danger)">{{ store.stats.offline }}</div>
          <div class="stat-label">离线</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 导出弹窗 -->
    <el-dialog v-model="showExport" title="导出频道" width="400px" destroy-on-close>
      <el-form label-width="60px" size="small">
        <el-form-item label="格式">
          <el-select v-model="exportFormat" style="width:200px">
            <el-option label="M3U" value="m3u" />
            <el-option label="M3U8" value="m3u8" />
            <el-option label="TXT" value="txt" />
          </el-select>
        </el-form-item>
        <el-form-item label="范围">
          <el-radio-group v-model="exportScope">
            <el-radio label="all">全部</el-radio>
            <el-radio label="selected">选中</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExport = false">取消</el-button>
        <el-button type="primary" @click="doExportConfirm" :loading="exportBusy">导出</el-button>
      </template>
    </el-dialog>

    <!-- 右键菜单 -->
    <div v-if="ctx.show" class="ctx-menu" :class="{ 'ctx-sub-left': ctx.flip }" :style="{ left: ctx.x + 'px', top: ctx.y + 'px' }">
      <!-- 播放类操作 -->
      <div class="ctx-item" @click="ctxPlay">播放</div>
      <div class="ctx-item" @click="ctxPlayExternal">用外部播放器打开</div>
      <div class="ctx-item" @click="ctxDlnaCast">DLNA 投屏</div>
      <div class="ctx-sep" />
      <!-- 复制 / 粘贴 -->
      <div class="ctx-item has-sub">
        <span>复制</span><span class="ctx-arrow">▸</span>
        <div class="ctx-sub">
          <div class="ctx-item" @click="ctxCopyUrl">复制链接</div>
          <div class="ctx-item" @click="ctxCopyNameUrl">复制名称+链接</div>
          <div class="ctx-item" @click="ctxCopyInfo">复制信息（表格样式）</div>
          <div class="ctx-item" @click="ctxCopyM3u">复制 M3U</div>
        </div>
      </div>
      <div class="ctx-item" @click="ctxSmartPaste">智能粘贴</div>
      <div class="ctx-sep" />
      <!-- 批量元数据编辑 -->
      <div class="ctx-item has-sub">
        <span>标记</span><span class="ctx-arrow">▸</span>
        <div class="ctx-sub">
          <div v-for="t in existingTags" :key="t" class="ctx-item" @click="ctxTagExisting(t)">{{ t }}</div>
          <div v-if="existingTags.length" class="ctx-sep" />
          <div class="ctx-item" @click="ctxTagCustom">自定义标记…</div>
          <div class="ctx-item ctx-danger" @click="ctxTagClear">清除标记</div>
        </div>
      </div>
      <div class="ctx-item has-sub">
        <span>设置分组</span><span class="ctx-arrow">▸</span>
        <div class="ctx-sub">
          <div v-for="g in epgGroups" :key="g" class="ctx-item" @click="ctxGroupExisting(g)">{{ g }}</div>
          <div class="ctx-sep" />
          <div class="ctx-item" @click="ctxGroupCustom">自定义分组…</div>
        </div>
      </div>
      <div class="ctx-sep" />
      <!-- 行操作 -->
      <div class="ctx-item" @click="ctxEdit">编辑</div>
      <div class="ctx-item ctx-danger" @click="ctxDelete">删除</div>
    </div>

    <!-- 右键菜单：分组树节点 -->
    <div v-if="ctxGroup.show" class="ctx-menu" :class="{ 'ctx-sub-left': ctxGroup.flip }" :style="{ left: ctxGroup.x + 'px', top: ctxGroup.y + 'px' }">
      <div class="ctx-item ctx-danger" @click="ctxDeleteGroup">
        删除「{{ ctxGroup.group }}」分组<br><small>共 {{ ctxGroup.count }} 个频道</small>
      </div>
    </div>

    <!-- 弹窗：导入文件 -->
    <el-dialog v-model="showImport" title="导入文件" width="420px" destroy-on-close>
      <el-upload drag :auto-upload="false" :on-change="onImportFile" accept=".m3u,.m3u8,.txt,.json">
        <el-icon :size="40"><UploadFilled /></el-icon>
        <div>拖拽文件到此处或点击上传</div>
        <template #tip>支持 M3U / TXT / JSON 格式</template>
      </el-upload>
    </el-dialog>

    <!-- 弹窗：多网址池 -->
    <el-dialog v-model="showUrlPool" title="多网址导入" width="500px" destroy-on-close>
      <el-input v-model="urlPoolText" type="textarea" :rows="8" placeholder="每行一个网址" />
      <template #footer>
        <el-button @click="showUrlPool = false">取消</el-button>
        <el-button type="primary" @click="doUrlPool">导入</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：乱码修补 -->
    <el-dialog v-model="showRepair" title="乱码修补" width="600px" destroy-on-close>
      <el-form label-width="70px" size="small">
        <el-form-item label="文本">
          <el-input v-model="repairText" type="textarea" :rows="6" placeholder="粘贴需要修补的 M3U 文本" />
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
          <el-select v-if="repairSaveOnly" v-model="repairFmt" size="small" style="width:80px;margin-left:8px">
            <el-option label="M3U" value="m3u" />
            <el-option label="TXT" value="txt" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRepair = false">取消</el-button>
        <el-button type="primary" @click="doRepair" :loading="repairBusy">执行修复</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：查找替换 -->
    <el-dialog v-model="showFindReplace" title="查找替换" width="450px" destroy-on-close>
      <el-form label-width="60px" size="small">
        <el-form-item label="查找">
          <el-input v-model="frFind" placeholder="查找内容" />
        </el-form-item>
        <el-form-item label="替换为">
          <el-input v-model="frReplace" placeholder="替换为" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFindReplace = false">取消</el-button>
        <el-button type="primary" @click="doFindReplace">执行</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：规则管理 -->
    <el-dialog v-model="showRules" title="规则管理" width="550px" destroy-on-close>
      <div style="display:flex;gap:10px;margin-bottom:10px">
        <el-input v-model="ruleForm.from" placeholder="原文字" size="small" style="width:160px" />
        <el-input v-model="ruleForm.to" placeholder="替换为" size="small" style="width:160px" />
        <el-button size="small" type="primary" @click="ruleAdd">添加</el-button>
      </div>
      <el-table :data="rulesList" size="small" border height="260" @row-click="rulePick">
        <el-table-column prop="from" label="原文字" />
        <el-table-column prop="to" label="替换为" />
        <el-table-column label="操作" width="60" align="center">
          <template #default="{ $index }">
            <el-button size="small" type="danger" text @click.stop="ruleDel($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showRules = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：查看日志 -->
    <el-dialog v-model="showLogs" title="执行日志" width="600px" destroy-on-close>
      <div class="log-box" style="height:300px" @click="selectLogText">{{ logText }}</div>
      <template #footer>
        <el-button size="small" type="primary" @click="copyLogs">复制日志</el-button>
        <el-button size="small" @click="showLogs = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：快捷键 -->
    <el-dialog v-model="showShortcuts" title="快捷键参考" width="500px" destroy-on-close>
      <el-table :data="shortcutList" size="small" border>
        <el-table-column prop="cat" label="分类" width="80" />
        <el-table-column prop="key" label="快捷键" width="140" />
        <el-table-column prop="desc" label="功能" />
      </el-table>
    </el-dialog>

    <!-- 弹窗：关于 -->
    <el-dialog v-model="showAbout" title="关于" width="400px" destroy-on-close>
      <div style="text-align:center;padding:12px 0">
        <p style="font-size:18px;font-weight:600">IPTV Core PRO MAX</p>
        <p style="color:var(--el-text-color-secondary)">版本 {{ appVersion }}</p>
        <p style="color:var(--el-text-color-secondary);margin-top:8px">IPTV 直播源管理工具</p>
      </div>
    </el-dialog>

    <!-- 弹窗：在线台标补全（后台任务 + 进度） -->
    <el-dialog v-model="showOnlineLogos" title="在线台标补全" width="470px"
               :close-on-click-modal="false" :close-on-press-escape="false" :show-close="onlineDone">
      <div v-if="!onlineStarted" style="color:var(--el-text-color-secondary);font-size:13px;line-height:1.7">
        <p>将从以下在线源并发下载台标并补全到本地（落地到程序目录 <code>logos/_online/</code>）：</p>
        <ul style="margin:6px 0 0 18px;padding:0">
          <li>中文台标站：tb.zbds.top/logo、无界.top/tvlogo</li>
          <li>GitHub 共享台标库：kodinerds-iptv、tvufop 等</li>
          <li>复用频道自带 tvg-logo 远程地址</li>
        </ul>
        <p style="margin-top:8px">仅补全当前<b>未匹配本地台标</b>的频道。开始后后台执行，可关闭此框稍后在「查看日志」中跟踪。</p>
      </div>
      <div v-else>
        <el-progress :percentage="onlinePercent"
                     :status="onlineDone ? (onlineError ? 'exception' : 'success') : undefined" />
        <div style="margin-top:10px;font-size:13px;color:var(--el-text-color-secondary);line-height:1.8">
          <div>总频道：{{ onlineStatus.total }}　已处理：{{ onlineStatus.done }}</div>
          <div>新增下载：<b style="color:var(--el-color-success)">{{ onlineStatus.downloaded }}</b>　已匹配(含原有)：{{ onlineStatus.found }}　未找到：{{ onlineStatus.failed }}</div>
          <div v-if="onlineError" style="color:var(--el-color-danger)">异常：{{ onlineError }}</div>
          <div v-if="!onlineDone" style="margin-top:4px">正在联网下载，请勿关闭程序…</div>
        </div>
      </div>
      <template #footer>
        <el-button v-if="!onlineStarted" size="small" @click="showOnlineLogos = false">取消</el-button>
        <el-button v-if="!onlineStarted" size="small" type="primary" @click="startOnlineLogos">开始补全</el-button>
        <el-button v-if="onlineStarted && !onlineDone" size="small" @click="showOnlineLogos = false">后台运行</el-button>
        <el-button v-if="onlineDone" size="small" type="primary" @click="finishOnlineLogos">完成</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：频道编辑 -->
    <el-dialog v-model="showEdit" title="编辑频道" width="450px" destroy-on-close>
      <el-form :model="editForm" label-width="60px" size="small">
        <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="地址"><el-input v-model="editForm.url" /></el-form-item>
        <el-form-item label="分组"><el-input v-model="editForm.group" /></el-form-item>
        <el-form-item label="标记"><el-input v-model="editForm.tag" /></el-form-item>
        <el-form-item label="Logo"><el-input v-model="editForm.logo" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="doEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showColumnSettings" title="列设置" width="500px" destroy-on-close>
      <el-checkbox-group v-model="hiddenCols">
        <div v-for="col in allCols" :key="col.key" style="display:inline-block;width:50%;margin-bottom:4px">
          <el-checkbox :label="col.key" :value="col.key">{{ col.defLabel }}</el-checkbox>
        </div>
      </el-checkbox-group>
    </el-dialog>

    <!-- 弹窗：搜索节目 -->
    <el-dialog v-model="showSearchProg" title="搜索节目" width="500px" destroy-on-close>
      <el-input v-model="searchProgKw" placeholder="输入节目名称" @keyup.enter="doSearchProg" />
      <el-table :data="searchProgResults" size="small" border style="margin-top:10px" @row-dblclick="searchProgPlay">
        <el-table-column prop="channel" label="频道" width="160" />
        <el-table-column prop="title" label="节目" />
        <el-table-column prop="start" label="开始" width="70" />
        <el-table-column prop="stop" label="结束" width="70" />
      </el-table>
      <template #footer>
        <el-button @click="showSearchProg = false">关闭</el-button>
        <el-button type="primary" @click="doSearchProg">搜索</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：DLNA 投屏 -->
    <el-dialog v-model="showDlna" title="DLNA 投屏" width="480px" destroy-on-close>
      <div class="dlna-body">
        <div class="dlna-target" v-if="dlnaTargetUrl">
          <span class="dlna-label">投播内容：</span>
          <el-tag size="small" type="info" closable @close="dlnaTargetUrl = ''">{{ dlnaTargetName || dlnaTargetUrl }}</el-tag>
        </div>
        <div class="dlna-devices-section">
          <div class="dlna-dev-header">
            <span>局域网设备</span>
            <el-button size="small" type="primary" @click="doDlnaDiscover" :loading="dlnaDiscovering" plain>
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
          </div>
          <div v-if="!dlnaDevices.length && !dlnaDiscovering" class="dlna-empty">
            未发现 DLNA 设备，请确保电视/音箱与电脑在同一局域网
          </div>
          <div v-else class="dlna-device-list">
            <div
              v-for="dev in dlnaDevices"
              :key="dev.location"
              class="dlna-device-card"
              :class="{ active: dlnaSelectedDevice && dlnaSelectedDevice.location === dev.location }"
              @click="dlnaSelectedDevice = dev"
            >
              <div class="dlna-dev-icon"><el-icon :size="24"><Monitor /></el-icon></div>
              <div class="dlna-dev-info">
                <div class="dlna-dev-name">{{ dev.name }}</div>
                <div class="dlna-dev-loc">{{ dev.location }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showDlna = false">关闭</el-button>
        <el-button type="danger" plain @click="doDlnaStop" :disabled="!dlnaSelectedDevice" :loading="dlnaStopping">停止播放</el-button>
        <el-button type="primary" @click="doDlnaPlay" :disabled="!dlnaSelectedDevice || !dlnaTargetUrl" :loading="dlnaPlaying">投屏播放</el-button>
      </template>
    </el-dialog>
  </div>
    <!-- 频道名校正：抓帧 → 台标/字幕 OCR → EPG 交叉验证 → 改名建议表（人工确认后应用） -->
    <el-dialog v-model="showNamefix" title="频道名校正" width="1000px" top="6vh" destroy-on-close>
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px">
        <el-button size="small" type="primary" :loading="nfRunning" @click="startNamefix">开始扫描</el-button>
        <span v-if="nfRunning" class="filter-info">
          进度 {{ nfDone }}/{{ nfTotal }}（可判定 {{ nfResolved }} · 源异常 {{ nfJunk }}）
        </span>
        <el-button size="small" @click="loadNamefix">刷新</el-button>
        <el-button size="small" @click="openUndo">撤销改名</el-button>
        <el-button size="small" type="danger" plain @click="clearNamefix">清空建议</el-button>
        <span style="margin-left:auto;font-size:12px;opacity:.7">当前策略：{{ nfStrategyLabel }}</span>
      </div>

      <el-alert
        v-if="!nfPending.length && !nfRunning"
        type="info" :closable="false" show-icon
        title="暂无待确认的改名建议"
        description="点「开始扫描」，程序会逐台抓一帧真实画面，读出台标/字幕文字，再和现有名称比对；对不上的会列在这里等你确认。" />

      <el-table v-if="nfPending.length" :data="nfPending" size="small" height="430"
                @selection-change="onNfSelect">
        <el-table-column type="selection" width="42" />
        <el-table-column prop="cid" label="#" width="52" align="center" />
        <el-table-column label="画面" width="96" align="center">
          <template #default="{ row }">
            <el-image v-if="row.frame" :src="row.frame" :preview-src-list="[row.frame]"
                      preview-teleported fit="cover"
                      style="width:72px;height:40px;border-radius:4px;cursor:zoom-in" />
            <span v-else style="opacity:.4">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="old" label="当前名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="识别为" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="color:#67c23a;font-weight:500">{{ row.new || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="96" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="nfConfType(row)">
              {{ ((row.confidence || 0) * 100).toFixed(0) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="依据" width="92" align="center">
          <template #default="{ row }">{{ nfKindLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="说明" min-width="210" show-overflow-tooltip />
      </el-table>

      <div v-if="nfSummaryOthers" style="margin-top:8px;font-size:12px;opacity:.7">
        其他判定：{{ nfSummaryOthers }}
      </div>

      <template #footer>
        <el-button size="small" @click="dismissSelected">忽略选中</el-button>
        <el-button size="small" type="primary" :disabled="!nfSelected.length" @click="applySelected">
          应用选中改名（{{ nfSelected.length }}）
        </el-button>
        <el-button size="small" @click="showNamefix = false">关闭</el-button>
      </template>
    </el-dialog>

</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick, h } from 'vue'
import { ElMessage, ElMessageBox, ElInput } from 'element-plus'
import { useChannelStore } from '@/stores/channels'
import { useSettingsStore } from '@/stores/settings'
import { usePlayerStore } from '@/stores/player'
import { saveTextFile, callNative } from '@/composables/useNative'
import * as channelApi from '@/api/channels'
import * as scrapeApi from '@/api/scrape'
import * as checkApi from '@/api/check'
import * as aiApi from '@/api/ai'
import * as exportApi from '@/api/export'
import * as configApi from '@/api/config'
import * as epgApi from '@/api/epg'
import * as rulesApi from '@/api/rules'
import * as dlnaApi from '@/api/dlna'
import * as appApi from '@/api/app'
import * as shotApi from '@/api/screenshots'
import * as nfApi from '@/api/namefix'
import { subscribeLogsSSE, subscribeEventsSSE } from '@/api/realtime'

const store = useChannelStore()
const settingsStore = useSettingsStore()
const playerStore = usePlayerStore()
const externalPlayerPath = ref('')

const showLeftPanel = ref(true)
const cfgUrl = ref('')
const pageStart = ref(1)
const pageEnd = ref(1)
const cfgSuffix = ref('m3u,m3u8,txt')
const useProxy = ref(false)
const cfgProxy = ref('127.0.0.1:10808')
const cfgMirror = ref('不使用加速')
const cfgEpg = ref('')
const scraping = ref(false)
const urlHistory = ref([])
const mirrorHistory = ref([])
const epgHistory = ref([])
const logText = ref('')
const logSince = ref(0)

const statsCardVisible = ref(true)
const statsCardPosition = ref('顶部')

const tableRef = ref()
const searchKw = ref('')
const filterStatus = ref('')
const hideDead = ref(false)   
const filterStack = ref('')
const page = ref(1)
const pageSize = ref(100)
const sortState = reactive(loadSortState())
const showGroupTree = ref(false)
const activeGroup = ref(null)
const groupKw = ref('')

const _collator = new Intl.Collator('zh-Hans-CN', { numeric: true })

function loadSortState() {
  try {
    const saved = localStorage.getItem('iptv-sort-state')
    return saved ? JSON.parse(saved) : { prop: 'id', order: 'ascending' }
  } catch { return { prop: 'id', order: 'ascending' } }
}
function saveSortState() {
  try {
    localStorage.setItem('iptv-sort-state', JSON.stringify({ prop: sortState.prop, order: sortState.order }))
  } catch { /* ignore */ }
}

const hiddenCols = ref(loadHiddenCols())
const visibleCols = computed(() => allCols.value.filter(c => !hiddenCols.value.includes(c.key)))

function loadHiddenCols() {
  try {
    const saved = localStorage.getItem('iptv-hidden-cols')
    return saved ? JSON.parse(saved) : []
  } catch { return [] }
}
function saveHiddenCols() {
  try {
    localStorage.setItem('iptv-hidden-cols', JSON.stringify(hiddenCols.value))
  } catch { /* ignore */ }
}


const favoriteOnly = ref(false)

function isFavRow(row) {
  const tags = String((row && row.tag) || '').split(',').map(s => s.trim()).filter(Boolean)
  return tags.includes('fav')
}

async function toggleFavRow(row) {
  if (!row) return
  const tags = String(row.tag || '').split(',').map(s => s.trim()).filter(Boolean)
  const on = tags.includes('fav')
  if (on) {
    const i = tags.indexOf('fav')
    if (i >= 0) tags.splice(i, 1)
  } else {
    tags.push('fav')
  }
  const next = tags.join(',')
  try {
    const { data } = await channelApi.setTag(row.id, next)
    row.tag = (data && data.tag !== undefined) ? data.tag : next
    ElMessage.success(on ? '已取消收藏' : '已收藏')
  } catch {
    ElMessage.error('收藏操作失败')
  }
}

const filtered = computed(() => {
  let list = store.channels
    if (activeGroup.value) list = list.filter(c => (c.group || '未分组') === activeGroup.value)
  if (filterStatus.value) list = list.filter(c => c.status === filterStatus.value)
  if (filterStack.value) list = list.filter(c => c.stack === filterStack.value)
  if (hideDead.value) list = list.filter(c => !(c.health && c.health.dead))
  if (favoriteOnly.value) list = list.filter(c => isFavRow(c))
  const kw = searchKw.value.trim().toLowerCase()
  if (kw) list = list.filter(c => [c.name, c.group, c.url, c.tag].some(v => String(v || '').toLowerCase().includes(kw)))
  const sp = sortState.prop, so = sortState.order
  if (sp && so) {
    const dir = so === 'ascending' ? 1 : -1
    list = list.slice().sort((a, b) => {
      const x = a[sp] ?? '', y = b[sp] ?? ''
      return _collator.compare(String(x), String(y)) * dir
    })
  }
  return list
})

const groupTree = computed(() => {
  const map = new Map()
  for (const c of store.channels) {
    const g = c.group || '未分组'
    map.set(g, (map.get(g) || 0) + 1)
  }
  return [...map.entries()]
    .map(([group, count]) => ({ group, count }))
    .sort((a, b) => b.count - a.count || a.group.localeCompare(b.group, 'zh-Hans-CN'))
})

const filteredGroups = computed(() => {
  const kw = groupKw.value.trim().toLowerCase()
  if (!kw) return groupTree.value
  return groupTree.value.filter(g => g.group.toLowerCase().includes(kw))
})

watch(activeGroup, () => { page.value = 1 })

const displayed = computed(() => {
  const f = filtered.value
  const s = (page.value - 1) * pageSize.value
  return f.slice(s, s + pageSize.value)
})

function healthClass(score) {
  if (score >= 0.7) return 'ok'
  if (score >= 0.4) return 'mid'
  return 'low'
}

const showColumnSettings = ref(false)

const ctx = reactive({ show: false, x: 0, y: 0, row: null, flip: false })
const ctxGroup = reactive({ show: false, x: 0, y: 0, group: '', count: 0, flip: false })
function onRowCtx(row, column, e) {
  e.preventDefault()
  ctxGroup.show = false
  ctx.row = row
  ctx.x = Math.min(e.clientX, window.innerWidth - 140)
  ctx.y = Math.min(e.clientY, window.innerHeight - 220)
  ctx.flip = ctx.x > window.innerWidth - 280
  ctx.show = true
}
function onGroupCtx(g, e) {
  e.preventDefault()
  ctx.show = false
  ctxGroup.group = g.group
  ctxGroup.count = g.count
  ctxGroup.x = Math.min(e.clientX, window.innerWidth - 140)
  ctxGroup.y = Math.min(e.clientY, window.innerHeight - 220)
  ctxGroup.flip = ctxGroup.x > window.innerWidth - 280
  ctxGroup.show = true
}
function onHeaderCtx(column, e) {
  e.preventDefault()
  showColumnSettings.value = true
}
function hideCtx() { ctx.show = false; ctxGroup.show = false }

function getTargetRows() {
  if (selectedRowIds.value.size > 1 && selectedRowIds.value.has(ctx.row?.id)) {
    return store.channels.filter(c => selectedRowIds.value.has(c.id))
  }
  return ctx.row ? [ctx.row] : []
}

function ctxPlay() { openPlayer(ctx.row); hideCtx() }
function ctxPlayExternal() { playExternal(ctx.row); hideCtx() }
function ctxDlnaCast() { openDlna(ctx.row); hideCtx() }
function ctxCopyUrl() {
  const rows = getTargetRows()
  const lines = rows.map(r => r.url).filter(Boolean)
  navigator.clipboard.writeText(lines.join('\n'))
  ElMessage.success(`已复制 ${lines.length} 条链接`)
  hideCtx()
}
function ctxCopyNameUrl() {
  const rows = getTargetRows()
  const lines = rows.filter(r => r.url).map(r => `${r.name}\n${r.url}`)
  navigator.clipboard.writeText(lines.join('\n'))
  ElMessage.success(`已复制 ${rows.length} 个频道的名称+链接`)
  hideCtx()
}
function ctxCopyInfo() {
  const rows = getTargetRows()
  const text = rows.map(row =>
    `名称: ${row.name}\n地址: ${row.url}\n分组: ${row.group || ''}\n状态: ${row.status || '未检查'}\n延迟: ${row.ms || ''}ms\n分辨率: ${row.res || ''}\n标记: ${row.tag || ''}\n网络栈: ${row.stack || ''}`
  ).join('\n---\n')
  navigator.clipboard.writeText(text)
  ElMessage.success(`已复制 ${rows.length} 条信息`)
  hideCtx()
}
function ctxCopyM3u() {
  const rows = getTargetRows()
  const m3u = []
  for (const row of rows) {
    if (!row.url) continue
    const grp = row.group || '自动分组'
    m3u.push(`#EXTINF:-1 group-title="${grp}" tvg-logo="${row.logo || ''}",${row.name}`)
    m3u.push(row.url)
  }
  navigator.clipboard.writeText(m3u.join('\n'))
  ElMessage.success(`已复制 ${rows.length} 个频道的 M3U`)
  hideCtx()
}
function ctxEdit() { editForm.value = { ...ctx.row }; showEdit.value = true; hideCtx() }
async function ctxDelete() {
  const rows = getTargetRows()
  if (rows.length === 0) { hideCtx(); return }
  try {
    const confirmMsg = rows.length > 1 ? `确认删除选中的 ${rows.length} 个频道？` : '确认删除该频道？'
    await ElMessageBox.confirm(confirmMsg, '警告', { type: 'warning' })
  } catch { hideCtx(); return }
  const ids = rows.map(r => r.id)
  await channelApi.deleteMany(ids)
  ElMessage.success(`已删除 ${rows.length} 个频道`)
  selectedRowIds.value = new Set()
  store.refresh()
  hideCtx()
}
async function ctxDeleteGroup() {
  const group = ctxGroup.group
  const count = ctxGroup.count
  if (!group) { hideCtx(); return }
  try {
    await ElMessageBox.confirm(
      `确认删除分组「${group}」下的全部 ${count} 个频道？\n此操作不可恢复。`,
      '删除分组',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch { hideCtx(); return }
  const { removed } = await channelApi.deleteByGroup(group)
  ElMessage.success(`已删除分组「${group}」，共 ${removed} 个频道`)
  if (activeGroup.value === group) activeGroup.value = null
  store.refresh()
  hideCtx()
}
const AD_REASON_TEXT = {
  ad_keyword: '切片地址含广告关键字',
  short_loop: '极短循环占位（≤30 秒）',
  vod_loop: '有限短片循环（点播式占位）',
}
function adReason(row) {
  const m = row?.ad_suspect
  if (!m || typeof m !== 'object') return ''
  const keys = Object.keys(m)
  if (!keys.length) return ''
  const reasons = [...new Set(keys.map(u => AD_REASON_TEXT[m[u]] || String(m[u])))]
  return '自动识别：' + reasons.join('、')
}

const shotIndex = ref({})
const shotBusy = ref('')
const shotRunning = ref(false)
const shotDone = ref(0)
const shotTotal = ref(0)
let shotTimer = null

async function loadShots() {
  try {
    const { data } = await shotApi.listShots()
    shotIndex.value = data.index || {}
    const st = data.status || {}
    if (st.running) {
      shotRunning.value = true
      shotDone.value = st.done || 0
      shotTotal.value = st.total || 0
      pollShots()
    }
  } catch { /* ignore */ }
}

function shotOf(row) {
  if (!row || !row.url) return ''
  return shotIndex.value[row.url] || ''
}

async function captureShotOne(row) {
  if (!row?.url || shotBusy.value) return
  shotBusy.value = row.url
  try {
    const { data } = await shotApi.captureShot({ channel_id: row.id, url: row.url })
    if (data.ok) {
      shotIndex.value = { ...shotIndex.value, [row.url]: data.path }
      ElMessage.success(`已抓取画面：${row.name}`)
    } else {
      ElMessage.warning(`${row.name}：${data.error || '抓帧失败'}`)
    }
  } catch {
    ElMessage.error('抓帧请求失败（后端可能已停止）')
  } finally {
    shotBusy.value = ''
  }
}

function pollShots() {
  if (shotTimer) return
  shotTimer = setInterval(async () => {
    try {
      const { data } = await shotApi.getShotStatus()
      shotDone.value = data.done || 0
      shotTotal.value = data.total || 0
      if (!data.running) {
        clearInterval(shotTimer); shotTimer = null
        shotRunning.value = false
        await loadShots()
        ElMessage.success(`画面抓取完成，已存画面 ${Object.keys(shotIndex.value).length} 张`)
      }
    } catch { /* ignore */ }
  }, 1500)
}

async function captureShotsBatch() {
  const rows = displayed.value || []
  const pending = rows.filter(r => r.url && !shotOf(r))
  if (!pending.length) {
    return ElMessage.info('当前列表的频道都已有画面，无需重复抓取')
  }
  try {
    await ElMessageBox.confirm(
      `将对当前列表中的 ${pending.length} 个「还没有画面」的源抓取首帧。\n` +
      `每个源约 3-10 秒，总计可能需要 ${Math.ceil(pending.length * 6 / 60)} 分钟左右，期间可正常使用软件。`,
      '批量抓取画面', { type: 'info', confirmButtonText: '开始抓取', cancelButtonText: '取消' }
    )
  } catch { return }
  try {
    const { data } = await shotApi.captureShotBatch({ ids: pending.map(r => r.id), only_missing: true })
    if (!data.started) {
      return ElMessage.warning(data.error || '没有需要抓取的地址')
    }
    shotRunning.value = true
    shotDone.value = 0
    shotTotal.value = data.total || 0
    ElMessage.success(`已开始抓取 ${data.total} 个源的首帧`)
    pollShots()
  } catch {
    ElMessage.error('批量抓帧请求失败')
  }
}

const showNamefix = ref(false)
const nfRunning = ref(false)
const nfDone = ref(0)
const nfTotal = ref(0)
const nfResolved = ref(0)
const nfJunk = ref(0)
const nfItems = ref([])
const nfSummary = ref({})
const nfSelected = ref([])
const nfStrategy = ref('advise')
let nfTimer = null

const nfPending = computed(() => nfItems.value.filter(it => it.state === 'pending' && it.new))

const NF_KIND = { exact: '台标直读', contain: '台标包含', fuzzy: '模糊匹配', epg: '节目单', vision: '视觉模型' }
function nfKindLabel(row) {
  return NF_KIND[row.kind] || ({ top: '台标区', mid: '画面中部', bot: '字幕条' }[row.region] || '—')
}
function nfConfType(row) {
  const c = Number(row.confidence || 0)
  return c >= 0.9 ? 'success' : c >= 0.7 ? 'warning' : 'info'
}
const nfStrategyLabel = computed(() => ({
  advise: '只出建议，人工确认（最稳）',
  auto_high: '高置信度自动改名',
  auto_all: '全部自动改名（激进）'
}[nfStrategy.value] || nfStrategy.value))

const nfSummaryOthers = computed(() => {
  const m = nfSummary.value || {}
  const map = { consistent: '名称一致', unresolved: '未能判定', unreachable: '抓帧失败',
                junk: '推广/公告页', no_text: '画面无文字', ambiguous: '候选打平',
                dismissed: '已忽略', applied: '已改名' }
  const parts = []
  for (const k in map) {
    if (m[k]) parts.push(`${map[k]} ${m[k]}`)
  }
  return parts.join(' · ')
})

async function loadNamefix() {
  try {
    const [sug, st, cfg] = await Promise.all([
      nfApi.nfSuggestions(), nfApi.nfStatus(), configApi.getConfig()
    ])
    nfItems.value = sug.data.items || []
    nfSummary.value = sug.data.summary || {}
    const s = st.data.status || {}
    nfRunning.value = !!s.running
    nfDone.value = s.done || 0
    nfTotal.value = s.total || 0
    nfResolved.value = s.resolved || 0
    nfJunk.value = s.junk || 0
    const c = cfg.data || {}
    if (c.namefix_strategy) nfStrategy.value = c.namefix_strategy
    if (s.running) pollNamefix()
  } catch {
    ElMessage.error('读取校正数据失败（后端可能已停止）')
  }
}

async function openNamefix() {
  showNamefix.value = true
  await loadNamefix()
}

function pollNamefix() {
  if (nfTimer) return
  nfTimer = setInterval(async () => {
    try {
      const { data } = await nfApi.nfStatus()
      const s = data.status || {}
      nfDone.value = s.done || 0
      nfTotal.value = s.total || 0
      nfResolved.value = s.resolved || 0
      nfJunk.value = s.junk || 0
      if (!s.running) {
        clearInterval(nfTimer); nfTimer = null
        nfRunning.value = false
        await loadNamefix()
        const applied = s.applied || 0
        ElMessage.success(applied
          ? `校正扫描完成，已自动改名 ${applied} 个`
          : `校正扫描完成，可判定 ${nfResolved.value} 个（按当前策略不自动改名）`)
      }
    } catch { /* ignore */ }
  }, 2000)
}

async function startNamefix() {
  const rows = displayed.value || []
  if (!rows.length) return ElMessage.info('列表为空，先导入频道')
  try {
    await ElMessageBox.confirm(
      `将对当前列表的 ${rows.length} 个频道逐个抓一帧真实画面并做文字识别。\n` +
      `每个源约 3-10 秒，总计约 ${Math.ceil(rows.length * 5 / 60)} 分钟，期间软件可正常使用。\n\n` +
      `抓帧与识别全部在本机完成，不上传任何数据。`,
      '开始名称校正扫描', { type: 'info', confirmButtonText: '开始扫描', cancelButtonText: '取消' })
  } catch { return }
  try {
    const { data } = await nfApi.nfScan({ limit: 0 })
    if (!data.started) return ElMessage.warning(data.error || '扫描未启动')
    nfRunning.value = true
    nfDone.value = 0
    nfTotal.value = data.total || 0
    ElMessage.success(`已开始扫描 ${data.total} 个频道`)
    pollNamefix()
  } catch {
    ElMessage.error('启动扫描失败')
  }
}

function onNfSelect(rows) { nfSelected.value = rows }

// ---- AI 智能分组 ----
const showAiGroup = ref(false)
const aiRunning = ref(false)
const aiApplying = ref(false)
const aiLimit = ref(200)
const aiExtra = ref('')
const aiRows = ref([])
const aiSummary = ref('')
const aiReady = ref(false)

function openAiGroup() {
  showAiGroup.value = true
  aiApi.getAiConfig().then(({ data }) => {
    aiReady.value = !!(data && data.ai_enabled && data.ai_api_key)
  }).catch(() => { aiReady.value = false })
}

async function runAiGroup() {
  aiRunning.value = true
  aiSummary.value = ''
  try {
    const { data } = await aiApi.groupChannels({ apply: false, limit: aiLimit.value, extra: aiExtra.value })
    if (!data.ok) {
      aiRows.value = []
      ElMessage.error(data.error || '分析失败')
    } else {
      aiRows.value = Object.entries(data.mapping || {}).map(([name, group]) => ({ name, group }))
      aiSummary.value = `模型建议 ${data.count} 个频道归入 ${Object.keys(data.groups || {}).length} 个分组`
    }
  } catch (e) {
    aiRows.value = []
    ElMessage.error('分析失败，请检查后端服务与 AI 配置')
  }
  aiRunning.value = false
}

async function applyAiGroup() {
  const mapping = {}
  for (const r of aiRows.value) {
    if (r.name && r.group) mapping[r.name] = String(r.group).trim()
  }
  if (!Object.keys(mapping).length) return ElMessage.warning('没有可应用的分组')
  aiApplying.value = true
  try {
    const { data } = await aiApi.groupChannels({ apply: true, mapping })
    if (!data.ok) {
      ElMessage.error(data.error || '应用失败')
    } else {
      ElMessage.success(`已应用 ${data.applied} 个频道的分组`)
      showAiGroup.value = false
      await store.refresh()
    }
  } catch (e) {
    ElMessage.error('应用失败')
  }
  aiApplying.value = false
}

async function applySelected() {
  const ids = nfSelected.value.map(r => r.cid)
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `将把选中的 ${ids.length} 个频道改为识别出的名称。\n` +
      `改名前会自动备份频道数据到 _bak_<日期>_改名前/，之后可随时整批撤销。`,
      '确认改名', { type: 'warning', confirmButtonText: '确认改名' })
  } catch { return }
  try {
    const { data } = await nfApi.nfApply(ids)
    ElMessage.success(`已改名 ${data.changed || 0} 个` + (data.failed?.length ? `，失败 ${data.failed.length} 个` : ''))
    await store.refresh()
    await loadNamefix()
  } catch {
    ElMessage.error('改名请求失败')
  }
}

async function dismissSelected() {
  const ids = nfSelected.value.map(r => r.cid)
  if (!ids.length) return ElMessage.info('先勾选要忽略的项')
  try {
    await nfApi.nfDismiss(ids)
    await loadNamefix()
  } catch { ElMessage.error('操作失败') }
}

async function openUndo() {
  try {
    const { data } = await nfApi.nfUndoList()
    const bs = data.batches || []
    if (!bs.length) return ElMessage.info('没有可撤销的改名记录')
    const latest = bs[0]
    await ElMessageBox.confirm(
      `找到 ${bs.length} 个改名批次，最近一批改动了 ${latest.count} 个频道。\n是否撤销最近这一批？`,
      '撤销改名', { type: 'warning', confirmButtonText: '撤销最近一批', cancelButtonText: '取消' })
    const r = await nfApi.nfUndo('')
    ElMessage.success(`已还原 ${r.data.restored || 0} 个频道名`)
    await store.refresh()
    await loadNamefix()
  } catch {  }
}

async function clearNamefix() {
  try {
    await ElMessageBox.confirm('清空建议表（不会改动任何频道数据）。', '清空建议',
                               { type: 'warning', confirmButtonText: '清空' })
  } catch { return }
  try {
    await nfApi.nfClear()
    await loadNamefix()
  } catch { ElMessage.error('操作失败') }
}

const existingTags = computed(() => {
  const set = new Set()
  for (const c of store.channels) {
    if (!c.tag) continue
    for (const x of String(c.tag).split(',')) {
      const s = x.trim()
      if (s) set.add(s)
    }
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
})
const epgGroups = ['央视频道', '地方卫视', '港澳台', '影院剧场', '体育竞技', '少儿动漫', '轮播专区']

async function applyTagToRows(tag) {
  const rows = getTargetRows()
  if (rows.length === 0) return
  const ids = rows.map(r => r.id)
    await channelApi.batchTagAdd(ids, tag)
  store.refresh()
  ElMessage.success(`已为 ${rows.length} 个频道添加标记：${tag}`)
}
async function ctxTagExisting(t) { await applyTagToRows(t); hideCtx() }
async function ctxTagCustom() {
  const rows = getTargetRows()
  if (rows.length === 0) { hideCtx(); return }
  try {
    const { value } = await ElMessageBox.prompt('添加标记', '标记', { inputPlaceholder: '多个标记用逗号分隔' })
    await applyTagToRows(value)
  } catch { /* cancel */ }
  hideCtx()
}
async function ctxTagClear() {
  const rows = getTargetRows()
  if (rows.length === 0) { hideCtx(); return }
  const ids = rows.map(r => r.id)
  await channelApi.batchTagClear(ids)
    const idsWithFake = rows.filter(r => r.is_fake_live).map(r => r.id)
  if (idsWithFake.length) await channelApi.batchFakeLive(idsWithFake, false)
  store.refresh()
  ElMessage.success(`已清除 ${rows.length} 个频道的标记`)
  hideCtx()
}

async function applyGroupToRows(group) {
  const rows = getTargetRows()
  if (rows.length === 0) return
  const ids = rows.map(r => r.id)
  await channelApi.batchGroup(ids, group)
  store.refresh()
  ElMessage.success(`已为 ${rows.length} 个频道设置分组：${group}`)
}
async function ctxGroupExisting(g) { await applyGroupToRows(g); hideCtx() }
async function ctxGroupCustom() {
  const rows = getTargetRows()
  if (rows.length === 0) { hideCtx(); return }
  try {
    const { value } = await ElMessageBox.prompt('设置分组', '分组', { inputPlaceholder: '可输入自定义分组名' })
    await applyGroupToRows(value)
  } catch { /* cancel */ }
  hideCtx()
}

function ctxSmartPaste() { smartPaste(); hideCtx() }

const selectedRowIds = ref(new Set())

const playingRowId = ref(null)

watch(() => playerStore.currentChannel, (ch) => {
  if (!ch || !ch.id) {
    if (!ch || !ch.url) { playingRowId.value = null; return }
        const byUrl = (displayed.value || []).find(r => r.url === ch.url)
    playingRowId.value = byUrl ? byUrl.id : null
    return
  }
  playingRowId.value = ch.id
    nextTick(() => {
    const el = document.querySelector(`.el-table__body tr[data-row-key="${ch.id}"]`)
    if (el && el.scrollIntoView) {
      try { el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) } catch (_) { /* ignore */ }
    }
  })
}, { immediate: false })

function toggleRowSelect(row) {
  const s = new Set(selectedRowIds.value)
  if (s.has(row.id)) s.delete(row.id)
  else s.add(row.id)
  selectedRowIds.value = s
}

function rowClassName({ row }) {
  const cls = []
  if (selectedRowIds.value.has(row.id)) cls.push('selected-row')
    if (playingRowId.value === row.id) cls.push('playing-row')
  return cls.join(' ')
}

function selectAll() {
  const allIds = new Set(store.channels.map(c => c.id))
  selectedRowIds.value = allIds
}

function invertSelect() {
  const allIds = new Set(store.channels.map(c => c.id))
  const inv = new Set([...allIds].filter(id => !selectedRowIds.value.has(id)))
  selectedRowIds.value = inv
}

async function checkAll() { await startCheck(false) }
async function checkSelected() { await startCheck(true) }
async function checkResume() { await startCheck(false, true) }
async function startCheck(onlySelected, resume = false) {
  try {
    const params = {
      only_selected: onlySelected,
      resume: resume,
      threads: settingsStore.get('check_threads', 20),
      timeout: settingsStore.get('check_timeout', 5),
      retries: settingsStore.get('check_retries', 1)
    }
    if (onlySelected) {
      params.selected_ids = [...selectedRowIds.value]
    }
    const { data } = await checkApi.startCheck(params)
    if (data.error) return ElMessage.warning(data.error)
    checkRunning.value = true; pollCheck()
  } catch (e) { ElMessage.error('检查失败') }
}
async function stopCheck() {
  await checkApi.stopCheck()
  checkRunning.value = false
  checkProcessed.value = 0
  checkTotal.value = 0
  checkStatus.value = ''
  ElMessage.success('已停止')
}
async function clearInvalid() {
  try { await ElMessageBox.confirm('确认清除所有离线频道？', '警告', { type: 'warning' }) } catch { return }
  await channelApi.removeInvalid(); store.refresh()
}
async function clearAllChannels() {
  try { await ElMessageBox.confirm('确认清空所有频道？不可恢复！', '警告', { type: 'error' }) } catch { return }
  await channelApi.clearAll(); store.refresh()
}

const showExport = ref(false)
const exportFormat = ref('m3u')
const exportScope = ref('all')
const exportBusy = ref(false)

function exportSelected() {
  exportScope.value = 'selected'
  showExport.value = true
}
function exportAll() {
  exportScope.value = 'all'
  showExport.value = true
}
async function doExportConfirm() {
  const ids = exportScope.value === 'selected' ? [...selectedRowIds.value] : []
  if (exportScope.value === 'selected' && !ids.length) {
    return ElMessage.warning('未选中频道')
  }
  exportBusy.value = true
  try {
    const { data } = await exportApi.exportChannels({ fmt: exportFormat.value, ids })
    const saved = await saveTextFile(`频道列表.${exportFormat.value}`, data)
    if (saved.ok) {
      ElMessage.success(saved.usedNative ? '已保存到本地' : '导出成功')
    }
    showExport.value = false
  } catch (e) {
    ElMessage.error('导出失败: ' + (e.response?.data?.detail || e.message))
  }
  exportBusy.value = false
}

function downloadFile(content, filename) {
  return saveTextFile(filename, content)
}
async function openPlayer(row, sourceUrl = null) {
  if (!row || !row.url) {
    ElMessage.info('请先选择或双击一个频道')
    return
  }
  const playUrl = sourceUrl || row.url
    if (settingsStore.get('prefer_external_player')) {
    await playExternal(sourceUrl ? { ...row, url: sourceUrl } : row)
    return
  }
    const api = window.pywebview?.api
  if (api && typeof api.play_channel === 'function') {
    await callNative('play_channel', {
      url: playUrl,
      name: row.name,
      group: row.group || '',
      id: row.id,
    })
        playerStore.currentChannel = {
      id: row.id,
      url: playUrl,
      name: row.name,
      group: row.group || '',
      url_note: row.url_note || '',
    }
    playerStore.currentUrlNote = row.url_note || ''
    if (playerStore.state === 'hidden') playerStore.state = 'drawer'
    return
  }
    const chList = (displayed.value || []).map(ch => ({
    id: ch.id,
    url: ch.url, name: ch.name || '', group: ch.group || '',
    tag: ch.tag || '',
    is_fake_live: !!ch.is_fake_live,
    url_note: ch.url_note || '',   
  }))
  const idx = chList.findIndex(ch => ch.url === playUrl)
  playerStore.open({
    id: row.id,
    url: playUrl,
    name: row.name,
    group: row.group || '',
    tag: row.tag || '',
    is_fake_live: !!row.is_fake_live,
    url_note: row.url_note || '',
  }, chList, idx >= 0 ? idx : 0)
    if (playerStore.state === 'hidden') playerStore.setState('drawer')
  else playerStore.exitPip()  
}

async function playExternal(row) {
  if (!row || !row.url) {
    ElMessage.info('请先选择或双击一个频道')
    return
  }
    let path = externalPlayerPath.value || settingsStore.get('external_player_path') || ''
  if (!path) {
    try {
      const { data } = await configApi.getPlayers()
      path = settingsStore.get('external_player') === 'potplayer' ? data.pot : (settingsStore.get('external_player') === 'mpv' ? data.mpv : data.vlc)
      externalPlayerPath.value = path || ''
    } catch { /* ignore */ }
  }
  if (!path) {
    ElMessage.warning('未检测到 VLC / PotPlayer / mpv，请在设置中指定播放器路径后再使用外部播放')
    return
  }
  const ok = await callNative('play_external', row.url, path)
  if (ok === undefined) {
    ElMessage.info('仅桌面版支持外部播放，请使用客户端打开')
  } else if (ok === false) {
    ElMessage.error('未找到外部播放器，请检查设置或安装 VLC / PotPlayer / mpv')
  }
}

function handleRowDblClick(row) {
    if (settingsStore.get('double_click_auto_play') === false) return
  openPlayer(row)
}

function shortUrl(u) {
  if (!u) return ''
  try {
    const url = new URL(u)
    const path = url.pathname === '/' ? '' : url.pathname
    return url.host + path + (url.search ? '?…' : '')
  } catch {
    return u.length > 48 ? u.slice(0, 48) + '…' : u
  }
}
function onRowClick(row, column, event) {
    if (event.shiftKey || event.ctrlKey || event.metaKey) {
    window.getSelection().removeAllRanges()
  }
  if (event.ctrlKey || event.metaKey) {
    toggleRowSelect(row)
  } else if (event.shiftKey && selectedRowIds.value.size > 0) {
    const idsArr = [...selectedRowIds.value]
    const lastSelectedId = idsArr[idsArr.length - 1]
    const lastIdx = displayed.value.findIndex(r => r.id === lastSelectedId)
    const currIdx = displayed.value.findIndex(r => r.id === row.id)
    if (lastIdx >= 0 && currIdx >= 0) {
      const start = Math.min(lastIdx, currIdx)
      const end = Math.max(lastIdx, currIdx)
      const newIds = new Set()
      for (let i = start; i <= end; i++) {
        newIds.add(displayed.value[i].id)
      }
      selectedRowIds.value = newIds
    }
  } else {
    selectedRowIds.value = new Set([row.id])
  }
}

const columnWidths = ref(loadColumnWidths())

function loadColumnWidths() {
  try {
    return JSON.parse(localStorage.getItem('iptv-col-widths') || '{}')
  } catch { return {} }
}

function saveColumnWidths() {
  try {
    localStorage.setItem('iptv-col-widths', JSON.stringify(columnWidths.value))
  } catch { /* ignore */ }
}

function onHeaderDragEnd(newWidth, oldWidth, column) {
  if (column && column.property) {
    columnWidths.value[column.property] = newWidth
    saveColumnWidths()
  }
}

watch(columnWidths, saveColumnWidths, { deep: true })

const COL_DEFS = [
  { key: 'name', prop: 'name', defLabel: '频道', width: 180 },
  { key: 'screenshot', prop: 'screenshot', defLabel: '画面', width: 90 },
  { key: 'status', prop: 'status', defLabel: '状态', width: 80 },
  { key: 'code', prop: 'code', defLabel: '状态码', width: 90 },
  { key: 'ms', prop: 'ms', defLabel: '延迟', width: 60 },
  { key: 'res', prop: 'res', defLabel: '分辨率', width: 90 },
  { key: 'quality', prop: 'quality', defLabel: '质量', width: 56 },
  { key: 'stack', prop: 'stack', defLabel: '网络栈', width: 64 },
  { key: 'group', prop: 'group', defLabel: '分组', width: 100 },
  { key: 'tag', prop: 'tag', defLabel: '标记', width: 90 },
  { key: 'url', prop: 'url', defLabel: '地址', width: 280, minWidth: 200, align: 'left' },
]
const allCols = computed(() => COL_DEFS.map(col => {
  if (columnWidths.value[col.prop]) {
    return { ...col, width: columnWidths.value[col.prop] }
  }
  return { ...col }
}))

const checkRunning = ref(false)
const checkProcessed = ref(0)
const checkTotal = ref(0)
const checkStatus = ref('')
const checkPercent = computed(() => {
  if (checkTotal.value === 0) return 0
  return Math.round((checkProcessed.value / checkTotal.value) * 100)
})
let checkTimer = null
function pollCheck() {
  checkTimer = setInterval(async () => {
    try {
      const { data } = await checkApi.getCheckStatus()
      checkProcessed.value = data.processed || 0
      checkTotal.value = data.total || 0
      checkStatus.value = data.status || ''
      if (!data.running) {
        checkRunning.value = false
        clearInterval(checkTimer)
                setTimeout(() => {
          checkProcessed.value = 0
          checkTotal.value = 0
          checkStatus.value = ''
        }, 1500)
        store.refresh()
      }
    } catch { clearInterval(checkTimer); checkRunning.value = false }
  }, 500)
}

let scrapeTimer = null
function pollScrape() {
  scrapeTimer = setInterval(async () => {
    try {
      const { data } = await scrapeApi.getScrapeStatus()
      if (!data.running) {
        scraping.value = false
        clearInterval(scrapeTimer)
        store.refresh()
      }
    } catch { clearInterval(scrapeTimer); scraping.value = false }
  }, 1000)
}

function getScrapeParams() {
    if (useProxy.value) {
    return { proxy: cfgProxy.value, mirror: '不使用加速' }
  }
  return { proxy: '', mirror: cfgMirror.value }
}

async function toggleScrape() {
  if (scraping.value) {
    await scrapeApi.stopScrape(); scraping.value = false; clearInterval(scrapeTimer)
  } else {
    if (!cfgUrl.value) return ElMessage.warning('请输入扫描网址')
    try {
      const { proxy, mirror } = getScrapeParams()
      const { data } = await scrapeApi.scrape({
        url: cfgUrl.value, start_page: pageStart.value, end_page: pageEnd.value,
        suffix_list: cfgSuffix.value, proxy, mirror
      })
      if (data.error) return ElMessage.warning(data.error)
            pushUrlHistory(cfgUrl.value)
      scraping.value = true; pollScrape()
    } catch { /* ignore */ }
  }
}
async function doSingleUrl() {
  if (!cfgUrl.value) return ElMessage.warning('请输入扫描网址')
  await toggleScrape()
}

const showUrlPool = ref(false)
const urlPoolText = ref('')
async function doUrlPool() {
  const urls = urlPoolText.value.split('\n').map(s => s.trim()).filter(s => s.startsWith('http'))
  if (!urls.length) return ElMessage.warning('请输入有效网址')
  try {
    const { proxy, mirror } = getScrapeParams()
    const { data } = await scrapeApi.scrapeBatch({ urls, suffix_list: cfgSuffix.value, proxy, mirror })
    if (data.error) return ElMessage.warning(data.error)
        pushUrlHistoryBatch(urls)
    scraping.value = true; showUrlPool.value = false; pollScrape()
  } catch { /* ignore */ }
}

function pushUrlHistory(url) {
  const u = (url || '').trim()
  if (!u) return
  urlHistory.value = [u, ...urlHistory.value.filter(x => x !== u)]
  exportApi.saveUrlHistory(u).catch(() => {})
}

function pushUrlHistoryBatch(urls) {
  const list = (urls || []).map(s => s.trim()).filter(Boolean)
  if (!list.length) return
  const merged = [...list]
  for (const u of urlHistory.value) {
    if (!merged.includes(u)) merged.push(u)
  }
  urlHistory.value = merged.slice(0, 50)
  exportApi.saveUrlHistoryBatch(urlHistory.value).catch(() => {})
}

const showImport = ref(false)
async function onImportFile(file) {
  const text = await file.raw.text()
  if (file.raw.name.endsWith('.json')) {
    const data = JSON.parse(text)
    await configApi.saveConfig(data)
    ElMessage.success('配置已导入')
    return
  }
  const { data } = await scrapeApi.importText(text)
  ElMessage.success(`导入完成，新增 ${data.added} 个频道`)
  store.refresh(); showImport.value = false
}

async function smartPaste() {
  try {
    const text = await navigator.clipboard.readText()
    const { data } = await scrapeApi.smartPaste(text)
    if (data.error) return ElMessage.warning(data.error)
    ElMessage.success(`粘贴成功：新增 ${data.added} 个频道`)
    store.refresh()
  } catch { ElMessage.error('读取剪贴板失败') }
}

const showRepair = ref(false)
const repairText = ref('')
const repairMode = ref('纯净模式')
const repairSaveOnly = ref(false)
const repairFmt = ref('m3u')
const repairBusy = ref(false)
async function doRepair() {
  if (!repairText.value.trim()) return ElMessage.warning('请输入文本')
  repairBusy.value = true
  try {
        const mode = repairSaveOnly.value ? repairMode.value : '完整增强'
    const resp = await exportApi.repair({
      text: repairText.value, mode: mode,
      save_only: repairSaveOnly.value, fmt: repairFmt.value
    }, repairSaveOnly.value ? 'text' : 'json')
    if (repairSaveOnly.value) {
      downloadFile(resp.data, `修复结果.${repairFmt.value}`)
      ElMessage.success('已保存修复结果')
    } else {
      if (resp.data.error) { ElMessage.error(resp.data.error) }
      else {
        await scrapeApi.importChannels(resp.data.channels)
        ElMessage.success(`已导入 ${resp.data.count} 个频道`)
        store.refresh()
      }
    }
    showRepair.value = false
  } catch { ElMessage.error('修补失败') }
  repairBusy.value = false
}

const showFindReplace = ref(false)
const frFind = ref('')
const frReplace = ref('')
async function doFindReplace() {
  if (!frFind.value) return ElMessage.warning('请输入查找内容')
  try {
    await exportApi.findReplace?.({ find: frFind.value, replace: frReplace.value })
    ElMessage.success('替换完成')
    store.refresh(); showFindReplace.value = false
  } catch { /* ignore */ }
}

const showRules = ref(false)
const rulesList = ref([])
const ruleForm = reactive({ from: '', to: '', index: null })
async function loadRules() {
  try { const { data } = await rulesApi.getRules(); rulesList.value = data.rules || [] } catch { /* ignore */ }
}
function rulePick(row) {
  ruleForm.from = row.from; ruleForm.to = row.to; ruleForm.index = rulesList.value.indexOf(row)
}
async function ruleAdd() {
  if (!ruleForm.from) return ElMessage.warning('请输入原文字')
  try {
    const { data } = await rulesApi.saveRule({ frm: ruleForm.from, to: ruleForm.to, mode: '包含', index: ruleForm.index })
    rulesList.value = data.rules
    ruleForm.from = ''; ruleForm.to = ''; ruleForm.index = null
  } catch { /* ignore */ }
}
async function ruleDel(index) {
  try {
    const { data } = await rulesApi.deleteRule(index)
    rulesList.value = data.rules
  } catch { /* ignore */ }
}

const showEdit = ref(false)
const editForm = ref({})
async function doEdit() {
  try {
    await channelApi.updateChannel(ctx.row.id, editForm.value)
    ElMessage.success('已保存')
    store.refresh(); showEdit.value = false
  } catch { /* ignore */ }
}

// ==================== EPG ====================
let epgTimer = null
async function loadEpg() {
  if (!cfgEpg.value) return ElMessage.warning('请输入EPG地址')
  try {
    await epgApi.loadEpg(cfgEpg.value)
    ElMessage.info('EPG 加载中...')
    if (epgTimer) clearInterval(epgTimer)
    epgTimer = setInterval(async () => {
      try {
        const { data } = await epgApi.getEpgStatus()
        if (!data.loading) {
          clearInterval(epgTimer)
          epgTimer = null
          if (data.error) {
            ElMessage.error('EPG 加载失败: ' + data.error)
          } else {
            ElMessage.success(`EPG 加载完成，共 ${data.count} 个频道`)
          }
        }
      } catch { clearInterval(epgTimer); epgTimer = null }
    }, 1000)
  } catch (e) { ElMessage.error('EPG 加载失败: ' + (e.response?.data?.detail || e.message)) }
}

const showSearchProg = ref(false)
const searchProgKw = ref('')
const searchProgResults = ref([])
async function doSearchProg() {
  if (!searchProgKw.value) return
  try {
    const { data } = await epgApi.searchProgram(searchProgKw.value)
    searchProgResults.value = data.results || []
  } catch { /* ignore */ }
}
function searchProgPlay(row) {
  openPlayer(row); showSearchProg.value = false
}

const showDlna = ref(false)
const dlnaDevices = ref([])
const dlnaSelectedDevice = ref(null)
const dlnaDiscovering = ref(false)
const dlnaPlaying = ref(false)
const dlnaStopping = ref(false)
const dlnaTargetUrl = ref('')
const dlnaTargetName = ref('')

function openDlna(row) {
  if (row && row.url) {
    dlnaTargetUrl.value = row.url
    dlnaTargetName.value = row.name
  }
  showDlna.value = true
  doDlnaDiscover()
}
async function doDlnaDiscover() {
  dlnaDiscovering.value = true
  try {
    const { data } = await dlnaApi.discoverDevices()
    dlnaDevices.value = Array.isArray(data) ? data : []
    if (dlnaDevices.value.length > 0) {
            dlnaSelectedDevice.value = dlnaDevices.value[0]
    }
  } catch { ElMessage.error('发现设备失败') }
  dlnaDiscovering.value = false
}
async function doDlnaPlay() {
  if (!dlnaSelectedDevice.value || !dlnaTargetUrl.value) return
  dlnaPlaying.value = true
  try {
    const { data } = await dlnaApi.playOnDevice(dlnaSelectedDevice.value, dlnaTargetUrl.value)
    if (data.error) { ElMessage.error(data.error) }
    else { ElMessage.success(`已投屏至「${dlnaSelectedDevice.value.name}」`) }
  } catch { ElMessage.error('投屏失败') }
  dlnaPlaying.value = false
}
async function doDlnaStop() {
  if (!dlnaSelectedDevice.value) return
  dlnaStopping.value = true
  try {
    const { data } = await dlnaApi.stopDevice(dlnaSelectedDevice.value)
    if (data.error) { ElMessage.error(data.error) }
    else { ElMessage.success('已停止播放') }
  } catch { ElMessage.error('停止失败') }
  dlnaStopping.value = false
}

const showLogs = ref(false)
const logBox = ref(null)
async function loadLogs() {
  try {
    const { data } = await exportApi.getLogs(logSince.value)
    if (data.logs && data.logs.length) {
      logText.value += data.logs.join('\n') + '\n'
      logSince.value = data.count
      nextTick(() => {
        if (logBox.value) {
          logBox.value.scrollTop = logBox.value.scrollHeight
        }
      })
    }
  } catch { /* ignore */ }
}
async function clearLogs() {
  await exportApi.clearLogs(); logText.value = ''; logSince.value = 0
}

function selectLogText(e) {
  const el = e.currentTarget
  const range = document.createRange()
  range.selectNodeContents(el)
  const sel = window.getSelection()
  sel.removeAllRanges()
  sel.addRange(range)
}

async function copyLogs() {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(logText.value)
    } else {
      const ta = document.createElement('textarea')
      ta.value = logText.value
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    ElMessage.success('日志已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}

const showAbout = ref(false)
const appVersion = ref('7.0.1')

const showOnlineLogos = ref(false)
const onlineStarted = ref(false)
const onlineDone = ref(false)
const onlineError = ref('')
const onlineStatus = reactive({ total: 0, done: 0, found: 0, downloaded: 0, failed: 0 })
const onlineTaskId = ref('')
let onlineTimer = null
const onlinePercent = computed(() => {
  if (!onlineStatus.total) return 0
  return Math.min(100, Math.round((onlineStatus.done / onlineStatus.total) * 100))
})

async function fetchAppVersion() {
  try {
    const { data } = await appApi.getAppVersion()
    if (data && data.version) appVersion.value = data.version
  } catch { /* ignore */ }
}

async function doMatchLogos() {
  try {
    const { data } = await channelApi.matchLogos(null)
    if (data.matched > 0) {
      ElMessage.success(`Logo 匹配成功：${data.matched} 个频道（共扫描 ${data.scanned} 张）`)
    } else {
      ElMessage.info(`未匹配到 Logo（扫描 ${data.scanned} 张）。请把 logo 图片放入程序目录的 logos 文件夹（顶层或任意子目录均可），文件名含频道名，例如 湖南卫视.png / logos/CCTV/CCTV5.png`)
    }
    store.refresh()
  } catch (e) {
    ElMessage.error('Logo 匹配失败: ' + (e.response?.data?.detail || e.message))
  }
}

function doOnlineLogos() {
    onlineStarted.value = false
  onlineDone.value = false
  onlineError.value = ''
  Object.assign(onlineStatus, { total: 0, done: 0, found: 0, downloaded: 0, failed: 0 })
  showOnlineLogos.value = true
}

async function startOnlineLogos() {
  try {
    const { data } = await channelApi.startOnlineLogos({ only_missing: true })
    onlineTaskId.value = data.task_id
    onlineStarted.value = true
    onlineDone.value = false
    if (onlineTimer) clearInterval(onlineTimer)
    onlineTimer = setInterval(pollOnlineLogos, 1500)
  } catch (e) {
    ElMessage.error('启动在线台标补全失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function pollOnlineLogos() {
  if (!onlineTaskId.value) return
  try {
    const { data } = await channelApi.getOnlineLogoTask(onlineTaskId.value)
    Object.assign(onlineStatus, {
      total: data.total || 0, done: data.done || 0,
      found: data.found || 0, downloaded: data.downloaded || 0, failed: data.failed || 0,
    })
    if (data.error) onlineError.value = data.error
    if (data.done_flag) {
      if (onlineTimer) { clearInterval(onlineTimer); onlineTimer = null }
      onlineDone.value = true
      store.refresh()
      if (data.error) {
        ElMessage.warning(`在线台标补全完成（有异常）：${data.error}`)
      } else {
        ElMessage.success(`在线台标补全完成：新增 ${data.downloaded} 个，已匹配(含原有) ${data.found} 个`)
      }
    }
  } catch (e) {
      }
}

function finishOnlineLogos() {
  showOnlineLogos.value = false
  if (onlineTimer) { clearInterval(onlineTimer); onlineTimer = null }
  store.refresh()
}

onUnmounted(() => { if (onlineTimer) clearInterval(onlineTimer) })

async function doReclassify() {
  try {
    const { data } = await channelApi.reclassifyChannels()
    if (data.changed > 0) {
      ElMessage.success(`已重新分组：${data.changed} / ${data.total} 个频道的分组被调整`)
    } else {
      ElMessage.info('分组无需调整')
    }
    store.refresh()
  } catch (e) {
    ElMessage.error('重新分组失败: ' + (e.response?.data?.detail || e.message))
  }
}

function onLogoError(e) {
  e.target.style.display = 'none'
}
const showShortcuts = ref(false)
const shortcutList = [
  { cat: '通用', key: 'Ctrl+A', desc: '全选' },
  { cat: '通用', key: 'Ctrl+V', desc: '粘贴' },
  { cat: '通用', key: 'Delete', desc: '删除选中' },
  { cat: '通用', key: 'Ctrl+F1', desc: '打开快捷键参考' },
]

watch(hiddenCols, saveHiddenCols, { deep: true })

function onSortChange({ prop, order }) {
  sortState.prop = prop; sortState.order = order
  saveSortState()
  page.value = 1
}

watch(() => ({ prop: sortState.prop, order: sortState.order }), saveSortState, { deep: true })

let logTimer = null
let logES = null
let evtES = null

function startRealtime() {
  try {
    logES = subscribeLogsSSE({
      onOpen: () => { if (logTimer) { clearInterval(logTimer); logTimer = null } },
      onMessage: (msg) => {
        logText.value += msg + '\n'
        nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
      },
      onError: () => { if (!logTimer) { loadLogs(); logTimer = setInterval(loadLogs, 2000) } },
    })
  } catch (e) {  }

  try {
    evtES = subscribeEventsSSE({
      onEvent: (obj) => {
        const d = obj.data || {}
        if (obj.name === 'stats' && store.stats) {
          store.stats.total = d.total || 0
          store.stats.online = d.online || 0
          store.stats.offline = d.offline || 0
        } else if (obj.name === 'check') {
          checkProcessed.value = d.processed || 0
          checkTotal.value = d.total || 0
          checkStatus.value = d.status || ''
          if (typeof d.running === 'boolean') checkRunning.value = d.running
        } else if (obj.name === 'scrape') {
          if (typeof d.running === 'boolean') scraping.value = d.running
        }
      },
    })
  } catch (e) {  }
}

onMounted(async () => {
  await store.fetchIfNeeded()
  await settingsStore.fetchSettings()
  fetchAppVersion()
      try {
    const manual = settingsStore.get('external_player_path')
    if (manual) {
      externalPlayerPath.value = manual
    } else {
      const { data } = await configApi.getPlayers()
      externalPlayerPath.value = (settingsStore.get('external_player') === 'potplayer' ? data.pot : data.vlc) || ''
    }
  } catch { /* ignore */ }
  loadShots()
  loadLogs()
  logTimer = setInterval(loadLogs, 2000)
  startRealtime()
  document.addEventListener('click', hideCtx)
    try {
    const { data } = await checkApi.getCheckStatus()
    if (data.running) {
      checkRunning.value = true
      checkProcessed.value = data.processed || 0
      checkTotal.value = data.total || 0
      checkStatus.value = data.status || ''
      pollCheck()
    }
  } catch { /* ignore */ }
})

watch(() => settingsStore.settings, async (s) => {
  if (!s || !Object.keys(s).length) return
    if (s.suffix_list) cfgSuffix.value = s.suffix_list
  if (s.proxy !== undefined) cfgProxy.value = s.proxy
  if (s.mirror) cfgMirror.value = s.mirror
  if (s.use_proxy !== undefined) useProxy.value = s.use_proxy
  if (s.default_epg) cfgEpg.value = s.default_epg
    statsCardVisible.value = s.stats_card_visible !== false
  statsCardPosition.value = s.stats_card_position || '顶部'
    try {
    const { data } = await exportApi.getHistory()
    if (data) {
      urlHistory.value = data.url || []
      mirrorHistory.value = data.mirror || []
      epgHistory.value = data.epg || []
    }
  } catch { /* ignore */ }
    try {
    if (s.external_player_path) {
      externalPlayerPath.value = s.external_player_path
    } else {
      const { data } = await configApi.getPlayers()
      externalPlayerPath.value = (s.external_player === 'potplayer' ? data.pot : data.vlc) || ''
    }
  } catch { /* ignore */ }
})
onUnmounted(() => {
  if (nfTimer) { clearInterval(nfTimer); nfTimer = null }
  clearInterval(logTimer)
  clearInterval(checkTimer)
  clearInterval(scrapeTimer)
  if (epgTimer) clearInterval(epgTimer)
  try { logES && logES.close() } catch (e) {}
  try { evtES && evtES.close() } catch (e) {}
  document.removeEventListener('click', hideCtx)
})

async function onKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return
  if (e.ctrlKey && e.key === 'a') { e.preventDefault(); selectAll() }
  if (e.ctrlKey && e.key === 'v') { e.preventDefault(); smartPaste() }
  if (e.key === 'Delete') {
    e.preventDefault()
    if (selectedRowIds.value.size === 0) return
    try {
      const confirmMsg = `确认删除选中的 ${selectedRowIds.value.size} 个频道？`
      await ElMessageBox.confirm(confirmMsg, '警告', { type: 'warning' })
    } catch { return }
    const ids = [...selectedRowIds.value]
    await channelApi.deleteMany(ids)
    ElMessage.success(`已删除 ${ids.length} 个频道`)
    selectedRowIds.value = new Set()
    store.refresh()
  }
  if (e.ctrlKey && e.key === 'F1') { e.preventDefault(); showShortcuts.value = true }
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.channel-page { height: 100%; display: flex; flex-direction: column; gap: 10px; }

.check-progress-bar {
  padding: 8px 12px;
  background: var(--el-bg-color);
  border-radius: 6px;
  flex-shrink: 0;
}
.progress-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 6px;
}
.progress-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.progress-text {
  font-size: 12px;
  color: var(--el-color-primary);
  font-weight: 500;
}
.progress-status {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-left: auto;
}

.stats-row { flex-shrink: 0; }
.stat-card { text-align: center; cursor: default; }
.stat-card :deep(.el-card__body) { padding: 12px; }
.stat-val { font-size: 28px; font-weight: 700; }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }

.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: var(--el-bg-color); border-radius: 6px;
  flex-shrink: 0;
}
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; }

.main-area { flex: 1; display: flex; gap: 0; overflow: hidden; min-height: 0; }

.left-panel {
  width: 280px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px;
  overflow-y: auto;
}
.config-card :deep(.el-card__body) { padding: 12px; }
.role-alert { margin-bottom: 12px; }
.scrape-form :deep(.el-form-item) { margin-bottom: 14px; }
.scrape-form :deep(.el-form-item__content) { flex-wrap: nowrap; }
.form-row { display: flex; align-items: center; width: 100%; gap: 0; }
.btn-group { margin-left: auto; display: flex; flex-direction: column; gap: 2px; flex-shrink: 0; align-items: stretch; }
.btn-group .el-button--small { width: 100%; margin: 0; }
.scrape-btn-item :deep(.el-form-item__label) { display: none !important; }
.scrape-btn-item :deep(.el-form-item__content) { margin-left: 0 !important; width: 100%; }
.scrape-btn-wrapper { display: flex; justify-content: center; width: 100%; }
.scrape-btn { padding: 0 30px; height: 40px; font-size: 16px; font-weight: 700; letter-spacing: 2px; }

.form-row .el-input-number--small { min-width: 40px; width: 40px; }
.form-row .el-input-number--small .el-input__wrapper { padding: 0 2px; }
.form-row .el-input-number--small .el-input__inner { padding: 0; text-align: center; }
.form-row .mx-1 { margin: 0 2px; }
.log-card { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.log-card :deep(.el-card__body) { padding: 8px 12px; flex: 1; overflow: hidden; }
.log-box {
  height: 100%; overflow-y: auto; font-size: 12px; font-family: 'Consolas', monospace;
  white-space: pre-wrap; color: var(--el-text-color-regular); line-height: 1.5;
  user-select: text; -webkit-user-select: text; cursor: text;
}
.log-header-actions { float: right; }
.log-header-actions .el-button { margin-left: 4px; }
.log-header-actions::after { content: ''; display: table; clear: both; }
.card-title { font-size: 13px; font-weight: 600; }

.panel-toggle {
  width: 14px; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  cursor: pointer; background: var(--el-fill-color-light); border-radius: 0 4px 4px 0;
  margin: 0 2px; align-self: stretch;
}
.panel-toggle:hover { background: var(--el-fill-color); }


.group-tree {
  width: 200px; flex-shrink: 0; display: flex; flex-direction: column;
  background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px; overflow: hidden; margin: 0 4px;
}
.gt-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 10px 4px; border-bottom: 1px solid var(--el-border-color-lighter);
}
.gt-collapse { cursor: pointer; color: var(--el-text-color-secondary); }
.gt-collapse:hover { color: var(--el-color-primary); }
.gt-search { padding: 6px 8px; }
.gt-list { flex: 1; overflow-y: auto; padding: 4px; }
.gt-node {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 8px; border-radius: 4px; cursor: pointer; font-size: 13px;
  color: var(--el-text-color-regular);
}
.gt-node:hover { background: var(--el-fill-color-light); }
.gt-node.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-weight: 600; }
.gt-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 8px; }
.gt-count {
  flex-shrink: 0; font-size: 11px; padding: 0 6px; border-radius: 10px;
  background: var(--el-fill-color); color: var(--el-text-color-secondary);
}
.gt-node.active .gt-count { background: var(--el-color-primary); color: #fff; }
.gt-empty { padding: 16px 8px; text-align: center; font-size: 12px; color: var(--el-text-color-secondary); }

.right-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }

.filter-bar {
  display: flex; align-items: center; gap: 8px; padding: 6px 0;
  flex-shrink: 0;
}
.filter-info { font-size: 12px; color: var(--el-text-color-secondary); }

.pager { flex-shrink: 0; margin-top: 8px; }


.status-cell { display: flex; align-items: center; gap: 6px; }
.health-dead {
  font-size: 11px; color: #fff; background: #f56c6c; border-radius: 3px;
  padding: 0 4px; line-height: 16px;
}
.health-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.health-dot.ok { background: #67c23a; }
.health-dot.mid { background: #e6a23c; }
.health-dot.low { background: #c0c4cc; }

.mx-1 { margin: 0 4px; font-size: 12px; }


.name-cell { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
.ch-logo { width: 22px; height: 22px; object-fit: contain; border-radius: 3px; flex-shrink: 0; background: var(--el-fill-color-light); }
.ch-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }


.shot-thumb {
  width: 76px; height: 43px; border-radius: 4px; cursor: zoom-in;
  border: 1px solid var(--el-border-color-light); background: var(--el-fill-color-light);
  display: block; margin: 0 auto;
}


.ctx-menu {
  position: fixed; z-index: 9999; background: var(--el-bg-color);
  border: 1px solid var(--el-border-color); border-radius: 6px;
  box-shadow: var(--el-box-shadow); min-width: 120px; padding: 4px 0;
}
.ctx-item { padding: 6px 16px; font-size: 13px; cursor: pointer; }
.ctx-item:hover { background: var(--el-fill-color-light); }
.ctx-sep { height: 1px; background: var(--el-border-color-lighter); margin: 4px 0; }

.ctx-item.has-sub { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.ctx-arrow { font-size: 11px; opacity: .55; }
.ctx-sub {
  display: none; position: absolute; top: -4px; left: 100%; margin-left: 4px;
  min-width: 140px; background: var(--el-bg-color);
  border: 1px solid var(--el-border-color); border-radius: 6px;
  box-shadow: var(--el-box-shadow); padding: 4px 0;
  max-height: 320px; overflow-y: auto; z-index: 10000;
}
.ctx-item.has-sub:hover > .ctx-sub { display: block; }
.ctx-menu.ctx-sub-left .ctx-sub { left: auto; right: 100%; margin-left: 0; margin-right: 4px; }
.ctx-danger:hover { color: var(--el-color-danger); background: var(--el-color-danger-light-9); }


:deep(.el-table__body tr.selected-row > td) {
  background-color: var(--el-color-primary-light-9) !important;
  border-top: 1px solid var(--el-color-primary-light-5) !important;
  border-bottom: 1px solid var(--el-color-primary-light-5) !important;
}
:deep(.el-table__body tr.selected-row > td:first-child) {
  border-left: 1px solid var(--el-color-primary-light-5) !important;
}
:deep(.el-table__body tr.selected-row > td:last-child) {
  border-right: 1px solid var(--el-color-primary-light-5) !important;
}


:deep(.el-table__body tr.playing-row > td) {
  background-color: rgba(74, 222, 128, 0.08) !important;
}
:deep(.el-table__body tr.playing-row > td:first-child) {
  box-shadow: inset 3px 0 0 var(--el-color-success) !important;
}


.form-row .el-button--small { width: 70px; }


.channel-table :deep(.el-table__body-wrapper) {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}


.dlna-body { display: flex; flex-direction: column; gap: 12px; }
.dlna-target { display: flex; align-items: center; gap: 8px; }
.dlna-label { font-size: 13px; color: var(--el-text-color-secondary); white-space: nowrap; }
.dlna-devices-section { display: flex; flex-direction: column; gap: 8px; }
.dlna-dev-header { display: flex; align-items: center; justify-content: space-between; font-size: 13px; font-weight: 600; }
.dlna-empty {
  padding: 24px 16px; text-align: center; font-size: 13px;
  color: var(--el-text-color-secondary); background: var(--el-fill-color-light);
  border-radius: 6px;
}
.dlna-device-list { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto; }
.dlna-device-card {
  display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  border: 1px solid var(--el-border-color-lighter); border-radius: 6px;
  cursor: pointer; transition: all 0.15s;
}
.dlna-device-card:hover { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.dlna-device-card.active { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); box-shadow: 0 0 0 2px var(--el-color-primary-light-5); }
.dlna-dev-icon { color: var(--el-color-primary); flex-shrink: 0; }
.dlna-dev-info { min-width: 0; }
.dlna-dev-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dlna-dev-loc { font-size: 11px; color: var(--el-text-color-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }
.fav-btn { color: var(--el-text-color-placeholder); padding: 0; }
.fav-btn.on { color: var(--el-color-warning); }
.fav-btn:hover { color: var(--el-color-warning); }

</style>