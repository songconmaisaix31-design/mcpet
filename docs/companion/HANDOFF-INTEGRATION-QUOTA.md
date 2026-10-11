# 额度与双角色集成 checkpoint（2026-10-12）

**状态：供原 C 干净 FF 的集成基线，非最终交付。** 原联合 heartbeat RED 仍复现；
新组合契约/有限退出 GREEN 与性能 RED 分列。按 root 后续指令，本版本不重复完整
pytest 挑 GREEN，最终 full/native 等同一 C Worker 领域返修。历史报告未修改。

## 精确 lineage 与写域

- 原 worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-companion-integration-20261011`。
- 原 branch：`songconmaisaix31-design/mcpet-companion-integration-20261011`。
- 恢复时干净 HEAD：`7a828d0e943a7881e1a5b220b665f1445cd593e1`。
- 独立 ls-remote 核对四 tip 一致，fetch 后干净 FF root
  `0d76aa917a7c55accff3297e6bbed8fe76559ccc`。
- 已读本轮 PLAN / PIXSO-DESIGN-BRIEF 和三份 HANDOFF。仓库及父级定向查找未发现
  AGENTS.md 文件，遵守会话 AGENTS 协议。Python/PySide6/httpx 保持，无新增轨。

| 顺序 | 远端交付 tip | 普通 merge SHA | 领域代码 SHA |
|---|---|---|---|
| A | `8b7da5c9d396a0e14b77f4e2b7ad5c844c0c4a1e` | `47c6ebc612f2163d3f8bcaf15044d31fdf514839` | `a74cc21e911b43d54514b14ef04d0c79bb2eb2d5`；内存返修 `29a2ff1729959c970644e936f4edeb95f6e60659` |
| B | `fa96c57801d705f21b400f6f5271745d9914d421` | `4b0c996b5a36ba8177a4bd79321ac928d81329b4` | 最后解析返修 `f77cbbee6fc7720b742f56c9fc5fa578118ece9d` |
| C | `1b2b08ed0dcd5790a11a14d70bc1fbf8d1d83488` | `8161099c0938f9c3c420580c82da47ad7a11a1d5` | 功能 `eb6858e7c5c98c541fed62224f48ed8c6d1a322a`；EOF 修正 `cde12f86d330039b4d3e89e4313daabb251c9e46` |

三次均 `git merge --no-ff --no-edit <exact-tip>`，无冲突、保留历史；无 squash、
cherry-pick、force、amend、reset。测试接线/组合协议提交：
`2babb9d0a27108c59f908eb7801936635b2292e7`。本文独立提交，发布 checkpoint 最终 tip
由终端通知及独立 ls-remote 核对，不伪造本文自引用 SHA。

只改旧 `tests/test_app_actions.py` / `test_main_startup.py` / `test_companion_integration.py`
的 AccountMonitor 离线 stub 接线、新 `tests/test_dual_pet_quota_integration.py` 和本文。
无需生产胶水，未改领域实现。旧 AgentMonitor、drag/TTL、四入口恢复、heartbeat<150ms、
stop<50ms、writer1、Win32回收与整体退出断言全部保留。stub 不执行 Orca CLI/HTTP。

## 真实监控组合契约

新协议构造 `MonsterApp([])`，不传 monitor_factory：真实默认 AgentMonitor 与真实
AccountMonitor 接 C 信号。仅账号 Source 构造依赖换为顶层可 pickle 受控类，真实
spawn/IPC/singleflight/generation/回收未替代。Agent worker 外层只记录实际 body PID、
硬拒网络，再调用原 `observe`；不 stub monitor、解析、UsageMeter 或 writer。
父进程Win32核对三个launcher/body PID退出；Qt退出后不由测试join/pump帮助回收。

- 新generic日志触发自动start、working/25%上下文、usage40。原联合前置断言另覆盖
  明确完成1/usage110/dedup。均为契约日志，不表示用户真实任务完成。
- 合并仓库真实素材：麦麦→DeepSeek娘→麦麦→DeepSeek娘，核对sheet、状态不重入、
  preview/tray、实际atlas timer推进；未过期greet中立即40px拖拽，释放恢复通知。
- Cursor monthly/Cursor Models/Other Models独立 `[20,35.5,90]`，UI已用/剩余分别核对。
  DeepSeek Decimal `123.456789012345678901` 原精度，换源后 `0.001`；标签受控夹具，
  不是真实缓存包、余额或模型调用。
- 已进入的旧受控查询中30次真实monitor.refresh合并，走C保存/换源入口，同对象
  reconfigure；旧generation不发布，新结果结束刷新；三次query/金额版本 `[1,1,2]`，
  两次snapshot。保存替换成内存更新，不创建/读取.env。
- duplicate、tray真实signal、右键popup QAction、真实双击，从Qt minimized/Win32
  iconic恢复同一面板，核对可见性/矩形与工作区。
- 第四次账号查询阻塞且0.25s非网络串行任务活跃时退出：拒绝新操作、timer停、QThread
  结束、窗口关闭、三reader回收、锁删除；重启恢复170/140、休息/闲逛及DeepSeek角色。
- 主进程及读worker硬拒socket/httpx；模型/MCP/ChatStore构造也拒绝。无账号CLI、
  网络、账号写操作、用户GUI操作或第三方DSH插件。

## 首 RED 与诊断（不被 GREEN 覆盖）

证据根：`C:/Users/DW/AppData/Local/Temp/mcpet-integration-quota-1e7e74e43cf248eab972523d1cab3b49/`。
各运行使用不同子目录/basetemp，原 result.log 保留。

| 运行 | 精确结果与界限 |
|---|---|
| `old-joint-first/result.log` | **1 failed /12.03s**，heartbeat545.25ms>150、692ticks；首panel458.47ms、stop3.3559ms<50、errors=[]。自动start/working/完成1/usage110/drag/四入口Win32恢复/writer1/thread结束前置断言通过。heartbeat后的整体8s/PID回收/锁删除/位置重启断言 **NOT_RUN**，不从布尔状态补推通过。 |
| `combo-first/result.log` | **2 setup errors /24.27s**，20s协议截止停在new-generation；首panel690.16ms、maxgap4727.51ms、network0。当时单回调30次C action_quota重建UI并保存TEMP mock设置文件；准确超时根因UNKNOWN，未延长任何门槛。 |
| `combo-diagnostic/result.log` | 保存改内存后 **1 passed /1 failed /20.10s**；契约/退出GREEN，heartbeat3250.21ms RED，首panel366.27ms、stop1.4498ms。尚无Agent实际body PID记录，不替代下一轮PID证据。 |
| `combo-pid-instrumented/result.log` | **2 failed /25.57s**；heartbeat3774.93ms、首panel521.10ms；重复实例确认后的整段协议8.077976s>8（含换源，不是纯quit耗时），stop2.1042ms。body PID7460/38280/11456已回收、unreaped=[]、锁删除/重启恢复有独立记录。work2561.62ms、duplicate2145.78ms、held-refresh3687.83ms；人工同步30次UI重建总耗时不等于单次查询耗时。 |

本域协议定向修正：30次改为真实AccountMonitor.refresh，保留C首次action_quota及
保存/reconfigure/刷新入口，验证同一singleflight；不在一个合成回调重建UI30次。
全部断言与持续heartbeat保留，无预热/延后heartbeat/等TTL/领域修改。补独立quit→退出
并Win32核对回收耗时，重复实例确认后<8s断言也保留。

## 当前独立 GREEN / remaining RED

`combo-protocol-corrected/result.log`：**1 passed /1 failed /24.82s**。
契约/有限退出GREEN，性能RED，不能称全套或最终集成通过。

- Windows/DPR1.5；真实两monitor/双素材/四入口/分桶/Decimal/generation/singleflight/
  活动退出/重启偏好断言通过，network_calls=0、errors=[]。
- launcher/body PID7680/27368/41732，writer1、unreaped=[]、lock_removed=true、QThread
  false、两个窗口关闭；stop7.7062ms<50、post-duplicate5.842377s<8、实际quit到回收
  0.848375s<8；restart={restored:true,character:deepseek,thread_running:false}。
- heartbeat773ticks、**2739.76ms>150**，首panel712.79ms。phase callback最大work3188.92ms、
  duplicate2138.21ms、held-refresh34.64ms、new-generation452.42ms、exit-query434.57ms、
  exit-task411.01ms。work含首show/连续角色动作，不是单函数profile，不认定根因。
  原联合独立复现cold-show RED，交回原C；集成不领域修复。
- `glue-applicable/result.log`：**22 passed /21.80s**，旧app_actions/main_startup，含独立
  Windows normal/active/external-quit、duplicate无扫描/初始化与原Qt退出门槛。
- `compileall -q src tests` exit0；全分支与cached diffcheck exit0。cached check覆盖新文件，
  普通初查不冒称覆盖当时未跟踪测试。

既有外部证据只引用：A335全套GREEN；B适用82GREEN但最终1failed/400passed，
heartbeat417.81/首open332.09/stop42.8088；C适用66GREEN/独立退出GREEN但最终
1failed/340passed，554.15/467.37/5.17，独立原联合439.24/345.08/9.5934仍RED。
C调查无确定根因，原v4六图审阅GREEN独立保留，不改历史报告。

## 实际命令

动态运行顺序独占，正确WorkBuddy Python，每条pytest新runDir。RUN_NAME为上表目录。

```powershell
$quotaPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$quotaRun = '<证据根>/RUN_NAME'
New-Item -ItemType Directory -Force -Path "$quotaRun/tmp" | Out-Null
$env:TEMP = "$quotaRun/tmp"
$env:TMP = $env:TEMP
$env:MCPET_DATA_DIR = "$quotaRun/data"
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1' # 本机原生DPR1.5
$env:PYTHONIOENCODING = 'utf-8'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:DEEPSEEK_API_KEY = 'mock-deepseek-key-only'
$env:MCPET_WATCH_PROCESSES = '0'
$env:MCPET_AGENT_ROOTS = "claude=$quotaRun/absent-claude,codex=$quotaRun/absent-codex,generic=$quotaRun/absent-generic"
$env:MCPET_CONFIG_PATH = "$quotaRun/absent-config.json"
& $quotaPython -m pytest tests/test_companion_integration.py -q -s --basetemp "$quotaRun/pytest"
# 新RUN_NAME：组合协议只读本轮新造inbox
& $quotaPython -m pytest tests/test_dual_pet_quota_integration.py -q -s --basetemp "$quotaRun/pytest"
# 新RUN_NAME
& $quotaPython -m pytest tests/test_app_actions.py tests/test_main_startup.py -q --basetemp "$quotaRun/pytest"
& $quotaPython -m compileall -q src tests
git diff 0d76aa917a7c55accff3297e6bbed8fe76559ccc --check
git diff --cached --check
```

## NOT_RUN / 返修交接

- 首旧联合RED用 [orca-cli](C:/Users/DW/.agents/skills/orca-cli/SKILL.md) 通知root terminal
  `term_2a23bbea-71c5-4f99-b15f-77e5b8ca591b`，accepted仅输入接受；root随后明确确认
  收到并要求C静态等待，集成独占时段。checkpoint普通push/ls-remote一致/干净后交回。
  所有本轮测试/探针有限结束，当前组合三reader实际无残留。旧联合后置NOT_RUN仍保留。
- 按root最新指令，本RED版本完整 `pytest -q` **NOT_RUN**，不挑同版GREEN。
- 六图home/home-bottom/home-deepseek/sessions/mcd/settings **checkpoint未运行**。
  新测试提供 `python tests/test_dual_pet_quota_integration.py --screenshots <全新TEMP目录>`，
  合并素材/真实两monitor/受控source，无跨worktree overlay；只grab自己的Qt窗口。
  截图单独核对契约/退出/六图/DPR1.5，不当heartbeatGREEN。最终截图审阅、原联合/新组合、
  完整pytest待C返修普通merge后执行。
- 未读取用户.env/凭证、既有聊天/会话/日志/ledger，未扫描真实根/17GB；未输出继承
  环境/原始账号包、未用--showlocals。首新协议仅创建TEMP mock设置文件，后改内存；
  未读取该文件或任何凭证文件。文档首次apply_patch因遗漏行前加号未应用，重发修正，
  不属于测试/业务RED，无文件残留或领域修改。
- 未重复动画10sbench，未发真实模型/MCP/账号网络，未操作用户GUI/常驻实例/账号写，
  未发布安装包/自启动/第三方插件，未合回root或删worktree。
- 原C从checkpoint干净FF修本域，集成只普通merge后续精确tip，再最终full/native。
  root负责最终FF、真实Orca只读缓存、DSkey存在时只读余额、真实单实例启动与人工验收。
  checkpoint不宣称真实余额/订单、最终交付或全产品通过。

## 2026-10-12 C/A 返修后的实际组合 review basis

**本节为追加证据，仍不是最终交付。** 上述 checkpoint 的所有首RED、GREEN、NOT_RUN
均保留其原版本界限。root明确交回独占时段后，本轮完成普通合并、旧联合、新真实组合、
唯一一次完整pytest和实际六图；性能仍RED，只发布供原C干净FF的review basis。
原会话/worktree/branch不变，不新建Worker，不写任何领域或测试协议/时序/断言。

### lineage / 已合入 root 计划

起始 `bf5ff01ca8de33ad417eb7fd1cacd64030177d5b` 干净。独立ls-remote逐一核对指定tip，
fetch后按要求普通merge，无冲突：

| 顺序 | 精确交付 tip | 本轮 merge SHA |
|---|---|---|
| C | `d037c5cf6b384d4930dbadef97b0240881978b73` | `c8d3bb97777939d0768554125974445c4fe72d01` |
| A | `7d06474e4cbbf86d0517cc94f2b8c088c08532e5` | `ed834e2d52fa9da8e938b06615a78bdbac4f1f2e` |
| root文档 | `cfde794493c3054aef88ca6afdd755918639940c` | `e1824f729ee4f0fc6bcb31ee3db22cbba95821df` |
| root后续文档 | `7fec18b930559804b01ad785d5dc4bca44ec3f09` | `fa779ff604721ffaef068f5699765031ac4c4f6b` |

最后root文档在动态验证结束后按新指令fetch/独立核对/普通merge，只追加计划，不改业务。
本轮动态验证代码基线为 `e1824f729ee4f0fc6bcb31ee3db22cbba95821df`；后续只有计划与本文。
root7fec保留为review basis祖先，可由root最后FF；未合回root。

领域代码：C `876ae0c8632ded4b172dfac35be5184ad1295bda`；A
`538e25e73c111d0c3e664ec3f69d536b7639ae0b` /
`476066cbbca5ff54e90d0858a5fa2ab4daeae13f` /
`ca3cf5f73c1df58eaf9164a4d0df7bf6f95dc3ba`；B仍为原发布实现。
已读取三份HANDOFF和root最新追加计划。A71适用/双角色native/原bench GREEN，C71适用/
实际30 action_quota3.7535ms GREEN，均不覆盖其旧/新联合RED及原轨full NOT_RUN。
四份旧接线/组合测试相对checkpoint零diff；原150/50ms、frame推进、TTL、四入口、writer1、
QThread/Win32回收及整体退出门槛原样，未预热/延后heartbeat/等TTL/改调度。

### 实际受控环境与命令

本轮证据根：
`C:/Users/DW/AppData/Local/Temp/mcpet-integration-quota-review-44589ca99b8b4bf8905beb5585dd82e5`。
`run.py`只是TEMP里的标准subprocess串行启动辅助，不是产品依赖/调度系统。子环境用
字面量allowlist，不复制凭证/代理；TEMP/TMP/data/HOME/USERPROFILE/APPDATA/LOCALAPPDATA
均为本轮新目录；mock token/key、不存在的三类roots/config、watch_processes=0。
`guard/sitecustomize.py`硬拒Python socket真实网络、真实Orca account CLI及证据根外.env读取。
测试自己的MockTransport/受控可pickle账号源照常，Qt协议使用自己的QLocalServer。
未读用户.env/凭证/既有会话/聊天/日志/ledger，不扫描17GB根；无--showlocals/环境输出。

每条运行创建新RUN_NAME，完整命令/exit/wall在各自command.json，原result.log不覆盖：

```powershell
$quotaPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$quotaReview = 'C:/Users/DW/AppData/Local/Temp/mcpet-integration-quota-review-44589ca99b8b4bf8905beb5585dd82e5'
& $quotaPython "$quotaReview/run.py" old-joint -m pytest tests/test_companion_integration.py -q -s --basetemp '{run}/pytest'
& $quotaPython "$quotaReview/run.py" new-combination -m pytest tests/test_dual_pet_quota_integration.py -q -s --basetemp '{run}/pytest'
& $quotaPython "$quotaReview/run.py" full-once -m pytest -q --basetemp '{run}/pytest'
& $quotaPython "$quotaReview/run.py" native-six tests/test_dual_pet_quota_integration.py --screenshots '{run}/screenshots'
& $quotaPython "$quotaReview/run.py" compile -m compileall -q src tests
git diff 7fec18b930559804b01ad785d5dc4bca44ec3f09 HEAD --check
git diff --cached --check
git merge-base --is-ancestor 7fec18b930559804b01ad785d5dc4bca44ec3f09 HEAD
```

动态运行全部串行，仅本轨有探针；root/A/B/C无动态测试。原startup normal/active/
external-quit、duplicate及A/B/C适用回归均在这一次完整pytest中通过，不额外挑绿重跑。

### 本轮首 RED 与独立结果

| 运行 | 实际结果与未执行界限 |
|---|---|
| `old-joint/result.log` | **1 failed /17.61s /exit1**。heartbeat795.87ms>150（911ticks）、firstpanel703.67ms、stop8.2874ms<50、errors=[]。自动start/working/真实touch-double-click-drag/方向/休息/位置操作、完成1/usage110、信号5/3、四入口Win32恢复、writer1、两reader、QThread false前置断言通过。heartbeat后的整体8s/PID回收/锁删除/位置重启断言 **NOT_RUN**，不补推。 |
| `new-combination/result.log` | **1 passed /1 failed /22.26s /exit1**。完整行为/帧推进/持久化/退出契约GREEN，heartbeat2526.44ms>150（816ticks）RED。firstpanel474.66ms，phase work2687.08/duplicate503.11/held-refresh21.28/new-generation109.57/exit-query79.54/exit-task103.99ms。stop7.6913ms<50，postduplicate2.675937s<8，quit-to-reaped0.932078s<8；body/launcher1224/31980/43236，writer1、unreaped=[]、锁删除、restart true/deepseek/thread false。network0/errors[]。 |
| `full-once/result.log` | **2 failed /450 passed /182.31s /exit1**（launcher wall184.239s），唯一一次完整运行，无skip/warning汇总。仅原旧联合heartbeat545.93ms（824ticks，firstpanel465.72ms、stop10.9947ms）及新组合heartbeat1038.21ms失败。新组合完整契约/有限回收及全部其他适用项通过。旧联合heartbeat后的原后置断言仍NOT_RUN。full中新组合firstpanel未在pytest失败报告保留，准确值UNKNOWN，不能拿独立轮值替代。 |
| `native-six/result.log` | **exit0 /wall15.886s**。实际合并六图/真实两monitor/受控源/帧推进/四入口/退出契约通过；Windows/DPR1.5，network0/errors[]，writer1，body/launcher37496/38360/43320、unreaped=[]、锁移除、重启DeepSeek/位置/休息/闲逛通过。stop3.7929ms，postduplicate2.055199s、quit-to-reaped0.718156s。heartbeat502.83ms、firstpanel377.83ms仍RED；截图入口没有执行heartbeat性能assert，exit0不冒称性能GREEN。 |
| `compile/command.json`、全分支diff | **compileall src tests exit0**（wall0.955s）；含新文件的全分支diffcheck/cached check通过。root后续文档merge后再核对全分支diff/祖先关系，不重复动态验证。 |

新组合真实默认AgentMonitor/AccountMonitor与top-level受控源，没有Monitor stub或旧overlay。
当前四入口恢复矩形均 `[1485,389,2557,1525]`、Qt非minimized且Win32非iconic/可见；
最小化前置状态iconic=true、rect[-32000,-32000,-31763,-31961]。新源generation丢弃、
singleflight三次query/金额版本[1,1,2]、Cursor独立[20,35.5,90]、Decimal和未过期greet拖拽
在新组合完整契约断言中通过；源与日志值都是夹具，不表示用户任务/真实账号余额。

### 实际六图 / root 审阅

图片目录：`native-six/screenshots/`，文件为home.png、home-bottom.png、home-deepseek.png、
sessions.png、mcd.png、settings.png；均 **1050×1080，原生DPR1.5**，只grab本探针自己的Qt。
使用实际合并A素材与C/B接线，无跨worktree overlay；六图全部view_image查看。

root随后明确确认已实际审阅六图，DeepSeek首页另按original完整重看，**视觉通过**：
双角色真实preview与选中配色、Codex session/weekly、Cursor monthly/两桶完整百分比、
Grok有效0/Claude UNKNOWN、独立CNY Decimal、会话/麦当劳/设置均可读。底部滚动能读
`123.456789012345678901`，金额无任意百分比尺度。数值标题标「受控夹具」，不是live；
设置字段只显示配置状态，没有凭证回填。原Pixso真实设计证据与本轮原生图各自成立，
不把这些截图当Pixso新操作、真实订单/余额或全产品验收。

### 有界退出 / slot 交回 / remaining RED

`pid-recheck.json`以OpenProcess(SYNCHRONIZE)/WaitForSingleObject仅复查本轮记录的15个
受控PID（含独立/全套/截图及重启marker）：1224/12600/15440/18028/31792/31980/35784/
37464/37496/38360/40972/42824/43236/43320/44244，**still_running=[]**。
新组合与截图的三reader原父断言已执行并通过，退出时活动SerialTasks/阻塞账号源有限
结束、QThread关闭、锁删除、偏好重启均核对。独立旧联合及full旧联合的原后置NOT_RUN
不被这次独立PID复查或新组合GREEN覆盖。

剩余领域：C `src/main.py::action_panel` / `src/pet/dialogs.py` 首show/同步激活仍超过预算，
原旧联合独立复现。新组合work阶段含C首show和A连续角色切换，阶段总值不是单函数profile；
A最后正常点击麦麦set164.059ms等既有剩余样本保留，不把组合总gap归于唯一模块。
冷激活/新结构卡片问题退原C，角色必要解码/切换问题若经分段定位退原A，集成不领域修复。
原C当前仅静态方案，root计划保留下一轮按实际结构增删/清空字段的边界，未冒称已实施。

本轮只有本文追加（另普通merge root计划），没有生产胶水或测试变更。普通commit/push、
独立ls-remote=HEAD、工作树干净后用orca-cli通知root精确review tip及 **slot idle**；
所有Qt/pytest/native/perf探针已有限结束，不再重复full或动态测试。root7fec已包含，
供原C后续干净FF返修；集成停止等待其精确tip及root再次明确返还时段。
本轮完整pytest确实执行且RED，前节checkpoint full NOT_RUN仍是历史事实，不改成GREEN。

未重复10sbench/17GB扫描，未进行真人账户/Orca cache/DS余额、模型/MCP网络、账号写、
用户GUI/常驻启动、安装包/自启动或第三方插件；root目前未FF/启动/真实只读采样。
性能两门槛未通过，不能称最终交付或全套/全产品完成。

## 2026-10-12 C 生命周期与限定诊断：仅静态 review 合并

本节只追加静态集成证据，以上各版本首RED、独立GREEN与NOT_RUN不变。
root明确限定本轮不返还动态时段；原Worker/worktree/分支保持，起始
`7ffeebd03179a2796cb88fb73e52929d22bbca6c` 工作树干净，独立ls-remote与fetch
逐一核对指定tip后，按C、root顺序普通merge，无冲突：

| 交付 | 精确 tip | 本轮 merge SHA |
|---|---|---|
| C 最终业务及诊断交接 | `8d2959af22dc708b3f796c08f58c21958618048f` | `2883439a3772b9a382e045ca8649793338210428` |
| root 最终文档 | `bac9f74ef462cdc451b8f54f8f7a9632cdd39c8f` | `d1dd466e76aa33676ce20eb4a32161736cb78eed` |

C业务提交 `0c4c5f80bd291a3faeb16b8ccb61e545601c7c5a`，业务交接
`36001485cb03b940c4d3f2eeee5b40915943865f`，最终8d2959仅追加诊断文档。
保留其五文件交付：真实快照provider/子行有限复用；换key同步擦除所有旧文本、
tooltip/accessibility、条与倒计时并隐藏；实际空快照释放缺席行。root计划包括7c7b3a9
及后续运行时对照/停止决定。没有领域、胶水、测试、协议、预算或运行时版本修改。
四份旧接线/真实组合测试相对7ffeebd零diff，原150/50、拖拽/TTL/四入口/帧推进、
writer1、QThread/Win32有限回收与整体退出断言保持。

### C 已执行证据（引用原 Handoff，本轮没有复测）

- `mcpet-c-lifecycle-1791758072944`：C最终自域 **41 passed /1 failed /67.69s**，
  唯一有界Windows前台断言仍RED。旧联合 **1 failed /11.96s**：heartbeat646.03ms、
  first542.64ms、stop6.5979ms；heartbeat后的原PID/锁/重启断言NOT_RUN。
  新真实组合 **1 passed /1 failed /23.68s**：完整行为、角色帧推进、换源/Decimal、
  三reader回收/单writer/有界退出契约GREEN；heartbeat2934.91ms、first621.34ms、
  stop8.2941ms，性能仍RED。首applicable重复启动失败、前台即时观察及探针修正
  均保留在HANDOFF-C-QUOTA-PANEL.md，不被最终自域结果覆盖。
- `mcpet-c-page-diag-1791759666421`：四入口前台归属均foreign，原精确前台断言RED；
  Qt active/本GUI线程焦点/受控Qt键入通过不替代OS last-input或人工前台验收。
  未访问页shell候选单配对：原show410.7618ms/heartbeat601.0772ms，
  shell show574.1284ms/heartbeat829.3257ms，均RED；没有实施按需页面依据。
  CSS原字符串缩进比较首RED与静态非空白等价界限保留。
- `mcpet-c-qt-minor-1791760074760`：隔离官方6.11.2候选与现6.12.0单配对，
  show455.3726/395.4577ms、heartbeat801.9684/668.6364ms均RED，
  stop8.7795/8.2751ms分别GREEN。未改变WorkBuddy环境/requirements或pin版本；
  metadata/support准备失败和OS-cache限制保留。两个候选均停止，不认定Qt/系统根因。

这些是C受控契约/界面诊断，不是本次合并后的新组合验收或live账号余额；真实监控
组合与UI监控stub对照分列。所有C探针已有限结束，本集成不另启动任何子协议。

### 本轮实际静态验证与命令

证据根：`C:/Users/DW/AppData/Local/Temp/mcpet-integration-quota-static-513e1abbb6c24b28a93e8cf6c0a4f4f4`。
compile.json/stdout/stderr记录合并基线d1dd466e、命令、exit0及耗时 **0.7065867s**。
通过ProcessStartInfo清空子环境，仅传Windows基础路径及新TEMP/data/home/appdata路径；
`-I -S`隔离Python启动、禁加载site/.pth，不导入或执行产品/Qt，仅编译src/tests字节码。
未继承账号key/token，未读取.env/凭证/真实日志/ledger或17GB根。

```powershell
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -I -S -m compileall -q src tests
git diff bac9f74ef462cdc451b8f54f8f7a9632cdd39c8f HEAD --check
git diff 0d76aa917a7c55accff3297e6bbed8fe76559ccc HEAD --check
git diff --cached --check
git merge-base --is-ancestor bac9f74ef462cdc451b8f54f8f7a9632cdd39c8f HEAD
git merge-base --is-ancestor 8d2959af22dc708b3f796c08f58c21958618048f HEAD
```

compile与两个全分支diffcheck、cached diffcheck、root/C祖先证明均exit0；本文暂存和
commit后再核对差异/祖先。root bac9f74是review tip祖先，允许后续root FF，本轮没有合回root。
最终review tip由普通commit/push及独立ls-remote确定，在终端通知，不在本文写自身SHA。

**本轮动态Qt/pytest/native/perf、新旧联合、完整pytest、更新六图全部NOT_RUN**，
没有来源网络/模型/MCP/账号请求、安装或系统设置操作、用户GUI或常驻启动。
原450 passed/2 failed和已审六图仅是7ffeebd所记旧基线历史，不冒称本轮full/视觉GREEN。
仅本文追加，原断言不变；普通push、remote=HEAD且工作区干净后通知root并停止，
全部slot idle。后续动态验证待用户桌面环境信息与root明确派发；冷show/系统前台
根因UNKNOWN、性能RED仍未解决，不能称最终交付/全套或全产品通过。
