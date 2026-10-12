# McPet（麦麦搭子）🍔

直接在正在使用、支持 MCP stdio 的 Agent 会话里查询优惠券、实时报价、营养、额度和本机用量，确认后完成领取、下单、撤单与记账。角色和动作也通过原会话选择，不绑定宿主品牌。

默认由宿主运行 MCP 服务，交互和结果留在原 Agent；没有独立窗口或聊天入口，也不需要额外的模型 Key。

```powershell
python -m pip install -r requirements-agent.txt
python -m src.agent_install
```

命令输出通用 stdio 服务的 `command` 和 `args`，填入当前宿主的 MCP 设置即可；默认不生成品牌配置或安装插件。宿主沿用自己的信任流程。麦当劳与余额操作复用已有本机凭证。
已有 OpenCode / Claude Code 的可选原生安装器仍可显式使用 `--client opencode` / `--client claude` / `--client both`。

直接说：“今天有什么券”“准备这个午餐订单”“确认记账 1.5 份”“饭点改成 12:15”“麦麦炸薯条循环”。外部写入前会展示摘要并要求明确确认。

完整接入、17 项工具、宿主事件、动画资源和验证边界见 [Agent 内使用说明](docs/AGENT-HOST.md)。两段视频动作已保留为透明资源；终端是否播放取决于宿主图像支持。[本地原视频与动画演示](docs/PORTABLE-AGENT-DEMO.md) 可在当前工作台浏览器预览。

仓库导航：[文档索引](docs/README.md) · [目录与运行入口](docs/REPOSITORY.md) · [开发与验证](CONTRIBUTING.md) · [麦当劳 MCP 集成](MCP_INTEGRATION.md) · [素材来源](assets/CREDITS.md)。

旧桌面实现与文档保留在 [桌面兼容说明](docs/LEGACY-DESKTOP.md)，仅显式 `python -m src.main --desktop` 启动。默认入口是 stdio 服务。

本机用量不是厂商额度/账单，idle/Stop 不代表任务成功；真实提交的未知结果不得自动重试。当前接入验证不包含真实订单、模型会话或宿主前台动画验收。
