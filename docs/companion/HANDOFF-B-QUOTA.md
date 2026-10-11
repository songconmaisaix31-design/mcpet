# B 账号额度/余额交接（2026-10-12）

## 分支、范围与提交

- 分支：`songconmaisaix31-design/mcpet-data-20261011`。
- 开始时工作区干净；`git fetch origin` 后普通 FF 到计划 `067ceca814ca8e52e14ad39dd8dc472a32ee2b0a`。已完整读取新计划、旧 HANDOFF-B；随后只读 root 计划的 reconfigure 补充。
- 首阶段：`a5d06ee53e95108bf72a61075eac5639a08592aa`；凭据/零余额/幂等停止返修：`05e45c73b51e66b5326d4c1bf0007cc288ec310d`。
- 最后代码 SHA（Windows 真实 PID 归属）：`d2b29263eb9896c735f6b548621df1b61f8b1611`。文档提交的最终 tip 另随 root 通知给出。
- 修改仅为新 `src/accounts/**`、`tests/test_account_balances.py`、`tests/test_account_monitor.py`、本文件。原 AgentMonitor、UsageMeter、usage.json、配置、main、UI 与其他轨测试均未改；未合并其他轨、未集成到 root。

## C 可直接使用的共享接口

`src.accounts` 导出计划指定四个冻结 dataclass，字段和默认值完全保留：`QuotaBucket`、`MoneyBalance`、`AccountStatus`、`AccountSnapshot`。所有公开时间为 Unix **秒**；金额为 Decimal，`used_percent=None` 表示未知。账号状态只产生 `ok/unavailable/error/stale/unconfigured`。

```python
from src.accounts import AccountMonitor, DeepSeekBalanceSource

accounts = AccountMonitor(
    parent=window,
    deepseek_source=DeepSeekBalanceSource(config.deepseek_api_key()),
)
accounts.snapshot_ready.connect(panel.set_account_snapshot)  # AccountSnapshot
accounts.failed.connect(panel.show_account_error)           # 已去敏的 str
accounts.stopped.connect(on_account_process_reaped)         # 无参数，可选
accounts.start()

# C 保存配置后：同一个对象；先显示刷新中，等新的 snapshot_ready 再结束。
accounts.reconfigure(deepseek_source=DeepSeekBalanceSource(config.deepseek_api_key()))
accounts.refresh()

# app.aboutToQuit 已自动连接 stop；提前关闭也可调用，重复 stop 安全。
accounts.stop()  # GUI 不 join/wait
```

- 构造器兼容 `AccountMonitor(parent=None, *, orca_source=None, deepseek_source=None, interval=300.0)`；另有默认 `query_timeout=15.0`，供受控超时测试覆盖。
- 方法 `start()/refresh()/stop()/reconfigure(*, orca_source=None, deepseek_source=None)`；reconfigure 的 None 保留现有源，全部立即返回。停止后的对象不可 restart；配置更换无需 stop 或新建 monitor。
- 只有一个活动查询和一个合并待刷新。同一个 spawn worker 按序应用源变更；旧查询可完成或超时，但其结果不发布为新凭据数据，包括 `failed` 回调同步换源的情况。更换源时清掉对应成功缓存，防止旧 key 的余额成为新 key 的失败回退。
- `last_snapshot` 是历史缓存，换源期间 C 仍需显示刷新中，不能自行当新凭据结果发布。失败快照保留该源最后成功值和原 updated_at，状态变为 stale；没有成功值则 error/UNKNOWN。官方有效的零余额及 `is_available=false` 仍是新观测，不回退为旧正余额。
- `first_failure` 保存首次去敏错误；后续 GREEN 不覆盖它。`stopped()` 表示进程清理完成，通过 Qt 队列通知；app 退出后无 event loop 时不等待信号，非 daemon 桥仍完成回收。
- 注入源应为可 spawn/pickle 的顶层类，只提供 `fetch()`；实际两个 Source 已验证可 spawn。不要注入 lambda、闭包、打开的 Client 或 QObject。不可序列化等后台异常只输出固定去敏错误。
- C 主入口在启动后异常退出时也应在 finally 调 stop；正常 Qt 退出已自动连接。禁止 GUI join/shutdown Future。

## 数据源事实与边界

`OrcaAccountSource(command=None, *, timeout=5.0, max_age=900.0).fetch()` 返回 tuple。command 可为单个可执行路径或 argv 前缀，统一追加 `account list --json`；不通过 shell 执行命令字符串。默认按公共 Orca CLI 环境选择 exe，Windows 使用 CREATE_NO_WINDOW，二进制 capture 后严格 UTF-8/可选 BOM 解码。CLI 超时/非零/不可执行/非法编码/JSON/缺 rateLimits 均明确 error，不返回伪造 0。

