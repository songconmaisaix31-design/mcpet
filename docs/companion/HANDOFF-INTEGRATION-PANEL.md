# 统一小窝：原唯一集成 Worker 交接

日期：2026-10-12。原 worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-companion-integration-20261011`。
原 branch：`songconmaisaix31-design/mcpet-companion-integration-20261011`。
业务事实源：`docs/companion/SESSION-PANEL-PLAN.md`；保持 Python / PySide6 / httpx。
没有新建 Agent / worktree / branch，没有合回 root 或启动常驻用户实例。

## 精确 lineage 与本轮写域

起始工作树干净，HEAD 为上一轮交付 `2885fa87f3eade21578b058e06a92bc78e697ed4`。
读取 root 计划、原 C/A 本轮 HANDOFF；`git ls-remote --heads origin` 检查三个远端 tip 与授权一致。

| 操作 | 输入 tip | 本集成分支结果 SHA |
|---|---|---|
| fetch 后 `git merge --ff-only` 根 tip | `de4691f2e80c0fe637e4ef1125649e133bcd4038` | `de4691f2e80c0fe637e4ef1125649e133bcd4038` |
| 普通 `git merge --no-ff --no-edit` C PANEL final | `58fbfd03118a08ceacea95e2fd0779654b051671` | `7a01566526618a1d4e9bae22ba54ff0da1fce5ed` |
| 普通 `git merge --no-ff --no-edit` A 文案 final | `6088ead001fc8ea97783758bab54477c2662ab38` | `15eb010cae2201cf7d779e00ba6da81485bd729b` |

两次普通 merge 均无冲突，没有 squash / cherry-pick / force / reset。
C 实现 `4f1f8b9439889fddb1d10b37e1b1e9d9e05c718c` 保留在历史中。
无需额外路由 / 导入 / 类型胶水；集成者只新增本文，没有改业务或测试断言。
本文单独 commit 并 push 原集成分支；最终 tip 随交接通知提供，可用
`git log -1 --format=%H -- docs/companion/HANDOFF-INTEGRATION-PANEL.md` 核对。

已合入的用户功能：双击 / 托盘 / 右键复用唯一非模态「麦麦小窝」，同窗整合陪伴控制、
会话与本机用量、麦当劳、设置；应用不创建独立聊天或偏好记忆入口，不读取旧聊天。
原 A 仅把触摸气泡提示改成“双击打开麦麦小窝”，没有改动画 / 手势。
自动 monitor、UNKNOWN / 过时 / 估算口径、麦当劳只读饭点及必要账号写确认保持。
使用文档由原 C 更新；历史验证报告和上一轮集成交接未改写。

## 本集成轮实际验证

解释器固定 `C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。
运行都用 TEMP 新目录、测试 token/key、受控日志；显式隔离三类 Agent roots。
应用夹具 / 原生探针禁用 `load_env`，配置测试使用内存 dotenv 读取替身。
不读取用户 .env / 凭证 / 既有聊天 / 真实日志 root，不请求真实模型/MCP或账号写操作。

| 验证 | 命令 | 实际结果 |
|---|---|---|
| 合并后首轮完整测试 | `python -m pytest -q` | **315 passed / 36.84s，exit 0，无 skip、无 warning**；父进程 windows、scale=1 |
| 编译 | `python -m compileall -q src tests` | exit 0 |
| 格式 | `git diff --check` | exit 0 |
| 独立真实 Windows 联合测试 | `python -m pytest tests/test_companion_integration.py -q -s` | **1 passed / 9.36s，exit 0**；原拖拽及心跳 `<150ms`、stop `<50ms` 断言保留 |
| 独立 normal startup | `python tests/test_main_startup.py --qt-smoke normal` | windows、thread_running=false、init=0、18 心跳、最大 11.87ms，exit 0 |
| 独立 active startup | `python tests/test_main_startup.py --qt-smoke active` | windows、thread_running=false、init=1、45 心跳、最大 11.02ms，exit 0 |
| 独立 external-quit startup | `python tests/test_main_startup.py --qt-smoke external-quit` | windows、thread_running=false、init=1、45 心跳、最大 11.42ms，exit 0 |
| 原生截图 | `python tests/test_companion_panel.py --screenshots <下方新 TEMP 目录>` | windows、DPR **1.5**、network_calls=**0**、errors=[]、worker_stopped=true，exit 0 |

