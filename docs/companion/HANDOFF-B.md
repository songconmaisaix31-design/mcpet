# B 轨交接：数据、后台运行时与麦当劳领域

分支：`songconmaisaix31-design/mcpet-data-20261011`。Worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-data-20261011`。任务规划代码基线 `48014681c10dabfecff0104fdb0676f271e21f09`；本 Worktree 起点 `6109eab4a767ec7a8ef46a7b0580aa538e381327`（增加 PLAN，未修改业务代码）。仅修改 PLAN 的 B write_paths，未派 Agent、未改 main/config/pet/llm/skill/client/其他轨测试，未集成。

代码阶段提交（已 push）：

- `d4ff7b82fac88ad5cb79543e63fb400db49a808f`：标准 spawn 后台进程、流式扫描、真实完成事件、上下文上限、计价可信度和运行时测试。
- `d65ff7e699e65f66c7a0b0d0f55cbba3c6349cd6`：未营业/无门店和业务错误传播、合法算价、选定餐品份数记账。
- `a460ce08394264df1e023cc01d05cb2b5afcb5e3`：持久化 Codex 游标处的模型证据，避免增量/重启使用文件头旧模型。

交付文档另有提交；最终交付 SHA 取本分支 `git rev-parse HEAD`，由完成通知同时提供。合并应取分支最终 tip，保留以上普通历史。

## 实现与 C 轨接口

`src.runtime.monitor.AgentMonitor(QObject)` 保持 PLAN 四信号四方法：

- `progress_ready(object)`：`ProgressSnapshot`。
- `usage_ready(object)`：`(UsageSnapshot, projected, sample_ok)`，没有加入第四个 tuple 项。
- `failed(str)`：明确失败；`first_failure` 保留首条，后续成功不会清掉它。
- `task_completed(object)`：`ProgressRecord`，包含 `completed_at`、`completion_id`。仅观察到明确完成证据后发出。
- `start()`、`stop()`、`refresh_progress()`、`refresh_usage()`。

构造可选参数全部有默认值：`parent=None`、`roots=None`、`state_path=None`、`pricing_override=None`、`progress_interval=10.0`、`usage_interval=60.0`（秒）、`window_hours=None`、`stale_minutes=None`、`max_sessions=12`、`watch_processes=None`。默认根仍按现有配置/环境变量/平台候选解析，遵守 `config.agent_config_path()`，没有增加其他 Orca 账户目录。公开 generic 接入继续兼容，并接受显式 `kind: task_complete`；generic 明确声明的 `state: done/complete/completed/task_complete` 也属于完成证据。

```python
# 必须在 QApplication 已创建之后构造；整个应用只持有一个 monitor。
from src.runtime.monitor import AgentMonitor

self.monitor = AgentMonitor(self.app)
self.monitor.progress_ready.connect(self.on_progress_snapshot)
self.monitor.usage_ready.connect(self.on_usage_snapshot)
self.monitor.failed.connect(self.show_observation_error)
self.monitor.task_completed.connect(self.on_confirmed_task_completion)
self.monitor.start()

def on_usage_snapshot(self, payload):
    snapshot, projected, sample_ok = payload
    # snapshot.status 为 UNKNOWN 时如实显示；sample_ok=False 时不展示外推结论。
    # 数值只代表本机日志，不能展示为厂商余额。

def quit(self):
    self.monitor.stop()  # 立即返回，不 join、不 wait Future、不 shutdown executor。
    self.app.quit()
