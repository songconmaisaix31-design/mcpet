# A 双角色渲染交接（2026-10-12）

分支：`songconmaisaix31-design/mcpet-pet-20261011`。
起始工作树干净；fetch 后按授权 FF root 至计划 `067ceca814ca8e52e14ad39dd8dc472a32ee2b0a`，完整读取 PIXSO-QUOTA-DUAL-PET-PLAN 与旧交接。
只写计划 A 域；未修改主计划、main/dialogs/config/runtime、旧测试或 bench_render 脚本，未合其他轨、未集成。

代码提交：

- `a74cc21e911b43d54514b14ef04d0c79bb2eb2d5`：指定素材、双角色契约、切换与持久化、实际 Qt 回归。
- **`29a2ff1729959c970644e936f4edeb95f6e60659`**：根据原生连续动作探针 RED 改为按帧缩放、限制驻留内存，增加动作巡回回归。
- 本文为后续单独文档提交；最终推送 tip 由完成通知提供，可用 `git rev-parse HEAD` / `git ls-remote origin refs/heads/songconmaisaix31-design/mcpet-pet-20261011` 核对。请普通 merge 最终 tip，包含以上两个代码提交和本文；A 不合回 root。

## 完成与共享接口

```python
from src.pet.characters import CHARACTER_IDS, character_name, load_character
CHARACTER_IDS == ("maimai", "deepseek")
character_name("maimai")     # 麦麦
character_name("deepseek")   # DeepSeek 娘
sheet = load_character("deepseek")  # SpriteSheet 子类，frame/frames/row_for/frame_count 兼容
sheet.frame("idle", 0)             # 用于 C 面板预览和托盘图标
pet.character_id                  # 可读
pet.set_character("deepseek")     # GUI 线程；失败 SpriteLoadError，旧角色/帧/偏好不变
```

- maimai 继续用原 longniang 图集，不改原素材。DeepSeek 九个专用动作，包括睡眠与吃饭；右跑镜像左跑。未知动作回 idle；progress→working、remind→greet、coupon/balance/waiting→thinking、failed→error。
- 角色选择在本机 `MCPET_DATA_DIR/pet-preferences.json` 与 position/screen/available_geometry/roaming/resting 一并保存。旧偏好无 character_id 时兼容 maimai；现 main 传 maimai sheet 启动也能恢复 DeepSeek。恢复角色失败保留传入素材，可读 `_preferences.error`，未跨域加 UI 提示。
- 切换不调用状态机 set，不改基态/TTL/交互层、位置、休息、闲逛、上下文与触摸气泡；当前行相位按新旧帧数比例转换。同角色重复切换不重入、不续期；旧 set_spritesheet 同样只刷新呈现。
- 原拖拽阈值、1px 反向滞回、拖拽优先于前台事件、显式休息/唤醒、松手不点击、后台不覆盖触摸、过期回最新 Agent 基态、循环与时间差播放继续有效。chat_requested 仍只打开会话小窝，未创建聊天框或模型链路。
- 缩放/裁框固定，正常播放不扫描 alpha。DeepSeek 仅保留一个解码源图集；窗口最多两组动作索引、每组最多两张近期缩放帧，切角色清缓存。窗口内部 DeepSeek 帧集合是按索引访问的 Sequence；公开 sheet.frames(state) 仍返回标准列表。C 应用 load_character/单帧预览接口，不依赖私有窗口帧类型或 preview image 的图集布局。

## 素材、真实格式与限制

固定来源：[PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet/tree/92662190cdd4dee05e38a5151584cc6254cd7a43)，SHA `92662190cdd4dee05e38a5151584cc6254cd7a43`；上游 **MIT / Copyright (c) 2026 PC2005-cloud** 原文保留在 `assets/dsh-deepseek/LICENSE`，CREDITS 已更新。
只下载九个 `dsh-pet/assets/webm/` 透明动画，未安装、运行或复制宿主/聊天/模型。原始 640×360、VP9 alpha、24fps；完整原帧 alpha>32 没有空白帧，联合边界 `[120,6,469,336]`。

