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
