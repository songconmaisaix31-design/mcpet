# Agent 宿主接入计划（2026-10-12）

事实源：用户要求全部能力在已有 Agent 工作台运行，通过 OpenCode、Claude Code 等原会话交互，
不增加独立界面或新的聊天入口。基线 `af8ef3988689721a507c0bac29f9515db5ff3284`。

采用单 Agent、单分支 `codex/agent-host-integration-20261012`；此任务业务、协议和配置接线共享，
不拆并行轨。保持 Python/httpx，复用现有业务、Guard、NutritionLedger、provider、DailySchedule。
使用官方 Python MCP SDK 实现 stdio，由宿主启动/结束进程，不创建 QWidget、托盘或额外模型请求。

1. 暴露查询券/价格、准备及确认订单、撤单、领券、营养查询/记账、额度、会话/用量、
   设置、角色/动作资源与提醒；真实写操作保留明确确认与既有业务护栏。
2. 提供项目级 OpenCode、Claude Code 接入及宿主原生 hooks；仅处理必要事件元数据，
   不记录对话/提示词、不把 idle/Stop 推成任务成功。设置不回传密钥。
3. 默认启动切到 MCP；旧桌面实现只作显式兼容入口，当前独立实例正常退出。
   动画以资源提供，宿主实际展示能力独立标注，不能假定 TUI 会播放图像。
4. 验收：真实 stdio initialize/list/call/resources/prompt/退出，业务护栏及失败语义离线测试，
   两宿主配置与实际 MCP 连接检查；不调用真实模型、下单、领券、撤单或读取无关账号资料。
   历史 GUI/heartbeat RED 保留，不把 MCP 验收写成旧桌面整体通过。

无需用户再学习一个应用；正常对话中提出查询/记账/换角色等请求。凭证沿用已有配置，
宿主自己的初次信任/工具审批按原生流程处理。不会通过改权限设置绕过宿主审批。