- 全动作统一裁框 `[111,0,366,360]`，等比 192×189 后固定透明补到 192×192；保留真实转身、姿势、气泡、吃饭和跳跃（原 happy 底部变化36px，转换后仍有跳跃）。中心范围包含手发和特效，不据此逐帧居中。
- 统一采样12.5fps，每帧80ms；八段126帧/10.08秒，error61帧/4.88秒；相对原24fps做离线时间采样，不盲目提高播放 fps。
- 9 个无损 WebP 缓存共21,392,334字节（20.4MiB）。PNG→WebP 已逐像素核对所有 alpha 和非透明 RGB 一致，冗余 PNG 移除。每动画源文件名/哈希/原帧数/首尾边界保存在 manifest.json；固定工具/转换流程见 SOURCE.md、convert.py。
- 正常循环不经过占位或透明首帧。不改上游首尾姿势；error 首尾头部约12源像素差、eating底部约13源像素差是源动作差异，未插值或逐帧锚平伪造无缝。有些动作因此仍有源生首尾姿势变化，需要用户观感验收。

## 首 RED 与诊断（保留，不被 GREEN 覆盖）

1. **修改前全仓基线 RED：1 failed / 318 passed / 41.87s。** `tests/test_companion_integration.py::test_native_app_auto_monitor_gestures_single_writer_and_exit`：heartbeat_ticks=484、max_tick_gap_ms=150.04，要求 `<150`；auto_start/working/gestures/四入口恢复/110 tokens/单writer/stop_ms=5.23均通过。未放宽该测试、未修改其代码。
2. **新契约首 RED：1 collection error / 1.33s / exit1。** `tests/test_characters.py` 导入 src.pet.characters 时 ModuleNotFoundError；当时尚未实现新契约。
3. 初次转换诊断：上游配置误用 `dsh-pet/config.jsonc` 得404，修正为公开 `dsh-pet/assets/config.jsonc`；本机旧FFmpeg3.0.1输出PNG alpha全255，丢弃。使用临时FFmpeg9.0.2/libvpx-vp9正确解码，工具不入仓库、不成运行依赖。
4. 首轮适用61 passed / 18.88s，但638条 Qt QImage.mirrored 弃用警告；改为QTransform镜像，后续无警告。中间完整GREEN333/58.84s、334/60.94s不替代最终内存修复后的复验。
5. **扩展原生连续动作探针 RED：exit1。** `native_probe` 第212行断言 `_frames` 非空失败；随后首次原bench启动工具返回 `System.OutOfMemoryException`（未运行，不记通过）。当时整段126帧预缩放缓存占73,483,200字节，另有19,464,192字节源图集。这是本机观察到的内存/渲染失败，未审计其他用户进程，不能归因其负载。将缓存改为按帧缩放后，连续动作探针独立GREEN，新增真实Qt动作巡回与驻留回归。

## 最终验证（单列 GREEN）

所有测试固定 WorkBuddy Python。以下每次 run 使用不同的 TEMP 子目录，创建后显式设置 TEMP/TMP/MCPET_DATA_DIR；完整pytest加 --basetemp，数据、Qt窗口截图均不落用户台账。

```powershell
$petPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$runDir = 'C:/Users/DW/AppData/Local/Temp/mcpet-A-dual-lazy-full-20261012'
New-Item -ItemType Directory -Force "$runDir/temp" | Out-Null
$env:TEMP = "$runDir/temp"
$env:TMP = $env:TEMP
$env:MCPET_DATA_DIR = "$runDir/data"
$env:QT_QPA_PLATFORM = 'windows'
$env:PYTHONIOENCODING = 'utf-8'
& $petPython -m pytest -q --basetemp "$runDir/pytest"
& $petPython -m compileall -q src tests assets/dsh-deepseek/convert.py
git diff --check
# 适用测试：新建隔离runDir再执行
& $petPython -m pytest tests/test_characters.py tests/test_dual_pet_render.py tests/test_window_render.py tests/test_pet_behavior.py -q
# 双角色原生探针：新建隔离runDir再执行
$env:PYTHONPATH = (Get-Location).Path
& $petPython tests/test_dual_pet_render.py
# 保留原Windows基准：新建隔离runDir再执行
& $petPython scripts/bench_render.py 10
```

