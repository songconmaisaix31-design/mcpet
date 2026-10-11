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
