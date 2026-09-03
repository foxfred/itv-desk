<template>
  <div class="settings-page">
    <el-card shadow="never">
      <template #header><span class="page-title">系统设置</span></template>
      <el-tabs v-model="activeTab" tab-position="left" class="settings-tabs">
        <!-- 常规 -->
        <el-tab-pane label="常规" name="general">
          <el-form label-width="100px" size="small">
            <el-form-item label="格式后缀">
              <el-input v-model="form.suffix_list" placeholder="m3u,m3u8,txt" style="width:300px" />
            </el-form-item>
            <el-form-item label="扫描网址">
              <el-input
                v-model="urlText"
                type="textarea"
                :rows="4"
                placeholder="每行一个网址，例如：&#10;https://example.com/page{1-5}.html"
                style="width:300px"
              />
              <div class="tip">每行一个扫描网址，保存后自动同步到抓取区列表</div>
            </el-form-item>
            <el-form-item label="加速源">
              <el-input
                v-model="mirrorText"
                type="textarea"
                :rows="4"
                placeholder="每行一个地址，例如：&#10;ghp.ci&#10;ghproxy.com&#10;kkgithub.com"
                style="width:300px"
              />
              <div class="tip">每行一个镜像地址，保存后自动同步到抓取区列表</div>
            </el-form-item>
            <el-form-item label="默认分组">
              <el-input v-model="form.default_group_name" placeholder="自动分组" style="width:200px" />
            </el-form-item>
            <el-form-item label="智能粘贴分组">
              <el-input v-model="form.smart_paste_default_group" placeholder="粘贴导入" style="width:200px" />
            </el-form-item>
            <el-form-item label="缓存文件名">
              <el-input v-model="form.cache_file_name" placeholder="channels_cache.json" style="width:300px" />
            </el-form-item>
            <el-form-item label="EPG地址">
              <el-input
                v-model="epgText"
                type="textarea"
                :rows="4"
                placeholder="每行一个地址，例如：&#10;https://epg.163189.xyz/pp.xml"
                style="width:300px"
              />
              <div class="tip">每行一个EPG地址，保存后自动同步到抓取区列表</div>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 网络 -->
        <el-tab-pane label="网络" name="network">
          <el-form label-width="100px" size="small">
            <el-form-item label="网络代理">
              <div style="display:flex;align-items:center;gap:8px">
                <el-switch v-model="form.use_proxy" size="small" />
                <span style="font-size:12px;color:var(--el-text-color-secondary)">启用代理</span>
                <el-input v-if="form.use_proxy" v-model="form.proxy" placeholder="127.0.0.1:10808" style="width:200px;margin-left:8px" />
              </div>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 抓取 -->
        <el-tab-pane label="抓取" name="scrape">
          <el-form label-width="100px" size="small">
            <el-form-item label="抓取超时">
              <el-input-number v-model="form.scraper_timeout" :min="5" :max="60" style="width:120px" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="抓取重试">
              <el-input-number v-model="form.scraper_retries" :min="0" :max="5" style="width:120px" />
            </el-form-item>
            <el-form-item label="抓取线程数">
              <el-input-number v-model="form.scraper_threads" :min="1" :max="50" style="width:120px" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 检查 -->
        <el-tab-pane label="检查" name="check">
          <el-form label-width="100px" size="small">
            <el-form-item label="超时时间">
              <el-input-number v-model="form.check_timeout" :min="1" :max="60" style="width:120px" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="最大重试">
              <el-input-number v-model="form.check_retries" :min="0" :max="5" style="width:120px" />
            </el-form-item>
            <el-form-item label="线程数">
              <el-input-number v-model="form.check_threads" :min="1" :max="100" style="width:120px" />
            </el-form-item>
            <el-form-item label="真实可看性探测">
              <el-switch v-model="form.probe_watchable" />
              <span class="tip">开启后检查时拉取媒体片段分析真实可看性（更准确但更慢）；关闭则仅测状态码</span>
            </el-form-item>
            <el-form-item label="HLS 流检查">
              <el-switch v-model="form.check_hls" />
              <span class="tip">对 HLS 源额外检查主索引和切片可达性</span>
            </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- 自动任务 -->
          <el-tab-pane label="自动任务" name="scheduler">
            <el-form label-width="130px" size="small">
              <el-form-item label="订阅源自动更新">
                <el-input-number v-model="form.subscription_auto_update_interval" :min="0" :max="86400" :step="60" style="width:140px" />
                <span class="unit">秒（0=关闭）</span>
              </el-form-item>
              <el-form-item label="EPG 定时刷新">
                <el-input-number v-model="form.epg_auto_refresh_interval" :min="0" :max="86400" :step="60" style="width:140px" />
                <span class="unit">秒（0=关闭）</span>
              </el-form-item>
              <el-form-item label="检查定时任务">
                <el-input-number v-model="form.check_auto_interval" :min="0" :max="86400" :step="60" style="width:140px" />
                <span class="unit">秒（0=关闭）</span>
              </el-form-item>
              <div class="tip" style="margin-left:130px">
                设置后保存即时生效：后端会按间隔自动增量更新订阅源 / 刷新 EPG 节目单 / 自动检查频道可用性。例如 3600 = 每小时一次。
              </div>
            </el-form>
          </el-tab-pane>

          <!-- 扫描 -->
          <el-tab-pane label="扫描" name="scan">
            <el-form label-width="100px" size="small">
              <el-form-item label="探测超时">
                <el-input-number v-model="form.scan_timeout" :min="1" :max="30" style="width:120px" />
                <span class="unit">秒</span>
              </el-form-item>
              <el-form-item label="并发数">
                <el-input-number v-model="form.scan_max_workers" :min="1" :max="200" style="width:120px" />
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- 启动 -->
          <el-tab-pane label="启动" name="startup">
            <el-form label-width="130px" size="small">
              <el-form-item label="启动时加载频道缓存">
                <el-switch v-model="form.load_cache_on_startup" />
                <span class="tip">启动时自动加载上次保存的频道缓存文件</span>
              </el-form-item>
              <el-form-item label="退出时保存频道缓存">
                <el-switch v-model="form.save_cache_on_exit" />
                <span class="tip">退出程序时自动保存频道缓存到文件</span>
              </el-form-item>
              <el-form-item label="保存窗口位置">
                <el-switch v-model="form.save_window_geometry" />
                <span class="tip">退出时保存窗口位置和大小，下次启动恢复</span>
              </el-form-item>
              <el-form-item label="启动延迟">
                <el-input-number v-model="form.startup_delay_ms" :min="0" :max="10000" :step="100" style="width:140px" />
                <span class="unit">毫秒</span>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- 导入导出 -->
          <el-tab-pane label="导入导出" name="io">
            <el-form label-width="130px" size="small">
              <el-form-item label="URL历史上限">
                <el-input-number v-model="form.url_history_limit" :min="5" :max="200" style="width:120px" />
              </el-form-item>
              <el-form-item label="镜像历史上限">
                <el-input-number v-model="form.mirror_history_limit" :min="5" :max="200" style="width:120px" />
              </el-form-item>
              <el-form-item label="EPG历史上限">
                <el-input-number v-model="form.epg_history_limit" :min="5" :max="200" style="width:120px" />
              </el-form-item>
              <el-form-item label="导入后自动检查">
                <el-switch v-model="form.auto_check_after_import" />
                <span class="tip">导入/粘贴频道后自动启动可用性检查</span>
              </el-form-item>
              <el-form-item label="检查后自动导出">
                <el-switch v-model="form.auto_export_after_check" />
                <span class="tip">检查完成后自动导出整理结果</span>
              </el-form-item>
              <el-form-item label="检查后自动删除离线">
                <el-switch v-model="form.auto_delete_invalid_after_check" />
                <span class="tip">检查完成后自动删除离线频道</span>
              </el-form-item>
              <el-form-item label="检查后重置筛选">
                <el-switch v-model="form.reset_filter_after_check" />
                <span class="tip">检查完成后自动重置频道列表的筛选条件</span>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- 频道 -->
          <el-tab-pane label="频道" name="channel">
            <el-form label-width="130px" size="small">
              <el-form-item label="未分组频道组名">
                <el-input v-model="form.unknown_group_name" placeholder="未分组" style="width:200px" />
              </el-form-item>
              <el-form-item label="缓存默认分组">
                <el-input v-model="form.cache_default_group" placeholder="杂项频道" style="width:200px" />
              </el-form-item>
              <el-form-item label="缓存默认地理位置">
                <el-select v-model="form.cache_default_geo" style="width:160px">
                  <el-option label="中国" value="中国" />
                  <el-option label="香港" value="香港" />
                  <el-option label="台湾" value="台湾" />
                  <el-option label="美国" value="美国" />
                  <el-option label="日本" value="日本" />
                  <el-option label="韩国" value="韩国" />
                  <el-option label="英国" value="英国" />
                  <el-option label="新加坡" value="新加坡" />
                </el-select>
              </el-form-item>
              <el-form-item label="缓存默认网络栈">
                <el-select v-model="form.cache_default_stack" style="width:160px">
                  <el-option label="IPv4" value="IPv4" />
                  <el-option label="IPv6" value="IPv6" />
                </el-select>
              </el-form-item>
              <el-form-item label="显示质量列">
                <el-switch v-model="form.show_quality_column" />
              </el-form-item>
              <el-form-item label="User-Agent">
                <el-input v-model="form.user_agent" placeholder="Mozilla/5.0..." style="width:340px" />
              </el-form-item>
              <el-form-item label="最大连接数">
                <el-input-number v-model="form.max_connections" :min="10" :max="500" style="width:120px" />
              </el-form-item>
              <el-form-item label="下载超时">
                <el-input-number v-model="form.download_timeout" :min="5" :max="120" style="width:120px" />
                <span class="unit">秒</span>
              </el-form-item>
              <el-form-item label="下载重试">
                <el-input-number v-model="form.download_retries" :min="0" :max="5" style="width:120px" />
              </el-form-item>
              <el-form-item label="启动时自动加载 EPG">
                <el-switch v-model="form.auto_load_epg" />
                <span class="tip">启动时自动加载上次保存的 EPG 源</span>
              </el-form-item>
              <el-form-item label="EPG 加载后自动校正">
                <el-switch v-model="form.auto_correct_after_epg" />
                <span class="tip">EPG 加载完成后自动校正频道名</span>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- 播放器 -->
          <el-tab-pane label="播放器" name="player">
            <el-form label-width="140px" size="small">
              <el-form-item label="默认音量">
                <el-input-number v-model="form.default_volume" :min="0" :max="100" style="width:120px" />
                <span class="unit">%</span>
              </el-form-item>
              <el-form-item label="默认倍速">
                <el-select v-model="form.default_playback_speed" style="width:120px">
                  <el-option v-for="sp in [0.5,0.75,1.0,1.25,1.5,2.0]" :key="sp" :label="`${sp}x`" :value="sp" />
                </el-select>
              </el-form-item>
              <el-form-item label="控制栏自动隐藏">
                <el-input-number v-model="form.player_hide_controls_delay_ms" :min="0" :max="30000" :step="500" style="width:140px" />
                <span class="unit">毫秒（0=不隐藏）</span>
              </el-form-item>
              <el-form-item label="快进/快退步长">
                <el-input-number v-model="form.player_seek_step_ms" :min="500" :max="60000" :step="500" style="width:140px" />
                <span class="unit">毫秒</span>
              </el-form-item>
              <el-form-item label="键盘音量步长">
                <el-input-number v-model="form.player_keyboard_volume_step" :min="1" :max="20" style="width:120px" />
                <span class="unit">%</span>
              </el-form-item>
              <el-form-item label="键盘快捷键">
                <el-switch v-model="form.player_keyboard_enabled" />
                <span class="tip">启用后支持 空格播放/暂停、←/→ 快退快进、↑/↓ 音量、M 静音、F 全屏</span>
              </el-form-item>
              <el-form-item label="双击频道自动播放">
                <el-switch v-model="form.double_click_auto_play" />
                <span class="tip">列表双击频道 → 独立播放窗自动跟播（列表即唯一选源入口）。</span>
              </el-form-item>
              <el-form-item label="播放窗口总在最前">
                <el-switch v-model="form.player_window_topmost" />
                <span class="tip">播放窗口常驻置顶（边看边操作频道列表）；也可用播放窗控制条「📌」随时切换。</span>
              </el-form-item>
              <el-form-item label="待播轮询间隔">
                <el-input-number v-model="form.player_update_interval_ms" :min="100" :max="5000" :step="100" style="width:140px" />
                <span class="unit">毫秒</span>
              </el-form-item>
              <el-form-item label="视频背景色">
                <el-color-picker v-model="form.color_video_bg" />
              </el-form-item>
              <el-form-item label="通过本地代理播放">
                <el-switch v-model="form.player_stream_proxy" />
                <span class="tip">开启后 HLS 流经本地后端中继（同源返回），可绕过 WebView 跨源/MSE 限制（部分源 PotPlayer 能放、内置报错时可用；会经后端转发流量）</span>
              </el-form-item>
              <el-divider>外部播放器</el-divider>
              <el-form-item label="默认使用外部播放">
                <el-switch v-model="form.prefer_external_player" />
                <span class="tip">开启后双击频道直接调用外部播放器（需安装 VLC / PotPlayer / mpv）</span>
              </el-form-item>
              <el-form-item label="外部播放器">
                <el-radio-group v-model="form.external_player">
                  <el-radio label="vlc">VLC</el-radio>
                  <el-radio label="potplayer">PotPlayer</el-radio>
                  <el-radio label="mpv">mpv</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="播放器路径">
                <div style="display:flex;gap:6px;width:360px">
                  <el-input v-model="form.external_player_path" placeholder="留空则自动检测，或手动指定可执行文件路径" style="flex:1" />
                  <el-button size="small" @click="browsePlayerPath">浏览</el-button>
                </div>
                <span class="tip">当播放器不在默认安装位置时，可手动指定 .exe 路径（如 D:\Tools\PotPlayer\PotPlayerMini.exe）</span>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- 主题 -->
          <el-tab-pane label="主题" name="theme">
          <el-form label-width="100px" size="small">
            <el-form-item label="预设主题">
              <div class="theme-grid">
                <div
                  v-for="t in PRESET_THEMES" :key="t.color"
                  class="theme-item"
                  :class="{ active: currentTheme === t.color }"
                  @click="setTheme(t.color)"
                >
                  <div class="theme-color" :style="{ background: t.color }" />
                  <span>{{ t.name }}</span>
                </div>
              </div>
            </el-form-item>
            <el-form-item label="自定义颜色">
              <el-color-picker v-model="customColor" @change="onCustomColor" show-alpha />
            </el-form-item>
            <el-form-item label="导入皮肤">
              <el-upload :auto-upload="false" :show-file-list="false" :on-change="onImportSkin" accept=".css">
                <el-button size="small">选择 Element Plus 皮肤 CSS 文件</el-button>
              </el-upload>
              <el-button v-if="currentTheme === '__custom__'" size="small" type="danger" style="margin-left:8px" @click="clearCustomTheme">清除自定义皮肤</el-button>
              <div class="tip">从 Element Plus 主题编辑器下载的 CSS 文件</div>
            </el-form-item>
            <el-form-item label="内置皮肤">
              <div class="skin-grid">
                <div class="skin-group">
                  <div class="skin-group-title">暗黑风格</div>
                  <div class="skin-list">
                    <div
                      v-for="s in BUILTIN_SKINS.filter(s => s.type === 'dark')" :key="s.file"
                      class="skin-item"
                      :class="{ active: builtinSkin === s.file }"
                      @click="onApplyBuiltinSkin(s)"
                    >
                      <span>{{ s.name }}</span>
                    </div>
                  </div>
                </div>
                <div class="skin-group">
                  <div class="skin-group-title">亮色风格</div>
                  <div class="skin-list">
                    <div
                      v-for="s in BUILTIN_SKINS.filter(s => s.type === 'light')" :key="s.file"
                      class="skin-item"
                      :class="{ active: builtinSkin === s.file }"
                      @click="onApplyBuiltinSkin(s)"
                    >
                      <span>{{ s.name }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </el-form-item>
            <el-form-item label="暗色模式">
              <el-switch v-model="darkMode" @change="setDarkMode" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 列设置 -->
        <el-tab-pane label="列设置" name="columns">
          <el-form label-width="100px" size="small">
            <el-form-item label="显示列">
              <el-checkbox-group v-model="columnVisibility">
                <div v-for="col in allCols" :key="col.key" style="display:inline-block;width:33%;margin-bottom:4px">
                  <el-checkbox :label="col.key" :value="col.key">{{ col.defLabel }}</el-checkbox>
                </div>
              </el-checkbox-group>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 高级 -->
        <el-tab-pane label="高级" name="advanced">
          <el-form label-width="120px" size="small">
            <el-form-item label="修补超时">
              <el-input-number v-model="form.repair_check_timeout" :min="1" :max="30" style="width:120px" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="修补重试">
              <el-input-number v-model="form.repair_max_retries" :min="0" :max="5" style="width:120px" />
            </el-form-item>
            <el-form-item label="修补线程数">
              <el-input-number v-model="form.repair_max_workers" :min="1" :max="50" style="width:120px" />
            </el-form-item>
            <el-form-item label="高清阈值">
              <el-input-number v-model="form.repair_hd_size_threshold" :min="10000" :step="10000" style="width:160px" />
              <span class="unit">字节</span>
            </el-form-item>
            <el-form-item label="标清阈值">
              <el-input-number v-model="form.repair_sd_size_threshold" :min="10000" :step="10000" style="width:160px" />
              <span class="unit">字节</span>
            </el-form-item>
            <el-form-item label="统计卡片位置">
              <el-radio-group v-model="form.stats_card_position">
                <el-radio label="顶部">顶部</el-radio>
                <el-radio label="底部">底部</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="显示统计卡片">
              <el-switch v-model="form.stats_card_visible" />
            </el-form-item>
            <el-divider>检查引擎</el-divider>
            <el-form-item label="延迟等级 A 阈值">
              <el-input-number v-model="form.latency_grade_a_threshold" :min="50" :max="2000" :step="50" style="width:140px" />
              <span class="unit">毫秒（≤此值=优）</span>
            </el-form-item>
            <el-form-item label="延迟等级 B 阈值">
              <el-input-number v-model="form.latency_grade_b_threshold" :min="100" :max="5000" :step="50" style="width:140px" />
              <span class="unit">毫秒（≤此值=良）</span>
            </el-form-item>
            <el-form-item label="检查批次大小">
              <el-input-number v-model="form.checker_batch_size" :min="1" :max="50" style="width:120px" />
            </el-form-item>
          </el-form>
         </el-tab-pane>

         <!-- 数据 -->
         <el-tab-pane label="数据" name="data">
           <el-form label-width="100px" size="small">
             <el-form-item label="数据备份">
               <div style="width:100%">
                 <input type="file" accept=".zip" ref="backupFileInput" style="display:none"
                        @change="onBackupFileChange" />
                 <div style="margin-bottom:8px">
                   <el-button type="success" @click="pickBackupFile" :loading="importing">
                     导入备份
                   </el-button>
                 </div>
                 <div>
                   <el-button type="primary" @click="exportBackup" :loading="exporting">
                     导出备份（zip）
                   </el-button>
                 </div>
                 <div class="tip">导入备份：选择之前导出的 zip 备份包，恢复后会覆盖当前全部数据。导出备份：把频道、设置、历史、收藏等全部数据导出为 zip 文件。</div>
               </div>
             </el-form-item>
             <el-divider>本地加密备份（AES 口令保护，零服务器）</el-divider>
             <el-form-item label="加密备份">
               <div style="width:100%">
                 <input type="file" accept=".enc" ref="encFileInput" style="display:none"
                        @change="onEncFileChange" />
                 <div style="margin-bottom:8px">
                   <el-button type="success" @click="pickEncFile" :loading="importingEnc">
                     导入加密备份
                   </el-button>
                 </div>
                 <div>
                   <el-button type="warning" @click="exportEncrypted" :loading="exportingEnc">
                     加密导出（.enc）
                   </el-button>
                 </div>
                 <div class="tip">加密导出：用口令把数据 AES 加密后导出为 .enc 文件，即使泄露也无法被打开。导入加密备份：选择 .enc 文件并输入相同口令即可恢复，恢复会覆盖当前数据。</div>
               </div>
             </el-form-item>
           </el-form>
         </el-tab-pane>

         <!-- 分组（#60 分组重构） -->
         <el-tab-pane label="分组" name="group">
           <el-form label-width="120px" size="small">
             <el-form-item label="导入自动分组">
               <el-switch v-model="form.auto_group" />
               <div class="tip">开启后，导入/粘贴的频道按统一算法自动分组（忽略源自带的分组）；关闭则保留源分组。</div>
             </el-form-item>
             <el-form-item label="外国频道组名">
               <el-input v-model="form.foreign_group_name" style="width:200px"
                         placeholder="外国频道" />
               <div class="tip">所有非中文、非港澳台的频道统一归入此组名。</div>
             </el-form-item>
             <el-divider>自定义分组规则（最高优先级，关键词命中即归入指定组）</el-divider>
             <el-form-item label="规则列表">
               <div style="width:100%">
                 <div v-for="(rule, idx) in form.custom_group_rules" :key="idx"
                      style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
                   <el-input v-model="rule.keyword" placeholder="关键词（如 CCTV）" style="width:200px" />
                   <span>→</span>
                   <el-input v-model="rule.group" placeholder="目标分组（如 央视频道）" style="width:200px" />
                   <el-button type="danger" text circle @click="form.custom_group_rules.splice(idx, 1)">
                     <el-icon><Close /></el-icon>
                   </el-button>
                 </div>
                 <el-button type="primary" text @click="form.custom_group_rules.push({ keyword: '', group: '' })">
                   + 新增规则
                 </el-button>
                 <div class="tip">例如：关键词填 <code>CCTV</code>、目标组填 <code>央视频道</code>，则所有含 CCTV 的频道优先归入央视频道。</div>
               </div>
             </el-form-item>
             <el-divider />
             <el-form-item label="立即重新分组">
               <el-button type="warning" text @click="reclassifyNow">对全部频道重新分组</el-button>
               <div class="tip">按当前算法（含上述规则）对已有频道池重跑分组，解决历史混乱。此操作会修改分组并保存。</div>
             </el-form-item>
           </el-form>
         </el-tab-pane>

         <!-- 更新 -->
         <el-tab-pane label="更新" name="update">
           <el-form label-width="100px" size="small">
             <el-form-item label="当前版本">
               <span class="ver-tag">v{{ curVersion }}</span>
             </el-form-item>
             <el-form-item label="更新源地址">
               <el-input v-model="form.update_url" placeholder="留空使用默认更新源" style="width:340px" />
               <div class="tip">更新检查清单 JSON 地址，默认指向 GitHub raw</div>
             </el-form-item>
             <el-form-item label="检查更新">
               <el-button type="primary" @click="checkForUpdate" :loading="checking">检查更新</el-button>
               <div v-if="updateInfo.latest" class="update-result" :class="{ avail: updateInfo.has_update }">
                 <template v-if="updateInfo.has_update">
                   <span class="ur-title">发现新版本 v{{ updateInfo.latest }}</span>
                   <p v-if="updateInfo.notes" class="ur-notes">{{ updateInfo.notes }}</p>
                   <div class="ur-actions">
                     <el-button v-if="updateInfo.packages.length" type="success" size="small" @click="doDownloadUpdate" :loading="downloading">
                       下载更新包
                     </el-button>
                     <el-button
                       v-if="downloadPaths.length && !updateInfo.is_installing"
                       type="warning" size="small"
                       @click="doInstallUpdate"
                     >退出并安装更新</el-button>
                     <span v-if="updateInfo.is_installing" class="ur-installing">更新器已启动，程序即将退出并自动安装…</span>
                   </div>
                 </template>
                 <span v-else class="ur-title">已是最新版本</span>
               </div>
             </el-form-item>
           </el-form>
         </el-tab-pane>
       </el-tabs>


      <div class="settings-actions">
        <el-button @click="resetSettings">恢复默认</el-button>
        <el-button type="primary" @click="saveAll" :loading="saving">保存设置</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'
import * as configApi from '@/api/config'
import { exportApi } from '@/api/export'
import * as appApi from '@/api/app'
import { reclassifyChannels } from '@/api/channels'
import { callNative } from '@/composables/useNative'
import {
  currentTheme, isDark, PRESET_THEMES, BUILTIN_SKINS,
  setTheme, setDarkMode, importThemeFile, clearCustomTheme, loadBuiltinSkin, getBuiltinSkinName
} from '@/composables/useTheme'

const settingsStore = useSettingsStore()
const activeTab = ref('general')
const saving = ref(false)
const exporting = ref(false)
const importing = ref(false)
const backupFile = ref(null)
const backupFileInput = ref(null)
// 应用版本与更新
const curVersion = ref('1.0.0')
// #58 更新
const checking = ref(false)
const updateInfo = reactive({ has_update: false, latest: '', notes: '', packages: [], is_installing: false })
const downloading = ref(false)
const downloadPaths = ref([])  // 多包下载路径列表
// #59 加密备份 / 恢复
const encFile = ref(null)
const encFileInput = ref(null)
const importingEnc = ref(false)
const exportingEnc = ref(false)
const darkMode = ref(isDark.value)
const customColor = ref(currentTheme.value.startsWith('#') ? currentTheme.value : '#409EFF')
const builtinSkin = ref(getBuiltinSkinName())
const urlText = ref('')
const mirrorText = ref('不使用加速')
const epgText = ref('')

const form = reactive({
  // 自动任务 / 检查
  auto_check_after_import: false,
  auto_correct_after_epg: false,
  auto_delete_invalid_after_check: false,
  auto_export_after_check: false,
  auto_group: true,
  auto_load_epg: false,
  cache_default_geo: '中国',
  cache_default_group: '杂项频道',
  cache_default_stack: 'IPv4',
  cache_file_name: 'channels_cache.json',
  check_auto_interval: 0,
  check_hls: false,
  checker_batch_size: 50,
  check_retries: 1,
  check_threads: 20,
  check_timeout: 5,
  color_video_bg: '#000000',
  custom_group_rules: [],
  default_epg: '',
  default_group_name: '自动分组',
  default_playback_speed: 1.0,
  default_volume: 75,
  double_click_auto_play: true,
  download_retries: 3,
  download_timeout: 30,
  epg_auto_refresh_interval: 0,
  epg_history_limit: 50,
  external_player: 'vlc',
  external_player_path: '',
  foreign_group_name: '外国频道',
  latency_grade_a_threshold: 500,
  latency_grade_b_threshold: 2000,
  load_cache_on_startup: true,
  max_connections: 100,
  mirror: '不使用加速',
  mirror_history_limit: 50,
  player_hide_controls_delay_ms: 3000,
  player_keyboard_enabled: true,
  player_keyboard_volume_step: 5,
  player_seek_step_ms: 5000,
  player_stream_proxy: false,
  player_update_interval_ms: 500,
  player_window_topmost: false,
  prefer_external_player: false,
  probe_watchable: false,
  proxy: '',
  repair_check_timeout: 5,
  repair_hd_size_threshold: 500000,
  repair_max_retries: 1,
  repair_max_workers: 10,
  repair_sd_size_threshold: 100000,
  reset_filter_after_check: false,
  save_cache_on_exit: true,
  save_window_geometry: false,
  scan_max_workers: 40,
  scan_timeout: 5,
  scraper_retries: 2,
  scraper_threads: 10,
  scraper_timeout: 20,
  show_quality_column: false,
  smart_paste_default_group: '粘贴导入',
  startup_delay_ms: 0,
  stats_card_position: '顶部',
  stats_card_visible: true,
  subscription_auto_update_interval: 0,
  suffix_list: 'm3u,m3u8,txt',
  unknown_group_name: '未分组',
  update_url: '',
  url_history_limit: 50,
  use_proxy: false,
  user_agent: '',
})

// 暗色模式同步
watch(darkMode, (val) => {
  setDarkMode(val)
})

const allCols = [
  { key: 'name', defLabel: '频道' },
  { key: 'status', defLabel: '状态' },
  { key: 'code', defLabel: '状态码' },
  { key: 'ms', defLabel: '延迟' },
  { key: 'res', defLabel: '分辨率' },
  { key: 'quality', defLabel: '质量' },
  { key: 'stack', defLabel: '网络栈' },
  { key: 'group', defLabel: '分组' },
  { key: 'tag', defLabel: '标记' },
  { key: 'url', defLabel: '地址' },
]
const columnVisibility = ref(allCols.map(c => c.key))

onMounted(async () => {
  await settingsStore.fetchSettings()
  const s = settingsStore.settings
  for (const key of Object.keys(form)) {
    if (s[key] !== undefined) form[key] = s[key]
  }
  if (s.column_visibility) {
    columnVisibility.value = s.column_visibility.filter((v, i) => v && i < allCols.length).map((_, i) => allCols[i]?.key).filter(Boolean)
  }
  if (s.update_url !== undefined) form.update_url = s.update_url
  // 拉取应用版本号与更新信息
  try {
    const { data } = await appApi.getAppVersion()
    if (data && data.version) curVersion.value = data.version
  } catch { /* ignore */ }
  darkMode.value = isDark.value
  // 加载历史到多行文本框
  try {
    const { getHistory } = await import('@/api/export')
    const { data } = await getHistory()
    if (data.url && data.url.length) {
      urlText.value = data.url.join('\n')
    }
    if (data.mirror && data.mirror.length) {
      mirrorText.value = data.mirror.join('\n')
    }
    if (data.epg && data.epg.length) {
      epgText.value = data.epg.join('\n')
    }
  } catch { /* ignore */ }
})

async function saveAll() {
  saving.value = true
  try {
    // 1. 先保存历史数据（避免 watcher 在 settings 更新后读到旧历史）
    const mirrors = mirrorText.value.split('\n').map(s => s.trim()).filter(Boolean)
    if (mirrors.length > 0) {
      try {
        const { saveMirrorHistoryBatch } = await import('@/api/export')
        await saveMirrorHistoryBatch(mirrors)
      } catch (e) {
        console.warn('同步镜像历史失败:', e)
      }
    }
    const urls = urlText.value.split('\n').map(s => s.trim()).filter(Boolean)
    if (urls.length > 0) {
      try {
        const { saveUrlHistoryBatch } = await import('@/api/export')
        await saveUrlHistoryBatch(urls)
      } catch (e) {
        console.warn('同步URL历史失败:', e)
      }
    }
    const epgs = epgText.value.split('\n').map(s => s.trim()).filter(Boolean)
    if (epgs.length > 0) {
      try {
        const { saveEpgHistoryBatch } = await import('@/api/export')
        await saveEpgHistoryBatch(epgs)
      } catch (e) {
        console.warn('同步EPG历史失败:', e)
      }
    }
    // 2. 同步加速源/EPG 首行为默认选中值
    if (mirrors.length > 0) form.mirror = mirrors[0]
    if (epgs.length > 0) form.default_epg = epgs[0]
    // 3. 最后保存设置（触发 watcher 时历史已是最新）
    const data = {
      ...form,
      column_visibility: allCols.map(c => columnVisibility.value.includes(c.key)),
    }
    await settingsStore.saveSettings(data)
    ElMessage.success('设置已保存')
  } catch (e) {
    console.error('保存设置失败:', e)
    ElMessage.error('保存设置失败，请检查后端服务是否运行')
  }
  saving.value = false
}

async function resetSettings() {
  try {
    await configApi.resetConfig()
    ElMessage.success('已恢复默认设置')
    await settingsStore.fetchSettings()
  } catch { /* ignore */ }
}

async function exportBackup() {
  exporting.value = true
  try {
    const { data } = await exportApi.exportBackupFile()
    if (!data.path) {
      ElMessage.error('导出失败')
      exporting.value = false
      return
    }
    // 通过原生保存对话框把服务器端临时 zip 保存到用户指定位置（二进制安全）
    const dest = await callNative('save_file_from', data.path, data.filename || 'iptv_backup.zip')
    if (dest) ElMessage.success('备份已保存')
    else ElMessage.info('取消保存')
  } catch {
    ElMessage.error('导出备份失败，请检查后端服务')
  }
  exporting.value = false
}

function pickBackupFile() {
  if (backupFileInput.value) backupFileInput.value.click()
}

function onBackupFileChange(e) {
  const f = e.target && e.target.files && e.target.files[0]
  // 允许重复选择同一文件（重置 input value）
  if (e.target) e.target.value = ''
  if (!f) return
  // 一步到位：选完文件确认后立即导入
  ElMessageBox.confirm(`确定用「${f.name}」恢复数据吗？恢复会覆盖当前全部数据。`, '导入备份', {
    confirmButtonText: '确定恢复', cancelButtonText: '取消', type: 'warning',
  }).then(() => { importBackup(f) }).catch(() => {})
}

async function importBackup(file) {
  const f = file || backupFile.value
  if (!f) {
    ElMessage.warning('请先选择备份文件')
    return
  }
  importing.value = true
  try {
    const { data } = await exportApi.importBackup(f, 'overwrite')
    ElMessage.success(`恢复成功，共恢复 ${data.restored && data.restored.length ? data.restored.length : 0} 项`)
    await settingsStore.fetchSettings()
    // 刷新频道列表
    try {
      const { useChannelStore } = await import('@/stores/channels')
      useChannelStore().refresh()
    } catch { /* ignore */ }
  } catch (e) {
    ElMessage.error('恢复失败：' + (e.response?.data?.detail || e.message))
  }
  importing.value = false
  backupFile.value = null
}

// #58 应用自更新：检查更新
async function checkForUpdate() {
  checking.value = true
  updateInfo.has_update = false
  updateInfo.latest = ''
  updateInfo.notes = ''
  updateInfo.packages = []
  downloadPaths.value = []
  try {
    const { data } = await appApi.checkUpdate(form.update_url || null)
    curVersion.value = data.current || curVersion.value
    updateInfo.has_update = data.has_update
    updateInfo.latest = data.latest
    updateInfo.notes = data.notes || ''
    updateInfo.packages = data.packages || []
    if (data.has_update) ElMessage.success(`发现新版本 v${data.latest}（共 ${updateInfo.packages.length} 个包）`)
    else ElMessage.info('已是最新版本')
  } catch (e) {
    ElMessage.error('检查更新失败：' + (e.response?.data?.detail || e.message))
  }
  checking.value = false
}

// 下载更新包（多包依次下载）
async function doDownloadUpdate() {
  if (!updateInfo.packages.length) return
  downloading.value = true
  downloadPaths.value = []
  try {
    for (const pkg of updateInfo.packages) {
      const { data } = await appApi.downloadUpdate(pkg.url, pkg.name || null)
      downloadPaths.value.push(data.path)
    }
    ElMessage.success(`已下载 ${downloadPaths.value.length} 个更新包到暂存目录`)
  } catch (e) {
    ElMessage.error('下载失败：' + (e.response?.data?.detail || e.message))
  }
  downloading.value = false
}

// 退出并安装更新：启动内嵌更新器（全自动）
async function doInstallUpdate() {
  if (!downloadPaths.value.length) return
  ElMessageBox.confirm('即将退出程序并自动安装更新（只替换程序文件，你的频道/设置/台标数据将完整保留，更新完成后自动重启）。确定继续？', '安装更新', {
    confirmButtonText: '安装', cancelButtonText: '取消', type: 'warning',
  }).then(async () => {
    const { data } = await appApi.applyUpdate(downloadPaths.value)
    if (data && data.ok && data.launched) {
      updateInfo.is_installing = true
      ElMessage.success('更新器已启动，程序即将退出并自动安装…')
      setTimeout(() => { try { window.close() } catch (_) {} }, 800)
    } else {
      ElMessage.error((data && data.error) || '启动更新器失败')
    }
  }).catch(() => {})
}

// #59 加密导出备份
async function exportEncrypted() {
  let pass = ''
  try {
    const { value } = await ElMessageBox.prompt('设置加密口令（解密时需要相同口令）', '加密导出', {
      inputType: 'password', inputPlaceholder: '请输入口令',
    })
    pass = value
  } catch { return }
  if (!pass) return ElMessage.warning('口令不能为空')
  exportingEnc.value = true
  try {
    const { data } = await exportApi.exportEncryptedBackup(pass)
    if (!data.path) { ElMessage.error('加密导出失败'); exportingEnc.value = false; return }
    const dest = await callNative('save_file_from', data.path, data.filename || 'iptv_backup.enc')
    if (dest) ElMessage.success('加密备份已保存')
    else ElMessage.info('取消保存')
  } catch (e) {
    ElMessage.error('加密导出失败：' + (e.response?.data?.detail || e.message))
  }
  exportingEnc.value = false
}

function pickEncFile() {
  if (encFileInput.value) encFileInput.value.click()
}

function onEncFileChange(e) {
  const f = e.target && e.target.files && e.target.files[0]
  // 允许重复选择同一文件（重置 input value）
  if (e.target) e.target.value = ''
  if (!f) return
  encFile.value = f
  // 一步到位：选完文件后输入口令并立即恢复
  ElMessageBox.prompt('输入导出时设置的加密口令', '导入加密备份', {
    inputType: 'password', inputPlaceholder: '请输入口令',
    confirmButtonText: '解密恢复', cancelButtonText: '取消',
  }).then(({ value }) => {
    if (!value) { ElMessage.warning('口令不能为空'); return }
    importEncrypted(f, value)
  }).catch(() => {})
}

// #59 加密恢复（解密导入）
async function importEncrypted(file, pass) {
  const f = file || encFile.value
  if (!f) { ElMessage.warning('请先选择 .enc 文件'); return }
  const pass2 = pass
  if (!pass2) { ElMessage.warning('请输入解密口令'); return }
  importingEnc.value = true
  try {
    const { data } = await exportApi.importEncryptedBackup(f, pass2)
    ElMessage.success(`解密恢复成功，共恢复 ${data.restored && data.restored.length ? data.restored.length : 0} 项`)
    await settingsStore.fetchSettings()
    try {
      const { useChannelStore } = await import('@/stores/channels')
      useChannelStore().refresh()
    } catch { /* ignore */ }
  } catch (e) {
    ElMessage.error('解密恢复失败：' + (e.response?.data?.detail || e.message))
  }
  importingEnc.value = false
  encFile.value = null
}

function onCustomColor(val) {
  if (val && val.startsWith('#')) setTheme(val)
}

// #60 立即重新分组（设置页内一键对整池重跑分组）
async function reclassifyNow() {
  try {
    const { data } = await reclassifyChannels()
    if (data.changed > 0) {
      ElMessage.success(`已重新分组：${data.changed} / ${data.total} 个频道的分组被调整`)
    } else {
      ElMessage.info('分组无需调整')
    }
    try {
      const { useChannelStore } = await import('@/stores/channels')
      useChannelStore().refresh()
    } catch { /* ignore */ }
  } catch (e) {
    ElMessage.error('重新分组失败：' + (e.response?.data?.detail || e.message))
  }
}

async function onImportSkin(file) {
  try {
    await importThemeFile(file.raw)
    ElMessage.success('皮肤已导入')
  } catch {
    ElMessage.error('导入皮肤失败')
  }
}

async function onApplyBuiltinSkin(skin) {
  try {
    await loadBuiltinSkin(skin.file)
    builtinSkin.value = skin.file
    ElMessage.success(`已应用「${skin.name}」皮肤`)
  } catch {
    ElMessage.error('应用皮肤失败')
  }
}

async function browsePlayerPath() {
  const path = await callNative('select_file', '选择外部播放器', 'Executable Files (*.exe)|All Files (*.*)')
  if (path && typeof path === 'string' && !path.startsWith('ERROR')) {
    form.external_player_path = path
    // 自动识别播放器类型
    const lower = path.toLowerCase()
    if (lower.includes('potplayer') || lower.includes('potplayermini')) {
      form.external_player = 'potplayer'
    } else if (lower.includes('mpv')) {
      form.external_player = 'mpv'
    } else if (lower.includes('vlc')) {
      form.external_player = 'vlc'
    }
  }
}
</script>

<style scoped>
.settings-page { height: 100%; }
.page-title { font-size: 16px; font-weight: 600; }
.settings-tabs { min-height: 400px; }
.settings-tabs :deep(.el-tabs__header) { width: 120px; }
.unit { margin-left: 6px; font-size: 12px; color: var(--el-text-color-secondary); }
.tip { font-size: 11px; color: var(--el-text-color-placeholder); margin-top: 4px; }
.ver-tag { font-weight: 600; color: var(--el-color-primary); }
.update-result { margin-top: 8px; padding: 8px 10px; border-radius: 6px; background: var(--el-fill-color-light); max-width: 420px; }
.update-result.avail { background: var(--el-color-success-light-9); }
.ur-title { font-size: 13px; font-weight: 600; }
.ur-notes { font-size: 12px; color: var(--el-text-color-secondary); margin: 4px 0 8px; white-space: pre-wrap; }
.ur-path { display: block; margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); word-break: break-all; }

.theme-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.theme-item {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 8px; border: 2px solid transparent; border-radius: 8px; cursor: pointer;
}
.theme-item:hover { border-color: var(--el-border-color); }
.theme-item.active { border-color: var(--el-color-primary); }
.theme-color { width: 32px; height: 32px; border-radius: 6px; }

.skin-grid { display: flex; flex-direction: column; gap: 16px; }
.skin-group-title {
  font-size: 13px; font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.skin-list { display: flex; flex-wrap: wrap; gap: 6px; }
.skin-item {
  padding: 5px 14px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--el-border-color-light);
  font-size: 12px; transition: all 0.2s;
}
.skin-item:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); }
.skin-item.active {
  border-color: var(--el-color-primary); background: var(--el-color-primary-light-9);
  color: var(--el-color-primary); font-weight: 600;
}

.settings-actions {
  margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--el-border-color-lighter);
  display: flex; justify-content: flex-end; gap: 8px;
}
</style>