- **最终完整 pytest：335 passed / 55.18s / exit0，无 skip、无 warning**，包含原联合 heartbeat<150ms、stop<50ms 与单writer测试。最终代码之后仅写本文。
- **最终适用测试64 passed /15.96s /exit0，无警告**，runDir=`mcpet-A-dual-applicable-final-20261012`，包含全部原触摸/窗口回归及新角色/动作巡回回归。compileall src/tests/转换脚本、git diff --check 均exit0。内存修复首轮适用63 passed /15.57s为独立先前证据。
- **双角色原生探针：Windows / DPR1.5 / exit0**，runDir=`mcpet-A-dual-lazy-bench-20261012`。每角色5s：均63次回调/12.6fps、0卡顿；maimai平均80.00ms、78.87..81.25ms；DeepSeek平均79.88ms、72.95..81.16ms、标准差1.03ms。切换DeepSeek36.01ms；九动作冷加载17.34..35.98ms。
- 120次真实Qt拖拽+反向1px+后台刷新：maimai8帧、0.143ms/事件；DeepSeek11帧推进、0.428ms/事件；均仅run-right、释放等待双击窗口仍0 clicked，拖拽前greet未到期。
- DeepSeek实际驻留像素缓存：缩放1,166,400字节、源图集19,464,192字节，合计约19.7MiB；这是像素缓冲计数，**不是整个应用RSS或GPU开销**，动作解码切换仍有短暂新旧源共存峰值。最多四张缩放帧与一个源图集通过回归断言。
- 仅截取自己的Qt窗口，未抓桌面其他内容：`TEMP/mcpet-A-dual-lazy-bench-20261012/data/{maimai,deepseek}-native.png`。已查看这两份DPR1.5截图，两角色可见，DeepSeek截图含37%上下文；不能替代用户长期观感或C面板/Pixso验收。
- **原 `scripts/bench_render.py 10` 独立GREEN / exit0**，runDir=`mcpet-A-dual-original-bench2-20261012`：Windows/DPR1.5，124帧/12.4fps（目标达成99%），平均80.0ms、中位80.1ms、78.8..81.4ms、标准差0.5ms、0卡顿；120次拖拽0.16ms/事件、8/8帧推进、仅run-right、0 clicked。原atlas锚点仍稳定，jumping46px仍保留。

## 剩余限制与主轨操作

- 本分支只有A双角色功能；未合B/C，未做双角色额度组合验收、Pixso设计、真实余额/MCP/模型请求，不宣称产品整体完成。原唯一集成Worker普通merge最终A tip后验证C选择器、预览、托盘与重启接线。
- 原动画不同角色的画面占比与动作持续时间不同；没有扩大单帧或改形象。未知上下文继续显示未知，0为有效测量。
- 原生测试为本机Windows/DPR1.5，尚未人工切物理屏/DPI、游戏全屏/远程桌面/长期休眠；既有边界/多屏负坐标/锚点回归仍通过。计时器回调与缓存证明不等于显示器逐帧呈现或主观自然度。
- 加载检查全部文件头和几何、预解码当前动作；全动作像素由回归检查，不在GUI一次性全部解码。若安装后素材被删除/破坏，后续动作可能显示原有占位兜底；切换时失败保留旧角色。
- 未操作GUI49784/launcher38676/monitors23860/48728；未读.env、凭证、用户既有日志/ledger，未安装第三方宿主、未发模型/MCP账号网络请求。仅下载公开固定素材和临时转换工具。
- 完成commit+普通push，通知主terminal `term_0dcc55fd-ccc4-4567-be46-3d441ca0ec24` 后停止。通知采用 [orca-cli skill](C:/Users/DW/.agents/skills/orca-cli/SKILL.md) 的公开terminal send；receipt只说明输入accepted，不声称对方已集成。

## 2026-10-12 组合性能返修：最终 A 交接

本节追加记录，前述 8b7da5c 的 335 全仓 GREEN、整 WebP 体积/驻留和未合 B/C 均为历史证据，不能用来描述本节组合版本。原 WT/branch 不变：`songconmaisaix31-design/mcpet-pet-20261011`。从干净 `8b7da5c9d396a0e14b77f4e2b7ad5c844c0c4a1e` fetch 后按授权 FF C basis `d037c5cf6b384d4930dbadef97b0240881978b73`。只读 fetch/git show root 文档 `cfde794493c3054aef88ca6afdd755918639940c`，没有合并 root sibling、rebase、reset 或 amend；最终唯一集成者还需普通合并该 root 文档 tip。

本轮代码提交（最终交接文档提交另由 `git rev-parse HEAD` / `ls-remote` 精确核对并通知）：

