# C · 统一麦麦小窝交接（2026-10-12）

## 分支与提交

- 原 C worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-app-20261011`。
- 原 C branch：`songconmaisaix31-design/mcpet-app-20261011`。
- 开始时 worktree 干净；按要求 `git merge --ff-only 45e2e4773f37a94ce64a634bf505fd4ea5dcb5f9` 成功，没有 reset / force / 独立集成。
- 实现及三份使用文档提交：`4f1f8b9439889fddb1d10b37e1b1e9d9e05c718c`，`feat(app): unify session companion controls in reusable native panel`。
- 本交接作为随后单独的文档提交；最终交付 tip 以 C 最终通知和 `git log -1 --format=%H` 为准。只 push 原 C 分支，不合回 root。
- 最新业务事实源：root `docs/companion/SESSION-PANEL-PLAN.md`。主轨最后告知计划补遗 `de4691f`，由唯一集成者处理；C 不再合入其他轨。

## 完成行为与接口

- `PetWindow.chat_requested`、托盘点击 / 真实 `QAction.triggered(bool)`、右键进入唯一非模态 `CompanionPanel`。`action_panel(page='home')` 处理 Qt 的 bool 参数；关闭 / Escape / 重开复用同一个实例。
- 四页：陪伴控制、会话与本机用量、麦当劳快捷功能、本机设置。复用已有角色 idle 帧；奶油、暖橙、淡紫、圆角卡片。各页可滚动，按当前屏幕工作区限制初始尺寸。
- `src/main.py` 不实例化 `ChatDialog` / `ChatStore`，不调用 StepFun / `run_skill`；无会话输入或记忆入口。旧模块及旧历史数据未删除、读取、迁移或发送。仅从既有 Skill 模块 import `validate_arguments`，复用严格订单 payload 校验。
- B 保持唯一 `AgentMonitor`，四信号 / 四方法不变；快照直接更新同一面板。保留 source、会话标签、日志状态、上下文、过时与 UNKNOWN。上限估算通过 `getattr(record, 'context_limit_estimated', False)` 标记。失效保留最后成功快照；庆祝只来自明确完成事件。
- 进度 / 用量 / 设置不另开正常控制窗口；付款在麦当劳页同窗显示。只保留领券、下单、撤单确认与餐品份数选择等必要业务对话框。
- 麦当劳沿用 worker 串行初始化 / 单飞、错误脱敏、饭点只读、真实选餐品与数量、提交前核价及严格 payload 人工确认。未知提交效果消费候选、保留 UNKNOWN、提示官方核对，不重发；HTTP(S) 支付打开 / 复制和凭证链接拦截保留。
- 设置页只展示 MCP、城市、可折叠显式 roots。凭证 Password 遮挡、不回填、留空保留、明确勾选清除；取消 / 关闭 / Escape 清除未保存输入。保存失败内联显示，忙时禁止保存；root 修改提示重启，不创建第二个 monitor。原 `config.save_settings` 保留旧 StepFun 字段及其他本机配置。
- 单实例锁及后台安全退出保留；最终使用 A `window.close()` 保存位置、停止 timer。没有 GUI wait、注册表或开机启动改动。
- 修改仅限新计划 C write_paths；A/B 文件没有修改。README、MCP_INTEGRATION、AGENT_BRIDGE 已更新使用入口及旧 CLI 适用范围。

## 验证命令与结果

PowerShell，工作目录为上述 C worktree：

```powershell
$py = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:MCPET_DATA_DIR = Join-Path $env:TEMP 'mcpet-panel-full-final-20261012'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_SCALE_FACTOR = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $py -m pytest -q -o faulthandler_timeout=30
```

最终 **315 passed in 32.56s**。外部凭证加载在应用夹具 / 探针被禁用，config 测试只使用内存 dotenv 读取替身；旧聊天单元测试只读自己新建的临时夹具，不读取已有用户历史。

```powershell
$env:MCPET_DATA_DIR = Join-Path $env:TEMP 'mcpet-panel-applicable-20261012'
& $py -m pytest tests/test_app_actions.py tests/test_companion_panel.py tests/test_companion_integration.py tests/test_main_startup.py tests/test_dialogs.py tests/test_config.py tests/test_chat.py tests/test_skill.py tests/test_stepfun.py -q -s
& $py -m compileall -q src tests
git diff --check
```

适用 **66 passed in 20.54s**；compileall / diff check 均 exit 0。Git 仅提示现有 CRLF 会规范为 LF，无 whitespace error。

真实 Qt 启动、活动任务退出、重复启动及手势 / monitor 联合命令可分别复现：

```powershell
& $py -m pytest tests/test_main_startup.py -q -s
& $py -m pytest tests/test_companion_integration.py -q -s
```

以上包含实际 `windows` 平台、真实角色资产和默认 B monitor 的受控日志子进程；活动退出还包含 376ms mock 初始化 / 慢任务以及外部 Quit，重复启动验证无第二 monitor / tasks / window，恢复验证移动后立即退出的位置及休息 / 闲逛选项。保留原联合断言 `max_tick_gap_ms <150`、`stop_ms <50` 和拖拽方向阈值，没有等 TTL、延迟显示或放宽标准。

最后适用联合实测：`heartbeat_ticks=398`、`max_tick_gap_ms=114.8`、`panel_open_ms=[101.39,1.18,29.85]`、`stop_ms=7.833`、真实两个扫描子进程 / 唯一用量 writer、`task_completed=1`、受控日志 `usage_tokens=110`、四次进度与四次用量信号。任务线程及子进程回收，无 QThread destroyed，锁释放与位置恢复通过。

## 原生截图与隔离边界

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1'
& $py tests/test_companion_panel.py --screenshots (Join-Path $env:TEMP 'mcpet-panel-20261012-delivery')
```

