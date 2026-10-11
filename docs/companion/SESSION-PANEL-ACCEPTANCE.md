# 会话辅助与统一小窝验收（2026-10-12）

最新用户要求：依托 Agent 会话，不设计独立聊天框，设置收进可爱的一个面板。
本记录对应 SESSION-PANEL-PLAN；上一轮 ACCEPTANCE.md 中的聊天实测是历史证据，
不是当前产品入口或继续要求。历史记录与首失败未改写。

## 完成内容与版本

- 双击、托盘、右键及第二实例激活复用唯一非模态“麦麦小窝”；陪伴、会话与本机用量、麦当劳、设置四页。
- 奶油底色、暖橙按钮、淡紫卡片与现有角色素材。移除应用的独立聊天、模型发送及偏好记忆入口；旧模块与历史数据保留。
- 自动 AgentMonitor、真实状态/上下文/UNKNOWN/过时、闲逛/休息/拖拽继续复用。日志上下文不是任务进度，用量不是厂商余额。
- 设置凭证掩码、不回填、留空保留及显式清除；目录修改提示重启，不启动第二个写入者。麦当劳确认、核价、营养份数和付款流程保留。
- 原 A 只修触摸气泡“双击打开麦麦小窝”；动画/手势未改。C 修复统一入口无法恢复最小化窗口的问题。

当前根分支：`codex/desktop-companion-20261011`。根仅维护计划与验收，无业务代码修改。

| 交付 | 精确 SHA |
|---|---|
| C 面板实现 | `4f1f8b9439889fddb1d10b37e1b1e9d9e05c718c` |
| C 首交付 tip / 普通 merge | `58fbfd03118a08ceacea95e2fd0779654b051671` / `7a01566526618a1d4e9bae22ba54ff0da1fce5ed` |
| A 提示交付 / 普通 merge | `6088ead001fc8ea97783758bab54477c2662ab38` / `15eb010cae2201cf7d779e00ba6da81485bd729b` |
| 首集成 tip，根已 FF | `ea32a40cfab4a38f1b712adc650ac94177053058` |
| C 最小化恢复实现 / 最终 tip | `4acf2fb0f073131a1c65cb78f30b20193df75f66` / `9d9101281a5bafe008f3d7e162f53977fae49d2e` |
| 返修普通 merge | `3507dcaa5008c6e5f9a460a0d02ead2b8c58fe47` |
| 最终集成 tip，根已 FF | `7a828d0e943a7881e1a5b220b665f1445cd593e1` |

所有轨道沿用原 Worker / Worktree / Branch，远端 tip 已核对，普通合并，无 reset / force / 删除贡献。
最终根验收提交可用 `git log -1 --format=%H -- docs/companion/SESSION-PANEL-ACCEPTANCE.md` 查得。

## 验证结果

固定 WorkBuddy Python：`C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。
以下测试由原 C 与原唯一集成 Worker 在隔离 TEMP / 受控日志执行，主轨审阅交接与截图并 FF。
命令环境、首失败与数据分别见 HANDOFF-C-PANEL.md、HANDOFF-INTEGRATION-PANEL.md。

| 最终集成验证 | 结果 |
|---|---|
| `python -m pytest -q` | **319 passed /37.99s**，无 skip/warning，包含三种 startup 模式 |
| `python -m compileall -q src tests` | exit 0 |
| `git diff --check` | exit 0；主轨 FF 后也通过 |
| `python -m pytest tests/test_companion_integration.py -q -s` | **1 passed /9.51s**，真实 Windows Qt/default monitor/受控日志 |

联合探针四入口从实际最小化恢复同一窗口；Qt 与 Win32 IsIconic/visible/工作区断言通过。
原触摸后立即拖拽、TTL、唯一 writer、重复实例、位置及休息/闲逛恢复、退出回收断言保留。
479 次心跳，最大 **114.23ms <150**；首次小窝打开 **100.26ms**；quit **3.5974ms <50**；
两个 spawn 子进程回收。110 token 与明确完成信号来自受控日志，不能据此推断用户任务或余额。
样式截图为真实 Qt DPR1.5，network_calls=0，worker_stopped=true；主轨已审阅四页及集成设置页。
本机截图目录：`C:/Users/DW/AppData/Local/Temp/mcpet-panel-20261012-delivery/` 和
`C:/Users/DW/AppData/Local/Temp/mcpet-panel-integration-screenshots-95da07cd093a4787ab93e091f98cda48/`。

## 实际启动首失败与返修后复验

主轨先优雅退出旧版本 PID54728/44204 及监控4140/55172；退出菜单后的进程检查均已回收。
首集成实际启动 GUI17912/launcher53316/监控51320/56516；日志无错误，但小窝窗口已最小化，
右键与第二实例未恢复。Win32 HWND11079244 title=麦麦小窝、visible=true、IsIconic=true、
DPI 逻辑 rect=(-21333,-21333,-21175,-21307)。透明窗口自动双击当时没有可靠确认，不冒称通过。
C 的原生回归先复现 **1 failed /4.97s**，再修 showNormal；该 RED 与历史315 green单列保留。
原 C 的 QMenu 超时、DPR2.25、心跳349.26ms/381.51ms首失败也保留在其交接中。
删除按钮装饰符号后耗时改善支持字体回退的推断，没有原生字体栈采样，不称已证明根因。

主轨通过旧实例退出菜单关闭17912及上述launcher/监控，确认均回收；未强制杀其他进程。
FF 最终集成后使用相同 Pythonw / 工作目录启动；日志：
`.tmp-test-data/launch-panel-fixed-20261012-011348/`，stdout/stderr检查均0字节。
当前 launcher **38676**、GUI **49784**，Responding=true；默认监控子 PID **23860/48728**。
从应用本身的第二实例激活小窝，激活进程48016 exit0；未手动调用Win32显示/恢复操作。
只读 Win32 复验 HWND10489284：title=麦麦小窝、visible=true、IsIconic=false，
DPI 逻辑 rect=[415,0,990,737]，已回到屏幕；仍仅两个监控子进程，GUI日志无错误。
Orca UIA list-windows 对 owned 面板的列举有限，实际窗口状态由上述只读检查补证。
新版保持运行供用户操作；双击或右键打开小窝。此为启动/恢复验收，不是长时间人工体验完成。

## 真实限制和未执行操作

- 只读观测日志，尚无向原 Agent 会话发送消息、打开会话或控制任务的接口；轮询有10/60秒滞后。
- 原约17.4GB历史日志冷回填约182秒、用量进程约2.01GiB/持久JSON约764MB的限制仍存在；本次未重复冷扫描或性能基准。
- 本轮未重新进行模型/MCP实时网络验收；真实营业报价、领券、下单、撤单、付款及厂商余额仍未验收。此前真实闭店/查询证据保持历史适用范围。
- 多屏热拔插、休眠、长期运行、全产品人工体验和安装包/签名/自动更新未完成；未开机启动、创建PR或合入公共主分支。
- 本轮原 C/集成测试未读用户凭证/旧聊天/真实根；最终正常用户启动沿用本机配置及默认日志监控，未主动执行账号写操作或发送聊天。