```

进度与用量各一个标准 `multiprocessing.get_context('spawn').Process`，用量只有一个持久 `UsageMeter` owner，所有 `usage.json` 写入串行。桥接线程只负责 IPC、spawn 和回收；GUI 不做 pipe recv、scan、join 或 Future wait。定时刷新每类最多一个 pending，忙时新请求合并，不无限排队。`start` 幂等；`stop` 幂等且终结实例，停止后重新启动需新建实例，并等待旧实例进程已退出后再写同一台账。应用退出已接 `QCoreApplication.aboutToQuit`。

退出审阅后的桥接线程是 **non-daemon**：GUI stop 只设置标记/停计时器，桥线程通知子进程协作退出；后台 `join(timeout=1)`，必要时 `terminate()` 再 `join(timeout=2)`。解释器正常退出会等有限回收，不在 daemon 桥尚未清理时直接消失。独立主进程退出测试故意不 join、不继续 pump Qt，见验证。

`last_progress`、`last_usage` 留存最后成功快照。数据源读取错误通过 `failed` 发出，错误轮不发 ready 覆盖成功缓存；C 应显示当前观测 UNKNOWN/错误，而非把缓存当作当前成功。空数据会正常发出 status=UNKNOWN 的快照。调用前与扫描中止时不会生成假完成。首次历史完成快照不庆祝；旧完成事件和重复轮询不庆祝；只发 monitor 启动以后新观察到的完成事件。不要从 stale、无更新、进程退出或 `agent_message` 推导成功，也不要用旧会话的 done 基态代替 `task_completed` 驱动庆祝。

`ProgressRecord.context_limit_estimated` 新字段有默认值。Codex 优先使用正整数、非 bool 的 `info.model_context_window`；实测审阅样本 `81918 input / 258400 limit` 显示 32%，cached `81280` 属输入子集，usage 总量仍为 input+output。旧启发式上限会在气泡/详细报告说明估算，不能宣称实测容量。

## 流式扫描、台账与营养

JSONL 使用完整行流式解析，批次上限 256 行或约 1 MiB（单行可能更大），冻结每个文件本轮大小，避免持续追加无限延长扫描。末尾半行不消费，偏移保持在最后完整换行；offset 是原始字节偏移，UTF-8 不改变它。`read_from_offset` 原有 `(rows, offset)` 接口仍可用，生产 provider 使用 `iter_offset_batches`，不整段 read，不 `list(provider.iter_usage(...))`。generic 追加进度在持久进程中增量续读，快照覆盖写法仍兼容。

保留原有截断重读、Codex 文件位置键、Claude/generic 稳定键、逐分量最大快照和正增量修正语义。截断文件仅首个批次重置文件位置去重键，批次/增量不重复计数。稳定键不再三天后丢弃，避免历史消息复制或迟到修正重计；代价是去重状态随真实日志历史增长。游标与当前模型证据一并原子落盘，重启后继续正确归属切换后的模型。旧台账没有游标模型证据时用 UNKNOWN，而非猜成文件头模型。

`estimatedModels` / `unknownModels` 持久化；旧状态可从保留的按模型分日数据保守恢复可信度。既有历史金额不会因计价配置或模型证据补齐自动重算。损坏/未知 schema 的用量文件会报错并保留，不静默覆盖。写失败传播，旧原子文件保留；部分 provider 失败仍保留已消费批次的账与游标，并在 snapshot.errors/status 中明示不完整，diagnostics.firstFailure 保留首失败。此模块没有厂商余额/账单读取能力。

```python
# C 从真实 brain.nutrition() 的返回结果中让用户选定具体 fact，再记账。
entry = ledger.add_fact(selected_fact, quantity=selected_quantity)
```

`NutritionLedger.add_fact(fact, date=None, *, quantity=1)` 和 `LedgerEntry.from_fact` 兼容旧调用。合法份数为有限正数，拒绝 bool、0、负数、NaN/Infinity；准确乘每个营养分量，保留餐品名字、服务端 note、quantity，重启可读。旧记录无 quantity 时默认 1。营养文件用原子替换，写失败回滚本次内存 append；仍按账目条数报告 items（份数另存在 entry.quantity），不取营养表首项代替用户选择。

## 麦当劳错误语义与跨域交接

`StoreUnavailable(McpError)` 是新增领域异常。`resolve_default_store()` 无门店/全部未营业或状态 UNKNOWN 时抛明确异常；不会挑 closed 店，不为测试更换城市。配送门店也必须明确营业。保留既有函数名与参数，原先无门店返回 None 的路径按本次错误明确化要求改为异常，C 必须通过已有异常 UI 展示。

业务检查在 **brain** 中完成，未修改工具协议客户端。菜单、餐品详情、门店券、营养和 calculate-price 的 `success:false` 在 unwrap 前抛 `McpError`，保留服务器完整 message 和 code（含一元素数组壳/同时 is_error 的返回）。真实基线服务端 `600057: 门店可能已关闭或不在营业时间` 不能转换为空菜单，也不能用菜单 currentPrice 掩盖算价失败。

实付价按 calculate-price 的明确“分”单位解析：`"990.00"` 为 990 分；缺失、bool、负数、非有限数、非整数分都报 UNKNOWN。优先使用最终 price，再完整 productList 小计或其他明确实付字段；明确零价可以作为有效查询价，实际下单仍受既有 guard 限制。无券只返回不带 coupon 身份的无券报价；券必须同时有 id/code，有券算价失败传播，不伪装成无券或原价优惠。未验证到可降价的券时不标券价。

跨域需要 C 完成：

- 按以上错误路径显示真实原因/UNKNOWN，饭点纯汇报调用 `coupon_roundup(claim=False)`；账号写操作按 C 确认流程执行。
- 用量菜单也通过唯一 monitor；不要另建 meter 并发写相同 usage.json。failed 后缓存只代表最后一次成功。
- 只用 `task_completed` 驱动完成庆祝，并尊重 stale 与未知上下文；估算上限在详情中说明。
- 营养选择使用选定 fact 和 quantity，不使用第一项或模糊名字匹配自动记账。
- frozen Windows 打包入口需标准 `multiprocessing.freeze_support()`；普通 `python -m src.main` 的 guarded 入口已可 spawn。本轨不改 main。
- client/skill 原生工具调用的业务错误总体策略仍属其他写域；本轨只在 brain 修复，不宣称协议客户端全体调用都已成熟。真实查询验收与账号写操作留给主 Agent/C 授权流程。

以上接口已通过 Orca CLI 通知主 Agent，最终完成通知附本分支 tip。

## 首失败、复测与命令

Python 固定为 `C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。测试均隔离 `MCPET_DATA_DIR`，Qt offscreen。不读取/打印/复制 .env 凭证；无 live 模型请求、MCP 网络或账号写操作。旧基线真实 closed stores 的失败仍以主 Agent 已保存记录为准，本轨没有用离线 green 替换它。

