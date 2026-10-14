# 文档索引

新用户先读[完整使用指南](USER-GUIDE.md)：下载安装、桌面操作、Agent 接入、账号配置与常见问题。
当前默认命令入口为原 Agent 中的 MCP 服务；显示桌宠使用发行包 `Start-Pet.vbs` 或显式 `--desktop`。
开发接管先读[根交接](../HANDOFF.md)与[当前状态](../STATUS.md)，阶段记录按下表定位。

## 使用与开发

| 文档 | 内容 |
|---|---|
| [完整使用指南](USER-GUIDE.md) | 安装、菜单、Agent 接入、账号配置、餐饮流程、提醒、更新与常见问题 |
| [Agent 使用说明](AGENT-HOST.md) | 通用 MCP stdio 接入、可选宿主适配、21 项工具及动画资源 |
| [Agent 技能层](AGENT-SKILL.md) | 可发现的 McPet 技能、通用/原生安装、确认流程与验证 |
| [首发召唤小抄](RELEASE-QUICKSTART.md) | v0.1.0 Windows 便携包与通用 Agent 包 |
| [免 Token 在线试用](PUBLIC-TRIAL.md) | 公开试用配置、个人配置优先与实际连接验证 |
| [宠物菜单与瑞幸](PET-MENU-LUCKIN.md) | 右键菜单、气泡交互、时间/条件触发及瑞幸官方接入 |
| [本地动作演示](PORTABLE-AGENT-DEMO.md) | 原视频与透明动画预览、通用客户端验证 |
| [DeepSeek 娘动作与皮肤](DEEPSEEK-SKINS.md) | 短循环、双向换装、持久皮肤及桌宠播放验证 |
| [ChatGPT 龙娘待机节奏](CHATGPT-IDLE-FIX.md) | 短图集循环过快的修复与实际定时验证 |
| [DeepSeek 娘 GIF 小相册](../assets/deepseek-recordings/SOURCE.md) | 两套皮肤全部动作的本机录制、分类导出与 Agent 资源 |
| [仓库结构](REPOSITORY.md) | 当前目录、入口与配置边界 |
| [开发与验证](../CONTRIBUTING.md) | 依赖、隔离测试、提交与验证口径 |
| [项目 Agent 约定](../AGENTS.md) | 事实源、写入范围和交付规则 |
| [开发交接](../HANDOFF.md) / [当前状态](../STATUS.md) | 当前任务、分支与工作树、功能状态、未完成阶段和最新验证 |
| [麦当劳 MCP 集成](../MCP_INTEGRATION.md) | 上游 HTTP 协议、业务工具、历史实测字段 |
| [本机日志桥接](AGENT_BRIDGE.md) | provider、日志目录、元数据/用量的口径 |
| [素材来源](../assets/CREDITS.md) | 上游来源、保留许可证和用户动作素材 |
| [参赛声明](../CONTEST_DECLARATION.md) | 既有参赛材料 |

## 当前交付记录

| 文档 | 范围 |
|---|---|
| [参赛 M0 报告](contest/M0-REPORT.md) / [实际工具清单](contest/M0-ACTUAL-TOOLS.md) | Python 现状、两家实际 schema、Tauri 后续里程碑与阶段确认条件 |
| [首发记录](FIRST-RELEASE.md) / [v0.1.0 说明](releases/v0.1.0.md) | 已发布两种包的构建、解压接入与桌宠启动验证 |
| [指定门店验证](MCD-STORE-SELECTION.md) | 麦当劳 / 瑞幸真实报价和准备摘要，创建及付款待执行 |
| [角色与容器整理](PET-HEADER-CLEANUP.md) | 当前按需气泡进度、角色命名与原生菜单记录 |
| [Agent 接入计划](AGENT-HOST-PLAN.md) | 从桌面入口切到原 Agent 的范围与假设 |
| [Agent 接入验证](AGENT-HOST-VALIDATION.md) | 315 项回归、真实 stdio、首次失败和待人工项 |
| [仓库整理记录](REPOSITORY-CLEANUP.md) | 文档整理、主分支归拢与本轮检查 |
| [菜单与瑞幸验证](PET-MENU-LUCKIN-VALIDATION.md) | 426 项适用回归、真实 stdio、可见菜单/气泡及保留的性能 RED |
| [动作导入验证](maimai-actions-verification.md) | 两段用户视频转换与旧桌面动作验证 |
| [GIF 全动作录制验收](DEEPSEEK-GIF-VALIDATION.md) | 112 个本机 GIF、完整帧/时间核对与实际 stdio 读取 |
| [早期九姿态验收](CETAPET-ACTIONS-VALIDATION.md) | 本机导入、分类导出、PNG 资源与静态姿态的使用边界 |

## 视频工程

| 文档 | 当前范围 |
|---|---|
| [新版视频说明](../videos/mcpet-reel/README.md) / [计划](../videos/mcpet-reel/PLAN.md) / [报告](../videos/mcpet-reel/REPORT.md) | Remotion 余额样板、双角色与九姿态预览；等待画风 / 声音确认后制作全片 |
| [旧桌面宣传片](demos/PROMO-VIDEO.md) | 已有 118 秒本地功能介绍与解码记录，演示数据与真实交易分别说明 |

## 历史实现与证据

GIF 录制的范围与验证计划见 [录制计划](DEEPSEEK-GIF-PLAN.md)。

- [旧桌面兼容说明](LEGACY-DESKTOP.md)：显式 `--desktop` 入口。
- [桌面开发轨与 Handoff](companion/README.md)：保留原计划、归属与未通过项。
- [历史真实调用报告](verification-report.md)、[运行检查](runtime-check-2026-10-11.md)：仅代表各自日期和验证范围。
- [WorkBuddy 开发记录](../workbuddy.md)：保留历史叙事，不作为当前默认入口说明。
- [麦当劳 schema 快照](mcp-schemas.json)：既有上游工具快照，非 McPet stdio 工具清单。

历史 GUI/foreground/heartbeat RED 不因文档整理或主分支合并变为通过；
宿主内 GIF 播放、真实订单以及真实宿主前台提醒的限制见当前接入验证记录。
