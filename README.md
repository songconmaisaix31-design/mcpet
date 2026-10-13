# McPet · 鲸鲸来陪你啦 🐳

**余额有人盯，进度有人陪，干饭有人喊。** 参赛桌面版当前处于 M0 验收阶段，目标使用 Tauri 2、原创默认形象与系统密钥链；下述现行发行仍为 Python/Qt。见 [M0 验收报告与阶段计划](docs/contest/M0-REPORT.md)、[两家实际工具清单](docs/contest/M0-ACTUAL-TOOLS.md)。

DeepSeek 娘到岗啦：陪你查麦当劳优惠、挑瑞幸咖啡，记饭饭小本本，也看看工作的用量小账本。想做什么，在正在用的 Agent 里说一句就好；宿主支持 MCP stdio 就能接入。

新用户默认 **DeepSeek 娘**，**ChatGPT 娘** 也可随时切换。DeepSeek 娘的默认套装和麦麦套装都在衣柜里，不用固定穿某一套；已有选择会继续记住。

宠物上方不再常驻状态条或上下文容器，也不留空白占位。右键查看进度时才冒个气泡，后台活动照常驱动动作。

**首发 v0.1.0**：[下载发行包](https://github.com/songconmaisaix31-design/mcpet/releases/tag/v0.1.0) · [召唤与接入小抄](docs/RELEASE-QUICKSTART.md)。Windows 便携包解压后双击 `Start-Pet.vbs`；通用 Agent 包沿用 Python 接入。

Agent 里的我沿用你正在聊的会话和模型，不用多开聊天窗口，也不用再买一份模型 Key。领取、下单、撤单和记账前，我们会先核对具体内容，再按你的明确确认操作。

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
