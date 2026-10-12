# McPet（麦麦搭子）🍔

直接在正在使用、支持 MCP stdio 的 Agent 会话里查询优惠券、实时报价、营养、额度和本机用量，确认后完成领取、下单、撤单与记账。角色和动作也通过原会话选择，不绑定宿主品牌。

默认由宿主运行 MCP 服务，交互和结果留在原 Agent；没有独立窗口或聊天入口，也不需要额外的模型 Key。

```powershell
python -m pip install -r requirements-agent.txt
python -m src.agent_install
```

命令输出通用 stdio 服务的 `command` 和 `args`，填入当前宿主的 MCP 设置即可；默认不生成品牌配置或安装插件。宿主沿用自己的信任流程。麦当劳与余额操作复用已有本机凭证。
已有 OpenCode / Claude Code 的可选原生安装器仍可显式使用 `--client opencode` / `--client claude` / `--client both`。

Agent 技能入口在 [.agents/skills/mcpet/SKILL.md](.agents/skills/mcpet/SKILL.md)，包含工具路由、瑞幸/麦当劳确认流程、营养和可切换皮肤。支持项目 `.agents/skills` 的宿主可直接发现；其他宿主可用 `python -m src.agent_install --skill-dir "宿主的 skills 目录"` 安装同一份技能。技能仍需上述 MCP 连接；原生安装器同时安装相应的技能目录。[技能接入与验证](docs/AGENT-SKILL.md)。

直接说：“今天有什么券”“准备这个午餐订单”“确认记账 1.5 份”“饭点改成 12:15”“DeepSeek 娘炸薯条循环”“穿麦麦套装”“切回默认套装”。外部写入前会展示摘要并要求明确确认。

DeepSeek 娘新增 2.40 秒炸薯条循环和 3.84 秒双向换装；麦麦套装是可保存、随时切换的皮肤。
已启动的桌宠可接收原 Agent 的动作/皮肤指令。[动作与皮肤使用说明](docs/DEEPSEEK-SKINS.md)。

完整接入、21 项工具、宿主事件、动画资源和验证边界见 [Agent 内使用说明](docs/AGENT-HOST.md)。两段视频动作已保留为透明资源；终端是否播放取决于宿主图像支持。[本地原视频与动画演示](docs/PORTABLE-AGENT-DEMO.md) 可在当前工作台浏览器预览。

仓库导航：[文档索引](docs/README.md) · [目录与运行入口](docs/REPOSITORY.md) · [开发与验证](CONTRIBUTING.md) · [麦当劳 MCP 集成](MCP_INTEGRATION.md) · [素材来源](assets/CREDITS.md)。

桌宠仅显式 `python -m src.main --desktop` 启动：操作集中在右键小菜单，查询、选择、设置、确认和付款入口在宠物气泡里；没有大面板。新增瑞幸官方 MCP，饭点/咖啡时间自动只读查询，后台会话和额度条件触发气泡。[宠物菜单与瑞幸说明](docs/PET-MENU-LUCKIN.md)。默认入口继续是 stdio 服务。

本机用量不是厂商额度/账单，idle/Stop 不代表任务成功；真实提交的未知结果不得自动重试。当前接入验证不包含真实订单、模型会话或宿主前台动画验收。