独立联合探针原始数据：auto_start=true、working=true、gestures=true；
progress_signals=4、usage_signals=4、completed=1、usage_tokens=110；
heartbeat_ticks=439、max_tick_gap_ms=**116.51**；panel_open_ms=**[104.03,1.55,37.66]**；
stop_ms=**10.2808**、thread_running=false、errors=[]。
默认真实 AgentMonitor 的两个 spawn 子 PID 为 **45516 / 51340**，writer_count=1。
重复 start / 40 次刷新 / 第二实例未生成重复 writer；退出后外层 Win32 进程句柄断言
确认两个 PID 均已回收。锁释放、位置 `[170,140]` 和闲逛 / 休息重启恢复通过。
单击 → 双击小窝 → 关闭重开 → 立即 40px 拖拽、反向阈值及松手无误触全部通过，
没有等待 TTL、删除断言或放宽心跳门槛。

startup 独立探针使用 MonitorStub / httpx.MockTransport（376ms 初始化延迟），只证明对应
启动 / 活动任务 / external-quit 契约；联合探针与截图才使用默认真实 monitor 读取受控日志。
110 / 1555 token、明确完成信号和 KNOWN 只代表受控日志契约，不是用户用量、任务成功或厂商余额。

## 原生截图供主轨审阅

目录：`C:/Users/DW/AppData/Local/Temp/mcpet-panel-integration-screenshots-95da07cd093a4787ab93e091f98cda48/`。

- `home.png`：原角色、奶油底色、暖橙按钮、淡紫卡片，陪伴 / 休息 / 隐藏 / 安全退出。
- `sessions.png`：generic 工作 24%、待输入 UNKNOWN、过时结果 UNKNOWN，以及 1,555 token 夹具用量。
- `mcd.png`：只读查询、主动领取、下单/撤单入口、餐品份数和今日营养；没有实时查询数据。
- `settings.png`：MCP Token 不回填、明确清除、城市、展开的显式目录、重启与批量覆盖提示。

四张均为真实 `panel.grab()`，不是网页 / HTML 截图；已用 view_image 查看。
没有会话输入框或模型 / 偏好记忆入口；样式与最终人工接受仍由主轨审阅。
截图 probe 返回 worker_stopped=true 且解释器自然退出；真实 spawn 的 PID 回收另由联合测试确认。

## 首失败保留与单列绿色证据

本集成轮首次完整、联合和截图运行均通过，无新增 RED，也没有返修后重跑冒充首轮绿。
原 C 的首失败完整保留在 `HANDOFF-C-PANEL.md`：

- 首次针对性运行卡在真实 `QMenu.exec`；原 C 用正确 popup 事件循环返修后 32 PASS。
- 首原生截图 DPR=2.25（scale=1.5 与系统 1.5 相乘），exit 1；原 C 改 scale=1 后 DPR1.5 green。
- 首完整 1 failed / 313 passed / 31.25s，心跳349.26ms；独立复测381.51ms。
  原 C 移除按钮装饰符号后最终完整315 PASS /32.56s、适用66 PASS /20.54s，是单独的返修证据。
  原 C 关于字体回退的说明仍是推断，没有原生字体栈采样。

以上是 **原 C 提供的历史证据**，不冒领为本集成执行。原 A 48 PASS /6.47s 同样来自
`HANDOFF-A-PANEL-HINT.md`。上一轮触摸 TTL 首失败与返修记录继续保留在
`HANDOFF-INTEGRATION.md` / `HANDOFF-A.md`，本轮未改写。

## 复现环境与边界