- `538e25e73c111d0c3e664ec3f69d536b7639ae0b`：固定 PNG 小分页/独立首帧预览、alpha 校验字节采样、切换实际相位同步准备、复用已提供的同角色 sheet。
- `476066cbbca5ff54e90d0858a5fa2ab4daeae13f`：同节奏角色切换保留活动计时器与 deadline，新增麦麦同像素 PNG 缓存。
- `ca3cf5f73c1df58eaf9164a4d0df7bf6f95dc3ba`：麦麦 PNG 改用标准 filter=0 / stored deflate，实测降低解码 CPU。最终生产代码/素材测试均在此版执行；随后仅追加本文。

只修改获授权 A 路径及 root 明确增补的 `assets/longniang/spritesheet-runtime.png`。未改 main/dialogs/B、任何旧/新集成测试、断言、预算、等待时序、root 计划。没有新框架/完成证明系统，没有预热所有角色/动作，没有把切换必要解码挪到下一 tick，没有恢复整段 scaled 缓存。原许可证、固定上游 SHA、接口与 TTL/拖拽/休息/恢复规则不变。

### 修复与素材取舍

1. C basis 的 `character_preview` 已使用 `sheet.image`，正常点击记录 `_icon` 为 0.261..0.422ms；没有为图标访问 idle 而淘汰 working 页。A 构造也不再解码整 idle 动画，改为同像素固定 192×192 首帧预览；当前动作的实际相位页仍在切换完成前同步解码/缩放。坏的目标相位页失败保留旧 sheet、画面、帧号、TTL 与偏好文件，回归断言覆盖。
2. 九个旧 DeepSeek 无损整 WebP 拆为 94 个 2304×192 PNG 页（每页 12 个固定 192×192 格），另加首帧 `preview.png`。完整页及全部 1069 个有效帧逐像素等于旧缓存，alpha/透明 RGB 都保留；没有重新缩放、裁边、居中、锚平真实跳跃或改帧数/80ms节奏。旧 WebP 先保存在本轮证据 `repack/originals`，确认一致后删除仓库冗余文件。PNG 页 33,264,844 字节，预览 34,560 字节，相比旧 21,392,334 字节增加磁盘体积，换取较小的必要解码；复现与许可见 SOURCE.md/CREDITS。
3. `AnimationSheet` 校验页头/几何，不预解码其他动作；缓存最多一页。切换释放旧角色像素，缩放仍最多两组动作、每组两张近期帧。后续页仅播放到达时解码，页边界/末页/循环回归检查真实像素。Native 最后驻留 DeepSeek：源页 1,769,472 + 缩放 1,166,400 + 预览 147,456 = 3,083,328 像素字节（约2.94MiB）；切换有新旧短暂共存，未测峰值 RSS/GPU，不将像素计数冒称整个应用内存。
4. 麦麦原校验规则仍是每4px采样、alpha>8；小格转换 RGBA 后读 alpha 字节、发现非空即停止，替代逐点 Python/Qt 调用。仍每次加载校验，没有跨版本元信息缓存。正常点击校验由旧样本 324.943ms 降至最终 15.785ms；独立启动样本 3.733ms。真实空格/低 alpha/采样规则回归通过。
5. 麦麦新增 PNG 与原 `spritesheet.webp` RGBA 所有像素/alpha 一致，原 WebP/pet.json/sprite-rows.json 不动。characters.py 有 PNG 时优先使用，缺失时仍可加载 WebP；没有缓存整个非活动角色。现 PNG 使用标准 filter=0、stored deflate，磁盘 **14,060,903 字节**，解码像素仍 **14,057,472 字节**；体积成本明确，许可证沿用原素材。转换器 `--maimai` 可离线复现并验证像素。
6. 角色切换同80ms节奏时保留活动 QTimer ID 与原 `_next_frame`，避免同一 Qt timer 回调内连续选择角色不断推迟下一帧。不同节奏/非活动计时器仍按原规则启动；真实嵌套 QTimer/QTest 回归检查 timer ID/deadline 不变且110ms推进。显示/隐藏、显式 `set_state(...force=True)`、`set_spritesheet` 的重置语义不变。

