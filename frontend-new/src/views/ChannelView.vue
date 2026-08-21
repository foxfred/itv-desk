<template>
  <div class="channel-page">
    <!-- 统计卡片 -->
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

    <!-- 检查进度条 -->
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

    <!-- 工具栏 -->
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
        <el-button size="small" type="success" @click="openPlayer">打开播放器</el-button>
        <el-button size="small" @click="openDlna()">
          <el-icon><Monitor /></el-icon>DLNA投屏
        </el-button>
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
              <el-dropdown-item divided @click="doMergeDuplicates">智能去重合并</el-dropdown-item>
              <el-dropdown-item @click="doMatchLogos">Logo 自动匹配</el-dropdown-item>
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
          <span class="filter-info">共 {{ filtered.length }} 条</span>
          <el-button size="small" text style="margin-left:auto" @click="showColumnSettings = true">列设置</el-button>
        </div>

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
          <el-table-column type="expand" width="40">
            <template #default="{ row }">
              <div class="src-expand" v-if="(row.sources && row.sources.length > 1) || (row.source_groups && row.source_groups.length)">
                <!-- 聚合频道标记按每个源独立显示，主行不再额外显示同一标签，避免与子行重复 -->
                <template v-for="(g, gi) in (row.source_groups || [])" :key="'g' + gi">
                  <div class="src-group-name">{{ g.name }}</div>
                  <div v-for="(u, ui) in g.urls" :key="'gu' + gi + '-' + ui" class="src-row" @dblclick="playSourceInline(row, u)" @contextmenu.stop="onSourceCtx(row, u, $event)">
                    <span class="src-tag">聚合</span>
                    <span v-if="(row.source_tags || {})[u]" class="src-tag src-tag-channel" :title="(row.source_tags || {})[u]">{{ (row.source_tags || {})[u] }}</span>
                    <span v-if="(row.source_is_fake_live || {})[u]" class="src-tag src-tag-fake" title="被标记为假直播">假直播</span>
                    <span class="src-url" :title="u">{{ shortUrl(u) }}</span>
                    <span v-html="sourceMsDisplay(row, u)"></span>
                    <el-button size="small" text type="primary" @click.stop="playSourceInline(row, u)">播放</el-button>
                    <el-button size="small" text type="danger" @click.stop="deleteSourceInline(row, u)">删除</el-button>
                  </div>
                </template>
                <div v-for="(u, ui) in standaloneSources(row)" :key="'s' + ui" class="src-row" @dblclick="playSourceInline(row, u)" @contextmenu.stop="onSourceCtx(row, u, $event)">
                  <span class="src-tag src-tag-num">{{ ui + 1 }}</span>
                  <span v-if="(row.source_tags || {})[u]" class="src-tag src-tag-channel" :title="(row.source_tags || {})[u]">{{ (row.source_tags || {})[u] }}</span>
                  <span v-if="(row.source_is_fake_live || {})[u]" class="src-tag src-tag-fake" title="被标记为假直播">假直播</span>
                    <span class="src-url" :title="u">{{ shortUrl(u) }}</span>
                    <span v-html="sourceMsDisplay(row, u)"></span>
                    <el-button size="small" text type="primary" @click.stop="playSourceInline(row, u)">播放</el-button>
                    <el-button size="small" text type="danger" @click.stop="deleteSourceInline(row, u)">删除</el-button>
                </div>
              </div>
              <div v-else class="src-empty">
                <span v-if="row.tag" class="src-tag-line">
                  <span class="src-tag-label">标记</span>
                  <el-tag size="small" type="warning" effect="dark" class="src-tag-value">{{ row.tag }}</el-tag>
                </span>
                <span v-if="row.is_fake_live" class="src-tag src-tag-fake" title="被标记为假直播">假直播</span>
                <span v-if="!row.tag && !row.is_fake_live">单一源（无合并）</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="id" label="#" width="50" sortable="custom" align="center" />
          <el-table-column label="源" width="52" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="plain" class="src-count" @click="toggleRowExpand(row)">
                {{ (row.sources && row.sources.length) || 1 }}
              </el-tag>
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
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <template v-if="col.key === 'status'">
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
      <div class="ctx-item" :class="{ 'ctx-danger': !selectedRowsAreFakeLive }" @click="ctxToggleFakeLive">
        {{ selectedRowsAreFakeLive ? '取消假直播标记' : '标记为假直播' }}
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
      <div class="ctx-item" @click="ctxSourceMgr">管理源</div>
      <div class="ctx-item ctx-danger" @click="ctxDelete">删除</div>
    </div>

    <!-- 右键菜单：聚合源单行（按单个源 URL 操作） -->
    <div v-if="ctxSource.show" class="ctx-menu" :class="{ 'ctx-sub-left': ctxSource.flip }" :style="{ left: ctxSource.x + 'px', top: ctxSource.y + 'px' }">
      <div class="ctx-item" @click="ctxSourcePlay">播放此源</div>
      <div class="ctx-item" @click="ctxSourcePlayExternal">用外部播放器打开</div>
      <div class="ctx-item" @click="ctxSourceCopyUrl">复制链接</div>
      <div class="ctx-sep" />
      <div class="ctx-item has-sub">
        <span>标记</span><span class="ctx-arrow">▸</span>
        <div class="ctx-sub">
          <div v-for="t in existingTags" :key="t" class="ctx-item" @click="ctxSourceTagExisting(t)">{{ t }}</div>
          <div v-if="existingTags.length" class="ctx-sep" />
          <div class="ctx-item" @click="ctxSourceTagCustom">自定义标记…</div>
          <div class="ctx-item ctx-danger" @click="ctxSourceTagClear">清除标记</div>
        </div>
      </div>
      <div class="ctx-item" :class="{ 'ctx-danger': !sourceCtxIsFakeLive }" @click="ctxSourceToggleFakeLive">
        {{ sourceCtxIsFakeLive ? '取消假直播标记' : '标记为假直播' }}
      </div>
      <div class="ctx-sep" />
      <div class="ctx-item ctx-danger" @click="ctxSourceDelete">删除此源</div>
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

    <!-- 弹窗：源管理 -->
    <el-dialog v-model="showSourceMgr" title="源管理" width="560px" destroy-on-close>
      <div class="source-mgr">
        <div class="sm-toolbar">
          <el-button size="small" type="primary" plain @click="smAddSource">+ 新增源</el-button>
          <el-button size="small" :disabled="!smSelected.length" @click="smAggregate">聚合选中</el-button>
          <el-button size="small" :disabled="!sourceMgrGroups.length" @click="smUngroupAll">解散全部聚合</el-button>
        </div>

        <!-- 聚合组 -->
        <div v-for="(g, gi) in sourceMgrGroups" :key="'g-' + gi" class="sm-group">
          <div class="sm-group-header" @click="smToggleGroup(gi)">
            <el-icon class="sm-arrow"><ArrowDown v-if="smExpandedGroups.has(gi)" /><ArrowRight v-else /></el-icon>
            <el-input v-model="g.name" size="small" class="sm-group-name" @click.stop />
            <el-button size="small" text type="danger" @click.stop="smRemoveGroup(gi)">解散</el-button>
          </div>
          <div v-show="smExpandedGroups.has(gi)" class="sm-group-body">
            <div v-for="(u, ui) in g.urls" :key="'gu-' + ui" class="sm-row">
              <el-input :model-value="u" size="small" class="sm-url" @blur="e => smUpdateUrl(u, e.target.value, 'group', gi, ui)" />
              <el-button size="small" text type="danger" @click="smRemoveGroupMember(gi, ui)">删除</el-button>
            </div>
          </div>
        </div>

        <!-- 独立源 -->
        <div class="sm-section-title">独立源（未聚合）{{ smStandalone.length ? `共 ${smStandalone.length} 个` : '' }}</div>
        <el-checkbox-group v-model="smSelected" class="sm-list">
          <div v-for="(u, i) in smStandalone" :key="'s-' + i" class="sm-row">
            <el-checkbox :label="u">&nbsp;</el-checkbox>
            <el-input :model-value="u" size="small" class="sm-url" @blur="e => smUpdateUrl(u, e.target.value, 'standalone', i)" />
            <el-button size="small" text type="danger" @click="smRemoveStandalone(i)">删除</el-button>
          </div>
        </el-checkbox-group>
        <div v-if="!smStandalone.length && !sourceMgrGroups.length" class="sm-empty">暂无源</div>
      </div>
      <template #footer>
        <el-button @click="showSourceMgr = false">取消</el-button>
        <el-button type="primary" @click="doSaveSources">保存</el-button>
      </template>
    </el-dialog>

    <!-- 弹窗：列设置 -->
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
import * as exportApi from '@/api/export'
import * as configApi from '@/api/config'
import * as epgApi from '@/api/epg'
import * as rulesApi from '@/api/rules'
import * as dlnaApi from '@/api/dlna'
import * as appApi from '@/api/app'
import { subscribeLogsSSE, subscribeEventsSSE } from '@/api/realtime'

