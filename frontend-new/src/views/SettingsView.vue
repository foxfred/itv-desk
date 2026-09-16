<template>
  <div class="settings-page">
    <el-card shadow="never">
      <template #header><span class="page-title">系统设置</span></template>
      <el-tabs v-model="activeTab" tab-position="left" class="settings-tabs">
        <!-- 常规 -->
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
          <el-divider>启动</el-divider>
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
          <el-divider>更新</el-divider>
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
                     <el-button v-if="updateInfo.packages.length && !updateInfo.is_installing" type="success" size="small" @click="doDownloadUpdate" :loading="downloading">
                       {{ downloadPaths.length ? '重新下载更新包' : '下载更新包' }}
                     </el-button>
                     <el-button
                       v-if="downloadPaths.length && !updateInfo.is_installing"
                       type="warning" size="small"
                       @click="doInstallUpdate"
                     >立即更新并重启</el-button>
                     <span v-if="updateInfo.is_installing" class="ur-installing">正在更新：程序即将关闭，覆盖完成会自动重新打开…</span>
                   </div>
                   <p class="ur-notes">更新会自动覆盖「当前程序所在目录」，无需选择安装路径；频道、设置、台标等数据不会被覆盖。</p>
                 </template>
                 <span v-else class="ur-title">已是最新版本</span>
               </div>
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
          <el-divider>抓取</el-divider>
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
          <el-divider>扫描</el-divider>
            <el-form label-width="100px" size="small">
              <el-form-item label="探测超时">
                <el-input-number v-model="form.scan_timeout" :min="1" :max="30" style="width:120px" />
                <span class="unit">秒</span>
              </el-form-item>
              <el-form-item label="并发数">
                <el-input-number v-model="form.scan_max_workers" :min="1" :max="200" style="width:120px" />
              </el-form-item>
            </el-form>
          <el-divider>局域网订阅网关</el-divider>
          <el-form label-width="110px" size="small">
            <el-form-item label="订阅网关">
              <div style="display:flex;align-items:center;gap:8px">
                <el-switch v-model="form.gateway_enabled" size="small" @change="onGatewayToggle" />
                <span style="font-size:12px;color:var(--el-text-color-secondary)">
                  开启后，盒子/手机/电视上的播放器可直接订阅本机频道库（需带令牌，不会裸奔）
                </span>
              </div>
            </el-form-item>

            <template v-if="form.gateway_enabled">
              <el-form-item label="订阅令牌">
                <div style="display:flex;align-items:center;gap:8px">
                  <el-input :model-value="gwInfo.token || form.gateway_token" readonly style="width:340px" />
                  <el-button size="small" @click="rotateGwToken">重新生成</el-button>
                </div>
              </el-form-item>
              <el-form-item label=" ">
                <span style="font-size:12px;color:var(--el-text-color-secondary)">
                  重新生成后旧链接立即失效，需要在播放器里重新填地址。
                </span>
              </el-form-item>

              <template v-if="gwInfo.playlist_url">
                <el-divider>播放器订阅地址</el-divider>
                <el-form-item label="播放列表">
                  <el-input :model-value="gwInfo.playlist_url" readonly style="width:560px">
                    <template #append><el-button @click="copyGw(gwInfo.playlist_url)">复制</el-button></template>
                  </el-input>
                </el-form-item>
                <el-form-item label="节目单">
                  <el-input :model-value="gwInfo.epg_url" readonly style="width:560px">
                    <template #append><el-button @click="copyGw(gwInfo.epg_url)">复制</el-button></template>
                  </el-input>
                </el-form-item>
                <el-form-item label="当前状态">
                  <span style="font-size:12px">
                    可订阅频道 <b>{{ gwInfo.channel_count }}</b> 个；EPG 已载入
                    <b>{{ gwInfo.epg_count }}</b> 个频道；本机局域网地址
                    <b>{{ gwInfo.lan_ip }}:{{ gwInfo.port }}</b>
                  </span>
                </el-form-item>
                <el-form-item label="用法">
                  <div style="font-size:12px;line-height:1.8;color:var(--el-text-color-secondary)">
                    1. 手机/盒子与本机连同一个路由器（同一局域网）<br />
                    2. 播放器里选「添加 M3U / 远程订阅」，粘贴上面的播放列表地址<br />
                    3. 节目单一般会自动跟上；没有的话再单独填「节目单」地址<br />
                    4. Windows 首次使用会弹防火墙提示，选「允许访问」<br />
                    5. 地址里的 token 就是你的钥匙，发给别人等于把频道库分享出去
                  </div>
                </el-form-item>
              </template>
              <el-alert v-else type="info" :closable="false" style="width:560px"
                title="还没有订阅令牌"
                description="点上面的「重新生成」拿到令牌，就能得到给盒子/手机用的订阅地址。" />
            </template>

            <el-alert v-else type="info" :closable="false" style="width:560px"
              title="订阅网关当前已关闭"
              description="打开上方开关并点「保存设置」即可启用。启用后必须有令牌才能访问，检测到的死源不会推送给播放器。" />
          </el-form>
        </el-tab-pane>

        <!-- 检测 -->
        <el-tab-pane label="检测" name="check">
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
          <el-divider>修补与阈值</el-divider>
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
        </el-tab-pane>

        <!-- 频道与节目单 -->
        <el-tab-pane label="频道与节目单" name="channel">
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
              <el-form-item label="URL 黑名单">
                <el-input v-model="urlBlacklistText" type="textarea" :rows="3" style="width:420px"
                  placeholder="每行一条，支持子串或 /正则/。命中则永久排除：导入、检测、导出均过滤" />
              </el-form-item>
              <el-form-item label="URL 白名单">
                <el-input v-model="urlWhitelistText" type="textarea" :rows="3" style="width:420px"
                  placeholder="每行一条，支持子串或 /正则/。命中则豁免检测，直接保留为在线" />
              </el-form-item>
              <el-form-item label="EPG 加载后自动校正">
                <el-switch v-model="form.auto_correct_after_epg" />
                <span class="tip">EPG 加载完成后自动校正频道名</span>
              </el-form-item>
              <el-divider>频道别名库（让「央视五套」能对上「CCTV5」）</el-divider>
              <el-form-item label="别名条目">
                <el-input v-model="aliasText" type="textarea" :rows="8" style="width:520px"
                  placeholder="每行一条：规范名=别名1,别名2&#10;例：CCTV5=央视体育,央视五套,中央5台" />
              </el-form-item>
              <el-form-item label=" ">
                <div style="display:flex;align-items:center;gap:8px">
                  <el-button size="small" type="primary" @click="saveAliases(false)">保存（合并）</el-button>
                  <el-button size="small" @click="saveAliases(true)">整体覆盖</el-button>
                  <el-button size="small" @click="loadAliases">重新载入</el-button>
                  <el-button size="small" @click="resetAliasSeed">恢复内置</el-button>
                  <span class="tip">{{ aliasStat }}</span>
                </div>
              </el-form-item>
            </el-form>
          <el-divider>自动分组</el-divider>
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
          <el-divider>频道名校正（看画面认台标）</el-divider>
          <el-form label-width="120px" size="small">
            <el-form-item label="改名策略">
              <el-radio-group v-model="form.namefix_strategy">
                <el-radio label="advise">只出建议，人工确认</el-radio>
                <el-radio label="auto_high">高置信度自动改名</el-radio>
                <el-radio label="auto_all">全部自动改名</el-radio>
              </el-radio-group>
              <div class="tip">
                抓一帧真实画面读出画面上的台标/字幕文字，与现有名称比对后改名。<br>
                <b>只出建议</b>：最稳，识别结果全部列在频道页「名称校正」里由你勾选；<br>
                <b>高置信度自动改名</b>：置信度达到下面门槛的自动改（仍可整批撤销）；<br>
                <b>全部自动改名</b>：激进，所有识别出结果的都改，误判风险最高。
              </div>
            </el-form-item>
            <el-form-item label="抓帧分辨率">
              <el-select v-model="form.namefix_capture_width" style="width:150px">
                <el-option :value="640" label="640（快，台标易认错）" />
                <el-option :value="960" label="960（推荐）" />
                <el-option :value="1280" label="1280（准，较慢）" />
              </el-select>
              <div class="tip">实测 320 会把台标认成「民新昆台」这类乱码，960 起才能稳定读出「中天新闻」「江苏综艺」。</div>
            </el-form-item>
            <el-form-item label="跳过首帧">
              <el-input-number v-model="form.namefix_capture_offset" :min="0" :max="30" />
              <span class="tip" style="margin-left:6px">秒（默认 3）</span>
              <div class="tip">不少免费源首帧是「扫码下载 APP」公告页或黑屏，跳过几秒才拿到真实节目画面。</div>
            </el-form-item>
            <el-form-item label="自动改名门槛">
              <el-input-number v-model="form.namefix_min_confidence" :min="0.5" :max="0.99"
                               :step="0.01" :precision="2" />
              <div class="tip">仅「高置信度自动改名」策略生效，默认 0.90。台标直读通常 0.95+，字幕条推断会封顶在 0.90 以下。</div>
            </el-form-item>
            <el-form-item label="模糊匹配阈值">
              <el-input-number v-model="form.namefix_fuzzy_threshold" :min="0.6" :max="1"
                               :step="0.01" :precision="2" />
              <div class="tip">名称相似度低于此值只做提示、不参与判定。默认 0.86。</div>
            </el-form-item>
            <el-form-item label="并发线程">
              <el-input-number v-model="form.namefix_workers" :min="1" :max="12" />
              <div class="tip">抓帧+识别同时跑几个频道，默认 4。机器好可调高。</div>
            </el-form-item>
            <el-form-item label="复用已有画面">
              <el-switch v-model="form.namefix_reuse_screenshot" />
              <div class="tip">开启后优先用「画面」列已抓好的截图，省一次抓帧；但若那张图分辨率不够会自动重抓。</div>
            </el-form-item>

            <el-divider>视觉模型兜底（可选）</el-divider>
            <el-form-item label="启用兜底">
              <el-switch v-model="form.namefix_vision_enabled" />
              <div class="tip">
                画面里一个字都没有时（纯图形台标），本地文字识别无能为力，交给视觉模型认台标。<br>
                关闭则这类频道只标记「未能判定」，不影响其他频道。
              </div>
            </el-form-item>
            <el-form-item label="接口地址">
              <el-input v-model="form.namefix_vision_base" style="width:430px"
                        placeholder="https://open.bigmodel.cn/api/paas/v4/chat/completions" />
              <div class="tip">OpenAI 兼容格式即可（/chat/completions）。</div>
            </el-form-item>
            <el-form-item label="模型名">
              <el-input v-model="form.namefix_vision_model" style="width:250px" placeholder="glm-4v-flash" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="form.namefix_vision_key" style="width:430px" show-password
                        placeholder="留空则不启用兜底" />
            </el-form-item>
            <el-form-item label="连通性测试">
              <el-button type="primary" text :loading="visionTesting" @click="testVision">测试识别</el-button>
              <span v-if="visionTestMsg" class="tip" style="margin-left:8px">{{ visionTestMsg }}</span>
              <div class="tip">用已抓到的画面帧试调一次视觉接口，确认地址/模型/Key 配对了。</div>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 界面 -->
        <el-tab-pane label="界面" name="ui">
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
          <el-divider>列设置</el-divider>
          <el-form label-width="100px" size="small">
            <el-form-item label="显示列">
              <el-checkbox-group v-model="columnVisibility">
                <div v-for="col in allCols" :key="col.key" style="display:inline-block;width:33%;margin-bottom:4px">
                  <el-checkbox :label="col.key" :value="col.key">{{ col.defLabel }}</el-checkbox>
                </div>
              </el-checkbox-group>
            </el-form-item>
          </el-form>
          <el-divider>统计卡片</el-divider>
            <el-form-item label="统计卡片位置">
              <el-radio-group v-model="form.stats_card_position">
                <el-radio label="顶部">顶部</el-radio>
                <el-radio label="底部">底部</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="显示统计卡片">
              <el-switch v-model="form.stats_card_visible" />
            </el-form-item>
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

        <!-- 数据与自动化 -->
        <el-tab-pane label="数据与自动化" name="data">
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
          <el-divider>自动任务</el-divider>
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
          <el-divider>备份</el-divider>
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
        <el-tab-pane label="录制" name="record">
          <el-form label-width="150px" size="small" class="settings-form">
            <el-form-item label="录像容器格式">
              <el-select v-model="form.record_container" style="width:200px">
                <el-option label="MP4（通用，推荐）" value="mp4" />
                <el-option label="TS（原始流）" value="ts" />
              </el-select>
            </el-form-item>
            <el-form-item label="单次录像时长上限">
              <el-input-number v-model="form.record_max_minutes" :min="0" :max="1440" :step="10" />
              <span style="margin-left:8px;color:var(--el-text-color-secondary);font-size:12px">分钟（0 = 不限）</span>
            </el-form-item>
            <el-form-item label="时移缓冲上限">
              <el-input-number v-model="form.timeshift_minutes" :min="0" :max="720" :step="10" />
              <span style="margin-left:8px;color:var(--el-text-color-secondary);font-size:12px">分钟（0 = 不限）</span>
            </el-form-item>
            <el-form-item label="时移切片长度">
              <el-input-number v-model="form.timeshift_segment_seconds" :min="2" :max="20" />
              <span style="margin-left:8px;color:var(--el-text-color-secondary);font-size:12px">秒</span>
            </el-form-item>
            <el-form-item label="回看（Catch-up）">
              <el-switch v-model="form.catchup_enabled" />
              <span style="margin-left:8px;color:var(--el-text-color-secondary);font-size:12px">关闭后节目单不再提供回看入口</span>
            </el-form-item>
            <el-form-item label=" ">
              <span style="color:var(--el-text-color-secondary);font-size:12px">录像文件保存在数据目录的 recordings 子目录，可在「录像管理」页回放与删除。</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="家长控制" name="parental">
          <el-form label-width="150px" size="small" class="settings-form">
            <el-form-item label="启用家长控制">
              <el-switch v-model="form.parental_enabled" />
            </el-form-item>
            <el-form-item label="PIN 码">
              <el-input v-model="form.parental_pin" maxlength="8" show-password
                        placeholder="4-8 位密码" style="width:200px" />
            </el-form-item>
            <el-form-item label="锁定的分组">
              <el-select v-model="form.parental_locked_groups" multiple filterable allow-create
                         default-first-option placeholder="选择要锁定的分组"
                         style="width:100%;max-width:560px">
                <el-option v-for="g in groupNames" :key="g" :label="g" :value="g" />
              </el-select>
            </el-form-item>
            <el-form-item label=" ">
              <span style="color:var(--el-text-color-secondary);font-size:12px">频道墙中锁定分组的画面会隐藏；点击播放时需输入 PIN 解锁。</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="AI 智能" name="ai">
          <el-form label-width="150px" size="small" class="settings-form">
            <el-form-item label="启用 AI 功能">
              <el-switch v-model="form.ai_enabled" />
              <span class="tip">关闭后「AI 智能分组」等入口不可用</span>
            </el-form-item>
            <el-divider>模型接口（OpenAI 兼容）</el-divider>
            <el-form-item label="API 地址">
              <el-input v-model="form.ai_base_url" placeholder="https://api.deepseek.com/v1"
                        style="max-width:460px" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="form.ai_api_key" show-password placeholder="sk-..."
                        style="max-width:460px" />
            </el-form-item>
            <el-form-item label="模型">
              <el-select v-model="form.ai_model" filterable allow-create default-first-option
                         placeholder="点「获取模型列表」，或直接输入模型名" style="width:280px">
                <el-option v-for="m in aiModels" :key="m" :label="m" :value="m" />
              </el-select>
              <el-button style="margin-left:8px" :loading="aiFetching" @click="fetchAiModels">获取模型列表</el-button>
              <el-button :loading="aiTesting" @click="testAiConn">测试连接</el-button>
            </el-form-item>
            <div v-if="aiStat" class="tip" style="margin-left:150px;margin-bottom:8px">{{ aiStat }}</div>
            <el-divider>参数</el-divider>
            <el-form-item label="请求超时">
              <el-input-number v-model="form.ai_timeout" :min="10" :max="300" :step="10" />
              <span class="unit">秒</span>
            </el-form-item>
            <el-form-item label="温度">
              <el-input-number v-model="form.ai_temperature" :min="0" :max="2" :step="0.1" :precision="1" />
              <span class="tip">越低越稳定，分类任务建议 0.1 ~ 0.3</span>
            </el-form-item>
            <el-form-item label="最大输出 token">
              <el-input-number v-model="form.ai_max_tokens" :min="256" :max="32768" :step="256" />
            </el-form-item>
            <el-form-item label="走系统代理">
              <el-switch v-model="form.ai_use_proxy" />
              <el-input v-model="form.proxy" placeholder="http://127.0.0.1:7890"
                        style="width:240px;margin-left:10px" />
              <span class="tip">默认直连，不走系统代理环境变量</span>
            </el-form-item>
            <el-form-item label="附加提示词">
              <el-input v-model="form.ai_prompt_extra" type="textarea" :rows="3" style="max-width:460px"
                        placeholder="例如：体育类频道统一归到「体育」，港澳台频道归到「港澳台」" />
            </el-form-item>
            <el-form-item label=" ">
              <span class="tip">保存后即时生效。换 Key 后建议先点「测试连接」确认可用，再到频道列表用「AI 智能分组」。</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="HDHomeRun" name="hdhr">
          <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
                    title="开启后本机就是一个 HDHomeRun 调谐器，Plex / Emby / Kodi 可直接添加该地址看直播" />
          <el-form label-width="150px" size="small" class="settings-form">
            <el-form-item label="启用 HDHomeRun">
              <el-switch v-model="form.hdhr_enabled" />
            </el-form-item>
            <el-divider>对外地址</el-divider>
            <el-form-item label="设备地址">
              <el-tag type="success" style="margin-right:8px">{{ hdhrStatus.base_url || '获取中…' }}</el-tag>
              <el-button size="small" @click="refreshHdhrStatus">刷新</el-button>
              <el-button size="small" @click="copyHdhrUrl">复制 lineup 地址</el-button>
            </el-form-item>
            <el-form-item label="手动指定地址">
              <el-input v-model="form.hdhr_base_url" placeholder="留空=自动探测局域网 IP" style="max-width:420px" />
              <div class="tip">多网卡/端口映射场景下，自动探测可能不准，可在此固定（如 http://192.168.1.10:8000）</div>
            </el-form-item>
            <el-form-item label="DeviceID">
              <el-input v-model="form.hdhr_device_id" maxlength="8" placeholder="留空=自动生成"
                        style="width:180px" />
              <span class="tip">8 位十六进制；当前生效：{{ hdhrStatus.device_id }}</span>
            </el-form-item>
            <el-divider>暴露范围</el-divider>
            <el-form-item label="调谐器数量">
              <el-input-number v-model="form.hdhr_tuner_count" :min="1" :max="16" />
              <span class="tip">同时最多几路播放，超出返回 503</span>
            </el-form-item>
            <el-form-item label="最大频道数">
              <el-input-number v-model="form.hdhr_limit" :min="1" :max="2000" :step="50" />
            </el-form-item>
            <el-form-item label="只暴露在线频道">
              <el-switch v-model="form.hdhr_only_online" />
            </el-form-item>
            <el-form-item label="排除成人频道">
              <el-switch v-model="form.hdhr_exclude_adult" />
            </el-form-item>
            <el-form-item label="限定分组">
              <el-select v-model="form.hdhr_groups" multiple filterable allow-create default-first-option
                         placeholder="留空=全部分组" style="width:100%;max-width:560px">
                <el-option v-for="g in groupNames" :key="g" :label="g" :value="g" />
              </el-select>
            </el-form-item>
            <el-form-item label="强制转码 H.264">
              <el-switch v-model="form.hdhr_transcode" />
              <span class="tip">关闭=直接转封装（省 CPU）；H.265 源播不出画面时再打开</span>
            </el-form-item>
            <el-form-item label="SSDP 自动发现">
              <el-switch v-model="form.hdhr_ssdp" />
              <span class="tip">开启后局域网客户端可自动搜到；占用 UDP 1900，被别家占用会失败（可手动填地址）</span>
            </el-form-item>
            <el-form-item label=" ">
              <span class="tip">
                当前暴露 {{ hdhrStatus.channels }} 个频道，占用 {{ (hdhrStatus.active || []).length }}/{{ hdhrStatus.tuner_count }} 路。
                lineup：{{ hdhrStatus.lineup_url }}
              </span>
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
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'
import * as configApi from '@/api/config'
import { exportApi } from '@/api/export'
import * as appApi from '@/api/app'
import { reclassifyChannels, getChannels } from '@/api/channels'
import * as gwApi from '@/api/gateway'
import * as aliasApi from '@/api/aliases'
import * as nfApi from '@/api/namefix'
import * as aiApi from '@/api/ai'
import * as hdhrApi from '@/api/hdhomerun'
import { callNative } from '@/composables/useNative'
import {
  currentTheme, isDark, PRESET_THEMES, BUILTIN_SKINS,
  setTheme, setDarkMode, importThemeFile, clearCustomTheme, loadBuiltinSkin, getBuiltinSkinName
} from '@/composables/useTheme'

