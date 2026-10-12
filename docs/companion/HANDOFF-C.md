# C 轨交接：应用入口、持续聊天、本机偏好与确认交互

分支：`songconmaisaix31-design/mcpet-app-20261011`。独立 Worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-app-20261011`。起点：`6109eab4a767ec7a8ef46a7b0580aa538e381327`。实现与回归提交（已 push）：`1e8d984b18c99debc68d9c0d9029c4e0f8e0d219`。此交接文档另有提交；合并应取分支最终 tip，最终 SHA 由完成通知提供。

仅修改 PLAN 的 C write_paths。没有改 window/states/spritesheet/brain/agentbridge/runtime/nutrition，没有派额外 Agent，没有 merge A/B，没有读取、复制或打印根 `.env` 凭证，没有 live 模型/MCP 调用、账号写操作、注册表或开机启动设置。A/B 尚不在本分支；接口使用兼容接线和测试 stub，不能把本轨绿色测试当作三轨集成或真实账号验收完成。

## 完成内容与用户操作

- 入口只建立一个长期 `SerialTasks` worker/QThread。MCP client 创建、initialize、所有 MCP 业务和 close 均在 worker 内串行；同 key 任务单飞，饭点两个读任务也排队。busy 在发出 worker 请求之前显示；失败初始化会关闭临时 client，不发布半初始化对象。入口将 MCP `max_retries_on_429=0`，关闭该客户端对网络失败/429的自动重试，防止账号写请求未知效果被重发。
- 退出停止调度、调用唯一 monitor.stop、丢弃未开始任务、拒绝新任务，GUI 继续处理事件直至当前请求与 worker cleanup 完成。没有 GUI QThread.wait/terminate。正常 QApplication.quit 通过 Quit 事件拦截进入同一路径。最后使用 `window.close()` 触发 A 的 closeEvent，保存最终位置、停 timer/关闭气泡；没有保留旧 clicked→营养接线，不覆盖 A 的触摸反馈。
- 单实例使用 Qt QLockFile + QLocalServer。锁在窗口、联网和 monitor 构造前取得；第二实例只唤醒原窗口并退出，不构造 pet/tasks/monitor。以用户数据目录为隔离边界。GUI 结束时关 socket，锁通过 atexit 保持到 Python non-daemon 后台桥线程回收后，避免退出期间第二实例抢写 usage.json。没有自研调度或完成证明系统。
- “问麦麦”是真正持续的 Qt 聊天窗口。用户明确选择“日常陪伴（仅 StepFun）”或“麦当劳实时查询”；默认日常陪伴不初始化 MCP，不发送工具定义。实时查询复用真实 run_skill，只暴露已知读工具；未知工具、坏 JSON、未知字段和服务端业务失败不执行/不假装成功。实时模式没有实际工具结果时明确无法确认实时数据。pending、排队、失败和继续发送可见，关闭聊天再打开保留现场。
- 聊天存在 `MCPET_DATA_DIR/chat.json`：最多 40 条，每条最多 4000 字；发给模型的旧上下文最多 12000 字。主动偏好最多 30 条、每条 500 字。聊天窗口“查看 / 保存 / 清除偏好”允许用户自己填写、查看、删除单条或清空；不做模型画像提取，不扫描其他个人文件，不新增隐式模型请求。清除偏好与清除聊天是两个可见操作，UI 明示区别。重开恢复有界历史；最后用户消息无回复时说明可能被上次退出中断。落盘原子替换，清除写失败会回滚内存并展示错误。
- 右键与托盘均提供聊天/偏好、只读券汇报、主动领券、报价、下单/撤单、餐品份数记账、今日营养、详细进度/用量、闲逛、休息/唤醒、设置及退出。详情在 Qt 窗口显示，不再只打印 stdout。主动领取、下单、撤单先核对摘要并勾选确认。自动饭点只查询券与报价，不领券、不下单。
- 营养查询展示真实 facts 中的餐品列表和 0.25–20 份选择，明示所选餐品及乘份数后的营养。取消没有台账写入。优先调用 B 的 `ledger.add_fact(fact, quantity=...)`；在本分支旧 ledger 下仅使用所选 fact 的精确比例兼容，不取 facts[0]。
- 下单先只读取得价格/服务端外带选项和 create-order schema。确认 UI 展示门店、商品、券（无券也显示）、金额、外带方式及实际 payload。确认后立即消费候选，提交前再核对报价，价格变化则拒绝提交并要求重新查询/确认。直接使用经过 schema 校验的同一 payload；模型参数不能直接进入订单提交。复用 brain 的查询、payload 构造和 OrderGuard 的限额/审计。
- create-order 网络异常、未知格式或无订单号都保留 UNKNOWN，写 unknown 审计且不重试、不复用候选；提示去官方核对再重新查。明确订单成功后，支付窗口展示订单号，可打开/复制 HTTP(S) 支付链接；本机命令链接及含已知凭证的链接禁止打开/复制。已知服务端成功但本机审计失败仍保留订单号/支付窗口并明示审计失败，不能丢失已知结果。撤单同样人工确认，并区分服务端成功与本机审计更新失败。
- 设置是 Qt UI：凭证输入密码遮挡、既有凭证不回填、空输入保留、有单独清除选项；同时配置城市与 Claude/Codex/generic 显式 root。不存在目录明确提示，不创建、不扫描全 Orca accounts。保存到用户数据目录 `.env`，不写仓库或聊天记录。加载顺序：进程环境 > 用户数据目录 `.env` > 项目 `.env`；不展开 `${...}` 凭证文本。凭证下一请求生效，root 修改提示退出重启，绝不在旧 monitor 停机时创建第二个 monitor/meter。
- 所有外部文本和历史落盘通过已知 MCP Token/StepFun Key 脱敏；修复显式 StepFun key 的网络/HTTP 错误脱敏及无效工具参数标记。普通聊天、用户偏好没有额外模型画像请求。

## A/B 接口与集成注意

A tip（主 Agent 提供）：`5c96e7846f9ca06700938f98f826ea1a17c5285f`；B tip：`e4b761f7923482a61e0d7b1b6eac075c42d55893`。没有将这些提交合入本轨。

- A：连接 `chat_requested`；使用 `set_activity(state, context_percent=None, label='')`、`set_roaming`、`set_resting`、`roaming_enabled`、`resting`。未归还位置初始值，不再 main.move 固定位置。`show_menu` 传入无 None 的条目列表，兼容 A 接口。进度自动切换使用基态接口，临时状态/交互由 A 仲裁。
- B：延迟 import `src.runtime.monitor.AgentMonitor`，一个应用仅构造一次，接四信号、调用 start/stop/refresh_progress/refresh_usage。本分支未落地时明确显示“后台观测不可用”，没有创建替代 UsageMeter 或 GUI 冷扫描。目录配置保存后只提示重启。B 正常解释器退出的有限回收在集成后由主 Agent 验收。
- `progress_ready` 使用真实活跃 session 的状态、context_percent 和 label；stale/无数据不带上下文百分比，不推断成功。即使快照写 done，基态也不庆祝；只有 B.task_completed 事件庆祝。`getattr(record, 'context_limit_estimated', False)` 为 True 时 label 附“上下文上限估算”。没有任务百分比。
- `usage_ready` 解包恰好 `(snapshot, projected, sample_ok)`。sample 不足不展示外推结论；提醒用本机日志口径，不能称厂商余额。B 未返回 remaining，C 详情不伪造滚出时间。failed 保留最后成功快照并明示“可能已过时”；再次打开详情不会把失败缓存变成当前成功。
- `NutritionLedger.add_fact(fact,date=None,*,quantity=1)` 已兼容。`StoreUnavailable(McpError)` 与 B 的营业/算价/营养业务错误通过 worker 脱敏显示；不吞成默认餐品或菜单原价。
- C 为保证 exact payload/确认金额，订单装配使用 B 保留的 `brain._store_args`、`brain._item`、`take_way_options`、`quote_order`、`render_order_summary`，再执行已确认 create-order/guard.record。没有修改 brain 的签名；今后调整这两个构造助手需同步 main 的这一小段装配。
- 根目录入口通过既有 `MCPET_AGENT_ROOT_*` 环境配置，不改 B 的 resolver。`MCPET_AGENT_ROOTS` 进程变量仍按 B 规则优先，设置会提示覆盖关系。`MCPET_CONFIG_PATH` 及已有 config.json 语义未改。README/AGENT_BRIDGE 的旧自动领券、一次性聊天和第一项营养文案由集成者更新。
- 当前 Orca 账号 root 由用户提供：`C:/Users/DW/AppData/Roaming/orca/codex-accounts/2a305740-3098-46da-a63f-2d9e42ae9d72/home/sessions`。本轨未读这些日志、未重新计数，保留 UI 显式 root 供主 Agent 只读验收注入；不能从旧 `~/.codex/sessions` 或未设置的 CODEX_HOME 宣称当前数据。

## 验证命令、结果与首失败

Python 固定为 `C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。以下命令在本 Worktree 执行；网络均使用测试 fake/MockTransport，凭证仅测试字符串，测试启动明确禁用 load_env，不读根 `.env`。

