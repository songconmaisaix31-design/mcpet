# 在原 Agent 里使用 McPet

用户只和正在使用的 OpenCode / Claude Code 对话。McPet 是该会话的一组 MCP 工具，
由宿主通过 stdio 启停，无 QWidget、托盘、独立聊天界面或模型调用。现有业务与本机台账复用。

## 一次接入

```powershell
python -m pip install -r requirements-agent.txt
python -m src.agent_install --client both --project "你的项目目录"
```

在 McPet 仓库运行接入命令；`--project` 是以后使用原 Agent 的项目，不必进入 McPet 才能对话。
可只接一个宿主：`--client opencode` 或 `--client claude`。安装器将当前 Python 和 McPet 路径写到
项目配置，不修改全局账号、权限或其他 MCP 服务。移动 McPet 或切换 Python 后重跑安装器。
当前机器的本仓库已生成这两份接入配置。Claude Code 的首次项目 MCP 信任由其原生流程处理。
已运行的宿主需要重开此项目会话以加载新配置。

仅 Agent 模式的依赖不含 Qt；完整旧桌面兼容依赖仍在 `requirements.txt`。
麦当劳相关操作沿用已有 `MCD_MCP_TOKEN`；官方余额查询沿用 `DEEPSEEK_API_KEY`。
本机设置位于原数据目录 `.env`（`MCPET_DATA_DIR` 可覆盖），不把凭证发送到对话或配置文件。
无需给 McPet 再配置模型 Key。原宿主会话照常使用其现有模型与计费。

## 正常对话

- “今天有什么券？只查一下。”
- “查最划算的午餐，先给我门店和价格。”
- “按这个方案准备订单。”看到摘要后再明确确认；不会把查询当成下单授权。
- “巨无霸的营养是多少？我吃了 1.5 份，确认记账。”
- “看今日营养记录 / 本机用量 / 当前会话状态 / 已接账号的剩余额度。”
- “饭点改成 12:15 / 关闭饭点提醒 / 城市改为上海。”
- “切到麦麦，炸薯条循环 / 换装一次 / 停止动作 / 休息 / 唤醒。”

## 能力与结果

| 原能力 | 原 Agent 内的入口 | 结果与限制 |
|---|---|---|
| 角色、休息、动作 | `mcpet_status` / `mcpet_pet` | 保存本机状态；动画为资源，不创建播放窗口 |
| 城市、饭点、提醒、显式日志目录 | `mcpet_settings` / `mcpet_configure` | 日志来源仅 claude/codex/generic 的明确目录；已有环境变量优先级保留 |
| 优惠券 | `mcpet_coupons` / `mcpet_claim_coupons` | 查询只读；领取需明确确认 |
| 门店、餐品、价格 | `mcpet_deals` | 沿用真实官方 MCP 查询；失败明确返回，禁止模型编造 |
| 下单 | `mcpet_prepare_order` / `mcpet_confirm_order` | 从当前会话真实报价选择，5 分钟有效；复核价格变化即重新确认 |
| 撤单 | `mcpet_cancel_order` | 核对具体订单号再确认 |
| 营养 | `mcpet_nutrition` / `mcpet_nutrition_log` / `mcpet_nutrition_today` | 选真实查询餐品，确认份数再记账；跨宿主写入加锁避免覆盖 |
| 额度 | `mcpet_balances` | 复用 Orca 缓存/官方 DeepSeek 余额；窗口、桶、币种独立，未知不填零 |
| 会话状态 | `mcpet_progress` | 原 provider + 宿主事件；idle/Stop 不意味着任务成功 |
| 本机 token 台账 | `mcpet_usage` / OpenCode 原生用量事件 | 手动查询 `refresh=true` 扫描已有配置；原生事件只扫描自身元数据，复用 busy/heavy 阈值提醒，不是厂商余额/账单 |
| 饭点提醒 | 原生 hooks / `mcpet_reminders` | 宿主活动时检查，同一天跨宿主去重；不保证宿主关闭时后台提醒 |

