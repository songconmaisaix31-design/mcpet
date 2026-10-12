# McPet 实际功能与卡顿检查（2026-10-11）

被测代码：`main` / `819c452`。本次只做验证与记录，没有修复业务代码。

## 结论

**复现账号余额首次回填期间的卡顿。** 空闲动画、增量余额查询和项目进度查询没有测到同等级卡顿。离线测试通过不能替代线上功能验收；本轮没有 MCP Token 和 StepFun Key，因此不把旧报告中的线上成功记录算作本轮通过。

## 环境与方法

- Windows，实际桌宠 PID 36740，由 WorkBuddy Python 环境启动。
- 验证解释器：`C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe`。
- 系统默认 `python` 为 3.13.13，缺少 PySide6；第一次 `python -m pytest -q` 在收集阶段出现 3 个 `ModuleNotFoundError: No module named 'PySide6'`。这是环境失败，保留该结果。切换桌宠解释器后的绿测是另一份结果。
- `orca computer` 检查现有窗口与右键菜单，实际选择「项目进度」，从后续可访问性树读到气泡：`12 个会话都停了，最近一个 1 天前。` 个别后续菜单操作遇到窗口 ID 失效，不将未断言的点击算作通过。
- 动画基准使用真实 `windows` Qt 平台；不是 offscreen 绘制。
- 另启动一个真实 `MonsterApp`，关闭饭点调度，用独立数据目录执行原有 `action_progress`、`action_balance`、`action_nutrition_summary`。读取默认配置的真实日志，不写日志源、不修改用户原有台账。
- 16 ms QTimer 记录 UI 心跳，80 ms 动画定时器记录帧间隔。动作耗时由开始到线程完成后的观察点计量，包含最多约 50 ms 的轮询粒度；营养摘要的 127 ms 是观察窗口，不是同步调用耗时。
- 默认数据源：Claude 7 个文件 / 3,809,021 bytes；Codex 1,714 个文件 / 6,287,649,470 bytes；合计 1,721 个文件、6,291,458,491 bytes。未把其他账号目录自动扩大加入扫描范围。
- 原始本机证据位于 `.tmp-test-data/runtime-check/`（Git 忽略，含日志与隔离台账）；入库报告只保留聚合结果。

## 实测结果

| 检查 | 本轮结果 |
|---|---|
| 离线测试 | **PASS**：200 passed in 5.79s |
| 导入与图集冒烟 | **PASS**：8×11 图集，192×208 单元，透明通道、状态映射校验通过 |
| 真实 Qt 程序构造 | 203.81 ms；这不是启动新 Python 进程到显示的总时间 |
| 空闲动画 10 秒 | **PASS**：125 帧 / 12.5 fps，间隔平均 80.0 ms，极值 78.5–81.1 ms，标准差 0.5 ms，超过目标 1.5 倍的间隔 0 次 |
| 拖拽状态模拟 | **PASS**：120 次相同跑动状态设置，8/8 动画帧均推进；每次 8.45 ms 包含脚本主动等待的 8 ms，不是纯渲染成本 |
| 项目进度 | **PASS（本机日志读取）**：首次 254.81 ms，重复 187.72 ms，动画最大间隔 81.40 ms |
| 账号余额首次回填 | **功能返回、性能 FAIL**：38,812.23 ms，动画最大间隔 389.81 ms，超过 120 ms 的动画间隔 29 次；心跳最大间隔 351.20 ms，超过 100 ms 共 19 次 |
| 账号余额第二次查询 | **PASS（本机增量路径）**：564.10 ms，动画最大间隔 80.53 ms，无超过 120 ms 的间隔 |
| 今日营养 | **PASS（空台账显示）**：独立台账正确显示「今天还没记账」，未记录虚构餐品 |
| 用量台账跨进程重开 | **PASS**：加载 23.74 ms；扫描 1,721 文件 / 0 新记录 / 0 修正 / 0 重置，扫描计时 517 ms；重开前后累计 token 相同，历史数据仍存在，游标数 1,721 |
| MCP 工具清单 | **BLOCKED**：`src.cli tools` 提示缺少 `MCD_MCP_TOKEN`，Python 子进程退出码 2 |
| 实时营养、优惠券、比价 | **NOT_RUN**：缺少 MCP Token |
| 「问麦麦」真实模型及工具链 | **NOT_RUN**：缺少 MCP Token 和 StepFun Key |
| 真实领券、下单、撤单 | **NOT_RUN**：本轮没有执行这些账号写操作 |
| 饭点真实自动流程 | **NOT_RUN**：为避免自动写操作，独立检查程序关闭了调度器；离线调度测试通过不代表真实饭点联调通过 |

