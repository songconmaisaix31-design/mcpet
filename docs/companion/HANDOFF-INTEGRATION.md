# 唯一集成 Agent 交接

日期：2026-10-12。Worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-companion-integration-20261011`。
分支：`songconmaisaix31-design/mcpet-companion-integration-20261011`。
保持 Python / PySide6 / httpx；没有派 Agent、重写领域或合回 root，没有删除工作树。

## Git lineage 与变更

开始时工作树干净；`git ls-remote --heads origin` 核对四个指定远端 tip 完全一致，再 fetch。
所有合并使用 `git merge --no-ff --no-edit <tip>`，没有 squash / cherry-pick / force / reset。

| 顺序 | 远端输入 tip | 本集成分支 merge SHA |
|---|---|---|
| 基础 | `696a063b015f9262c50ac3a06d65ae08c5e181f7` | 起点 |
| A | `5c96e7846f9ca06700938f98f826ea1a17c5285f` | `0a8072370fc2bb4d1e7b40ac98047009a66bd385` |
| B | `e4b761f7923482a61e0d7b1b6eac075c42d55893` | `c5d9f418b7005df2d12e3437c561f1e1dbe60b18` |
| C | `703eae4bd02de17eb90a8f1a8f93a2130bc5bb67` | `647b8114b2e951343dc5db29ef4eeda822323f02` |
| 原 A 返修 | `0c329d9c98d5086ea4c9e0e82a1b45c1b9fa222c` | `2065b5852c4efdcbd2cb11591eca2260282ade37` |

三次无冲突；读取 `HANDOFF-A/B/C.md`，检查 C 已接上 A 手势/活动/偏好接口及 B 唯一 monitor。
无需集成业务胶水修改；领域问题交主 Agent 由原 Worker 修复。

使用文档提交：`71aea375938e03ca360e434935ec9218ac8a47f1`。
联合测试提交：`a774f5040a871f212f412c0a2aa1ae11e685f46d`。本文单独提交，最终 tip
由交接通知提供；可用 `git log -1 --format=%H -- docs/companion/HANDOFF-INTEGRATION.md` 核对。
更新 README、MCP_INTEGRATION、AGENT_BRIDGE：单击摸摸/双击持续聊天、日常模式仅 StepFun、
主动偏好查看/清除、真实查询餐品与份数选择、自动饭点只读、账号写操作勾选确认、单实例、
自动后台观测/本机日志口径/显式当前 root/冷扫描等待。历史验证报告没有改写。
新增 `tests/test_companion_integration.py` 是原生 Qt + 默认真实 AgentMonitor + 隔离受控 generic
日志的联合契约测试；禁止模型/MCP 网络，禁用 `load_env`，三类 source root 都显式隔离。

## 首失败与独立验证

固定解释器 `C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。
所有测试使用 TEMP 下独立 `MCPET_DATA_DIR` 和 mock token/key；不触碰用户台账，
不读取/复制/打印用户 .env 或凭证，不扫描当前 17GB root，不重复主 Agent 的真实网络探针。