只提取 `result.rateLimits` 的 codex/grok/cursor/claude、status、updatedAt、known window/bucket 的 usedPercent/resetsAt。忽略账户、key、其他 metadata、任意 error 文本及未知 provider/桶；这些不会进入快照或磁盘。支持 provider 列表或 provider 键映射；Cursor buckets 可在 monthly 内或 provider 外，嵌套桶只继承其明确父 monthly 重置时间。时间严格按毫秒除 1000，不按量级猜单位；bool、非数、非有限、非正时间保持 None。百分比要求有限数值 0..100，bool/字符串/越界保持 None。

codex/grok 各自 `weekly`；Cursor `monthly`、`Cursor Models`、`Other Models` 独立保留，不相加。缺 provider/window/额度字段明确 unavailable；过 900 秒缓存或过重置点标 stale，保留观测数字但不宣称即时厂商余额。Claude 未提供可识别额度时 unavailable。使用者可自行计算已知桶的 `100-used_percent`，未知桶不计算。

`DeepSeekBalanceSource(api_key="", *, timeout=5.0).fetch()` 只使用 C 显式传入的 key。空 key 直接 unconfigured，无请求。仅 GET `https://api.deepseek.com/user/balance`；不发模型调用、不读取 env/key 文件、不跟随重定向、不使用继承的代理凭据。官方响应 is_available 必须 bool，balance_infos 必须非空列表，各币种金额必须非空字符串、有限 Decimal 且非负，缺字段/非法金额/重复币种都是 error。保留各币种 total/granted/topped_up 的精度；不折算、不生成余额百分比。HTTP/网络错误不暴露响应体、Authorization、异常文本。

后台为标准 multiprocessing spawn、一个非 daemon IPC 桥线程，无自研调度/Attempt/Manifest/证明系统。总查询截止默认 15 秒（含 worker 启动），CLI/HTTP 各自默认 5 秒；超时先回收再允许下一次刷新重建 worker，至多一个查询。GUI 不启动/加入子进程、不等 pipe。stop 清掉后续请求立即返回；桥轮询 25/50ms，join 0.2s，必要时 terminate/join 1s，再 kill/join 1s。Windows Job Object 关闭时杀掉 CLI 后代；同时绑定启动器 PID 和握手报告的真实 Python PID，首次查询前消除 venv redirector 竞态。POSIX worker 先 setsid，再接命令。无台账或账号快照持久化，无 usage writer。

## 首 RED（保留）

| 阶段/命令 | 首失败和原因 |
|---|---|
| 新两份测试，实施前 | 2 个收集 ERROR：`ModuleNotFoundError: src.accounts`；新模块尚未实现。 |
| 首阶段 staged `git diff --cached --check` | 7 个新增文件尾空行；PowerShell 后续 commit 仍执行，首阶段 SHA 保留，后续独立返修清掉，未 amend/覆盖历史。 |
| `pytest test_account_monitor.py -k 'failed_callback or last_successful_zero or stop_before_start'` | 3 failed：failed 回调换 key 后仍发旧余额；官方零余额未进入成功缓存，后续失败回退到更老的 6；重复 stop 发两次 stopped。 |
| 新真实 UTF-8 CLI/退出测试第一轮 | 3 failed, 67 passed：0.1s timeout 调用整体 2.063s 超过测试 2s；blocked/Qt whole exit 6.053/7.156s 超过测试自定 6s。整体包含 Win32 CreateProcess/模块启动，不是 GUI stop。 |
| 上述定向重试 | 1 failed, 3 passed：UTF-8 fixture 的 2s 查询返回 error；未记录该次来源 message，精确错误原因 UNKNOWN。另一次独立计时观测 CreateProcess 400.887ms、timeout 107.507ms、kill 0.173ms、reap 0.957ms，不能用它倒推出每次启动耗时。 |
| 记录真实 CLI body PID 后 | 1 failed, 69 passed：1.5s 测试查询预算在 fixture PID 标记创建前已超时。改为先记录已创建 CLI PID，body PID 独立记录；受控查询预算 3s（产品默认仍 15s）。 |
| 手动退出探针与完整 pytest 并行 | immediate exit 成功（整体7.276s/stop后2.931s）；第二个 blocked probe 外层 TimeoutExpired(10s)。本轮保留 RED，受控 worker/CLI/body PID 50828/58056/39196 检查均退出；不声称任意负载下都有同样整体延迟。 |

