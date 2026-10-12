# Agent 宿主接入验证记录（2026-10-12）

用户事实源：功能放入已有 Agent 工作台，通过 OpenCode / Claude Code 原会话操作，
不增加独立界面。单 Agent 执行，计划见 `AGENT-HOST-PLAN.md`。

## Git

- 基线：`af8ef3988689721a507c0bac29f9515db5ff3284`。
- 计划：`889d8dc`。
- 功能分支：`codex/agent-host-integration-20261012`，
  `bd8e4ea651c067ab1dccce71444aeb07cad43f26`，已 push。
- 普通 no-ff 合入 `codex/desktop-companion-20261011`：
  `f9903cc25f047047fb1732b319fbaceb2ef29180`。
- 合并父提交依次为基线与功能提交；无冲突，没有修改公共历史。

## 实现

官方 MCP SDK stdio 服务提供 17 tools、三项资源和一个 prompt；复用现有业务、
Guard、营养台账、额度源、日志 provider 和 DailySchedule。默认模块入口先进入 MCP，
不导入 Qt；桌面仅显式 `--desktop` 兼容。新入口不创建任何独立模型请求。

已为本仓库生成项目级 OpenCode / Claude Code 配置、原生 hook 与指令。
机器路径配置被 gitignore 排除，可通过接入安装器在其他项目重建。
OpenCode 插件只提交会话元数据与已完成助手消息的数值用量；Python 丢弃正文和秘密字段。
本机写入跨宿主加锁。提醒走原上下文/toast；用量阈值复用原 busy/heavy 判断。

两段已有动作导出 GIF 资源，各 126 个编码帧、总时长 10160 ms。
原 127 帧 RGBA 页保留，相同 GIF 画面合并时长。没有新增外部播放器窗口。

## 验证命令与结果

使用现有项目 Python 3.13.12，MCP SDK 1.30.0。业务 fixture 不发真实外部写入。

```powershell
python -m pytest tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py -q
```

结果：**315 passed in 36.34s**。原始日志：`.tmp-test-data/agent-host-delivery-validation.log`。
其中新的宿主测试覆盖真实 stdio initialize/list/call/resources/prompt/关闭、任意 cwd 启动、
默认入口、中文 UTF-8、未导入 Qt、确认闸门、价格改变、报价来源校验、
提交后网络异常与缺少订单号均为 delivery_unknown、审计一致、同会话不重放、
真实营养选择与份数、四个进程记账不丢失、设置保存、hook 隐私筛选、
跨宿主饭点去重、用量事件去重与阈值提醒，以及 Node 插件调用真实 Python hook。

```powershell
python -m compileall -q src scripts tests/test_agent_host.py tests/test_account_balances.py
git diff --cached --check
python scripts/build_agent_animations.py
python -m src.agent_install --client both
opencode mcp list
claude mcp get mcpet
```

- compileall 与最终 staged diff 检查通过。
- GIF 导出：frying/outfit 各 source_frames=127、gif_frames=126、duration_ms=10160。
- 安装器成功生成两宿主项目配置；重跑不重复 hook，保留其他 MCP/权限/hook。
- OpenCode 1.18.35：实际 `mcpet connected`，记录在 `agent-host-opencode-connection.log`。
- Claude Code 2.1.238：项目 stdio 已发现，**Pending approval**；
  修正后的命令无 SessionEnd 路径错误，记录在 `agent-host-claude-discovery.log`。
- 原桌面进程 PID 32900 已不在运行。退出控件点击返回 app_not_found，
  不据此声称本次 UI 点击触发了正常退出；没有强制终止进程。

## 首次失败保留

- GIF 初次以“编码帧数等于 127”校验失败：编码器合并相同帧；修为校验完整时长，
  没有篡改原画面或缩短动作。
- 首轮测试：6 failed / 29 passed（报价 fixture 字段不符合既有 price 契约，
  MCP 返回 `dict` 未产生 structuredContent）。修正 fixture 字段与 `dict[str, Any]`
  返回类型后 35 passed。日志 `agent-host-first-tests.log` / `agent-host-retest.log`。
- 首次 Claude 原生命令：Windows 反斜杠被 Git Bash 消耗导致 hook command not found；
  修正为正斜杠及 shell 引用，没有修改宿主权限。
- UTF-8 加强验证初次 1 failed / 20 passed：测试 subprocess 以 GBK 读 Node UTF-8。
  明确 UTF-8 解码后通过。原日志 `agent-host-utf8-retest.log` 保留。
- 一轮回归 1 failed / 310 passed：旧额度 fixture 使用任意浮点 time.time()，
  毫秒往返差一个浮点尾数导致严格相等失败；改为整秒的精确毫秒样本，
  原额度、状态、独立桶断言保留。日志 `agent-host-verified-regression.log` 保留。
- 首次 staged diff 检查发现新 core.py 多一个末尾空行，已修正。
- 此前桌面 foreground/heartbeat 和小尺寸滚动断言的历史 RED 不改写为通过。

## 真实剩余限制与未执行

- Claude 首次项目 MCP 信任需用户在原 Claude Code 中确认；未修改其审批状态。
  运行中的原宿主需要重开此项目会话加载新接线。
- 没有发送真实模型请求、真实领取/下单/撤单，也没有完整厂商余额实时验收。
- 终端宿主的 GIF 内嵌播放尚未验证；只有工具/资源读取通过。
- toast 测试接收端是 fixture，不能视为真实 TUI 前台提醒或人工接受。
- 宿主关闭时不保证后台提醒；Claude hooks 不读取 transcript，不自动采集其 token 用量。
  其已有配置日志仍可按请求查询。
- 其他已运行宿主保留已有环境设置；重开后读取新配置。
- 本轮是上述 15 个测试文件的回归，不是全仓/旧桌面整体动态验收；没有放宽或 skip 历史 GUI 断言。
