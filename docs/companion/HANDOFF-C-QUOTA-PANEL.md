# C：额度与双角色小窝交接（2026-10-12）

原 worktree `C:/Users/DW/orca/workspaces/mcpet/mcpet-app-20261011`；原 branch
`songconmaisaix31-design/mcpet-app-20261011`。没有新增 Agent / worktree，没有合 A/B 或合回 root。
起始干净，fetch 后 FF `origin/codex/desktop-companion-20261011` 到
`067ceca814ca8e52e14ad39dd8dc472a32ee2b0a`。完整读新 PLAN、旧 C/集成交接及验收。
之后仅 fetch/read 主轨设计 brief，未 merge 其他进度；只写本轮 C write_paths。

代码交付 SHA 和最终完整结果见本文末尾。视觉与适用测试通过不代表原联合性能通过；
本轮冷打开 remaining RED 如实保留，未放宽任何门槛。

## 实现与接口

- 唯一非模态四页小窝；顶部刷新额度、首页真实角色预览与互斥橘/蓝按钮、紧凑订阅行，
  独立 DeepSeek 金额卡。角色名/preview/tray 跟随 A `character_id/set_character`，
  失败保留原角色。A 未合入时禁用切换，不制作替代素材或独立角色持久化。
- 延迟 import B `src.accounts`，单独一个 AccountMonitor；不改 AgentMonitor，不新建 UsageMeter。
  刷新走同监控 refresh。保存 DeepSeek Key 后同对象 reconfigure 新 source，再 refresh；
  清除旧账号快照，显示刷新中到新信号。B 的安全换源/丢弃旧结果/单飞由 B 实现。
- 每个窗口/桶分别显示已用、剩余、reset 和更新时间；Cursor 不相加。未知不显示假 0% 条，
  失败保留旧值并标过时，reset 经过不猜额度恢复。Orca 来源标账号缓存；本机日志仍只在会话页。
  余额用 Decimal 原精度按币种显示，赠送/充值独立，不用任意金额上限造进度条。
- 设置新增 masked DeepSeek Key；不回填，留空保留，明确清除，取消/关闭/Escape 丢弃未保存输入。
  allowlist 持久化保留旧 StepFun 配置，dotenv 优先级保持；错误也遮盖尚未保存的新 Key。
  Decimal 数字避免误匹配手机号/身份证，仍遮盖已知凭证与 token 模式。
- 保留四入口 showNormal 恢复、单实例、MCP 串行、只读饭点、真实营养份数、下单/撤单确认、
  未知落单效果消费候选、付款链接。没有聊天输入、模型发送或旧聊天读取。
- 分阶段退出：第一阶段 closing 同步拒绝新操作并 stop 两个现有监控，停止倒计时、关闭任务队列；
  GUI 不 wait/join。退出提示排到下一事件循环；任务安全清理结束后 _finish_quit 统一
  window.close（A 保存位置/停 timer）、panel.close、解除事件过滤器/关闭单实例 server、app.quit。
  锁仍经 atexit 在 non-daemon 桥回收后释放，没有只提前返回漏掉后续关闭。

## 设计和真实截图边界