const settingsStore = useSettingsStore()
const activeTab = ref('general')
const groupNames = ref([])
const saving = ref(false)
const exporting = ref(false)
const importing = ref(false)
const backupFile = ref(null)
const backupFileInput = ref(null)
const curVersion = ref('1.0.0')
const checking = ref(false)
const updateInfo = reactive({ has_update: false, latest: '', notes: '', packages: [], is_installing: false })
const downloading = ref(false)
const downloadPaths = ref([])  
const downloadPkgs = ref([])   
const encFile = ref(null)
const encFileInput = ref(null)
const importingEnc = ref(false)
const exportingEnc = ref(false)
const darkMode = ref(isDark.value)
const aiModels = ref([])
const aiFetching = ref(false)
const aiTesting = ref(false)
const aiStat = ref('')

async function fetchAiModels() {
  aiFetching.value = true
  aiStat.value = ''
  try {
    const { data } = await aiApi.listModels(form.ai_base_url, form.ai_api_key)
    if (!data.ok) {
      aiStat.value = '获取失败：' + (data.error || '未知错误')
      ElMessage.error('获取模型列表失败')
      return
    }
    aiModels.value = data.models || []
    if (!form.ai_model && aiModels.value.length) form.ai_model = aiModels.value[0]
    aiStat.value = `已获取 ${data.count || aiModels.value.length} 个模型：${aiModels.value.slice(0, 8).join('、')}${aiModels.value.length > 8 ? ' …' : ''}`
    ElMessage.success(`获取到 ${data.count || aiModels.value.length} 个模型`)
  } catch (e) {
    aiStat.value = '获取失败：无法连接后端服务'
    ElMessage.error('获取模型列表失败')
  }
  aiFetching.value = false
}

