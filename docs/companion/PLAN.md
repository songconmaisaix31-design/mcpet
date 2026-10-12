# AI 桌宠成熟化：本轮开发计划

基线：`48014681c10dabfecff0104fdb0676f271e21f09`，集成目标分支 `codex/desktop-companion-20261011`。用户要求同时覆盖开发陪伴、日常陪伴、麦当劳助手，并核查原项目画面复用和抽搐。保持 Python/PySide6/httpx 技术栈，复用现有真实 MCP、Agent provider、用量和营养台账；本轮不换引擎或生成新形象。

验收：启动/退出稳定；图集切片与播放时序正确，拖拽有阈值和方向稳定性；触摸、双击聊天、闲逛/休息可用；位置和选项跨启动保留；真实日志自动驱动状态和上下文显示；冷回填与联网不阻塞 UI；连续聊天与可查看/清除的本机记忆；营养选择真实餐品；营业状态错误明确；账号写操作需确认；适用测试、编译、真实 Qt、现有凭证的只读网络路径通过，保留首轮失败与未覆盖限制。

## 固定开发轨与写域

| 轨 | Agent / Worktree / Branch | write_paths | 责任 |
|---|---|---|---|
| A 画面与宠物行为 | 一个固定 Worker；Orca child `mcpet-pet-20261011` | `src/pet/window.py`, `src/pet/states.py`, `src/pet/spritesheet.py`, `src/pet/behavior.py`, `src/pet/preferences.py`, `tests/test_window_render.py`, `tests/test_states.py`, `tests/test_spritesheet.py`, `tests/test_pet_behavior.py`, `scripts/bench_render.py`, `docs/companion/HANDOFF-A.md` | 图集/播放核查、抗抖拖拽、触摸、闲逛、休息、位置保存、上下文控件 |
| B 数据与后台运行时 | 一个固定 Worker；Orca child `mcpet-data-20261011` | `src/agentbridge/**`, `src/metering/**`, `src/progress/**`, `src/runtime/**`, `src/mcd_mcp/brain.py`, `src/nutrition/**`, `tests/test_agentbridge.py`, `tests/test_metering.py`, `tests/test_progress.py`, `tests/test_brain.py`, `tests/test_ledger.py`, `tests/test_runtime_monitor.py`, `docs/companion/HANDOFF-B.md` | 冷扫描内存/后台进程、自动观测、真实生命周期、未营业错误、计量诚实口径 |
| C 应用与聊天 | 一个固定 Worker；Orca child `mcpet-app-20261011` | `src/main.py`, `src/config.py`, `src/pet/dialogs.py`, `src/pet/tray.py`, `src/chat/**`, `src/llm/**`, `src/mcd_mcp/skill.py`, `tests/test_main_startup.py`, `tests/test_config.py`, `tests/test_skill.py`, `tests/test_stepfun.py`, `tests/test_chat.py`, `tests/test_app_actions.py`, `tests/test_dialogs.py`, `docs/companion/HANDOFF-C.md` | 应用唯一装配者；异步联网、任务串行、自动联动、聊天/记忆、菜单、营养选择、写操作确认、安全退出 |

各 Worker 在自己的 write_paths 持续实现、测试、返修，完成 commit + push。可读取全仓与根仓库的 `.tmp-test-data/references`，不得修改其他轨文件，不读取/打印/提交凭证，不自行启动账号写操作。跨轨问题写各自 Handoff 并通知主 Agent。

## 内部接口约定

- A：保留 `PetWindow` 现有接口，新增 `chat_requested` 信号、`set_activity(state, context_percent=None, label='')`、`set_roaming(enabled)`、`set_resting(enabled)`，以及 `roaming_enabled` / `resting` 可读属性。`set_activity` 更新后台基态/上下文显示，不能每次轮询重置动画或打断前台交互。触摸是单击，拖拽松手不触发点击，双击打开聊天。未知上下文不生成百分比。窗口行为与位置在独立本机偏好文件保存。
- B：`src.runtime.monitor.AgentMonitor(QObject)`，信号 `progress_ready(object)`（现有 `ProgressSnapshot`）、`usage_ready(object)`（`(UsageSnapshot, projected, sample_ok)`）、`failed(str)`、`task_completed(object)`（仅明确完成事件）；方法 `start()`, `stop()`, `refresh_progress()`, `refresh_usage()`。使用标准后台进程/执行器隔离 CPU 扫描，不能在 GUI 线程等待 Future 或 shutdown；定时任务不重入，保留最后成功快照并显式失败。没有证据不能把不活跃或停止推为成功。
- C：独占 `src/main.py` 装配 A/B 接口；需要跨域调整先 Handoff。普通聊天不强依赖 MCP Token，餐品/价格仍走真实 MCP；用有界本机历史与用户明确保存的记忆，不隐式采集其他文件。读请求和写请求区分；下单/撤单/领券进入确认流程。聊天 UI、详细进度/用量、设置应对普通用户可操作。

## 集成与证据

全部轨完成后派发一个集成 Agent，在新 Worktree 普通 merge 三轨；只补路由、导入、配置、类型胶水，领域失败退回原 Worker。主 Agent 只维护计划、调研、状态、决策、验收；不写业务代码。最终集成分支 push，不 force push，不删其他 Worktree/历史。

初始事实：现有 `CREDITS.md` 明示窗口播放器是重写，CeTaPet 单状态 PNG 不能直接作为 spritesheet 播放器复用；CeTaPet 原实现有拖拽阈值、状态暂停/恢复、位置保存。当前 McPet 缺少这些完整语义。longniang 原仓库本次查询/clone 不可达，不能声称审阅到其原播放器。上次真实验证发现用量冷回填 38.8 秒并有 390 ms 动画间隔、MCP 同步初始化约 376 ms 动画间隔。

## 本轮交付状态（2026-10-12）

A 最终 tip `0c329d9c98d5086ea4c9e0e82a1b45c1b9fa222c`（含集成发现的手势优先级返修），B `e4b761f7923482a61e0d7b1b6eac075c42d55893`，C `703eae4bd02de17eb90a8f1a8f93a2130bc5bb67`。三轨完成、push、停止；唯一集成者普通 merge，并推送最终 `2885fa87f3eade21578b058e06a92bc78e697ed4` 后停止。主分支 `codex/desktop-companion-20261011` 已快进接受，无业务代码由主 Agent 编写。没有 force push、删除工作树或覆盖历史。

集成完整 Windows Qt 测试 313 PASS，编译与差异检查通过，原 RED 联合流程修复后通过；主轨真实开发日志/连续聊天/只读券/真实营养/闭店错误验收已执行。最终证据及首失败见 [ACCEPTANCE.md](ACCEPTANCE.md)。三类核心实现已交付；大历史日志的内存/回填性能、真实营业报价/订单/支付、多屏热插拔与长期人工观感仍有限制或未验收。本轮没有发布安装包、设置开机启动或执行账号写操作。