只调整新测试自定启动预算：合法 UTF-8 fixture 使用产品默认 CLI timeout=5s；真实 0.1s 超时调用整体要求 <5s。新 whole-interpreter 预算对齐原运行时 <8s，另增 stop 后 <3s。未放宽原 GUI stop<50ms、heartbeat<150ms，也未延长产品 15s 截止。Python 标准 subprocess 的 timeout 不可中断 Win32 CreateProcess 本身；此开销留在后台。

## GREEN（独立结果）

| 检查 | 修复后结果 |
|---|---|
| 首阶段账号测试 / 扩展账号测试 | 44 passed (0.96s)；58 passed (29.80s)。 |
| 首阶段完整 pytest | 377 passed (75.87s)。 |
| 三个定向返修回归 | 3 passed, 15 deselected (0.27s)。 |
| 凭据/金额返修账号测试 / 完整 pytest | 70 passed (26.60s)；389 passed (75.73s)。 |
| venv 真实 PID 归属回归后的最终账号测试 | 71 passed (27.49s)。 |
| 最终完整 pytest | 390 passed (59.69s)。 |
| `python -m compileall -q src tests` | 通过。 |
| `git diff --check`、基线范围 `git diff 067ceca... --check` | 通过；stage 前后再次检查。 |

71 项覆盖冻结契约、UTF-8/BOM、白名单、独立桶/窗口、ms->s、未知/bool/NaN/非法值、stale、Decimal 多币种、官方 GET/HTTP 错误去敏、真实 fixture CLI、Qt/spawn 刷新合并/换源、零余额/失败回退、heartbeat<150ms、GUI stop<50ms、超时重建、自动刷新、实际 Python PID 归属和整个解释器退出。无真实账号查询。

额外串行真实 Windows spawn/解释器退出观测（在 05e45c 版本，非用户 GUI）：

| 场景 | 整体退出秒 | stop / Qt quit ms | stop 后退出秒 | 剩余受控 PID |
|---|---:|---:|---:|---|
| spawn 启动后立即 stop，不 pump/join | 2.0451 | 0.0766 | 0.4271 | [] |
| CLI/body 真正启动并阻塞后 stop，不 pump/join | 4.5296 | 0.0466 | 0.2526 | [] |
| CLI/body 阻塞，app.exec -> aboutToQuit | 4.9349 | 0.1844 | 0.2860 | [] |

外层 subprocess.run timeout=10s；只对测试报告的 worker/launcher/真实 CLI body PID 使用 OpenProcess(SYNCHRONIZE)/WaitForSingleObject 检查退出。新握手修复后的相同三场景也包含在最终 pytest 内。

## 复验命令与限制

```powershell
$python = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$quotaRoot = Join-Path $env:TEMP ('mcpet-b-quota-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $quotaRoot | Out-Null
$env:TEMP = $quotaRoot
$env:TMP = $quotaRoot
$env:MCPET_DATA_DIR = Join-Path $quotaRoot 'data'
$env:MCPET_AGENT_ROOTS = "claude=$quotaRoot/absent-claude,codex=$quotaRoot/absent-codex,generic=$quotaRoot/absent-generic"
$env:MCPET_WATCH_PROCESSES = '0'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:QT_SCALE_FACTOR = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $python -m pytest tests/test_account_balances.py tests/test_account_monitor.py -q
& $python -m pytest -q
& $python -m compileall -q src tests
git diff 067ceca814ca8e52e14ad39dd8dc472a32ee2b0a HEAD --check

# 独立解释器、受控假 CLI，仅 pytest 外层有 join/退出 PID 检查。
& $python -m pytest tests/test_account_monitor.py -q -k whole_interpreter_exit
```

本轮仅 contract fixtures/mock 网络和隔离 Qt/spawn；未读真实 `orca account list`、凭证/.env、用户会话/ledger，未实际访问 DeepSeek、模型/MCP 账号网络，未操作用户 PID 49784/38676/23860/48728。Orca cache 实际形状和 DeepSeek 余额仍由 root 最终只读实测，CLI缓存不保证厂商即时值。默认刷新 300 秒、缓存过期阈值 900 秒；更换源的旧查询最迟到本轮截止后才串行换源，期间 C 显示刷新中。

无 Pixso/角色/UI验收结论。唯一集成 Worker 负责旧 main/app/integration 测试的默认账号源离线注入，不删除旧断言/放宽门槛；B 未越域修改它们。跨轨装配、DPR/native 页面截图、当前用户实例重启和人工验收交给 root/集成。B commit+push+通知后停止。