async function testAiConn() {
  aiTesting.value = true
  aiStat.value = ''
  try {
    const { data } = await aiApi.testAi(form.ai_base_url, form.ai_api_key, form.ai_model)
    if (!data.ok) {
      aiStat.value = '连接失败：' + (data.error || '未知错误')
      ElMessage.error('连接失败')
    } else {
      const u = data.usage || {}
      aiStat.value = `连接成功（模型 ${data.model || form.ai_model}，返回「${data.reply || ''}」${u.total_tokens ? '，消耗 ' + u.total_tokens + ' tokens' : ''}）`
      ElMessage.success('连接成功')
    }
  } catch (e) {
    aiStat.value = '连接失败：无法连接后端服务'
    ElMessage.error('连接失败')
  }
  aiTesting.value = false
}

// ---- HDHomeRun 仿真 ----
const hdhrStatus = reactive({ base_url: '', device_id: '', tuner_count: 0, channels: 0, active: [], lineup_url: '' })

async function refreshHdhrStatus() {
  try {
    const { data } = await hdhrApi.getHdhrStatus()
    Object.assign(hdhrStatus, data || {})
  } catch (e) {
    hdhrStatus.base_url = '读取失败'
  }
}

async function copyHdhrUrl() {
  const url = hdhrStatus.lineup_url || (hdhrStatus.base_url ? hdhrStatus.base_url + '/lineup.json' : '')
  if (!url) return ElMessage.warning('地址尚未就绪')
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('已复制：' + url)
  } catch (e) {
    ElMessage.info('请手动复制：' + url)
  }
}