| 阶段 | 命令 / 结果 |
|---|---|
| A/B/C 首次合并完整测试 | `python -m pytest -q`：300 passed / 23.53s，exit 0；父进程 offscreen，startup 子进程为 Windows Qt |
| 新联合探针首失败 | `python -m pytest tests/test_companion_integration.py -q -s`：1 failed / 5.18s，exit 1；auto_start=true、working=true，后续手势断言失败，最初只有空 AssertionError；heartbeat 最大间隔 160.66ms |
| 仅增强诊断复跑 | 同命令：1 failed / 5.03s，exit 1；完整堆栈指向真实触摸后立即拖拽的 `machine.state == 'run-right'`；heartbeat 最大间隔 144.19ms |
| 独立 Windows Qt bench | `python scripts/bench_render.py 10`：DPR 1.5、124 帧、12.4fps、均值/中位 80.0ms、78.6..81.0ms、标准差 0.5ms、0 卡顿帧，exit 0 |
| 独立拖拽 benchmark | 120 次真实 Qt mouseMove、1px 反向噪声和后台状态更新：0.19ms/事件，8/8 动画帧出现，状态只切 run-right，松手后 0 clicked |
| 独立 main-startup normal | `python tests/test_main_startup.py --qt-smoke normal`：windows、thread_running=false、init=0、17 心跳、最大 10.91ms，exit 0 |
| 独立 main-startup active | `python tests/test_main_startup.py --qt-smoke active`：windows、thread_running=false、init=1、45 心跳、最大 10.87ms，exit 0 |
| 独立 main-startup external-quit | `python tests/test_main_startup.py --qt-smoke external-quit`：windows、thread_running=false、init=1、45 心跳、最大 10.80ms，exit 0 |
| 编译与格式（文档提交后） | `python -m compileall -q src tests` / `git diff --check`：exit 0 |

首失败责任为 A 的 `src/pet/window.py` / `src/pet/states.py`：触摸 greet 的前台 TTL 阻止
随后的 drag 跑动状态，移动发生但仍播放 greet。已用 `orca terminal send` 通知 root
`term_0dcc55fd-ccc4-4567-be46-3d441ca0ec24`；主 Agent 确认收到并交原 A Worker 返修。
没有等待 TTL、删断言或由集成者越界修复。首失败与原 Worker 首失败均保留，后续绿色单列。

独立 main-startup 探针使用 MonitorStub 和 httpx.MockTransport（376ms 初始化延迟注入），
不是新的真实模型/MCP 性能证据。新增联合测试使用真正 spawn monitor，属于受控日志契约；
不能作为用户真实任务完成或厂商余额证据。

## 返修合并与最终验证

收到原 A Worker 最终 tip 后重新 `git ls-remote --heads origin songconmaisaix31-design/mcpet-pet-20261011`
并 fetch，remote 与指定 `0c329d9c98d5086ea4c9e0e82a1b45c1b9fa222c` 完全一致。
普通 merge 无冲突，merge SHA 为 `2065b5852c4efdcbd2cb11591eca2260282ade37`，领域修复来自
原 A 的 `835df319613517d1dc7c6b8782a3f9a6f0385173`；集成者没有修改领域。
读取更新后的 HANDOFF-A；其本地首次 9 failed / 14 deselected / 1.25s、最终原 A 完整
237 passed / 8.43s 是 **A 提供的独立证据**，详见该文档，不冒领为集成测试。

| 修复后独立证据 | 命令 / 实际结果 |
|---|---|
| 原联合测试定向复跑 | `python -m pytest tests/test_companion_integration.py -q -s`：1 passed / 7.93s，exit 0；没有修改失败手势断言、等待 TTL 或仅清 greet |
| 最终完整测试 | `python -m pytest -q`：**313 passed / 37.25s，exit 0，无 skip、无 warning**；父进程及原生子进程均 Windows Qt |
| 最终编译与格式 | `python -m compileall -q src tests` / `git diff --check`：exit 0 |
| 返修后 Windows bench | `python scripts/bench_render.py 10`：DPR 1.5、124 帧、12.4fps、均值/中位 80.0ms、78.8..81.1ms、标准差 0.5ms、0 卡顿帧，exit 0 |
| 返修后拖拽 benchmark | 明确从未到期 greet 开始，120 次真实 Qt mouseMove：0.21ms/事件、8/8 帧、状态只切 run-right、0 clicked |
| 最终 normal | `python tests/test_main_startup.py --qt-smoke normal`：windows、thread_running=false、init=0、17 心跳、最大 12.40ms，exit 0 |
| 最终 active | `python tests/test_main_startup.py --qt-smoke active`：windows、thread_running=false、init=1、46 心跳、最大 10.99ms，exit 0 |
| 最终 external-quit | `python tests/test_main_startup.py --qt-smoke external-quit`：windows、thread_running=false、init=1、45 心跳、最大 10.92ms，exit 0 |