root 最后提出的 `_reload_frames(force=True)`/后续 resize 候选已核对：本 C basis 的 `window.py` **没有 `_reload_frames` 或 resizeEvent 重载**，canvas/window 构造后固定大小，set_character 不改几何；屏幕/DPI通知通过 `_load_frames(state)`。最终正常点击两份记录在 role change 后到 QTest 等待结束没有再次 `_load_frames` 或 showEvent，不能把候选当作已证根因。原同节奏重启版诊断等待前 `_next_frame` 尚余54.498ms，实际等待150.897ms后帧仍0/到期-96.507ms且没有 advance 回调；修复版保留早已到期的 clock，原110ms请求后由0推进11（stored PNG）/13（WebP对照）。等待实际返回169.477/202.698ms反映同步事件耗时，**没有把测试请求110ms改长**。显式 force 语义未弱化；本轮不声称人工跨物理屏/DPI验收。

### 解码分段证据（不要相加嵌套耗时）

证据根：`C:/Users/DW/AppData/Local/Temp/mcpet-a-perf-20261012-r1`。每个 run 保留独立 `command.json`（确切命令/代码版号/PID/exit）和 `result.log`；分段另有自己的 `data/profile-observe.json`，不覆盖首 RED。诊断包装调用原发布组合协议/断言，仅记录 source、requested_source、state、相位、cache、clock；WebP对照显式记录 `webp_comparison=true`，只将本进程请求 runtime PNG 的实际来源改为原 WebP。该对照不是生产测试 GREEN，也不改仓库 main/测试。

| 正常点击样本 | 必要解码叶子 | load/校验或缩放包装 | set_character 总耗时 |
| --- | --- | --- | --- |
| `profile-before` / d037 | DeepSeek idle268.102 + working308.089ms（两个实际解码） | 旧构造277ms | 602.222ms |
| 同上回麦麦 | WebP279.917ms | 校验324.943ms | 615.544ms |
| `profile-after` / 538e | DeepSeek working39.565/45.168ms；单页总体33..57ms | 构造/页头/首帧64.965/71.710ms | 116.363/129.559ms |
| 同上回麦麦 | 原WebP304.838ms | 校验15.617ms | 352.514ms |
| `profile-stored-runtime` / ca3cf5f | DeepSeek working39.955/43.423ms | load71.781/62.987ms；scaled43.078/46.106ms（含前述解码） | 123.482/120.085ms |
| 同上回麦麦 | stored PNG **118.466ms** | load139.852ms（含解码与校验15.785）；scaled14.826ms | **164.059ms** |
| `profile-current-webp` / 同ca3cf5f对照 | 实际原WebP **288.028ms**，requested_source明确runtime PNG | 同结构加载与校验 | **330.345ms** |

这些是冷进程中的正常点击、当前working动作/实际缓存路径；不是 OS 文件缓存清空后的普遍结论，也不能把 init/load/scaled/set 包装再相加。当前 DeepSeek 单个 QPixmap.scaled 调用最终最大3.586ms；较长 `_scaled_frames` 包装含必要源页解码，不能全部归因缩放。

**PNG取舍保留反证**：旧 compressed runtime PNG 单独新进程 wall62.201ms/CPU62.500ms，原WebP53.982/CPU46.875ms，前者不更快；同正常点击旧PNG解码283.472ms，也未证明收益。后续普通提交 ca3cf5f 改为 stored deflate 后，独立新进程31.153ms/CPU31.250ms，且同ca3cf5f正常点击分列118.466 vs 原WebP288.028ms，支持以更大磁盘文件降低当前解码成本的取舍。**不能冒称仅改PNG格式已解决所有305ms、150ms组合门槛或环境根因**；麦麦set164.059ms样本仍超过150ms，组合仍RED。原生独立动作加载5.72..8.34ms与正常点击33..57ms是不同调用场景，不互相替代。

### 本轮首 RED 与中间失败（独立保留）