const urlBlacklistText = computed({
  get: () => (Array.isArray(form.url_blacklist) ? form.url_blacklist : []).join('\n'),
  set: (v) => { form.url_blacklist = String(v || '').split('\n').map(s => s.trim()).filter(Boolean) }
})
const urlWhitelistText = computed({
  get: () => (Array.isArray(form.url_whitelist) ? form.url_whitelist : []).join('\n'),
  set: (v) => { form.url_whitelist = String(v || '').split('\n').map(s => s.trim()).filter(Boolean) }
})
const customColor = ref(currentTheme.value.startsWith('#') ? currentTheme.value : '#409EFF')
const builtinSkin = ref(getBuiltinSkinName())
const urlText = ref('')
const mirrorText = ref('不使用加速')
const epgText = ref('')

const form = reactive({
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
    url_blacklist: [],
  url_whitelist: [],
    gateway_enabled: false,
  gateway_token: '',
    namefix_strategy: 'advise',
  namefix_capture_width: 960,
  namefix_capture_offset: 3,
  namefix_min_confidence: 0.9,
  namefix_fuzzy_threshold: 0.86,
  namefix_workers: 4,
  namefix_reuse_screenshot: true,
  namefix_vision_enabled: false,
  namefix_vision_base: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
  namefix_vision_model: 'glm-4v-flash',
  namefix_vision_key: '',
  record_container: 'mp4',
  record_max_minutes: 0,
  timeshift_minutes: 0,
  timeshift_segment_seconds: 4,
  catchup_enabled: true,
  parental_enabled: false,
  parental_pin: '',
  parental_locked_groups: [],
  ai_enabled: false,
  ai_base_url: 'https://api.deepseek.com/v1',
  ai_api_key: '',
  ai_model: 'deepseek-chat',
  ai_timeout: 60,
  ai_temperature: 0.2,
  ai_max_tokens: 2048,
  ai_use_proxy: false,
  ai_prompt_extra: '',
  hdhr_enabled: false,
  hdhr_device_id: '',
  hdhr_tuner_count: 3,
  hdhr_only_online: true,
  hdhr_groups: [],
  hdhr_limit: 300,
  hdhr_transcode: false,
  hdhr_ssdp: false,
  hdhr_exclude_adult: true,
  hdhr_base_url: '',
  hdhr_port: 0,
})