- 最终路径：`C:/Users/DW/AppData/Local/Temp/mcpet-panel-20261012-delivery/`，四张 `home.png`、`sessions.png`、`mcd.png`、`settings.png`。是实际 Qt `panel.grab()`，不是 HTML / 浏览器 mock。
- 实际平台 windows、DPR **1.5**、`network_calls=0`、`errors=[]`、`worker_stopped=true`，exit 0；主轨已审阅此前 final 同布局 / 文案截图并通过，delivery 是删除装饰符号后的最终截图，已在 push 前告知。
- 独立 TEMP 数据目录与自造 generic 日志（含工作、待输入、过时 UNKNOWN 三个会话）；实际默认 B monitor 读取受控日志。1555 token 来自夹具事件，只证明解析 / 展示契约，不是用户真实用量。
- 构造前仅在探针中替换 `QtDailyScheduler.start`，阻止同步补饭点产生任务；同时断言 worker 没有意外任务，模型 / ChatStore / MCP 构造及 HTTP 请求都硬拒绝。没有读取任何 `.env`、已有聊天、真实日志根或全 accounts，没有 live 模型 / MCP / 账号写操作。

## 首失败与返修记录（不覆盖为 GREEN）

1. 首次针对性命令 `pytest tests/test_companion_panel.py tests/test_app_actions.py tests/test_config.py tests/test_dialogs.py -q` 未完成，卡在右键 `QMenu.exec`。诊断 `pytest tests/test_companion_panel.py -vv -s -o faulthandler_timeout=15` 报超时，堆栈为 A `show_menu` → C `on_menu` → 新面板测试。停止的是这两次测试的已识别 Python PID。返修改为真实 popup event loop 的 QTimer 触发 QAction 后关闭；随后 **32 PASS**，保留首超时。
2. 原生 `native-v1` 截图探针 exit 1：断言实际 DPR 1.5，但 `QT_SCALE_FACTOR=1.5` 与系统 1.5 相乘成 **2.25**。截图和输出保留在 `TEMP/mcpet-panel-20261012-native-v1`。改成 scale=1，`native-v2` / `final` / `delivery` 实际 DPR1.5 全部通过。
3. 首次完整 pytest **1 failed,313 passed in31.25s**：联合心跳 `349.26ms <150` 失败；独立复测 **381.51ms**，不是偶发放行。首次计时首次打开 **343.16ms**、再开 **1.54/13.63ms**。Profile 构造约16ms，进一步隔离显示首次 QWidget.show 约352ms；事件过滤、窗口 owner / 激活、字体名试验未解决，均撤回。
4. 替换按钮装饰三角 / 箭头为中文“展开 / 收起”后，在原退出机制、原 owner 和直接显示流程下，联合心跳 **119.25ms**、首次打开 **113.58ms**；去掉诊断 profiler 后最终 **114.8ms /101.39ms**。对照支持 Windows 首次显示时字体回退是延迟来源的推断，未做原生字体栈采样。最终全套315 PASS 是单独的返修后证据，不能抹掉原 RED。

## 真实限制与后续

- 仅观测原 Agent 日志，不提供向原会话发送消息、打开会话或控制任务的 API；轮询固有延迟 / UNKNOWN / 过时语义保持。没有真实账号查询、模型、下单、支付或17GB冷回填验收。
- 设置保留既有进程环境优先于文件配置的规则，批量 `MCPET_AGENT_ROOTS` 会覆盖单 provider roots；界面提示必须退出重启。旧 StepFun 配置字段保留，主 UI 不再展示。
- A `src/pet/window.py` 的单击气泡还曾有“双击我可以聊天”旧文案。主轨已恢复原 A 只修该文案，C 不等待、不改 A 文件，后续由集成者普通合入 A 文案 tip。
- 原唯一集成者按主轨安排先 FF `de4691f`，再普通 merge C 最终 tip 与 A 文案 tip；C 不自行集成。主轨启动新版供用户操作属于后续人工 / 集成验收；本次隔离测试实例均已退出。
- 完成通知使用已读 [orca-cli skill](C:/Users/DW/.agents/skills/orca-cli/SKILL.md)，目标 `term_0dcc55fd-ccc4-4567-be46-3d441ca0ec24`。最终通知含 push tip 与截图路径；CLI input_accepted 只代表输入接受，不伪称新 turn 已启动。