已完整读 root 最新 PIXSO-DESIGN-BRIEF，并用 view_image 查看真实 PIXSO-HOME-DESIGN.png。
主轨实际 Pixso frame `3:1`：[设计链接](https://pixso.cn/app/design/c7aSBvfcRT5aEFJtF7vTmQ?node-id=3%3A1)。
该设计由主轨生成，C 只对照原生实现；其余三页沿同一体系，无全页面 Pixso 交互原型声明。

最终候选截图目录：
`C:/Users/DW/AppData/Local/Temp/mcpet-c-quota-final-1791751045265/native-compact-v4/`。
home / home-bottom / home-deepseek / sessions / mcd / settings 共六张，均真实 Qt panel.grab，
Windows、DPR **1.5**，network_calls=**0**、errors=[]、worker_stopped=true。
用显式参数只读 overlay A 固定 `8b7da5c9d396a0e14b77f4e2b7ad5c844c0c4a1e` 的
spritesheet/preferences/characters/window 模块，资产仍从 A 原 worktree 读取，无 merge/复制。
真实麦麦和指定 DeepSeek 娘选择、名/预览/选中态/tray 同步断言通过。
账号数字都标「受控夹具」，不是真实额度/余额；AgentMonitor 读取新造 generic 日志。

## 首 RED 保留；GREEN 分别列出

所有原始日志/图片保留，不覆盖首失败：

1. 首适用 `first-targeted.log`：**1 failed /25 passed /14.94s**，
   Decimal `123.456789012345678901` 被身份证匹配遮成 `123.4567**********8901`。
   修复仅数值个人信息模式后 `targeted-green.log` **26 PASS /2.84s**。
2. native-v1 运行码虽绿，人工 view_image 发现动态额度卡压缩成细条，列为**视觉 RED**。
   返修父布局最小尺寸/先归入父布局再显示/显式显示，新加尺寸断言；native-v2 数据可读，
   为单列可读 GREEN，主轨仍要求压紧，不能作为最终视觉验收。
3. 初次完整 `first-full.log` **336 PASS /57.50s**，是当时版本证据，不代表最终返修版。
   当时独立适用+原联合 **27 PASS /13.06s**：heartbeat **102.57ms<150**，
   first open **88.7ms**，stop **3.9388ms<50**，四入口恢复，writer=1，两个子进程回收。
4. compact 首适用 `compact-targeted.log` **1 failed /28 passed /39.57s**：cold quit
   **149.3486ms>50**。`stop-profile.log` **108.8439ms**，panel.hide **65.7069ms**、
   bubble **41.7412ms**，监控 stop 很快。只禁重绘/去气泡仍 **85.4885ms**，
   event-filter/去父窗口/字体尝试未解决（80.57/98.23/71.39ms），不挑绿也不归因账号 worker。
   去父窗口和事件过滤尝试已撤回；采用安全任务完成后统一 close 的分阶段方案。
   独立 `compact-targeted-fix.log` **29 PASS /30.77s**，stop **3.8028ms**。
5. 第一次只读 A 原生探针 `native-final.log` **exit1 /monitor timeout（20秒）**，
   无图片、network_calls=0、worker_stopped=true；没有延长超时，补明确诊断。
   后续 native-compact 自然返回六张图片/DPR1.5/零网络，属于独立运行。
6. native-compact 虽运行绿，主轨审图发现窄 summary 被长条抢宽：Codex 已用16.25%和
   Cursor 末行被裁，是第二条**视觉 RED**。v4 限条最大宽度、完整文字保留空间，
   reset 与更新时间正常分配，未再缩字体。C view_image 显示完整百分比，新增700/560
   label.height>=heightForWidth(width) 断言。主轨随后用 view_image 审阅 v4 六张图，
   首页双角色/四provider/分桶百分比/精确金额及设置、会话、麦当劳页视觉通过；
   这不是实际账号或完整集成验收，此前 compact 裁切 RED 保留。
7. v4 适用 `targeted-final.log` **30 PASS /32.18s**，idle stop **4.3066ms**，包含
   活动任务第一阶段拒绝操作、下一事件循环实际关闭窗口、QThread 有限结束。原50ms不变。

旧证据位于 `C:/Users/DW/AppData/Local/Temp/mcpet-c-quota-1791742755598/`，
compact/v4 与 profile 位于 `C:/Users/DW/AppData/Local/Temp/mcpet-c-quota-final-1791751045265/`。

环境失败单列：会话恢复后两次 exec_command CreateProcess 被拒绝，
`helper_unknown_error: setup refresh had errors`；并非 pytest 失败。用户恢复同会话的
danger-full-access 后只读 git status 成功。用户所述原生内存退出/两次路由超时保留为
外部会话恢复事实，C 未取得精确 PID/exit code，不改写成代码测试结果。
主轨报告 B CPU采样76%和测试失败后要求错开测试时段；C 等唯一适用运行有限退出并通知
测试空闲，只做静态审阅。CPU 样本不作为上述性能 RED 的确定原因。
主轨随后只读确认 B 串行82 PASS/32.33s，并继续将无并行时段交 B 完整验证；
C 未在等待期间启动任何新 Qt/native/退出/完整测试，等明确交回再运行。

## 最终独占时段：冷打开调查与 remaining RED

主轨正式交回时段，B 已停止且无探针，远端 tip 为
`fa96c57801d705f21b400f6f5271745d9914d421`。其外部完整证据为1 failed/400 passed/110.65s，
heartbeat417.81ms、首panel332.09ms、stop42.8088ms；不把它改写成本轨结果或确定原因。

C 适用 `verification/applicable.log`：**66 PASS /55.81s**，idle stop **2.3412ms**；
包括活动任务第一阶段 stop<50ms、拒绝新动作、放行任务后下一事件循环关闭两个窗口、
停止 quota timer 与 QThread 有限结束。旧测试只运行，未改任何跨域断言。

C 首原联合 `verification/joint-final.log`：**1 failed /11.55s**。
失败精确值 heartbeat **439.24ms>150ms**（650 ticks）；首次panel **345.08ms**，
stop **9.5934ms<50ms**；四入口 native 恢复、拖拽、writer=1、两个受控子进程、
thread_running=false、errors=[]。该轮 pytest 在 heartbeat 断言失败，故该断言之后的
PID 回收/锁删除/位置重启断言尚未执行，不把前面的布尔状态当作这些断言已通过。

随后均为新造 TEMP root、串行、无业务改动的诊断，不是绿验收：

| 诊断日志（verification 下） | 关键结果 / 解释 |
|---|---|
| panel-profile-run.log | 首诊断 generic root 指错，tokens=40 断言先失败，未进入性能采样；保留诊断 RED |
| panel-profile-run-2.log / panel-profile.txt | cProfile 首panel628.99ms，queue/thread归属有扰动，不据此认定原因 |
| panel-wall-profile-run.log / panel-wall-profile.json | 构造74.464ms，同步/渲染约1–5ms，show508.259ms，首panel591.25ms |
| panel-font-probe.log / panel-font-wall.json | 禁 font merging 后 show442.480ms，首panel520.69ms；未消除 RED |
| panel-filter-probe.log / panel-filter-wall.json | 去全局过滤器后 show440.423ms，首panel482.69ms；未消除 RED |
| panel-layout-probe.log / panel-layout-wall.json | 构造29.429ms，layout.activate11.605ms，show416.321ms |
| panel-native-probe.log / panel-native-wall.json | layout14.445ms，winId创建72.084ms，含拆分的show354.829ms；首panel403.56ms |
| panel-events-probe.log | TEMP脚本写入的PowerShell here-string错误，沿用旧诊断；随后重复入口仍iconic，exit1。不能当新事件采样 |
| panel-events-probe-2.log / panel-events-profile.json | Qt事件诊断首panel499.82ms；Expose82.051ms，paint scrollbar32.852ms，仍无法解释全部show成本 |
| panel-owner-probe.log | 去父窗口首panel328.00ms，heartbeat413.67ms；未消除 RED |
| panel-style-probe.log | 移除全局样式首panel287.31ms，heartbeat374.02ms；未消除 RED |
| panel-report-probe.log | 将报告方块字符替换ASCII首panel387.73ms，heartbeat465.70ms；未消除 RED |
| panel-content-probe.log | 隐藏全部直接内容仅诊断：首panel184.04ms，heartbeat280.89ms；未过门槛，不能作UI交付方案 |
| panel-access-probe.log | 禁accessibility仅诊断：首panel310.54ms，show278.515ms，heartbeat389.10ms；未消除 RED |

确认数据渲染低耗时，冷show占主导；**未稳定定位根因**。字体/过滤/owner/样式/文本/
accessibility 任一单项都未证明能消除问题，不宣称它们毫无影响或把差异归因CPU。
全部实验仅存在TEMP harness，没有进入生产实现；不隐藏UI、不预热、不延后heartbeat、
不等TTL、不修改原联合预算。主轨允许如实交接调查与remaining RED，最终组合后如仍失败，
退回同一C Worker继续定位。原native-v4视觉GREEN独立保留。

`verification/full-final.log`（补独立退出回归前）：**1 failed /339 passed /72.31s**，
唯一失败仍为原联合 heartbeat **359.76ms>150**（570 ticks），首panel **259.46ms**，
stop **2.5267ms**。不能称本轮全套通过。

由于原联合在 heartbeat 断言处先失败，新增自域
`test_native_active_exit_reaps_children_releases_lock_and_saves_position`：复用旧受控原生协议，
显式注入 AccountMonitorStub，真实 AgentMonitor 仍拥有两个 spawn 子进程，硬拒 HTTP；
单独核对既有0.25s任务的有限清理、stop<50ms、QThread结束、两子进程PID已回收、
锁删除、移动后位置保存与重启休息/闲逛恢复，不取代旧性能测试。
`verification/active-native-exit.log`：**1 PASS /11.67s**，stop **3.7113ms**；
其 heartbeat **395.37ms** 与首panel **306.63ms** 仍RED，不将退出GREEN扩成性能GREEN。

## 复现环境 / 命令

固定解释器 `C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。
每轮隔离 TEMP/MCPET_DATA_DIR；QT_QPA_PLATFORM=windows、QT_SCALE_FACTOR=1、
PYTHONIOENCODING=utf-8、MCPET_WATCH_PROCESSES=0；三类 Agent roots 指新 TEMP 的
不存在目录，原联合/native退出协议会显式改 generic root 为该轮新造 inbox；
MCPET_CONFIG_PATH 指不存在配置。网络 mock 只用于测试，不给 live 声明。
应用 fixture 禁 load_env、构造前禁 scheduler.start（避免同步补饭点排联网任务），
AccountMonitor 注入 UI stub；配置测试用内存 dotenv reader，不读取任何 .env。

```powershell
$quotaPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
# 每次复现把此路径换成全新 TEMP 目录；以下是本轮实际 verification 路径
$quotaEvidence = 'C:/Users/DW/AppData/Local/Temp/mcpet-c-quota-final-1791751045265/verification'
$env:MCPET_DATA_DIR = "$quotaEvidence/data"
$env:TEMP = "$quotaEvidence/tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:MCPET_WATCH_PROCESSES = '0'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:DEEPSEEK_API_KEY = ''
$env:MCPET_AGENT_ROOTS = "claude=$quotaEvidence/absent-claude,codex=$quotaEvidence/absent-codex,generic=$quotaEvidence/absent-generic"
$env:MCPET_CONFIG_PATH = "$quotaEvidence/absent-config.json"
& $quotaPython -m pytest tests/test_quota_panel.py tests/test_settings.py tests/test_companion_panel.py -q -s
# applicable.log 实际还包括原 app_actions/main_startup/dialogs/config：66 PASS
& $quotaPython -m pytest tests/test_quota_panel.py tests/test_settings.py tests/test_companion_panel.py tests/test_app_actions.py tests/test_main_startup.py tests/test_dialogs.py tests/test_config.py -q -s
& $quotaPython tests/test_companion_panel.py --screenshots <新TEMP目录> 'C:/Users/DW/orca/workspaces/mcpet/mcpet-pet-20261011'
# 最终独占时段原联合、完整、compile/diff（结果在末尾）
& $quotaPython -m pytest tests/test_companion_integration.py -q -s
& $quotaPython -m pytest tests/test_quota_panel.py::test_native_active_exit_reaps_children_releases_lock_and_saves_position -q -s
& $quotaPython -m pytest -q
& $quotaPython -m compileall -q src tests
git diff --check
```

## 真实限制 / 集成交接

- C 分支不含 A/B 领域实现；fixture 只证明 UI 接线。B single-flight/换源丢旧结果/子进程
  回收由 B 验证，最终组合由唯一集成 Worker 验证，不将 UI stub 冒称真实账号监控。
- 原 tests/test_app_actions.py、test_main_startup.py、test_companion_integration.py 不在
  本轮 C write_paths；主轨决定唯一集成 Worker 给默认账号源注入离线 stub，保留原断言。
  C 自域 companion_panel 已注入 stub，native 图也硬拒绝模型/MCP/HTTP 网络。
- 未读 .env/凭证/旧聊天/既有日志或 ledger，未访问用户 GUI49784/launcher38676/
  monitors23860/48728，未实测 Orca 缓存或 DeepSeek 账号网络；不做模型/账号写操作。
- 双角色重启偏好/动画/透明帧/锚点性能属于 A；C 只读真实素材截图不替代其整域验收。
  旧单实例/拖拽/TTL/退出原联合已运行；heartbeat未过，完整性能验收仍待组合返修。
  用户实例优雅切换、最终账号只读验收由主轨完成。
- 不发布安装包/PR/开机启动，不改注册表，不合回 root，不删 worktree。
- 最终通知使用 [orca-cli](C:/Users/DW/.agents/skills/orca-cli/SKILL.md)，新 root terminal
  `term_2a23bbea-71c5-4f99-b15f-77e5b8ca591b`；accepted 只证明输入接受，不证明集成完成。

## 最终交付验证与提交

包含新增独立原生退出测试的 `verification/full-delivery.log`：
**1 failed /340 passed /103.99s**。本轮最终完整 pytest **未通过**。
唯一失败为 `tests/test_companion_integration.py:103` 原 heartbeat gate：
**554.15ms>150ms**（720 ticks），首panel **467.37ms**；stop **5.1700ms<50ms**。
四入口/拖拽/writer=1/thread_running=false/errors=[]，原门槛原样保留；
独立有限退出/PID回收/锁删除/重启位置回归在该全套也通过。

- `python -m compileall -q src tests`：exit0，`verification/compile-final.log`。
- 首普通 `git diff --check`：exit0，`verification/diff-final.log`；当时不含未跟踪新测试。
  随后的首次 cached check 为RED：test_quota_panel.py:421、test_settings.py:69 多余EOF空行。
  shell批次仍生成代码提交；保留其历史，以后续普通提交仅删两处空行，没有amend/reset。
  最终基于FF起点的全分支diff check（含新文件）与cached check均exit0，
  `verification/diff-delivery-green.log`；不将首普通check冒称全覆盖。
- 适用66 PASS、独立退出1 PASS、v4六图审阅GREEN各自成立，不当成全套GREEN。
- 功能提交 `eb6858e7c5c98c541fed62224f48ed8c6d1a322a`。
- 代码最终提交（仅后续EOF空行修正）`cde12f86d330039b4d3e89e4313daabb251c9e46`；
  与全套测试版逻辑一致，空白改动不重新挑性能GREEN。再compile exit0，
  `verification/compile-delivery-green.log`；全分支diff exit0。
- 本文单独文档提交随后普通push同一原分支；包含本文件的交付tip由
  `git rev-parse HEAD` / `git ls-remote --heads origin songconmaisaix31-design/mcpet-app-20261011`
  精确核对并发送root，不在文件内伪造自身commit hash。
- 测试已有限结束，最终仅允许唯一集成 Worker 普通merge；remaining heartbeat RED待组合后
  如仍复现退回原C。真实账号/用户GUI验收未执行，主轨负责。

## 2026-10-12 冷显示 / 配额刷新领域返修 basis

本节追加历史，不覆盖以上首次 RED。原 WT/branch 未重建，先确认干净，从
`1b2b08ed0dcd5790a11a14d70bc1fbf8d1d83488` fetch 后 FF 已发布集成 checkpoint
`bf5ff01ca8de33ad417eb7fd1cacd64030177d5b`，完整读其 `HANDOFF-INTEGRATION-QUOTA.md`。
本 basis 因该 FF 已包含 A/B；C 没有合并其他轨或改动其领域。
本轮代码提交 **`876ae0c8632ded4b172dfac35be5184ad1295bda`**，只改
`src/main.py`、`src/pet/dialogs.py`、`tests/test_quota_panel.py`。
本追加另作文档提交；最终 tip 由 push 后独立 ls-remote 核对，不在文件内写自身 SHA。

### 已实施的 C 修复与契约

- 同一冻结 snapshot 的刷新/重开只更新状态文字和倒计时，不删除再建所有账号行。
  新 snapshot 若 provider/桶数/金额行数相同，则原位更新来源名称、状态/错误说明、
  时间戳、桶名称/值/UNKNOWN/警示颜色、reset、精确 Decimal/币种、stale 提示。
  结构改变仍重建；换 key 的 main 路径仍把 account_snapshot 清为 None，立即隐藏并
  deleteLater 旧卡片，仅显示等待查询，不冒用旧余额。保留真实源每次发布。
- 同一角色 `_sync_panel` 不重复 setStyleSheet；选择按钮状态仍重新同步，以保留失败回滚。
- `character_preview(sheet)` 对 A 的 AnimationSheet 读取已有公开 `image`（原始 idle 首帧），
  转 QPixmap 给原托盘和 88px 预览；普通 SpriteSheet 保留 frame('idle',0)。没有额外 decode、
  预热、atlas 缓存或 A 文件改动，避免 C 在工作动画和 idle atlas 之间触发淘汰/重载。
  自域回归验证真实 QImage/QPixmap 显示及不调用 frame、不改变活动 atlas；不是模型/账号证据。
- 查询失败后的刷新保留原错误/过时标记并立即显示“刷新中”，只有新 snapshot 成功才恢复正常。
  B AccountMonitor 同对象 reconfigure/refresh/singleflight 契约保持；没有第二个 monitor。
- 没有改 action_panel 的同步 showNormal/show/raise_/activateWindow，非 Windows 路径保持。
  没有延后激活/heartbeat、等待 TTL、删旧断言、改预算、操作其他用户 GUI 或全局系统设置。

### 冷进程对照：发现与未解决项

唯一证据根：`C:/Users/DW/AppData/Local/Temp/mcpet-c-perf-1791754262774`。
`cold_baseline.py` 每个 case 为独立进程，空 QDialog 和面板同 700×720/最小560、同字体、
真实 Windows DPR1.5；heartbeat 在创建/显示前开始，计入构造/原生窗口创建/激活/最小化。
不含监控或账号联网。日志分别保留；这些是诊断，不是原联合 GREEN。

| 日志 | 原始样本 ms / 结论边界 |
|---|---|
| cold-bare.log | 空窗口 construct0.23 / show336.71 / minimize64.03 / heartbeat555.35。面板/账号不是该空窗口阻塞的必要条件。 |
| cold-panel.log | 面板 construct62.95 / show309.60 / minimize85.23 / heartbeat571.23；Expose70.38。不能据此排除面板成本。 |
| cold-frameless.log、cold-no-shadow.log、cold-custom.log | show295.85 /310.71 /392.11，均未解决；未采用这些样式改动。 |
| cold-no-activate.log | show78.49，Qt activateWindow249.95，heartbeat571.46；成本移动，不是可删激活的证据。 |
| cold-native-activate.log / cold-native-activate-detail.log | 首整段原生激活236.04；细分 SetForegroundWindow156.03，own_foreground=true，heartbeat399.10。仍超过原门槛。 |
| cold-native-local.log | SetActiveWindow269.37，随后 SetFocus0.55 / SetForegroundWindow0.35，heartbeat721.13。成本跟随首次激活。 |
| cold-native-wndproc.log | 仅 subclass 自有 HWND 计时，结束前恢复 WndProc：WM_ACTIVATE159.05、同期 WM_GETOBJECT45.35；show166.99 / native setup40.46 / heartbeat416.15。尚不能认定根因，也未关闭可访问性。 |

所有原生 API 对照只作用于自己创建的窗口；own_foreground 读值不当成人工前台/键盘焦点验收。
未找到可保持同步用户激活语义且满足原预算的稳定原生替代，所以**未实施 Windows 激活适配**。
首次 native show 仍属 C 待定位限制，不归因 AccountMonitor，也不凭 API 返回值宣称完成。

### 本轮首次 RED / 单列 GREEN

| 路径 / 命令 | 结果 |
|---|---|
| targeted.log；quota_panel/companion_panel/settings | 首命令遗漏 basetemp 父目录：6 passed /27 setup errors /0.92s，WinError3。执行命令错误，修正 mkdir 后重跑；与既有 helper setup refresh 环境失败分列。 |
| targeted-fixed/result.log；同三文件 | 33 passed /35.31s；实际30 action_quota3.83ms、stop2.82ms。独立活动退出 heartbeat141.22 /首panel120.22；仅这次单项样本 GREEN。 |
| old-joint/result.log；原 test_companion_integration.py -q -s | **1 failed /10.41s**；heartbeat383.09>150 /首panel294.02 /stop5.6404<50。四入口 visible/正常rect/非iconic、拖拽/writer1/thread停止/errors[]前置通过；heartbeat后的原顶层PID/锁/重启断言 NOT_RUN。 |
| new-combination/result.log；原 test_dual_pet_quota_integration.py -q -s | **1 passed /1 failed /21.61s**。完整契约/退出通过，性能RED：heartbeat2290.13 /首panel436.85。work2609.64 /duplicate445.21 /held-refresh15.50 /new-generation62.52；stop2.1838、quit-to-reaped0.8317s、unreaped=[]/lock移除/重启通过、network0/errors[]。 |
| profile-combination.log、profile-combination/profile-observe.json | 单次原协议函数计时，完整契约断言通过，heartbeat1702.53 /首panel287.94仍RED；当时未把性能 assert 放入诊断父脚本，不冒称两测试通过。C _icon260.89 /新结构set_accounts486.66；A set_character544.90/380.83/135.66，定位后才追加 idle预览/原位更新修复。 |
| targeted-row-preview/result.log | **1 failed /34 passed /40.58s**：新增测试错误地把隐藏待deleteLater旧标签计为可见余额。修正为卡片隐藏/实际布局等待查询；没有扩大预算。该次独立退出heartbeat135.26，仅样本GREEN，不替代全套。 |
| applicable-final/result.log；下列七文件 | **71 passed /51.97s**。实际30 action_quota3.7535ms、stop4.4362ms；包括同结构新源全字段/UNKNOWN/精确金额更新、错误stale恢复、换key清卡片、静态预览/托盘不淘汰atlas、保存取消/拒绝新动作/活动任务有限退出。独立退出回收2子进程/锁/快速移动保存位置/重启通过；其 heartbeat168.79 /首panel147.89 **仍为性能RED**，此退出测试不替代原性能门槛。 |
| profile-after-c-fix.log、profile-after-c-fix/profile-observe.json | 修复后单次真实两monitor/三受控source进程原协议诊断，**exit1**：顶层契约首先失败 role_frames_advanced=false；后续 heartbeat assert NOT_RUN，测得heartbeat3261.51 /首panel765.25明确RED。work4329.47 /duplicate394.82 /held19.85 /newgeneration137.26。四入口内部恢复断言执行，network0/errors[]；回收观测unreaped=[]、lock移除、重启probe断言通过、stop1.8346/quit-to-reaped0.8563s，不冒称完整契约GREEN。 |

后诊断中，C `_icon` 已为 **0.477/0.315/0.145ms**；同快照 set_accounts **0.040–0.534ms**，
30次实际 UI 路由回归独立成立。A set_character **637.36/1203.02/589.41ms**，后续 _scaled_frames
**220–358ms**，交给原 A，不改领域。首次 panel.show **559.27ms**，换 key 后新结构卡片
重建 **425.16ms** 仍是 C remaining RED；普通同结构更新复用不冒称解决结构重建或首次显示。
样本运行耗时波动，未将 CPU、字体、WM_GETOBJECT 或账号 worker 判定为唯一根因。

### 重现命令 / 收尾

```powershell
$quotaPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$quotaRepair = 'C:/Users/DW/AppData/Local/Temp/mcpet-c-perf-1791754262774'
$quotaRun = "$quotaRepair/<新RUN_NAME>"
New-Item -ItemType Directory -Force -Path "$quotaRun/tmp" | Out-Null
$env:TEMP = "$quotaRun/tmp"
$env:TMP = $env:TEMP
$env:MCPET_DATA_DIR = "$quotaRun/data"
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1' # 本机实际DPR1.5
$env:PYTHONIOENCODING = 'utf-8'
$env:MCD_MCP_TOKEN = 'mock-token-only'
$env:STEPFUN_API_KEY = 'mock-key-only'
$env:DEEPSEEK_API_KEY = ''
$env:MCPET_WATCH_PROCESSES = '0'
$env:MCPET_AGENT_ROOTS = "claude=$quotaRun/absent-claude,codex=$quotaRun/absent-codex,generic=$quotaRun/absent-generic"
$env:MCPET_CONFIG_PATH = "$quotaRun/absent-config.json"
& $quotaPython -m pytest tests/test_quota_panel.py tests/test_settings.py tests/test_companion_panel.py tests/test_app_actions.py tests/test_main_startup.py tests/test_dialogs.py tests/test_config.py -q -s --basetemp "$quotaRun/pytest"
# 新RUN_NAME，各自串行；原日志对应本节表格。
& $quotaPython -m pytest tests/test_companion_integration.py -q -s --basetemp "$quotaRun/pytest"
& $quotaPython -m pytest tests/test_dual_pet_quota_integration.py -q -s --basetemp "$quotaRun/pytest"
# 分段原生诊断脚本存证于TEMP，不复制到A/B/集成测试域：
& $quotaPython "$quotaRepair/cold_baseline.py" bare
& $quotaPython "$quotaRepair/cold_baseline.py" native-wndproc
& $quotaPython "$quotaRepair/profile_combination.py" --run "$quotaRun"
& $quotaPython -m compileall -q src tests
git diff bf5ff01ca8de33ad417eb7fd1cacd64030177d5b --check
git diff --cached --check
```

实际各 pytest 使用独立 basetemp，TEMP/MCPET_DATA_DIR 为本证据根新造 data/tmp；原生子协议
再显式限定其新造 inbox，并硬拒绝 parent/worker 网络，未读真实日志或任何凭证文件。
`compile-final.log` exit0；全分支含新文件与 cached diff check 均 exit0。
未改旧/新集成 test 的断言、时序、协议或 B 刷新接口；30次真实 action_quota 在 C 自域另测。

依据 root 最新“最终可完成安全适用/compile/diff+Handoff/push供A接续”协调，
**本返修完整 pytest NOT_RUN**，组合核心仍 RED，不能宣称完成。不对同版无变化全套挑GREEN。
原 v4 六图布局/配色/idle首帧外观没有改变，按允许复用其已审 DPR1.5 视觉证据；本轮未重新
出六图，最终组合 native 截图/真实账号/人工前台键盘语义验收仍待后轨/主轨。
历史首RED与所有TEMP对照保留，独立运行日志为对应样本依据；不保证早期复用路径的汇总JSON
永不覆盖，不以另一次同名JSON值改写首次样本。

测试/原生探针已有限结束（最后三受控进程44788/43264/44812回收观测无残留）。
不改主计划、A/B文件、集成tests，不合回root；最终 push/ls-remote精确tip/干净后通过
[orca-cli](C:/Users/DW/.agents/skills/orca-cli/SKILL.md) 通知 root
`term_2a23bbea-71c5-4f99-b15f-77e5b8ca591b` 和唯一集成
`term_7a4e4c11-2813-49cd-8879-43311e269929`，交回独占时段并停止，供原 A 接续。

## 2026-10-12 第二轮返修：卡片生命周期与有界激活诊断

原 C / 原 WT / 原分支 `songconmaisaix31-design/mcpet-app-20261011`。
先确认干净，从 `d037c5cf6b384d4930dbadef97b0240881978b73` fetch 后独立核对
远端集成分支 `songconmaisaix31-design/mcpet-companion-integration-20261011`，
FF 到 root 授权的 `7ffeebd03179a2796cb88fb73e52929d22bbca6c`。
未 merge sibling，未新建 Worker/WT；最新计划、A/B/C及集成交接已读。
本轮业务及自域回归提交：`0c4c5f80bd291a3faeb16b8ccb61e545601c7c5a`；随后单独提交本交接。
精确最终交接 tip 在终端通知及独立 `ls-remote` 回执中；不 amend/force push。

仅修改 C 的 `src/main.py`、`src/pet/dialogs.py`、`tests/test_quota_panel.py`、
README 和本文件。A/B、主计划、旧三 test 和新 dual-pet 集成 test/协议/门槛均未修改。

### 已交付的生命周期行为

- 只在实际快照中出现 provider 时创建行；换 key 不造快照、不预建行。
- key 保存成功后，在构造/更换余额源前同步清空旧快照和旧错误。隐藏的旧卡也擦除
  全部标签/金额/更新时间、tooltip、accessible name/description、可访问文本、条值和
  倒计时引用。QProgressBar reset 为 -1 并隐藏，UNKNOWN 不画假 0%。新源构造失败
  同样保持清空；普通查询失败仍保留当前来源快照并标过时。
- 隐藏的已清空行有限复用；下一实际快照按 provider/出现次序及实际子行数增减，
  保留未变化的行/子对象，完整覆盖名称、状态、来源提示、时间、分桶和各币种 Decimal。
  provider 顺序及额度/金额分区随真实结构更新。实际空快照释放全部缺席行，
  不缓存历史 provider 或历史快照。
- 仅同步改布局时暂停该页重绘，finally 恢复调用者原设置；没有排到 gate 后显示、
  隐藏或激活，没有 event-pump、预热、TTL 等待。四入口仍走原统一 action_panel。
- provider 标题/状态沿用旧版本非可选标签属性；实际额度摘要、金额和原有有意义的
  可复制文本保留。没有全局去掉选择、accessibility 或修改焦点/Windows 激活实现。
- 自域回归涵盖对象/子行复用、结构增减与分区/顺序、连续换 key、真实空快照释放、
  新源失败、重绘异常恢复、Qt accessibility 文本/值清空、30次实际 action_quota、
  DPR1.5 的560/700可读性与活动任务最终关闭。

### 本轮证据目录与 first RED

独立证据根：`C:/Users/DW/AppData/Local/Temp/mcpet-c-lifecycle-1791758072944`。
各次运行独立新目录、result.log、command.json、TEMP/MCPET_DATA_DIR/fixture roots。
`run.py` 是本次 TEMP 子进程启动脚本，literal allowlist 环境，不打印/复制继承环境。
guard 禁止真实 socket 和证据根外的 .env/真实账号 CLI；仅设置测试允许创建的新
TEMP 凭证夹具。scheduler.start 在构造前隔离。未读用户凭证/日志/聊天/ledger，
未操作用户 GUI 或访问账号网络。

`before/data/metrics.json` 首 RED（实际 A 角色模块及真实 Qt，两个监控显式 UI stub）：

| 样本 | first_panel wall/thread CPU | key_save wall/CPU | 新快照 wall/CPU | 旧隐藏非空标签 | 复用 |
|---|---:|---:|---:|---:|---:|
| before | 608.8891 / 468.75ms | 110.6926 / 109.375ms | 205.2712 / 187.5ms | 36 | 0/5 |
| after | 298.9793 / 234.375ms | 93.2998 / 93.75ms | 86.8310 / 78.125ms | 0 | 5/5 |

after 是一次独立样本，不能宣称冷开性能通过；first_panel 仍超过150ms。
后续仅恢复新增标题/状态辅助标签的旧属性并避免创建无用的第二桶时间标签，
未修改真实数据/字体尺寸/布局规格。上述 before/after 文件原样保留。

| 验证目录 | 结果 | 说明 |
|---|---|---|
| lifecycle-tests | 23 passed / 1 deselected，31.82s | 首自域卡片回归；30action_quota3.0662ms |
| applicable | 61 passed / 1 failed，70.82s | 首旧main重复启动收到普通启动 JSON；未改该测试，未断言由卡片导致 |
| old-joint | 1 failed，11.96s | heartbeat646.03ms / 首开542.64ms / stop6.5979ms |
| new-joint | 1 passed / 1 failed，23.68s | 契约GREEN；heartbeat2934.91ms / 首开621.34ms / stop8.2941ms |
| owned-final | 40 passed / 1 failed，53.03s | 首四入口即时观察前台false；当时尚未区分异步事件 |
| focus-events | 1 passed / 2 failed，14.36s | 有界事件观察；新增700案例错误要求内容即使可容纳也必须滚动，属探针断言错误 |
| focus-current-thread | 2 passed / 1 failed，14.83s | 560/700 GREEN；真实有界前台项仍RED |
| accessible-text | 1 passed / 25 deselected，1.67s | 补验Qt可访问文本接口也没有旧文字 |
| c-final | 41 passed / 1 failed，67.69s | 修正后的三份C自域完整运行；唯一前台断言RED，未放宽 |
| compile | exit0 | compileall src tests |

原 basis 完整450pass/2fail182.31s以及其旧/新/native心跳首RED仍为历史证据。
本轮 old-joint 前置四入口可见/正常rect、拖拽、writer1、stop<50、errors[]通过；
heartbeat后原PID/锁/重启断言未执行，不能把前置结果当作原联合全部通过。
自域独立活动任务退出不替代原心跳：applicable stop6.8375ms，owned-final stop4.5540ms，
两真实 AgentMonitor 子进程回收、最后移动位置保存、锁释放及重启恢复另有GREEN。
它们自身诊断心跳631.14/421.54ms仍为RED样本，不能称性能GREEN。

新组合使用真实默认 AgentMonitor/AccountMonitor + 可pickle受控sources，非UI监控stub：
角色帧推进、实时通知拖拽、金额精确、旧代结果丢弃、单飞3次查询、换key、三子进程
全部有限回收、writer1、全部窗口关闭、锁释放及角色重启恢复通过，network_calls=0，
errors=[]。退出到回收2.02484s，无unreaped。work3196.37ms / duplicate315.71ms /
held-refresh39.99ms / new-generation70.94ms 是阶段样本，不是归因结论。
没有单独证明 A 必要解码本轮稳定越门槛，不向A归咎整体阶段、不跨域修改。

### 有界冷显示/激活证据及诚实限制

`version` 实测 PySide6/Qt **6.12.0**，windows QPA，DPR1.5。
`activation/data/activation.json`：正常 action_panel 首次构造23.5515ms，
数据渲染34.1443ms，show370.4518ms / threadCPU234.375ms，raise1.4054ms，
显式activate0.0713ms，总437.5019ms / CPU296.875ms。
自有 WndProc 只在正常创建 HWND 后观察，并在关闭前恢复；记录父事件/深度、
wall、threadCPU及子事件排除后的exclusive时间，不能嵌套相加：
show内 WM_ACTIVATE278.6386ms/CPU171.875ms，内嵌 OBJID_CLIENT(-4)
WM_GETOBJECT130.5035ms/CPU109.375ms（自身exclusive27.9096ms/CPU15.625ms）。
线程CPU计时粒度约15.625ms，小段0/跳变不等于没有CPU工作。
同进程随后显示的自有空Qt窗（同parent/尺寸/flags）show157.7288ms/CPU62.5ms，
WM_ACTIVATE69.4351ms，内嵌(-4)8.9161ms。它是在面板之后、applicationState不同，
不是独立冷进程系统基线，不能据此把成本归为Windows/外部系统。

[微软WM_GETOBJECT说明](https://learn.microsoft.com/en-us/windows/win32/winauto/wm-getobject)
支持将消息识别为可访问对象查询，不能识别客户端身份或证明性能根因。
已核对[实际Qt6.12.0 requestActivateWindow源码](https://raw.githubusercontent.com/qt/qtbase/v6.12.0/src/plugins/platforms/windows/qwindowswindow.cpp)：
applicationState及activationBehavior影响其分支。运行时nativeInterface返回None，
behavior未暴露；未假设AlwaysActivateWindow分支，更未套用6.9源码。
show前ApplicationInactive，show后nativeforeground/visible为true，非iconic；
显式activate前Qt applicationState仍Inactive。异步状态与原生状态分别记录。

按root新候选，仅做一个限定装饰标签的TEMP对照配对，未用于生产：
`label-reference`与`label-decorative`均独立新进程，一次各一；只改变23个装饰标题、
状态/重置/时间标签的选择属性，保留额度摘要、金额、来源错误及可访问性。
show381.1086ms/CPU265.625ms → 347.1367ms/CPU234.375ms，
总action445.6108ms→437.9133ms；(-4)125.6876ms→98.0589ms。
同进程后开empty show120.9402→123.4064ms。没有消除门槛RED，单对样本不足以证明因果，
故未采用装饰属性优化，没有再扩展一堆控制。
[Qt6.12 QLabel源码](https://raw.githubusercontent.com/qt/qtbase/v6.12.0/src/widgets/widgets/qlabel.cpp)
中的文本控制/文档布局路径只是支持候选机制，不能替代实测归因。

四入口新增自域native-focus首RED保留在`native-focus`，duplicate恢复可见/正常rect，
但即时foreground=false。补齐所有入口即时观察在`owned-final`，不直接认定真实未激活。
按[QWindow平台激活请求说明](https://doc.qt.io/qt-6/qwindow.html#requestActivate)
及[QWidget Windows激活限制](https://doc.qt.io/qt-6/qwidget.html#activateWindow)，
改为监听activeChanged/focusChanged并有界条件观察，不固定睡眠、不改产品/旧协议。
`focus-current-thread`中，四入口activeChanged分别15.3821/8.7705/10.7549/7.7133ms；
观察到约1501–1503ms时Qt active=true、visible=true、iconic=false、正常rect，
当前GUI线程原生键盘焦点归属、Qt字段焦点和受控键入均true，nativeforeground均false。
仅QTest直接输入成功不代表OS用户键盘/人工前台验收，前台断言仍RED，原因UNKNOWN。
保留连续10ms心跳，补充探针首开期间max gap1161.2035ms；不靠等激活使性能GREEN。
stop0.1131ms，面板/任务线程有限关闭。该样本UI监控stub，与新组合真实监控分列。

最终`c-final`同版本完整自域运行：30action_quota5.1001ms；同步stop阶段自域1.5293ms。
真实AgentMonitor活动退出stop4.1015ms，两个子进程33544/36620回收、位置/锁/重启通过，
其诊断hb678.48ms/首开590.04ms仍RED。独立前台项四入口activeChanged约8.68–16.36ms，
在1500–1510ms仍nativeforeground=false，其余可见/rect/Qtactive/自线程焦点/受控键入true；
stop0.0974ms，任务线程退出。此最终前台探针的诊断hb1182.8441ms亦保留，不称性能GREEN。

首focus探针误用GetGUIThreadInfo(0)，实际查询前台线程，不是当前GUI线程：
这部分早期native_keyboard_root=false不能用作本进程焦点结论。
已依据[微软参数说明](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getguithreadinfo)
改为GetCurrentThreadId显式查询本探针GUI线程，只保留归属布尔值，不枚举/操作其他窗口。
早期错误日志保留。700新增断言亦纠正为内容不裁切，560原滚动要求保留。
此前用户恢复记录的helper setup refresh/路由/内存异常仍单列环境证据，非测试失败；
本轮没有同类环境错误，没有循环重试。

### 重现命令、交接边界

```powershell
$quotaPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$quotaLifecycle = 'C:/Users/DW/AppData/Local/Temp/mcpet-c-lifecycle-1791758072944'
# run.py运行名必须新建，原目录保留不可复用覆盖；{run}由runner替换。
& $quotaPython "$quotaLifecycle/run.py" replay-c -m pytest tests/test_companion_panel.py tests/test_settings.py tests/test_quota_panel.py -q -s '--basetemp={run}/pytest'
& $quotaPython "$quotaLifecycle/run.py" replay-old -m pytest tests/test_companion_integration.py -q -s '--basetemp={run}/pytest'
& $quotaPython "$quotaLifecycle/run.py" replay-new -m pytest tests/test_dual_pet_quota_integration.py -q -s '--basetemp={run}/pytest'
& $quotaPython "$quotaLifecycle/run.py" replay-show "$quotaLifecycle/activation_probe.py"
& $quotaPython "$quotaLifecycle/run.py" replay-compile -m compileall -q src tests
git diff 7ffeebd03179a2796cb88fb73e52929d22bbca6c --check
$quotaBranchBase = git merge-base origin/codex/desktop-companion-20261011 HEAD
git diff $quotaBranchBase --check
git diff --cached --check
```

各实际命令、退出码和耗时见对应command.json；原旧/新联合各改动后一次，未改150/50，
未使用showlocals、预热、延后激活/heartbeat、TTL或放宽断言。
**本轮完整仓库pytest NOT_RUN**：核心仍RED，按root授权不重复全套挑GREEN。
**本轮更新六图 NOT_RUN**：未改视觉规格，560/700/DPR1.5自域几何通过，
复用root已审basis六图的视觉历史，不能宣称新结构经过人工图审或真实账号验收。
激活/冷显示根因仍UNKNOWN；前台不能以Qtactive/API返回或fixture输入假装人工通过。
不接管A/B领域，也不认为卡片复用已修复整体联合。此tip供root按剩余RED决定下一返修。

所有本轮Qt/pytest/native子协议已有限结束，当前slot idle；普通push及独立ls-remote后
通过[orca-cli](C:/Users/DW/.agents/skills/orca-cli/SKILL.md)向root与原集成通知精确tip，
交回独占时段并停止。输入accepted不冒充接收者已读或开始合并。
不合回root，不改用户正在使用的GUI/凭证/日志/系统设置，不发真实模型/MCP账号请求。