const aliasText = ref('')
const aliasStat = ref('')

async function loadAliases() {
  try {
    const { data } = await aliasApi.listAliases()
    const lines = []
    for (const [canon, aliases] of Object.entries(data.map || {})) {
      lines.push(aliases && aliases.length ? `${canon}=${aliases.join(',')}` : `${canon}=`)
    }
    aliasText.value = lines.join('\n')
    aliasStat.value = `共 ${data.groups || 0} 组 / ${data.aliases || 0} 个别名`
  } catch {
    aliasStat.value = '别名库读取失败'
  }
}

async function saveAliases(replace) {
  try {
    const { data } = await aliasApi.importAliases(aliasText.value, replace)
    if (!data.ok) return ElMessage.warning(data.error || '保存失败')
    aliasStat.value = `共 ${data.groups} 组 / ${data.aliases} 个别名`
    if (data.errors && data.errors.length) {
      ElMessage.warning(`已保存，但有 ${data.errors.length} 行没解析成功：${data.errors[0]}`)
    } else {
      ElMessage.success(replace ? '已整体覆盖别名库' : '别名已合并保存')
    }
    await loadAliases()
  } catch {
    ElMessage.error('保存别名失败')
  }
}

async function resetAliasSeed() {
  try {
    await ElMessageBox.confirm('恢复内置别名会覆盖当前自定义内容，确定？', '恢复内置别名', { type: 'warning' })
  } catch { return }
  try {
    await aliasApi.resetAliases()
    await loadAliases()
    ElMessage.success('已恢复内置别名')
  } catch {
    ElMessage.error('恢复失败')
  }
}

