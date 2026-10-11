# 桌宠成熟化验收记录

用户范围：开发陪伴、日常陪伴、麦当劳助手三者同时保留。基线与上一轮结果见 `PLAN.md`、`../runtime-check-2026-10-11.md`；历史的失败和未运行记录不被本轮结果覆盖。

## 验收方法

- 固定使用已安装 PySide6 的 WorkBuddy Python：`C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。系统 Python 缺少 PySide6 的上一轮收集失败继续保留。
- 集成 Worker 先执行全套适用测试、编译检查、图集 smoke 与 Windows 动画基准。主 Agent 再以独立临时数据目录运行真实 Qt 应用，关闭饭点调度，观察冷扫描和网络任务期间的心跳与动画间隔。测试数据不会覆盖用户台账。
- 开发陪伴分别验证真实日志自动刷新，以及受控日志追加带来的工作/完成/用量变化。受控事件属于契约验收，不宣称实际用户任务完成。
- 日常陪伴验证鼠标触摸/拖拽/双击、持续聊天窗口、明确保存的记忆跨启动读取和删除、休息与唤醒、闲逛、位置恢复。
- 麦当劳测试只允许查询。初始化、营养、优惠券查询和模型调用使用用户已提供的本机凭证；不领取券、不创建或撤销订单、不打开付款链接。营养台账验证只写独立临时目录。下单/撤单确认和支付链接界面用离线契约验证，不能替代真实支付验收。
- 普通聊天须在无 MCP Token 的情况下可用；食物事实查询走真实 MCP，不能以模型记忆替代餐品事实。
- 关闭时存在活动任务、单实例重复启动、监视进程退出都需要验证。测试结果按实际层次记录；没有验收的能力保留为未运行。

## 当前状态

三条开发轨和 A 返修已提交、推送，唯一集成结果已由主分支快进接受。以下是初次独立工作树结果；返修、最终组合和真实验收见后文，不能将此表当作组合应用或真实账号验收结果：

| 轨 | 最终提交 | 独立验证 |
|---|---|---|
| A 画面/行为 | `5c96e7846f9ca06700938f98f826ea1a17c5285f` | 完整 pytest 225 PASS；Windows 10 秒动画 124 帧，最大间隔 81.3ms、0 卡顿；真实 Qt 拖拽 120 个事件、方向无小幅反转、松手 0 点击 |
| B 后台/数据 | `e4b761f7923482a61e0d7b1b6eac075c42d55893` | 适用 161 PASS、完整 237 PASS；默认根 1721 文件/6.29GB 冷 33.132 秒、增量 1.244 秒；60ms 心跳最大 78.095ms；实际 spawn 后立即 stop，外层退出 1.728 秒、0 残留子进程 |
| C 入口/聊天 | `703eae4bd02de17eb90a8f1a8f93a2130bc5bb67` | 适用 63 PASS、完整 238 PASS；Windows Qt 活动任务退出时，模拟 376ms 初始化延迟下心跳最大 12.35ms；单实例、线程退出通过 |

各轨的首轮失败、修复后结果、命令和限制保存在各自 HANDOFF。三个完整 pytest 数量不能相加；它们包含重复基线测试。

集成 Worktree：`C:/Users/DW/orca/workspaces/mcpet/mcpet-companion-integration-20261011`。所有 Worker 已停止，工作树保留；主轨真实 Qt/只读网络验收结果已单列于后文。

## 集成首轮（保留失败）

指定基础和三轨远端 tip 一致，普通 merge 无冲突。合并提交：A `0a8072370fc2bb4d1e7b40ac98047009a66bd385`，B `c5d9f418b7005df2d12e3437c561f1e1dbe60b18`，C `647b8114b2e951343dc5db29ef4eeda822323f02`。完整 `python -m pytest -q` 首轮 **300 PASS / 23.53s**。

新增原生 Qt + 真实 AgentMonitor + 受控 generic 日志组合探针 `python -m pytest tests/test_companion_integration.py -q -s` 首轮 **1 failed / 5.18s**，诊断复跑 **1 failed / 5.03s**。后台自动 start、working、usage、明确完成信号前置检查通过；随后单击摸摸、立即双击聊天/关闭重开、按下拖拽 40px，预期 `run-right`，实际仍为 `greet`。触摸前台 TTL 阻挡显式拖拽状态，属于 A 领域。主 Agent 已派原 A Worker 返修，集成者未改领域，也未通过延迟等待或删断言掩盖失败。该首失败不能被后续绿色结果覆盖。

## 返修及最终组合结果

原 A Worker 同域返修：领域提交 `835df319613517d1dc7c6b8782a3f9a6f0385173`，最终 tip `0c329d9c98d5086ea4c9e0e82a1b45c1b9fa222c`，已 push。A 本轨新增回归首轮 9 failed，随后定向 62 PASS、完整 237 PASS；集成者普通 merge `2065b5852c4efdcbd2cb11591eca2260282ade37`。交互规则为达到阈值的拖拽 > 显式休息 > 未到期前台事件 > 最新基态，通知期限不续期；后台不能打断手势。不是提高所有跑动事件的优先级。

唯一集成分支 `songconmaisaix31-design/mcpet-companion-integration-20261011` 最终 `2885fa87f3eade21578b058e06a92bc78e697ed4`，已 push 且远端 tip 一致；主 `codex/desktop-companion-20261011` 已 `git merge --ff-only 2885fa87f3eade21578b058e06a92bc78e697ed4`。最终集成结果：

| 验证命令（固定 WorkBuddy Python） | 结果与口径 |
|---|---|
| `python -m pytest tests/test_companion_integration.py -q -s` | 返修后 **1 PASS / 7.93s**；保留原失败手势断言 |
| `python -m pytest -q` | **313 PASS / 37.25s**，无 skip/warning；父进程和原生子进程均 Windows Qt |
| `python -m compileall -q src tests`、`git diff --check` | PASS，exit 0 |
| `python scripts/bench_render.py 10` | Windows DPR 1.5，124 帧/12.4fps，平均 80.0ms，78.8–81.1ms，标准差 0.5ms，**0 卡顿帧** |
| 同一 benchmark 的 Qt 拖拽 | 从未过期 greet 开始，120 次事件，0.21ms/事件，8/8 帧推进，仅 run-right，0 误点击 |
| `python tests/test_main_startup.py --qt-smoke normal/active/external-quit` | 三个独立 Windows Qt 子进程 exit 0，QThread 已停；心跳最大 12.40/10.99/10.92ms，网络为 MockTransport，monitor 为 stub |

新增组合测试使用默认真实 AgentMonitor 和受控 generic 日志：自动 start、working、上下文 25%、用量 40→110、明确完成仅一次；重复 start/40 次刷新/第二实例无第二写入者，两个 spawn 子进程、仅一个 usage writer。退出含受控 250ms 串行任务及刷新，quit 调用 8.83ms；外层 Win32 句柄检查两个子进程均退出。位置 `[170,140]`、闲逛和休息重开恢复。真实单击/双击聊天重开/触摸 TTL 内拖拽/反向阈值/松手无误触/休息唤醒均通过。组合探针心跳最大 111.95ms，不能宣称所有 UI 场景零间隔波动。详见 [HANDOFF-INTEGRATION.md](HANDOFF-INTEGRATION.md)。

## 主轨真实日志、模型与 MCP（2026-10-12）

主轨以用户已提供、本机 Git 忽略 `.env` 内的凭证运行真实服务，独立临时数据目录，不打印/提交凭证或用户原始日志。当前已知 Orca 账号 root 显式配置，只读该 root 与既有 Claude root，没有扫描其他账号。GUI、model 和 MCP 各有真实证据；账户写操作在探针入口禁止执行。

可复现本轮本机命令（探针和原始 JSON/截图在 Git 忽略目录，不是产品入口）：

```powershell
$petPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:PYTHONIOENCODING = 'utf-8'
& $petPython .tmp-test-data/companion-acceptance/gui.py developer
& $petPython .tmp-test-data/companion-acceptance/gui.py mcd
# 首轮调度补执行影响券阶段后，仅复测券；不是重新运行整套或再次请求模型：
& $petPython .tmp-test-data/companion-acceptance/gui.py mcd-coupons
```

这些探针要求独立/预期为空的数据目录；不要直接反复复用已有聊天/营养数据。真实日志持续变化，token 和优惠券数量是本次快照，不是以后启动的固定验收值。

### 开发与日常陪伴

- 原生 Windows Qt 构造 212.54ms；真实根 1964 个 JSONL、约 17.4GB。首次进度 1.13 秒返回，12 个近期会话中 8 个新鲜，随后约每 10 秒更新；明确容量 258400 来自日志，界面展示真实项目/上下文。新鲜会话不等于已确认仍有进程运行；上下文不是任务完成百分比。
- 从事件循环启动至首次历史用量与聊天联合条件满足 **182.281 秒**。本机历史台账 token 为 358,598,332,840；这是配置根的本机日志统计，不是厂商账单、余额或本轮消耗。该 root 与 B 的默认 6.29GB root 不同，不能直接作同数据集的性能对比。
- 2272 帧，平均动画间隔 **80.187ms**，最大 **192.254ms**，**7 次 >120ms**；16ms 心跳最大 **187.090ms**、**1 次 >100ms**。少量长间隔仍存在，不宣称大型日志/首次聊天开窗零卡顿。
- 500ms 采样峰值：GUI **134.40MiB**，进度 **40.85MiB**，用量 **2056.27MiB（约 2.01GiB）**；落盘用量状态 **763,869,938 bytes**。历史去重记录驻留和 JSON 序列化仍随历史增长，是实际常驻成本，不以“流式读取”宣称总内存有固定小上限。
- 日常聊天在 MCP Token 为空时完成真实两轮，MCP initialize/tool 调用均 0，模型 tools 均未提供；两次模型响应 1153/1045ms，实际返回 296/319 token，共 615 token（缓存是输入子集，不另加）。第二轮能回答刚才在调试桌宠，显式偏好“请叫我小麦”进入回复。
- 4 条消息和明确偏好重开可读，删除偏好后重开为空；真实宠物和聊天截图已检查。角色/上下文布局清晰；原素材保留。立即移至 `[380,470]` 后关闭，位置落盘；事件循环退出 18.06ms，外层自然退出 exit 0，进度/用量子 PID 均已消失。强制关闭未验收。

### 麦当劳只读与真实营养

- 构造 204.52ms；唯一 MCP initialize **292.41ms，非 GUI 线程**。真实工具返回 transport/business 均成功：券中心、我的券、地址、附近门店、营养；write allowlist 阻止领取/创建/撤单等请求。
- 门店查询返回没有明确营业门店，界面原文 **`StoreUnavailable: 查询到的门店均未营业或营业状态 UNKNOWN；无法获取菜单和报价`**，候选报价为空。闭店错误显示正确；没有假价格、菜单 fallback 或可下单结论。真实营业菜单/算价/提交仍 NOT_RUN。
- 真实选择“巨无霸” **2 份**，每份服务端 **513kcal**，临时台账实际 **1026kcal**；仅写隔离临时台账，没有改用户饮食记录。选择框显示总蛋白 54g、脂肪 52g、碳水 84g、钠 1922mg。默认 quantity=1 与小数份数由适用测试覆盖。
- 实时聊天实际调用营养工具并回答 **513 大卡 / 蛋白质 27 克**，约 3.092 秒、两次真实模型响应共 **12,239 token**。这是本次返回 usage，不是支付金额。联网阶段心跳最大 16.93ms，动画最大 81.05ms；营养选择框首次显示阶段另有 1 次 139.01ms 动画间隔。
- 位置立即保存，事件循环退出 27.20ms、外层 exit 0，进度/用量子进程均退出。未领取、下单、撤单、打开付款链接；账号效果无写入。

### 探针自身的问题与定向重验（保留）

首轮两个探针在构造后调用 scheduler.stop；QtDailyScheduler.start 会先同步补执行已过的饭点，因此首轮 MCP 中已排入额外只读券/报价任务。没有账号写操作，但券阶段的最终气泡被后续闭店错误覆盖。首轮记录保留为 `mcd-first-result.json`，不能用它证明券汇报显示通过；闭店/营养/实时聊天证据仍有效。修正探针，在构造前禁止 scheduler.start，再仅运行 `mcd-coupons`，没有重复请求模型或重新跑冷扫描：

- **PASS / exit 0**；界面 **“只查询：券中心 7 张；手上 4 张。未主动领取。”**，只调用 available-coupons/query-my-coupons，未查询门店、未执行写操作。
- 约 0.811 秒完成，心跳最大 17.11ms；动画最大 123.33ms、1 次 >120ms，不能宣称该短阶段零长间隔。退出 10.56ms，外层 exit 0、子进程均已退出。

首轮探针把脱敏函数应用到整个 JSON 文本，约 17.4GB 的数值恰好匹配手机号规则，导致 bytes 数字被部分遮罩、原 JSON 格式受损；这是探针问题，不是产品数据失败。保留 `developer-first-result.txt`，规范化记录将 bytes 设 null 并保留原遮罩字符串，不猜补数字；其余数值和测量未改。今后的探针对结构内字符串脱敏后才序列化。没有因此重复实际冷扫描。

本机原始记录及截图：`.tmp-test-data/companion-acceptance/`。截图未提交用户项目名/聊天内容到 Git，已在本机检查 `developer-pet.png`、`developer-chat.png`、`nutrition-picker.png`、`mcd-chat.png`。根分支只增加计划/调研/验收文档，未写业务代码。

## 真实剩余限制与未执行操作

- **大历史日志性能仍需改善**：本次约 17.4GB 冷回填约 182 秒、用量进程约 2.01GiB，持久 JSON 约 764MB；重启载入和长期增长成本没有在该大数据集重测。轻量增量绿色不能代替这一限制。工作/聊天可先使用，历史用量应等待，不能称即时读完。
- **真实营业报价/下单/撤单/领券/支付未验收**：当前门店关闭，确认、payload、价格变化/UNKNOWN、支付链接等只有离线/Qt 契约覆盖。需要营业门店和用户明确确认的实际账号流程；不自动替用户完成。
- 日志轮询有 10/60 秒默认滞后，可能漏两次观测之间完成又开始的任务；某些来源/模型容量及价格仍为估算或 UNKNOWN。厂商账单/余额未接入。JSONL 按追加读取，同长度重写和异常超大单行保留既有边界。
- 记忆是用户主动偏好及有界聊天历史；没有语音、自动画像、隐式屏幕观察。休息复用 idle 动画，没有新增原创睡眠/麦当劳素材。位置/边界测试不等于物理多屏热拔插/DPI/休眠/远程桌面及长期主观观感验收。
- 本轮未发布安装包、签名/自动更新、设置开机启动、创建 PR、合并公共主分支，也未强制终止系统已有应用。验收 GUI 已退出；日常启动使用 README 的 `python -m src.main`，应使用安装了 PySide6 的解释器。凭证沿用本机忽略的 `.env`，Windows chmod 不等于已验证的完整 NTFS 独占 ACL。