```powershell
$env:MCPET_DATA_DIR = Join-Path (Get-Location) '.tmp-test-data/track-c-final'
$env:QT_QPA_PLATFORM = 'offscreen'
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -m pytest -q
# 最终完整结果：238 passed in 14.46s，exit 0。
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -m compileall -q src tests
# exit 0。
git diff --check
# exit 0。PowerShell 写入 main 的 CRLF 转 LF 提示不是失败。
```

适用集合包含 `test_main_startup/test_config/test_skill/test_stepfun/test_dialogs/test_chat/test_app_actions`。最终独立适用结果为 **63 passed in 12.47s，exit 0**；最终完整为 **238 PASS**。关键回归：worker initialize 非 GUI、只初始化一次/任务串行/重复单飞、UI 心跳、失败临时 client 关闭/脱敏后可再次初始化、队列退出丢弃未开始请求、普通聊天无 MCP/tools/额外画像调用、实时 Skill 读调用、聊天重开与记忆持久删除、失败清除回滚、营养第二项/小数份数/取消、完整订单摘要与取消、价格变化拒绝、三种 UNKNOWN 提交不重发、已知订单审计失败保留结果、支付打开/复制和敏感链接拒绝、触摸气泡不覆盖、closeEvent 立即位置保存契约。

```powershell
$env:MCPET_DATA_DIR = Join-Path (Get-Location) '.tmp-test-data/track-c-applicable'
$env:QT_QPA_PLATFORM = 'offscreen'
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -m pytest tests/test_main_startup.py tests/test_config.py tests/test_skill.py tests/test_stepfun.py tests/test_dialogs.py tests/test_chat.py tests/test_app_actions.py -q
# 63 passed in 12.47s，exit 0。
```