const gwInfo = ref({ enabled: false, token: '', playlist_url: '', epg_url: '', channel_count: 0, epg_count: 0, lan_ip: '', port: 0 })

async function loadGwInfo() {
  try {
    const { data } = await gwApi.getGatewayInfo()
    gwInfo.value = data
        if (typeof data.enabled === 'boolean') form.gateway_enabled = data.enabled
    if (data.token) form.gateway_token = data.token
  } catch { /* ignore */ }
}

async function ensureGwToken() {
  try {
    const { data } = await gwApi.rotateGatewayToken()
    gwInfo.value = { ...gwInfo.value, ...data }
    form.gateway_token = data.token
    form.gateway_enabled = true
    ElMessage.success('已生成订阅令牌，记得点「保存设置」')
  } catch {
    ElMessage.error('生成令牌失败，请检查后端服务是否运行')
  }
}

function onGatewayToggle(v) {
    if (v && !form.gateway_token) ensureGwToken()
}

async function rotateGwToken() {
  try {
    await ElMessageBox.confirm('重新生成令牌会让所有已配置的播放器立刻失效，需要重新填地址。继续？', '重新生成令牌', { type: 'warning' })
  } catch { return }
  await ensureGwToken()
}

async function copyGw(url) {
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选中地址复制')
  }
}

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
  refreshHdhrStatus()
  try {
    const { data } = await getChannels()
    groupNames.value = [...new Set((data || []).map(c => c.group || '未分组'))].sort()
  } catch { /* ignore */ }
  const s = settingsStore.settings
  for (const key of Object.keys(form)) {
    if (s[key] !== undefined) form[key] = s[key]
  }
  if (s.column_visibility) {
    columnVisibility.value = s.column_visibility.filter((v, i) => v && i < allCols.length).map((_, i) => allCols[i]?.key).filter(Boolean)
  }
  if (s.update_url !== undefined) form.update_url = s.update_url
    loadGwInfo()
  loadAliases()
    try {
    const { data } = await appApi.getAppVersion()
    if (data && data.version) curVersion.value = data.version
  } catch { /* ignore */ }
  darkMode.value = isDark.value
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
        if (mirrors.length > 0) form.mirror = mirrors[0]
    if (epgs.length > 0) form.default_epg = epgs[0]
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
    if (e.target) e.target.value = ''
  if (!f) return
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