const store = useChannelStore()
const settingsStore = useSettingsStore()
const playerStore = usePlayerStore()
// 外部播放器可执行文件路径（默认 VLC / PotPlayer 探测结果）
const externalPlayerPath = ref('')

// ==================== 左侧面板 ====================
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

// ==================== 统计卡片 ====================
const statsCardVisible = ref(true)
const statsCardPosition = ref('顶部')

// ==================== 表格 ====================
const tableRef = ref()
const searchKw = ref('')
const filterStatus = ref('')
const hideDead = ref(false)   // 隐藏连续失败判定的死源
const filterStack = ref('')
const page = ref(1)
const pageSize = ref(100)
const sortState = reactive(loadSortState())
// 分组树状态
const showGroupTree = ref(true)
const activeGroup = ref(null)
const groupKw = ref('')

// 预编译排序比较器（避免每次排序新建）
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

const filtered = computed(() => {
  let list = store.channels
  // 分组树过滤：选中分组后仅显示该分组频道
  if (activeGroup.value) list = list.filter(c => (c.group || '未分组') === activeGroup.value)
  if (filterStatus.value) list = list.filter(c => c.status === filterStatus.value)
  if (filterStack.value) list = list.filter(c => c.stack === filterStack.value)
  if (hideDead.value) list = list.filter(c => !(c.health && c.health.dead))
  const kw = searchKw.value.trim().toLowerCase()
  if (kw) list = list.filter(c => [c.name, c.group, c.url].some(v => String(v || '').toLowerCase().includes(kw)))
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

// 分组树：从已加载频道池聚合各分组数量（与表格一致，瞬时过滤）
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

// 切换分组时回到第一页
watch(activeGroup, () => { page.value = 1 })

const displayed = computed(() => {
  const f = filtered.value
  const s = (page.value - 1) * pageSize.value
  return f.slice(s, s + pageSize.value)
})

// 健康度色阶：>=0.7 绿 / >=0.4 橙 / 其余灰
function healthClass(score) {
  if (score >= 0.7) return 'ok'
  if (score >= 0.4) return 'mid'
  return 'low'
}

const showColumnSettings = ref(false)

// ==================== 右键菜单 ====================
const ctx = reactive({ show: false, x: 0, y: 0, row: null, flip: false })
const ctxSource = reactive({ show: false, x: 0, y: 0, row: null, url: '', flip: false })
const ctxGroup = reactive({ show: false, x: 0, y: 0, group: '', count: 0, flip: false })
function onRowCtx(row, column, e) {
  e.preventDefault()
  ctxSource.show = false
  ctxGroup.show = false
  ctx.row = row
  ctx.x = Math.min(e.clientX, window.innerWidth - 140)
  ctx.y = Math.min(e.clientY, window.innerHeight - 220)
  ctx.flip = ctx.x > window.innerWidth - 280
  ctx.show = true
}
function onSourceCtx(row, url, e) {
  e.preventDefault()
  ctx.show = false
  ctxGroup.show = false
  ctxSource.row = row
  ctxSource.url = url
  ctxSource.x = Math.min(e.clientX, window.innerWidth - 140)
  ctxSource.y = Math.min(e.clientY, window.innerHeight - 220)
  ctxSource.flip = ctxSource.x > window.innerWidth - 280
  ctxSource.show = true
}
function onGroupCtx(g, e) {
  e.preventDefault()
  ctx.show = false
  ctxSource.show = false
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
function hideCtx() { ctx.show = false; ctxSource.show = false; ctxGroup.show = false }

// 获取当前应操作的行列表（多选时取所有选中行，否则取右键点击的行）
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
  const lines = []
  for (const r of rows) {
    const srcs = (r.sources && r.sources.length) ? r.sources : [r.url]
    for (const u of srcs) lines.push(u)
  }
  navigator.clipboard.writeText(lines.join('\n'))
  ElMessage.success(`已复制 ${lines.length} 条链接（含多源）`)
  hideCtx()
}
function ctxCopyNameUrl() {
  const rows = getTargetRows()
  const lines = []
  for (const r of rows) {
    const srcs = (r.sources && r.sources.length) ? r.sources : [r.url]
    for (const u of srcs) lines.push(`${r.name}\n${u}`)
  }
  navigator.clipboard.writeText(lines.join('\n'))
  ElMessage.success(`已复制 ${rows.length} 个频道的名称+链接（含多源）`)
  hideCtx()
}
function ctxCopyInfo() {
  const rows = getTargetRows()
  const text = rows.map(row => {
    const srcs = (row.sources && row.sources.length) ? row.sources : [row.url]
    const srcLines = srcs.map((u, i) => `源${i + 1}: ${u}`).join('\n')
    return `名称: ${row.name}\n地址: ${row.url}\n分组: ${row.group || ''}\n状态: ${row.status || '未检查'}\n延迟: ${row.ms || ''}ms\n分辨率: ${row.res || ''}\n标记: ${row.tag || ''}\n网络栈: ${row.stack || ''}\n全部源:\n${srcLines}`
  }).join('\n---\n')
  navigator.clipboard.writeText(text)
  ElMessage.success(`已复制 ${rows.length} 条信息（含多源）`)
  hideCtx()
}
function ctxCopyM3u() {
  const rows = getTargetRows()
  const m3u = []
  for (const row of rows) {
    const grp = row.group || '自动分组'
    const srcs = (row.sources && row.sources.length) ? row.sources : [row.url]
    srcs.forEach((u, i) => {
      const name = i === 0 ? row.name : `${row.name} (源${i + 1})`
      m3u.push(`#EXTINF:-1 group-title="${grp}" tvg-logo="${row.logo || ''}",${name}`)
      m3u.push(u)
    })
  }
  navigator.clipboard.writeText(m3u.join('\n'))
  ElMessage.success(`已复制 ${rows.length} 个频道的 M3U（含多源）`)
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
// 现有标记库：聚合所有频道主 tag 与每个源(source_tags)的标记，不再包含"假直播"
const existingTags = computed(() => {
  const set = new Set()
  const collect = (tagStr) => {
    if (!tagStr) return
    for (const x of String(tagStr).split(',')) {
      const s = x.trim()
      if (s && s !== '假直播') set.add(s)
    }
  }
  for (const c of store.channels) {
    collect(c.tag)
    for (const t of Object.values(c.source_tags || {})) collect(t)
  }
  return [...set].sort()
})
const selectedRowsAreFakeLive = computed(() => {
  const rows = getTargetRows()
  if (rows.length === 0) return false
  return rows.every(r => r.is_fake_live)
})
const sourceCtxIsFakeLive = computed(() => {
  const row = ctxSource.row
  if (!row || !ctxSource.url) return false
  return !!(row.source_is_fake_live || {})[ctxSource.url]
})
// EPG 规范分组（默认提供的常用分组，取自 epg_service.update_groups 规则）
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
  store.refresh()
  ElMessage.success(`已清除 ${rows.length} 个频道的标记`)
  hideCtx()
}
async function ctxToggleFakeLive() {
  const rows = getTargetRows()
  if (rows.length === 0) { hideCtx(); return }
  const ids = rows.map(r => r.id)
  const next = !rows.every(r => r.is_fake_live)
  await channelApi.batchFakeLive(ids, next)
  store.refresh()
  ElMessage.success(next ? `已将 ${rows.length} 个频道标记为假直播` : `已取消 ${rows.length} 个频道的假直播标记`)
  hideCtx()
}

// ==================== 聚合源单行右键菜单 ====================
function ctxSourcePlay() { playSourceInline(ctxSource.row, ctxSource.url); hideCtx() }
function ctxSourcePlayExternal() { playExternal({ ...ctxSource.row, url: ctxSource.url }); hideCtx() }
function ctxSourceCopyUrl() {
  navigator.clipboard.writeText(ctxSource.url)
  ElMessage.success('已复制源链接')
  hideCtx()
}
async function ctxSourceTagExisting(t) {
  await channelApi.setSourceTag(ctxSource.row.id, ctxSource.url, t)
  store.refresh()
  ElMessage.success(`已设置源标记：${t}`)
  hideCtx()
}
async function ctxSourceTagCustom() {
  try {
    const { value } = await ElMessageBox.prompt('添加源标记', '标记', { inputPlaceholder: '多个标记用逗号分隔' })
    await channelApi.setSourceTag(ctxSource.row.id, ctxSource.url, value)
    store.refresh()
    ElMessage.success('已设置源标记')
  } catch { /* cancel */ }
  hideCtx()
}
async function ctxSourceTagClear() {
  await channelApi.setSourceTag(ctxSource.row.id, ctxSource.url, '')
  store.refresh()
  ElMessage.success('已清除源标记')
  hideCtx()
}
async function ctxSourceToggleFakeLive() {
  const next = !sourceCtxIsFakeLive.value
  await channelApi.setSourceFakeLive(ctxSource.row.id, ctxSource.url, next)
  store.refresh()
  ElMessage.success(next ? '已标记该源为假直播' : '已取消该源的假直播标记')
  hideCtx()
}
async function ctxSourceDelete() {
  try {
    await ElMessageBox.confirm('确认从该频道中删除此源？', '警告', { type: 'warning' })
  } catch { hideCtx(); return }
  await deleteSourceInline(ctxSource.row, ctxSource.url)
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

// 右键「智能粘贴」：复用顶部工具栏已有的 smartPaste（读取剪贴板 → 智能解析导入）
function ctxSmartPaste() { smartPaste(); hideCtx() }

// ==================== 选择行管理（去掉选框列后） ====================
const selectedRowIds = ref(new Set())

// R1: 正在播放的频道 id（播放器换台后列表高亮跟随 + 定位）
const playingRowId = ref(null)

// R1: watch 播放器当前频道 → 高亮 + scrollIntoView 定位
watch(() => playerStore.currentChannel, (ch) => {
  if (!ch || !ch.id) {
    if (!ch || !ch.url) { playingRowId.value = null; return }
    // 无 id（历史/EPG 播放）按 url 匹配
    const byUrl = (displayed.value || []).find(r => r.url === ch.url || (r.sources || []).includes(ch.url))
    playingRowId.value = byUrl ? byUrl.id : null
    return
  }
  playingRowId.value = ch.id
  // 定位到可见行（虚拟滚动大列表用 scrollIntoView 兜底）
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
  // R1: 正在播放的频道行高亮（含子源命中当前播放地址）
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

// ==================== 导出（弹出框选择格式和位置） ====================
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
  // 设置开启「默认使用外部播放」时，直接调用外部播放器
  if (settingsStore.get('prefer_external_player')) {
    await playExternal(sourceUrl ? { ...row, url: sourceUrl } : row)
    return
  }
  // 双窗口（Phase 1）：经纪人转发到独立播放窗（run.py Api.play_channel），列表即唯一选源入口
  const api = window.pywebview?.api
  if (api && typeof api.play_channel === 'function') {
    await callNative('play_channel', {
      url: playUrl,
      name: row.name,
      group: row.group || '',
      id: row.id,
    })
    // 主窗口保留「正在播放」高亮（跨窗口状态不共享，列表侧自己记）
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
  // 退化：浏览器/无原生桥 → 旧单窗口路径（仅 dev 预览）
  const chList = (displayed.value || []).map(ch => ({
    id: ch.id,
    url: ch.url, name: ch.name || '', group: ch.group || '',
    sources: ch.sources && ch.sources.length ? ch.sources : [ch.url],
    source_groups: Array.isArray(ch.source_groups) ? ch.source_groups : [],
    tag: ch.tag || '',
    is_fake_live: !!ch.is_fake_live,
    source_tags: ch.source_tags || {},
    source_is_fake_live: ch.source_is_fake_live || {},
    url_note: ch.url_note || '',   // 1.5: $ 后标签透传
  }))
  const idx = chList.findIndex(ch => ch.url === playUrl)
  playerStore.open({
    id: row.id,
    url: playUrl,
    name: row.name,
    group: row.group || '',
    sources: row.sources && row.sources.length ? row.sources : [row.url],
    source_groups: Array.isArray(row.source_groups) ? row.source_groups : [],
    tag: row.tag || '',
    is_fake_live: !!row.is_fake_live,
    source_tags: row.source_tags || {},
    source_is_fake_live: row.source_is_fake_live || {},
    url_note: row.url_note || '',
  }, chList, idx >= 0 ? idx : 0)
  // 浮层自动展开为 drawer（hidden → drawer）
  if (playerStore.state === 'hidden') playerStore.setState('drawer')
  else playerStore.exitPip()  // pip 态回到 drawer（列表视图播放）
}

async function playExternal(row) {
  if (!row || !row.url) {
    ElMessage.info('请先选择或双击一个频道')
    return
  }
  // 优先使用手动配置路径（settings.external_player_path），其次自动探测
  let path = externalPlayerPath.value || settingsStore.get('external_player_path') || ''
  if (!path) {
    try {
      const { data } = await configApi.getPlayers()
      path = settingsStore.get('external_player') === 'potplayer' ? data.pot : data.vlc
      externalPlayerPath.value = path || ''
    } catch { /* ignore */ }
  }
  if (!path) {
    ElMessage.warning('未检测到 VLC / PotPlayer，请在设置中指定播放器路径后再使用外部播放')
    return
  }
  const ok = await callNative('play_external', row.url, path)
  if (ok === undefined) {
    ElMessage.info('仅桌面版支持外部播放，请使用客户端打开')
  } else if (ok === false) {
    ElMessage.error('未找到外部播放器，请检查设置或安装 VLC / PotPlayer')
  }
}

// ==================== 双击播放 ====================
function handleRowDblClick(row) {
  // Phase 5：设置项「双击频道自动播放」关闭时，双击不触发播放（可用顶栏/右键播放）
  if (settingsStore.get('double_click_auto_play') === false) return
  openPlayer(row)
}

// ==================== 合并频道：列表内展开子源，逐条播放/删除 ====================
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
// 子源延迟/健康信息：从聚合频道的 source_health 读取每个源的独立检测结果
function sourceHealth(row, u) {
  return (row.source_health || {})[u] || null
}
function sourceMsDisplay(row, u) {
  const h = sourceHealth(row, u)
  if (!h) return ''
  if (h.status === '离线') return '<span class="src-ms src-ms-off">离线</span>'
  if (h.ms || h.ms === 0) return `<span class="src-ms">${h.ms}ms</span>`
  return ''
}
function standaloneSources(row) {
  const grouped = new Set((row.source_groups || []).flatMap(g => g.urls || []))
  const srcs = (row.sources && row.sources.length) ? row.sources : [row.url]
  return srcs.filter(u => !grouped.has(u))
}
function playSourceInline(row, url) {
  openPlayer(row, url)
}
async function deleteSourceInline(row, url) {
  const srcs = ((row.sources && row.sources.length) ? row.sources : [row.url]).filter(u => u !== url)
  if (!srcs.length) {
    ElMessage.warning('至少需保留一个源')
    return
  }
  const groups = (row.source_groups || [])
    .map(g => ({ name: g.name, urls: (g.urls || []).filter(u => u !== url) }))
    .filter(g => g.urls.length >= 2)
  const payload = {
    url: row.url === url ? (srcs[0] || row.url) : row.url,
    sources: srcs,
    source_groups: groups,
  }
  try {
    await channelApi.updateChannel(row.id, payload)
    ElMessage.success('已删除该源')
    store.refresh()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}
function toggleRowExpand(row) {
  const t = tableRef.value
  if (t) t.toggleRowExpansion(row)
}

// ==================== Ctrl/Shift 点击多选 ====================
function onRowClick(row, column, event) {
  // 阻止浏览器默认的文本选择行为（Shift+click触发）
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

// ==================== 列宽持久化 ====================
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

// 自动保存列宽（任何修改都落盘，含拖拽后）
watch(columnWidths, saveColumnWidths, { deep: true })

// 应用保存的列宽（使用computed实现响应式更新）
const COL_DEFS = [
  { key: 'name', prop: 'name', defLabel: '频道', width: 180 },
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

// ==================== 检查状态轮询 ====================
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
        // 延迟一下再刷新，让用户看到100%
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

// ==================== 抓取状态轮询 ====================
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

// ==================== 抓取 ====================
function getScrapeParams() {
  // 代理和加速源互斥：开代理时不用加速源，用加速源时清空代理
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
      scraping.value = true; pollScrape()
    } catch { /* ignore */ }
  }
}
async function doSingleUrl() {
  if (!cfgUrl.value) return ElMessage.warning('请输入扫描网址')
  await toggleScrape()
}

// ==================== 多网址 ====================
const showUrlPool = ref(false)
const urlPoolText = ref('')
async function doUrlPool() {
  const urls = urlPoolText.value.split('\n').map(s => s.trim()).filter(s => s.startsWith('http'))
  if (!urls.length) return ElMessage.warning('请输入有效网址')
  try {
    const { proxy, mirror } = getScrapeParams()
    const { data } = await scrapeApi.scrapeBatch({ urls, suffix_list: cfgSuffix.value, proxy, mirror })
    if (data.error) return ElMessage.warning(data.error)
    scraping.value = true; showUrlPool.value = false; pollScrape()
  } catch { /* ignore */ }
}

// ==================== 导入 ====================
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

// ==================== 粘贴 ====================
async function smartPaste() {
  try {
    const text = await navigator.clipboard.readText()
    const { data } = await scrapeApi.smartPaste(text)
    if (data.error) return ElMessage.warning(data.error)
    ElMessage.success(`粘贴成功：新增 ${data.added} 个频道`)
    store.refresh()
  } catch { ElMessage.error('读取剪贴板失败') }
}

// ==================== 乱码修补 ====================
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
    // 开关关闭时（导入列表），强制使用最新完整修补规则
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

// ==================== 查找替换 ====================
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

// ==================== 规则管理 ====================
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

// ==================== 源管理 ====================
const showSourceMgr = ref(false)
const sourceMgrRow = ref(null)
const sourceMgrSources = ref([])
const sourceMgrGroups = ref([])
const smSelected = ref([])
const smExpandedGroups = ref(new Set())

const smStandalone = computed(() => {
  const grouped = new Set(sourceMgrGroups.value.flatMap(g => g.urls || []))
  return sourceMgrSources.value.filter(u => !grouped.has(u))
})

function openSourceMgr(row) {
  sourceMgrRow.value = row
  sourceMgrSources.value = [...(row.sources?.length ? row.sources : [row.url])]
  sourceMgrGroups.value = JSON.parse(JSON.stringify(row.source_groups || []))
  smSelected.value = []
  smExpandedGroups.value = new Set(sourceMgrGroups.value.map((_, i) => i))
  showSourceMgr.value = true
  hideCtx()
}
function ctxSourceMgr() { openSourceMgr(ctx.row) }

function smAddSource() {
  sourceMgrSources.value.push('')
}
function smRemoveStandalone(idx) {
  const url = smStandalone.value[idx]
  sourceMgrGroups.value.forEach(g => { g.urls = (g.urls || []).filter(u => u !== url) })
  sourceMgrSources.value = sourceMgrSources.value.filter(u => u !== url)
  smSelected.value = smSelected.value.filter(u => u !== url)
  sourceMgrGroups.value = sourceMgrGroups.value.filter(g => (g.urls || []).length)
}
function smRemoveGroup(gi) {
  sourceMgrGroups.value.splice(gi, 1)
  smExpandedGroups.value = new Set([...smExpandedGroups.value].filter(i => i !== gi).map(i => i > gi ? i - 1 : i))
}
function smRemoveGroupMember(gi, ui) {
  const url = sourceMgrGroups.value[gi].urls[ui]
  sourceMgrGroups.value[gi].urls.splice(ui, 1)
  if (!sourceMgrGroups.value[gi].urls.length) {
    sourceMgrGroups.value.splice(gi, 1)
    smExpandedGroups.value = new Set([...smExpandedGroups.value].filter(i => i !== gi).map(i => i > gi ? i - 1 : i))
  }
  // 如果该 URL 已不在任何 group 中，仍保留在 sources 里作为独立源
  const stillGrouped = sourceMgrGroups.value.some(g => (g.urls || []).includes(url))
  if (!stillGrouped && !sourceMgrSources.value.includes(url)) {
    sourceMgrSources.value.push(url)
  }
}
function smToggleGroup(gi) {
  if (smExpandedGroups.value.has(gi)) smExpandedGroups.value.delete(gi)
  else smExpandedGroups.value.add(gi)
}
function smAggregate() {
  const urls = smSelected.value.filter(u => smStandalone.value.includes(u))
  if (urls.length < 2) return ElMessage.warning('请至少选择 2 个独立源进行聚合')
  sourceMgrGroups.value.push({ name: `聚合源 ${sourceMgrGroups.value.length + 1}`, urls })
  smSelected.value = []
  smExpandedGroups.value.add(sourceMgrGroups.value.length - 1)
}
function smUngroupAll() {
  sourceMgrGroups.value = []
  smExpandedGroups.value.clear()
}
function smUpdateUrl(oldUrl, newUrl, where, gi, ui) {
  newUrl = (newUrl || '').trim()
  if (newUrl === oldUrl) return
  if (!newUrl) {
    if (where === 'standalone') {
      const idx = smStandalone.value.indexOf(oldUrl)
      if (idx >= 0) smRemoveStandalone(idx)
    } else {
      smRemoveGroupMember(gi, ui)
    }
    return
  }
  sourceMgrSources.value = sourceMgrSources.value.map(u => u === oldUrl ? newUrl : u)
  sourceMgrGroups.value.forEach(g => {
    g.urls = (g.urls || []).map(u => u === oldUrl ? newUrl : u)
  })
  smSelected.value = smSelected.value.map(u => u === oldUrl ? newUrl : u)
}
async function doSaveSources() {
  if (!sourceMgrRow.value) return
  sourceMgrSources.value = sourceMgrSources.value.map(u => (u || '').trim()).filter(Boolean)
  // 去重
  const seen = new Set()
  sourceMgrSources.value = sourceMgrSources.value.filter(u => { if (seen.has(u)) return false; seen.add(u); return true })
  // 清理聚合组：name 非空、urls 至少 2 个且都在 sources 中
  sourceMgrGroups.value.forEach(g => {
    g.name = (g.name || '').trim() || '聚合源'
    g.urls = (g.urls || []).map(u => (u || '').trim()).filter(Boolean).filter(u => sourceMgrSources.value.includes(u))
    const s = new Set()
    g.urls = g.urls.filter(u => { if (s.has(u)) return false; s.add(u); return true })
  })
  sourceMgrGroups.value = sourceMgrGroups.value.filter(g => g.urls.length >= 2)
  try {
    const payload = {
      url: sourceMgrSources.value[0] || sourceMgrRow.value.url,
      sources: sourceMgrSources.value,
      source_groups: sourceMgrGroups.value
    }
    await channelApi.updateChannel(sourceMgrRow.value.id, payload)
    ElMessage.success('已保存')
    store.refresh()
    showSourceMgr.value = false
  } catch { /* ignore */ }
}

// ==================== 频道编辑 ====================
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

// ==================== 搜索节目 ====================
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

// ==================== DLNA 投屏 ====================
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
      // 自动选中第一个设备
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

// ==================== 日志 ====================
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

// ==================== 弹窗 ====================
const showAbout = ref(false)
const appVersion = ref('7.0.1')

// #58 在线台标补全（后台任务 + 轮询进度）
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

// 应用版本号（后端单一真相源）
async function fetchAppVersion() {
  try {
    const { data } = await appApi.getAppVersion()
    if (data && data.version) appVersion.value = data.version
  } catch { /* ignore */ }
}

// #56 智能去重合并
async function doMergeDuplicates() {
  try {
    const { data } = await channelApi.mergeDuplicates()
    if (data.removed > 0) {
      ElMessage.success(`已合并 ${data.removed} 个重复频道（URL ${data.removed_by_url} / 名称 ${data.removed_by_name}），剩余 ${data.remaining}`)
    } else {
      ElMessage.info('未发现重复频道')
    }
    store.refresh()
  } catch (e) {
    ElMessage.error('去重合并失败: ' + (e.response?.data?.detail || e.message))
  }
}

// #57 Logo 自动匹配（默认扫描程序目录下的 logos 文件夹）
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

// #58 在线台标补全（后台任务 + 轮询进度）
function doOnlineLogos() {
  // 打开对话框并重置状态
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
    // 轮询失败（任务可能已过期）不阻断，继续下一次
  }
}

function finishOnlineLogos() {
  showOnlineLogos.value = false
  if (onlineTimer) { clearInterval(onlineTimer); onlineTimer = null }
  store.refresh()
}

onUnmounted(() => { if (onlineTimer) clearInterval(onlineTimer) })

// #60 重新自动分组（对整池按统一算法重跑分组，解决历史混乱 / 外国频道统一）
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

// 频道 logo 加载失败时不显示破图标
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

// ==================== 列设置持久化 ====================
watch(hiddenCols, saveHiddenCols, { deep: true })

// ==================== 排序 ====================
function onSortChange({ prop, order }) {
  sortState.prop = prop; sortState.order = order
  saveSortState()
  page.value = 1
}

// 自动保存排序状态（含清空排序的 undefined 场景）
watch(() => ({ prop: sortState.prop, order: sortState.order }), saveSortState, { deep: true })

// ==================== 生命周期 ====================
let logTimer = null
let logES = null
let evtES = null

// 实时推送（SSE）；连接成功则停掉 2s 日志轮询，失败自动回退轮询，绝不破坏既有路径。
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
  } catch (e) { /* 回退轮询 */ }

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
  } catch (e) { /* 忽略 */ }
}

onMounted(async () => {
  await store.fetchIfNeeded()
  await settingsStore.fetchSettings()
  fetchAppVersion()
  // 探测外部播放器路径（VLC / PotPlayer），供「用外部播放器打开」使用
  // 优先读手动配置路径，其次自动探测
  try {
    const manual = settingsStore.get('external_player_path')
    if (manual) {
      externalPlayerPath.value = manual
    } else {
      const { data } = await configApi.getPlayers()
      externalPlayerPath.value = (settingsStore.get('external_player') === 'potplayer' ? data.pot : data.vlc) || ''
    }
  } catch { /* ignore */ }
  loadLogs()
  logTimer = setInterval(loadLogs, 2000)
  startRealtime()
  document.addEventListener('click', hideCtx)
  // 检查是否有正在运行的检查任务
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

// 监听设置变化，实时同步到抓取面板（设置保存后自动生效，无需刷新页面）
watch(() => settingsStore.settings, async (s) => {
  if (!s || !Object.keys(s).length) return
  // 同步抓取配置项
  if (s.suffix_list) cfgSuffix.value = s.suffix_list
  if (s.proxy !== undefined) cfgProxy.value = s.proxy
  if (s.mirror) cfgMirror.value = s.mirror
  if (s.use_proxy !== undefined) useProxy.value = s.use_proxy
  if (s.default_epg) cfgEpg.value = s.default_epg
  // 同步统计卡片设置
  statsCardVisible.value = s.stats_card_visible !== false
  statsCardPosition.value = s.stats_card_position || '顶部'
  // 同步历史列表（加速源、EPG、URL历史）
  try {
    const { data } = await exportApi.getHistory()
    if (data) {
      urlHistory.value = data.url || []
      mirrorHistory.value = data.mirror || []
      epgHistory.value = data.epg || []
    }
  } catch { /* ignore */ }
  // 外部播放器路径随设置同步（手动路径优先，其次 external_player 切换 VLC/PotPlayer 自动探测）
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
  clearInterval(logTimer)
  clearInterval(checkTimer)
  clearInterval(scrapeTimer)
  if (epgTimer) clearInterval(epgTimer)
  try { logES && logES.close() } catch (e) {}
  try { evtES && evtES.close() } catch (e) {}
  document.removeEventListener('click', hideCtx)
})

// 键盘快捷键
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
/* 覆盖 Element Plus 输入数字框的最小宽度，使页码输入框紧凑 */
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

/* 分组树 */
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

/* 播放健康度指示 */
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

/* 频道名 + Logo 缩略图 */
.name-cell { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
.ch-logo { width: 22px; height: 22px; object-fit: contain; border-radius: 3px; flex-shrink: 0; background: var(--el-fill-color-light); }
.ch-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 右键菜单 */
.ctx-menu {
  position: fixed; z-index: 9999; background: var(--el-bg-color);
  border: 1px solid var(--el-border-color); border-radius: 6px;
  box-shadow: var(--el-box-shadow); min-width: 120px; padding: 4px 0;
}
.ctx-item { padding: 6px 16px; font-size: 13px; cursor: pointer; }
.ctx-item:hover { background: var(--el-fill-color-light); }
.ctx-sep { height: 1px; background: var(--el-border-color-lighter); margin: 4px 0; }
/* 二级子菜单（复制 / 标记 / 设置分组） */
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

/* 选中行高亮 */
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

/* R1: 正在播放行高亮（区别于选中态，绿色弱底） */
:deep(.el-table__body tr.playing-row > td) {
  background-color: rgba(74, 222, 128, 0.08) !important;
}
:deep(.el-table__body tr.playing-row > td:first-child) {
  box-shadow: inset 3px 0 0 var(--el-color-success) !important;
}

/* 单网址/多网址按钮宽度统一 */
.form-row .el-button--small { width: 70px; }

/* 禁止表格内文字选中（Shift多选时避免选中单元格文本） */
.channel-table :deep(.el-table__body-wrapper) {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

/* DLNA 投屏弹窗 */
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
/* 源管理弹窗 */
.source-mgr { max-height: 480px; overflow-y: auto; }
.sm-toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.sm-group { border: 1px solid var(--el-border-color-lighter); border-radius: 6px; margin-bottom: 10px; overflow: hidden; }
.sm-group-header { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: var(--el-fill-color-light); cursor: pointer; }
.sm-group-header .sm-arrow { color: var(--el-text-color-secondary); }
.sm-group-name { flex: 1; }
.sm-group-name :deep(.el-input__inner) { background: transparent; }
.sm-group-body { padding: 8px 10px; display: flex; flex-direction: column; gap: 6px; }
.sm-row { display: flex; align-items: center; gap: 8px; }
.sm-row .sm-url { flex: 1; }
.sm-row .el-checkbox { margin-right: 0; flex-shrink: 0; }
.sm-section-title { font-size: 13px; font-weight: 600; margin: 12px 0 8px; color: var(--el-text-color-primary); }
.sm-list { display: flex; flex-direction: column; gap: 6px; }
.sm-empty { text-align: center; color: var(--el-text-color-secondary); padding: 24px 0; font-size: 13px; }

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

/* 频道列表：合并源展开区 */
.src-expand { padding: 6px 12px 10px 38px; background: var(--el-fill-color-light); }
.src-tag-line { display: flex; align-items: center; gap: 6px; margin: 2px 0 6px; }
.src-tag-label { font-size: 12px; color: var(--el-text-color-secondary); }
.src-tag-value { font-weight: 600; }
.src-group-name { font-size: 12px; font-weight: 600; color: var(--el-color-primary); margin: 6px 0 4px; }
.src-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; border-top: 1px dashed var(--el-border-color-lighter); }
.src-row:first-of-type { border-top: none; }
.src-tag { font-size: 11px; color: #fff; background: var(--el-color-info); border-radius: 3px; padding: 1px 6px; flex-shrink: 0; }
.src-tag-num { background: var(--el-color-primary); }
.src-tag-channel { max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; background: var(--el-color-warning); color: var(--el-color-black); }
.src-tag-fake { background: var(--el-color-danger); color: #fff; }
.src-url { flex: 1; min-width: 0; font-size: 12px; color: var(--el-text-color-regular); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: default; }
.src-ms { flex-shrink: 0; font-size: 12px; font-weight: 600; color: var(--el-color-success); }
.src-ms-off { color: var(--el-color-danger); }
.src-empty { padding: 6px 12px 6px 38px; font-size: 12px; color: var(--el-text-color-secondary); }
.src-empty .src-tag-line { margin: 0; }
.src-count { cursor: pointer; font-weight: 600; }
.src-count:hover { color: var(--el-color-primary); }
</style>