余额首次回填时，单次进程采样的 Working Set 为 799,760,384 bytes（约 763 MiB），当时进程 `Responding=True`。这不是全程峰值采样。动作回调均在 UI 线程执行；本轮没有发现跨线程 UI 回调。

## 卡顿定位与限制

1. **首轮用量扫描是已复现的性能问题。** `src/metering/usage.py:203` 先把整个 provider 的 `iter_usage` 收集为列表；`src/agentbridge/providers/base.py:151` 从游标一次性读取剩余文件并解析。冷启动需要读取约 6.29 GB。虽然扫描已移到 QThread，本轮 UI 心跳与动画仍有长间隔。GIL 竞争及批量对象分配是代码层面的可能原因，尚未用采样分析器证明每次停顿的具体调用栈。
2. **数据源覆盖有限。** 当前默认读取 `~/.claude/projects` 和 `~/.codex/sessions`，没有通用收件箱。本轮显示 12 个旧会话、今天 0 token，只能描述这些已配置日志；不能解释为当前 Orca / WorkBuddy 没有任务或没有消耗。需要显式配置实际使用的日志根目录，或由相应 Agent 接入 generic provider。
3. **12.5 fps 是图集配置的目标。** 稳定 80 ms 帧间隔不代表高帧率，也不能据此否定主观动画观感。基准量的是 Qt 定时器推进，不是显示器合成后实际呈现的每一帧。
4. **线上初始化还有未测的同步风险。** `src/main.py:182` 的 `ensure_client()` 在 UI 调用路径执行同步 `initialize()`。缺凭证，本轮没有测到真实网络等待，不把它当作已复现的卡顿。
5. 本轮没有覆盖托盘图标点击、真实鼠标拖拽整条输入路径、任务执行中退出或重复并发余额请求。现有进度/余额自动联动、头顶进度条、餐品选择框等 README 已列明的未实现项保持未完成。

## 验证命令

以下命令在仓库根目录执行：

```powershell
# 第一轮环境失败：3 个 PySide6 导入错误
python -m pytest -q

# 使用实际桌宠的解释器：200 项通过
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' -m pytest -q

$env:PYTHONIOENCODING = 'utf-8'
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' scripts/smoke_check.py
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' scripts/bench_render.py 10
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' -m src.cli agents
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' -m src.cli tools

# 本机保留的临时动作探针；测试台账已存在时再次运行不会重复冷回填
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' -u .tmp-test-data/runtime-check/check.py
```

原始动作探针在本机的忽略目录，不是公共可安装脚本。报告记录本次测量，未把本机日志、凭证、订单或营养台账提交到 Git。

## 剩余操作

- 修复首轮回填的批量读取/解析压力，并用同等真实日志量复测。
- 在实际启动环境配置 MCP Token、StepFun Key 后，重新验证线上只读功能；账号写操作需要单独明确授权。
- 按需要配置当前 Agent 的日志数据源，再验收进度与用量是否覆盖当前任务。

## 提供凭证后的真实接口补测（2026-10-11，约 23:16 CST）

用户提供凭证后，保存到已被 Git 忽略的仓库本机 `.env`，重新启动独立验证进程。凭证值不进入报告、命令行参数或提交。上文的缺凭证结果属于首轮记录，以下是另一轮真实调用，不覆盖首轮失败或未运行结果。