async function checkForUpdate() {
  checking.value = true
  updateInfo.has_update = false
  updateInfo.latest = ''
  updateInfo.notes = ''
  updateInfo.packages = []
  downloadPaths.value = []
  downloadPkgs.value = []
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

function isFolderPkg(pkg) {
  if (!pkg) return false
  if (String(pkg.role || '').toLowerCase() === 'folder') return true
  return /-folder\.zip$/i.test(String(pkg.name || pkg.url || ''))
}

async function doDownloadUpdate() {
  if (!updateInfo.packages.length) return
  downloading.value = true
  downloadPaths.value = []
  downloadPkgs.value = []
  try {
    const folder = updateInfo.packages.filter(isFolderPkg)
    const list = folder.length ? folder : updateInfo.packages
    for (const pkg of list) {
      const { data } = await appApi.downloadUpdate(pkg.url, pkg.name || null, pkg.sha256 || null, pkg.size || null)
      downloadPaths.value.push(data.path)
      downloadPkgs.value.push(pkg)
    }
    const mb = Math.round((downloadPkgs.value.reduce((s, p) => s + (Number(p.size) || 0), 0) / 1048576) * 10) / 10
    ElMessage.success(`已下载并校验更新包${mb ? `（${mb}MB）` : ''}，可以点「立即更新并重启」`)
  } catch (e) {
    downloadPaths.value = []
    downloadPkgs.value = []
    ElMessage.error('下载失败：' + (e.response?.data?.detail || e.message))
  }
  downloading.value = false
}

async function doInstallUpdate() {
  if (!downloadPaths.value.length) return
  const ver = updateInfo.latest || ''
  const pkg = downloadPkgs.value[0] || {}
  const target = pkg.path || downloadPaths.value[0]
    if (isFolderPkg(pkg) || /\.zip$/i.test(String(downloadPaths.value[0]))) {
    try {
      await ElMessageBox.confirm(
        `即将更新到 v${ver}：\n\n程序会自动关闭，用新版本覆盖「当前程序所在目录」里的程序文件，完成后自动重新打开。\n\n· 不需要选择安装路径，不会再出现“装到别处、版本号没变”\n· 频道、设置、台标、缓存等数据不在更新包内，不会被覆盖删除\n· 更新过程约需十几秒到一分钟，期间请不要手动双击程序\n\n确定现在更新吗？`,
        `更新到 v${ver}`, { confirmButtonText: '立即更新', cancelButtonText: '取消', type: 'warning' })
    } catch { return }
    const native = window.pywebview && window.pywebview.api && window.pywebview.api.apply_folder_update
    if (!native) {
      ElMessage.error('当前环境不支持自动覆盖更新，请手动下载更新包解压覆盖程序目录')
      return
    }
    updateInfo.is_installing = true
    let res = ''
    try {
      res = await native(target, pkg.sha256 || null, pkg.size || null, ver)
    } catch (e) {
      updateInfo.is_installing = false
      ElMessage.error('更新失败：' + (e && e.message))
      return
    }
    if (res === 'OK') {
      ElMessage.success('更新已开始，程序即将关闭，稍后会自动重新打开新版本…')
    } else {
      updateInfo.is_installing = false
      ElMessage.error(String(res || '启动更新失败').replace(/^ERROR:\s*/, ''))
    }
    return
  }

    try {
    await ElMessageBox.confirm('即将退出程序并启动安装包。注意：安装向导里请把安装目录改成当前程序所在目录，否则会装到别处、版本号不变。确定继续？', '安装更新', {
      confirmButtonText: '安装', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  const exeTarget = downloadPaths.value.find((p) => /setup/i.test(p)) || downloadPaths.value[0]
  const nativeInstall = window.pywebview && window.pywebview.api && window.pywebview.api.install_update
  if (nativeInstall) {
    try {
      const res = await nativeInstall(exeTarget)
      if (res === 'OK') {
        updateInfo.is_installing = true
        ElMessage.success('安装器已启动，程序即将退出，请在安装向导中完成更新…')
      } else {
        ElMessage.error(String(res || '启动安装器失败'))
      }
    } catch (e) {
      ElMessage.error('启动安装器失败：' + (e && e.message))
    }
    return
  }
    try {
    const { data } = await appApi.applyUpdate(downloadPaths.value)
    if (data && data.ok && data.launched) {
      updateInfo.is_installing = true
      ElMessage.success('安装器已启动，程序即将退出，请在安装向导中完成更新…')
      setTimeout(() => { try { window.close() } catch (_) {} }, 800)
    } else {
      ElMessage.error((data && data.error) || '启动安装器失败')
    }
  } catch (e) {
    ElMessage.error('启动安装器失败：' + (e.response?.data?.detail || e.message))
  }
}

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
    if (e.target) e.target.value = ''
  if (!f) return
  encFile.value = f
    ElMessageBox.prompt('输入导出时设置的加密口令', '导入加密备份', {
    inputType: 'password', inputPlaceholder: '请输入口令',
    confirmButtonText: '解密恢复', cancelButtonText: '取消',
  }).then(({ value }) => {
    if (!value) { ElMessage.warning('口令不能为空'); return }
    importEncrypted(f, value)
  }).catch(() => {})
}

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

const visionTesting = ref(false)
const visionTestMsg = ref('')
async function testVision() {
  visionTesting.value = true
  visionTestMsg.value = ''
  try {
    const { data } = await nfApi.nfVisionTest()
    if (data.ok) {
      visionTestMsg.value = `接口正常，示例帧识别结果：${data.answer}`
      ElMessage.success('视觉接口可用')
    } else {
      visionTestMsg.value = data.error || '测试失败'
      ElMessage.warning(visionTestMsg.value)
    }
  } catch {
    visionTestMsg.value = '请求失败（后端可能已停止）'
    ElMessage.error(visionTestMsg.value)
  } finally {
    visionTesting.value = false
  }
}

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