保留首轮扩展失败：

```powershell
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -m pytest tests/test_config.py tests/test_skill.py tests/test_stepfun.py tests/test_dialogs.py tests/test_chat.py tests/test_app_actions.py -q
# 3 failed, 48 passed in 1.37s，exit 1。
```

三个失败为 `test_confirmation_requires_checkbox_and_reject_means_no_write`、`test_food_ui_selects_actual_second_fact_and_fractional_quantity`、`test_settings_ui_keeps_secrets_masked_and_saves_local_file`。新测试错误地使用了实例 `dialog.Rejected/Accepted` 和 `edit.Password`，该 PySide6 版本只暴露类枚举。改成 `QDialog.Rejected/Accepted`、`QLineEdit.Password` 后通过；没有删测试，也不将后来完整绿覆盖为“首轮全绿”。其后中间完整结果为 234 PASS；最终新增写失败/实时 Skill/凭证字面重开回归后 238 PASS。

原生 Windows Qt 独立探针（可复现，不是 offscreen；monitor 为契约 stub，MCP 为 MockTransport）：

```powershell
$env:QT_QPA_PLATFORM = 'windows'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:MCPET_DATA_DIR = Join-Path (Get-Location) '.tmp-test-data/qt-normal'
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' tests/test_main_startup.py --qt-smoke normal
# 实际：qt_platform=windows, thread_running=false, init=0,
# heartbeat_ticks=19, max_tick_gap_ms=11.06，exit 0。
$env:MCPET_DATA_DIR = Join-Path (Get-Location) '.tmp-test-data/qt-active'
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' tests/test_main_startup.py --qt-smoke active
# 实际：qt_platform=windows, thread_running=false, init=1,
# heartbeat_ticks=45, max_tick_gap_ms=12.35，exit 0。
# initialize 注入延迟376ms，GUI仍有心跳；不是新的真实网络性能证据。
```

以下单项已由完整 pytest 调用，可独立复现：

```powershell
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -m pytest tests/test_main_startup.py::test_real_qt_start_and_safe_exit_subprocess -q
# normal / active / external-quit 三个子进程均 Windows Qt，exit 0、worker已停，无 QThread destroyed。
& 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe' -m pytest tests/test_main_startup.py::test_duplicate_launch_does_not_initialize_or_scan -q
# 第二实例 secondary=true, has_tasks=false, has_window=false；原实例退出后锁文件消失。
```

## 真实剩余限制与未执行操作

- 没有 live 模型、MCD 只读查询或当前 Orca 1956 文件日志验收。本轨所有网络与 monitor 数据效果都是 mock/契约证据；真实资产和 Qt/线程/单实例子进程是本机实际证据。主 Agent 已安排合并后的真实探针，C 不重复执行。
- 真实 A 的位置偏好/行为、真实 B 的冷扫描与退出桥线程尚未在 C 分支联合运行。C 的“移动后立即退出”回归真实触发 Qt closeEvent 并用持久化契约 stub 检查保存先于服务关闭；不是 A 偏好模块自身的集成验收。集成后应移动再立即退出，检查 pet-preferences.json 最后位置及重开位置。
- 凭证按既有 `.env` 方案在本机明文保存，尝试收为 0600；Windows chmod 不等于完整 NTFS ACL/系统凭证库，未宣称已验证独占 ACL。Key/Token 不进入聊天或仓库。外部环境变量仍具有最高优先级，外部变量覆盖本机配置属于公开加载规则。
- 退出必须等待已开始的网络请求安全结束；GUI不阻塞、不强杀线程。真实服务慢/超时可能延长整体退出时间，受 HTTP 超时及有限 Skill 轮数约束。强制杀进程/系统强制关机不属于已验证的优雅退出。
- 订单继续保留原“一份最优报价、到店外带”的业务范围，确认全部信息和实际 payload；没有新增自选多商品或配送地址写业务。模型其他写操作只显示待操作参数并引导明确菜单流程，不自主执行、不假装已执行。撤单仅本次运行已知订单；跨启动历史订单统计未新增。
- 未创建 PR、未 merge、未发布/打包；主 Agent/集成 owner 普通合并三轨最终 tip 后再做真实只读验收和文案更新。本 Worker 在文档提交并 push 后停止。