```powershell
$panelPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:MCPET_DATA_DIR = Join-Path $env:TEMP ('mcpet-panel-integration-' + [guid]::NewGuid().ToString('N'))
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:MCPET_WATCH_PROCESSES = '0'
$env:MCPET_AGENT_ROOTS = "claude=$env:MCPET_DATA_DIR/absent-claude,codex=$env:MCPET_DATA_DIR/absent-codex,generic=$env:MCPET_DATA_DIR/absent-generic"
$env:MCPET_CONFIG_PATH = Join-Path $env:MCPET_DATA_DIR 'absent-config.json'
& $panelPython -m pytest -q
& $panelPython -m compileall -q src tests
git diff --check
& $panelPython -m pytest tests/test_companion_integration.py -q -s
# 三个 startup 模式各换一个 TEMP 数据目录：
& $panelPython tests/test_main_startup.py --qt-smoke normal
& $panelPython tests/test_main_startup.py --qt-smoke active
& $panelPython tests/test_main_startup.py --qt-smoke external-quit
# 使用新目录，脚本内部隔离 data / inbox 并硬拒绝网络：
$panelShots = Join-Path $env:TEMP ('mcpet-panel-shots-' + [guid]::NewGuid().ToString('N'))
& $panelPython tests/test_companion_panel.py --screenshots $panelShots
```

未执行：17GB 冷扫描、动画10秒bench（动画未改，按指令不重复）、用户真实日志/聊天、
模型/MCP网络、账号写操作、真实订单/支付/余额验收。未启动常驻用户实例、打包/发布/PR，
不合回 root，不删除 worktree。主轨随后 FF 最终分支、审阅截图并优雅切换新版用户实例。
本面板只读观测日志，不提供原会话输入、打开或控制 API；轮询 / stale / UNKNOWN 限制保留。
物理多屏、长期运行、休眠及全产品人工接受仍未在本轮确认。

交接通知使用 [orca-cli](C:/Users/DW/.agents/skills/orca-cli/SKILL.md)，目标 root terminal
`term_0dcc55fd-ccc4-4567-be46-3d441ca0ec24`；输入接受不等于主轨已 FF 或新版已启动。

## 追加：最小化恢复返修集成（2026-10-12）

恢复同一集成 worktree / branch，起始干净，HEAD=`ea32a40cfab4a38f1b712adc650ac94177053058`。
读取 root 最新 SESSION-PANEL-PLAN 实际启动补遗，fetch 前用 ls-remote 核对 root / C tip 一致。

| 操作 | 输入 tip | 本集成分支结果 SHA |
|---|---|---|
| `git merge --ff-only` root | `64b7b87b51dc14ba5ec4df1e4c1ce197cf71b9aa` | `64b7b87b51dc14ba5ec4df1e4c1ce197cf71b9aa` |
| `git merge --no-ff --no-edit` C 返修 final | `9d9101281a5bafe008f3d7e162f53977fae49d2e` | `3507dcaa5008c6e5f9a460a0d02ead2b8c58fe47` |

无冲突，保留实现 `4acf2fb0f073131a1c65cb78f30b20193df75f66` 及原历史。main 仅在统一
`action_panel` 中判断 isMinimized，最小化则 showNormal，否则继续 show，再沿用 raise / activate。
没有强制还原普通最大化窗口；集成无需胶水，没有修改领域或测试断言，仅追加本节。
本节 commit + push 后的最终 tip 由通知提供，可用本文件最后一条 git log 核对。

### 首失败界限与新 GREEN

此前本集成 315 green 保持原文，只覆盖当时受控路径，不抹掉主轨实际启动 RED：正常启动
新版后右键 / 第二实例未恢复最小化小窝，日志0错误，IsIconic=true、逻辑边界在 -21333。
该实际失败和 C 本地首 RED **1 failed /4.97s**（duplicate 入口仍 minimized / iconic，
原生物理边界 `[-32000,-32000,-31763,-31961]`）均由原 C 追加在 HANDOFF-C-PANEL。
C 修复后适用70 PASS /23.53s、完整319 PASS /33.90s 属 **原 C 独立证据**，不冒领为本集成执行。
主轨已通过退出菜单优雅关闭旧用户实例及其子进程，是用户提供的操作结果；本集成没有操作它们。