真实 monitor 联合定向输出：auto_start=true、working=true、gestures=true，progress_ready 4 次、
usage_ready 4 次、明确 completed 1 次，重复刷新没有再次庆祝。两个真实 spawn 子进程 PID
`44156` / `52132`，仅一个 `mcpet-usage` writer；重复 start、40 次重复刷新和第二实例启动
没有创建第二 writer。受控 usage 从 40 到 110 token，无重复计数。
退出时存在请求刷新及受控 250ms 串行任务，GUI quit 调用 8.83ms，结束后 QThread 已停止；
主解释器自然退出、外层 Win32 进程句柄检查证明这两个子 PID 均退出，无残留。
400 次 Qt 心跳、最大间隔 111.95ms，errors=[]。第二实例没有 window/tasks/monitor，
原实例退出后锁文件消失；即时移动退出的偏好为 `[170,140]`，重开真实应用恢复位置及闲逛/休息。
单击反馈、聊天双击关闭重开、触摸 TTL 内立即拖拽、反向阈值与松手无误触、C 的休息/唤醒
均在真实窗口验证；其余闲逛/边界/状态/图集等适用回归包含在最终完整测试中。

全部新增日志是受控 generic 契约，110 token 与明确完成信号不代表用户实际用量/任务完成。
没有把这条 green、原生启动或 benchmark 提升为本轮全产品验收。首轮 RED 保留在上表。

复现环境模板（每条独立探针换一个 TEMP 数据目录）：

```powershell
$petPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:MCPET_DATA_DIR = Join-Path $env:TEMP ('mcpet-integration-' + [guid]::NewGuid().ToString('N'))
$env:QT_QPA_PLATFORM = 'windows'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:PYTHONIOENCODING = 'utf-8'
$env:MCPET_AGENT_ROOTS = "claude=$env:MCPET_DATA_DIR/absent-claude,codex=$env:MCPET_DATA_DIR/absent-codex,generic=$env:MCPET_DATA_DIR/absent-generic"
$env:MCPET_CONFIG_PATH = Join-Path $env:MCPET_DATA_DIR 'absent-config.json'
& $petPython -m pytest tests/test_companion_integration.py -q -s
& $petPython -m pytest -q
& $petPython -m compileall -q src tests
git diff --check
& $petPython scripts/bench_render.py 10
& $petPython tests/test_main_startup.py --qt-smoke normal
& $petPython tests/test_main_startup.py --qt-smoke active
& $petPython tests/test_main_startup.py --qt-smoke external-quit
```

## 限制与未执行

- 本轮集成没有 live 模型/MCP 调用、领取/创建/撤销订单、付款链接打开或用户台账写入。
  真实订单/支付、厂商余额、用户实际任务完成、全产品验收均没有在此确认。
- 主 Agent 后续 FF 集成分支，并运行真实闭店错误、当前账号原生 GUI 冷扫描、连续真实聊天、
  真实营养等已准备的只读验收。本集成不合回 root，不创建 PR、不发布或打包、不删除工作树。
- 自动日志观测有轮询滞后，可能漏两次观测之间完成又开始的任务；上下文容量可能估算。
  冷扫描等待和内存随日志规模、最大单行和长期去重状态增长；不能用受控小日志推广 17GB 性能。
- 退出会等已开始的请求结束；本轮活动退出探针用受控任务/MockTransport，不证明所有真实
  网络超时及系统强杀场景。多屏热拔插、改 DPI、休眠、全屏/远程桌面和长期观感仍待人工验收。
- 休息使用现有 idle 动画，未新增角色/原创素材、语音、开机启动、历史订单统计或自动更新。
- 用于向 root 发送通知的技能：[orca-cli](C:/Users/DW/.agents/skills/orca-cli/SKILL.md)。