| 阶段 | 结果与原始失败原因 |
|---|---|
| 修改前完整 pytest | 200 passed / 4.71s |
| 首轮 B 适用测试 | 120 passed / 4 failed / 0.77s |
| 首轮失败 1 | `test_resolve_default_store_returns_none_when_nothing`：`StoreUnavailable: 未查询到可用门店`；旧测试期待 None，与新错误明确化要求冲突。改为断言领域异常。 |
| 首轮失败 2–3 | `test_best_deal_pairs_coupon_by_product_code`、`test_best_deal_passes_both_coupon_id_and_code`：`McpError: 算价结果 UNKNOWN：响应不是价格对象`；两个候选只有一个餐品的两次价格样本，旧回退掩盖了缺失样本。补齐第二个餐品算价样本。 |
| 首轮失败 4 | `test_best_deal_falls_back_to_menu_price_when_pricing_fails`：`McpError: 门店已关闭` / code 600057；旧测试要求用菜单价掩盖真实算价失败。改为断言 message/code 传播。 |
| 新退出测试首轮 | 158 passed / 1 failed / 4.47s；`ModuleNotFoundError: No module named 'psutil'`，不属于运行时产品失败。改用标准库 active_children 和 Win32 进程句柄，没有新增依赖。 |
| 修复后适用测试 | 159 passed / 6.48s；增加 is_error 服务端事实回归后 160 passed / 5.73s。首失败保留于上方。 |
| 最终适用测试 | 161 passed / 5.80s（包含最新游标模型重启回归） |
| 最终完整 pytest | 237 passed / 9.17s（包含最新游标模型重启回归） |
| 标准编译 | `python -m compileall -q src tests` exit 0 |
| 格式检查 | `git diff --check` 通过；仓库 LF 规范的 CRLF 转换提示不是测试失败。 |