| run | 首次结果/意义 |
| --- | --- |
| `applicable-first` / d037 | 64 passed /30.96s，旧A适用基线 |
| `old-joint-first` / d037 | 1 failed /11.75s，heartbeat414.64ms、首面板331.08ms；后置PID/锁/重启断言NOT_RUN |
| `combo-first` / d037 | 1 passed、1 failed /18.40s，完整行为契约通过，heartbeat1790.11ms/首面板382.81ms |
| `regression-first` | 2 failed、1 passed、6 deselected /0.34s，新测试暴露构造解码整个idle及旧单图格式 |
| `phase-regression-first` | 1 failed、11 deselected /0.44s，目标相位63前多余解码帧0；后续修复只请求63 |
| `applicable-repair` | 2 failed、67 passed /18.27s，新测试把QPixmap预乘alpha像素与straight QImage直接比较，修正expected采用同QPixmap表示；独立全像素/alpha审计未放宽 |
| `old-joint-repair` | 1 failed /9.11s，heartbeat364.06ms/首面板273.91ms；后置仍NOT_RUN |
| `combo-repair` / 538e | 2 failed /14.81s，role_frames_advanced=false与heartbeat1132.08ms；行为契约在帧推进之后的断言NOT_RUN |
| `cadence-first` | 1 failed、12 deselected /0.59s，真实Qt嵌套回调证明同节奏切换重置timer ID/deadline |
| `profile-clock-runtime` / 476066c | exit1仅heartbeat986.20ms/首面板366.73ms；帧推进与完整契约通过，不记pytest GREEN |
| `profile-stored-runtime` / ca3cf5f | exit1仅heartbeat939.50ms/首面板457.43ms；帧推进/完整契约通过 |
| `profile-current-webp` / ca3cf5f对照 | exit1仅heartbeat1082.95ms/首面板459.37ms；帧推进/完整契约通过 |

`profile-timer` 最初采到 QWidget.window 方法而非PetWindow导致部分clock字段null，作为诊断脚本错误保留，未据此推结论；`timer-detail` 修正后有前述真实clock数据。旧会话 helper setup refresh 错误单列环境失败，不是 pytest RED；本轮执行工具恢复正常。

### 最终验证：GREEN、RED、NOT_RUN 分列

最终 ca3cf5f 代码/素材，正确 WorkBuddy Python，所有测试串行，windows平台/DPR1.5；不改原测试等待/预算。不在本轮重复完整 pytest 挑GREEN。

| 验证run | 最终结果 |
| --- | --- |
| `applicable-final` | **71 passed /21.01s /exit0**：characters、dual_pet_render、window_render、pet_behavior；新增分页/透明像素/相位失败事务/既有sheet复用/同节奏真实Qt回归全部通过 |
| `old-joint-final` | **1 failed /9.58s /exit1**：heartbeat483.55ms、首面板397.53ms；auto_start/working/手势/四入口/110tokens/单writer/stop5.3736ms均在此前断言通过；之后原PID/锁/重启断言仍NOT_RUN，未宣称完整契约GREEN |
| `combo-final`（无诊断包装的已发布测试） | **1 passed、1 failed /13.47s /exit1**：`test_native_dual_pet_accounts_contract_and_bounded_exit`完整GREEN；`...heartbeat`829.28ms>150为RED。first_panel391.90ms；stop3.603ms<50；role_frames_advanced=true；实时通知拖拽、decimal/cursor、单writer、singleflight/generation、重启角色偏好通过。quit到reaped0.593895s、unreaped=[]、锁移除/重启true、network_calls=0、errors=[] |
| `native-final` | **exit0，Windows/DPR1.5**：两角色各5s均63帧/12.6fps/0卡顿；麦麦平均80.002ms、78.932..81.182；DeepSeek平均80.002ms、71.316..88.268。真实拖拽120事件，麦麦0.251ms/事件、8帧；DeepSeek0.269ms/事件、11帧；均greet TTL尚未到期时进入run-right，反向1px/后台通知不重置，释放0clicked。独立切DeepSeek17.70ms，九动作冷页5.72..8.34ms，窗口最多2动作索引/源1页/每组2帧 |
| `bench-final`（原scripts/bench_render.py 10） | **exit0，Windows/DPR1.5**：125帧/12.5fps、平均/中位80.0ms、79.0..81.1、标准差0.5ms、0卡顿；拖拽0.35ms/事件、8/8帧、仅run-right、0clicked。atlas idle横中心0.5px/底部0px、右跑底部3px、jumping46px有意跳跃均保留 |
| `compile-final` | **compileall src/tests/转换脚本 exit0**；全分支diff/check及最终cached check exit0 |
| 本轮全仓pytest | **NOT_RUN**：组合核心仍RED，按授权交原唯一集成者合C/A/root文档后做一次最终full/native；历史8b7的335GREEN不替代组合验收 |

只grab并查看自身Qt窗口 `native-final/data/{maimai,deepseek}-native.png`，透明边缘/两角色可见，未抓用户桌面/操作常驻实例。Native source_cache_bytes=0 对麦麦仅表示它没有AnimationSheet._atlases字典，**不表示零像素**；麦麦实际整sheet像素14,057,472字节，另有native最后scaled3,227,040字节（约16.48MiB总像素，不含对象/RSS/GPU）。原bench文本输出原脚本编码，数值/exit日志保留，不越域改脚本。