本轮使用真实麦当劳 MCP 与默认 `step-3.5-flash`。探针在实际 `call_tool` 入口限制可调用的只读工具，并关闭饭点调度；没有调用领券、下单、撤单或抽奖工具。台账仍隔离，工具返回的地址与账号原始数据没有进入提交。

| 补测项 | 结果与耗时 |
|---|---|
| MCP 初始化 | **PASS**：显式调用 `initialize()`，314.27 ms |
| 工具与参数核对 | **PASS**：35 个真实工具、35 项参数核对，168.22 ms，没有缺失工具或字段 |
| 服务端时间 | **PASS**：非空真实响应，77.96 ms |
| 营养数据 | **PASS**：160 条，1,296.01 ms；巨无霸 513 kcal、蛋白质 27 g、脂肪 26 g、碳水 42 g、钠 961 mg |
| 优惠券只读查询 | **PASS**：券中心 5 张、未领 0 张、手上 4 张，284.69 ms；未执行领取 |
| StepFun 模型清单 | **PASS**：真实接口返回 7 个聊天模型，279.26 ms，默认模型在清单中 |
| 「问麦麦」 | **PASS**：3,309.07 ms，实际调用 `list-nutrition-foods`；最终回答巨无霸 513 大卡、蛋白质 27 克。2 次真实聊天请求，无需写操作确认 |
| 默认门店比价 | **FAIL（无报价）**：572.66 ms；`query-meals` 传输成功但业务 `success=false` |
| 桌宠真实「今天最划算」路径 | **功能受阻、性能 FAIL**：852.48 ms，无 pending quote；最大心跳间隔 325.58 ms，最大动画间隔 376.33 ms，出现 1 次超过 120 ms 的动画间隔 |

比价失败追查：默认门店为 `1950970`，`businessStatus=false`。再次查询附近门店共返回 5 家，营业中的门店为 0；`query-meals` 的实际业务错误是「门店可能已关闭或不在营业时间」。本轮没有到达 `calculate-price`，不能宣称算价或下单预览已经通过，也未改城市或替换门店来覆盖默认流程的失败。

桌宠使用原有 `action_best_deal()` / `ensure_client()` 路径、真实 Windows Qt 平台，动作结果气泡为「没找到可用报价（请检查 MCPET_CITY 设置）。」。这条信息没有传达真实的未营业原因，是一项已复现的错误提示问题。动画记录包含动作前的稳定基线；网络初始化在 UI 线程同步运行期间出现了上述长间隔。因此首轮仅标为同步风险的初始化路径，现在有了真实短暂停顿证据；尚未注入慢网或断网，不推断其最坏时长。

「问麦麦」两次请求分别报告 9,905 和 12,244 total tokens，合计 22,149；这是本轮模型返回的请求用量，不是余额、费用或完整厂商账单。没有据此报告费用。

本轮本机证据：`.tmp-test-data/live-check/check.log`、`result.json`、`deal-debug.json`、`gui.log`、`gui-result.json`，均为 Git 忽略的本机记录。验证命令：

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' -u .tmp-test-data/live-check/check.py
& 'C:\Users\DW\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe' -u .tmp-test-data/live-check/gui.py
```

接口探针退出码 **1**，原因是默认门店比价失败及菜单业务失败；其余成功项不将整批结果改为全绿。GUI 探针完成观测后自行退出，退出码 0 只表示正常结束，不代表功能或性能验收通过。两份临时探针保留在本机，不是公开安装脚本。

未改动业务代码，没有重复执行首轮离线测试或约 6.29 GB 的冷回填。下一步仍需修复首轮回填卡顿；新增需要处理的是 UI 线程同步初始化和未营业门店的错误提示。价格链路需要在有营业门店时单独复测。真实账号写操作与饭点自动流程继续保持 **NOT_RUN**。