本集成轮首完整、独立联合均通过，无新增 RED；以下结果单列，未改历史315 green：

| 验证 | 实际命令 / 结果 |
|---|---|
| 首完整 | `python -m pytest -q`：**319 passed /37.99s，exit 0，无 skip、无 warning**；windows、QT_SCALE_FACTOR=1；包含 normal / active / external-quit startup 三种适用测试 |
| 编译 / 格式 | `python -m compileall -q src tests`、`git diff --check`：exit 0 |
| 独立 Windows 联合 | `python -m pytest tests/test_companion_integration.py -q -s`：**1 passed /9.51s，exit 0**；真实 Qt / 默认真实 monitor / 受控 generic logs |

原生联合实际数据：先确认 minimized=true、iconic=true、visible=true、native_visible=true，
rect=`[-32000,-32000,-31763,-31961]`。随后 **duplicate / tray / right-menu / double-click**
四入口均为 minimized=false、iconic=false、visible=true、native_visible=true，
rect=`[1695,419,2557,1525]`；原测试同时断言同一 panel 复用及 Qt frameGeometry 与工作区相交。
duplicate 是真正第二进程 / QLocalServer 激活，tray 是实际 Qt activated signal，right-menu
是实际 popup / QAction，double-click 是 Qt 鼠标事件；Win32 只读检查探针自有 HWND。

auto_start=true、working=true、gestures=true；progress_signals=4、usage_signals=4、completed=1、
usage_tokens=110；heartbeat_ticks=**479**、max_tick_gap_ms=**114.23 <150**；
panel_open_ms=**[100.26,8.16,1.63,10.58,7.53,5.4,5.1]**；
stop_ms=**3.5974 <50**、thread_running=false、errors=[]。
两个真实 spawn 子 PID **55072 /56752**，writer_count=1；外层 Win32 PID 检查确认退出回收。
原触摸 / 即时拖拽 / 方向 / 休息 / 位置持久化与重开断言继续通过；没有等 TTL、删断言、
放宽心跳 / stop 或强制 Win32 显示绕过应用路径。

实际运行环境与命令（两次 pytest 各用新 TEMP 目录）：

```powershell
$panelPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:MCPET_DATA_DIR = Join-Path $env:TEMP ('mcpet-minimize-integration-' + [guid]::NewGuid().ToString('N'))
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:MCPET_WATCH_PROCESSES = '0'
$env:MCPET_AGENT_ROOTS = "claude=$env:MCPET_DATA_DIR/absent-claude,codex=$env:MCPET_DATA_DIR/absent-codex,generic=$env:MCPET_DATA_DIR/absent-generic"
$env:MCPET_CONFIG_PATH = Join-Path $env:MCPET_DATA_DIR 'absent-config.json'
& $panelPython -m pytest -q
& $panelPython -m compileall -q src tests
git diff --check
# 独立联合验证重新分配以上 TEMP 数据目录及 roots：
& $panelPython -m pytest tests/test_companion_integration.py -q -s
```

应用夹具禁用 dotenv，配置测试用内存读取替身；源 roots 均为受控 TEMP / 不存在目录。
没有读用户 .env / 凭证 / 既有聊天 / 真实 root，没有真实模型 / MCP / 账号写请求；
110 token / 完成信号是契约日志，不等于用户实际用量 / 任务成功。
UI 样式和动画未改，按指令不重复截图 /10sbench /17GB扫描；startup 三种模式已包含在全套，
没有另启动常驻实例或合回 root。本轮 green 证明隔离原生 Qt 恢复路径，用户实例重启后
右键 / 托盘 / 第二实例的实际验收仍由主轨随后完成，整体产品限制保持。