可复现本轮确切命令（诊断工具在上述自有TEMP，不是运行依赖）：

```powershell
$petPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$probeRoot = 'C:/Users/DW/AppData/Local/Temp/mcpet-a-perf-20261012-r1'
# launch.py每次创建全新RUN_NAME；参数{run}替换为该目录，不能复用现有run覆盖证据。
& $petPython "$probeRoot/launch.py" applicable-final -m pytest tests/test_characters.py tests/test_dual_pet_render.py tests/test_window_render.py tests/test_pet_behavior.py -q --basetemp '{run}/pytest'
& $petPython "$probeRoot/launch.py" old-joint-final -m pytest tests/test_companion_integration.py -q -s --basetemp '{run}/pytest'
& $petPython "$probeRoot/launch.py" combo-final -m pytest tests/test_dual_pet_quota_integration.py -q -s --basetemp '{run}/pytest'
& $petPython "$probeRoot/launch.py" native-final tests/test_dual_pet_render.py
& $petPython "$probeRoot/launch.py" bench-final scripts/bench_render.py 10
& $petPython "$probeRoot/launch.py" compile-final -m compileall -q src tests assets/dsh-deepseek/convert.py
# 同版正常点击诊断，对照标签在profile JSON中明确记录：
& $petPython "$probeRoot/launch.py" profile-stored-runtime "$probeRoot/profile.py" '{run}/data'
& $petPython "$probeRoot/launch.py" profile-current-webp "$probeRoot/profile.py" '{run}/data' --maimai-webp
# 离线转换（写入唯一获授权麦麦runtime PNG，必须在开发验收时运行，未预热运行时）：
& $petPython assets/dsh-deepseek/convert.py --maimai
git diff d037c5cf6b384d4930dbadef97b0240881978b73 --check
git diff --cached --check
```

launch.py子进程使用字面量allowlist环境，未复制/打印继承环境：TEMP/TMP/MCPET_DATA_DIR、HOME/USERPROFILE/APPDATA/LOCALAPPDATA均为新隔离目录，controlled inbox/source、mock token、不存在的config/agent roots、process-watch=0；sitecustomize禁止socket网络及既有凭证读取。真实 AgentMonitor/账号source运行发布协议的本地受控mock进程，不是实际账号网络。未读用户.env/凭证/既有日志/ledger、未用--showlocals、未扫真实根/进程表/控制GUI49784等用户实例。

### 剩余限制、接口及交还

组合性能仍未完成，不能宣称UI/full GREEN。C native首次show与新结构重建仍需原C/主轨处理：最终正常点击C show364.243ms（原WebP对照370.013）、新结构set_accounts255.240ms（对照498.288），均仅对应记录，不推断环境或C确定根因。A本域必要解码/校验/缓存已明显下降，但麦麦整切换164.059ms样本仍在，连续角色选择在同一工作阶段会累计同步耗时；不绕150/50ms门槛，不越域修C、不改协议调度。

共享接口原样：`character_id`、`set_character`同步失败事务、`load_character`返回SpriteSheet兼容API（image首帧预览、frames/frame/row_for/frame_count）；`chat_requested`仍打开依托Agent会话的小窝，不新建独立聊天；set_activity(state, context_percent=None, label='')、set_roaming/set_resting及属性/本机偏好不变，未知上下文不编百分比。C继续用已发布character_preview取得静态首帧即可，不能遍历其他动作预热。

所有本轮测试/探针有限结束，最终记录子PID40332/42260/28400/38692/20376/44736均已结束，组合三个reader42204/4144/15792已被发布协议回收（unreaped=[]）。交回独占时段，不再运行Qt/pytest/native/perf。最终普通push/精确ls-remote/干净后，用 [orca-cli SKILL.md](C:/Users/DW/.agents/skills/orca-cli/SKILL.md) 通知root `term_2a23bbea-71c5-4f99-b15f-77e5b8ca591b` 和原唯一集成 `term_7a4e4c11-2813-49cd-8879-43311e269929` 最终SHA及GREEN/RED/NOT_RUN。由唯一集成普通merge已发布C d037、A最终tip与root文档，做final full/native；A不集成、不合回root，通知后停止。
