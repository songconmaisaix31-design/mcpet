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