原来的窗口拖动、闲逛、显示隐藏和桌面触摸属于桌面操作，在 Agent 模式不建立这些窗口。
旧素材、实现与测试保留，兼容入口只有显式 `python -m src.main --desktop`；默认 `python -m src.main`
启动 stdio 服务，终端看不到新界面是正常的，通常由宿主启动而非手动运行。

所有外部写入都要求摘要与明确确认，并沿用单笔/每日订单上限。网络提交后结果不确定返回
`delivery_unknown`，同会话已消耗的订单不允许重放；先核对已有账号订单，禁止自动重下。
宿主自己的工具审批不会被安装器绕过。

## 两个宿主的配置

OpenCode：`opencode.json` 添加 `mcp.mcpet` 的 `type: local`、绝对 `command` 数组；原生
`.opencode/plugins/mcpet.js` 仅接会话状态、权限等待和已完成助手消息中的数值用量，饭点走已有 toast。
文档依据：[本地 MCP](https://opencode.ai/docs/mcp-servers/)、[插件](https://opencode.ai/docs/plugins/)、
[原生 SDK toast](https://opencode.ai/docs/sdk/)。若已有 `opencode.jsonc`，安装器拒绝覆写；
按同样的 `mcp.mcpet` 结构合入现有 JSONC，并加载提供的插件。不会丢弃现有注释。

Claude Code：项目 `.mcp.json` 添加 `mcpServers.mcpet` 的 stdio 命令；
`.claude/settings.local.json` 加 SessionStart/UserPromptSubmit/Stop/SessionEnd command hooks。
规则在 `.claude/rules/mcpet.md`。开始/提交提示时可加饭点上下文；Stop/SessionEnd 不延长会话或触发新模型请求。
Windows hooks 使用带引号的正斜杠路径，避免 Git Bash 消耗反斜杠。
文档依据：[项目 MCP](https://code.claude.com/docs/en/mcp)、[hooks](https://code.claude.com/docs/en/hooks)。

hooks 丢弃提示词、消息文本、transcript_path、工具输入输出、错误正文，只写本机必要元数据。
OpenCode 用量采用宿主原有 message ID，经既有 generic provider 去重，重复事件不重复计费；
reasoning 未另加到 output，避免把包含关系猜成独立用量。对未提供的上下文上限不编造百分比。
现有日志 provider 的读取范围仍由用户原有配置决定，不探测其他账号。
Claude hooks 不读取 transcript，因此没有自动采集其 token 用量；原有已配置日志仍可按请求查询。
修改本机设置即时作用于当前服务；其他已运行宿主保留其已有环境变量，重开会话后加载新配置。

## 动画资源

`mcpet://animation/maimai/frying` 与 `mcpet://animation/maimai/outfit` 返回透明 GIF；
来源是用户提供的两段视频及已有 PNG 页。原 127 帧、80 ms 的时间轴总长 10.16 秒。
GIF 合并了相同画面，编码后各 126 帧，总时长仍为 10.16 秒；炸薯条无限循环，换装无循环。
GIF 的颜色/透明度是调色板形式，原 RGBA PNG 未改动。

工具和资源通路可验证，但 OpenCode/Claude Code 的普通终端不保证播放 GIF；当前没有把动画
强行塞进另一窗口。需要宿主支持图像资源或提供工作台渲染插槽才可内嵌播放。

## 验证范围

真实 stdio 测试执行 initialize、17 tools、调用、资源与 prompt、EOF 关闭，两个入口均运行；
业务安全使用离线响应 fixture，没有真实下单、领券、撤单或模型请求。
OpenCode `mcp list` 验证实际连接；Claude `mcp get mcpet` 验证项目发现，首次信任尚需人工。
Node 插件测试验证原生事件格式到 Python hook 的真实子进程连接及 toast 回调；其 toast 目标为测试 fixture，
不等于真实 TUI 前台提醒验收。旧 GUI/foreground/heartbeat 的历史失败不改写为通过。