```powershell
$python = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:MCPET_DATA_DIR = Join-Path $env:TEMP 'mcpet-b-tests-final-20261011'
$env:PYTHONIOENCODING = 'utf-8'
$env:QT_QPA_PLATFORM = 'offscreen'
& $python -m pytest tests/test_agentbridge.py tests/test_metering.py tests/test_progress.py tests/test_brain.py tests/test_ledger.py tests/test_runtime_monitor.py -q
& $python -m pytest -q
& $python -m compileall -q src tests
git diff --check

# 真实日志冷扫描；必须是未用过的隔离目录，模块拒绝覆盖已有 usage.json。
$env:MCPET_DATA_DIR = Join-Path $env:TEMP ('mcpet-b-real-' + [guid]::NewGuid().ToString('N'))
& $python -m src.runtime.benchmark --deadline 120

# 在独立主进程中真实 spawn 后立即 stop，不等扫描或手动 join。
$env:PYTHONPATH = (Get-Location).Path
$env:MCPET_DATA_DIR = Join-Path $env:TEMP ('mcpet-b-exit-' + [guid]::NewGuid().ToString('N'))
& $python tests/test_runtime_monitor.py --real-exit
```

退出测试用外层 `subprocess.run(..., timeout=15)` 限时，并用 `OpenProcess(SYNCHRONIZE)` / `WaitForSingleObject` 验证子 PID 均已退出。真实默认日志立即 stop 实测：两个子进程，stop 0.0967 ms，外层主进程退出 1.728s，remaining_children=[]；不是等完 30 多秒冷扫描。pytest 中另有 64 MiB 冷 JSONL、主进程退出不 pump/join 的同类测试。

## 真实 Windows 扫描证据与限制

第一次只读真实扫描（对应 runtime 首阶段代码）：默认根仅 claude/codex，共 1,721 文件、6,291,458,491 字节。无错误；冷 ready 34.529s，增量 ready 1.279s；两次 lifetime tokens 同为 30,040,697,267，可信度模型数量也一致（家族估算 8 / 未知 3）。这不是厂商余额。

首次进度 ready 0.883s（包含 Windows spawn 启动），会话限额 12。60ms Qt 心跳 576 次，最大间隔 78.256ms；stop 0.005ms。100ms 采样工作集峰值：GUI 父进程 45.91 MiB，用量子进程 485.11 MiB，进度子进程 45.12 MiB。相较根基线 QThread 最大动画间隔 390ms、内存单次采样 763MiB，这是不同方法的观测：当前是 Qt 心跳与多次采样工作集，不能表述为完成画面帧验收或等价精确峰值比较。

最终代码 `a460ce08394264df1e023cc01d05cb2b5afcb5e3` 的只读真实扫描复测：仍为 1,721 文件、6,291,458,491 字节；errors=[]；冷 ready 33.132s、增量 ready 1.244s；两次 lifetime tokens 同为 30,040,697,267，家族估算 8 / 未知 3。首次进度 ready 0.614s。60ms Qt 心跳 554 次，最大间隔 78.095ms；stop 0.003ms。100ms 采样工作集最高值：GUI 父进程 46.11 MiB、进度子进程 44.75 MiB、用量子进程 503.48 MiB。观测方法与局限同上，不将只读后台证据提升为画面或 live MCP 完成结论。

限制：冷扫描仍需约半分钟，GUI 不等待它；JSONL 内存界为批次加最大单行，异常超大单行仍会占用内存。永久稳定键去重提高精确性，也使台账大小随历史增长；JSON 原子保存仍有成本。轮询只知道已落盘且在快照范围内的事件，可能漏过两次轮询之间完成又启动的轮次；不能宣称掌握全部 Agent 生命周期。文件大小没有变小的同路径原地重写不是现有游标协议可检测的截断，仍要求日志按公开规范追加。本轮未迁移到自研任务/调度/证明系统。

首失败不能被本机离线用例或后台数据成功覆盖。live MCP 修复后重验、真实营业菜单/算价、C/A 装配后的窗口交互/帧时序、人工接受、真实模型与账号写操作均未在 B 执行。B 完成 push 后停止，不合并其他轨。
