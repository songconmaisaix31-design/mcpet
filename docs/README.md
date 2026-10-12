# 文档索引

当前默认入口是在原 Agent 会话中运行 McPet MCP 服务。

## 使用与开发

| 文档 | 内容 |
|---|---|
| [Agent 使用说明](AGENT-HOST.md) | OpenCode / Claude Code 接入、17 项工具、提醒及动画资源 |
| [仓库结构](REPOSITORY.md) | 当前目录、入口与配置边界 |
| [开发与验证](../CONTRIBUTING.md) | 依赖、隔离测试、提交与验证口径 |
| [项目 Agent 约定](../AGENTS.md) | 事实源、写入范围和交付规则 |
| [麦当劳 MCP 集成](../MCP_INTEGRATION.md) | 上游 HTTP 协议、业务工具、历史实测字段 |
| [本机日志桥接](AGENT_BRIDGE.md) | provider、日志目录、元数据/用量的口径 |
| [素材来源](../assets/CREDITS.md) | 上游来源、保留许可证和用户动作素材 |
| [参赛声明](../CONTEST_DECLARATION.md) | 既有参赛材料 |

## 当前交付记录

| 文档 | 范围 |
|---|---|
| [Agent 接入计划](AGENT-HOST-PLAN.md) | 从桌面入口切到原 Agent 的范围与假设 |
| [Agent 接入验证](AGENT-HOST-VALIDATION.md) | 315 项回归、真实 stdio、首次失败和待人工项 |
| [仓库整理记录](REPOSITORY-CLEANUP.md) | 文档整理、主分支归拢与本轮检查 |
| [动作导入验证](maimai-actions-verification.md) | 两段用户视频转换与旧桌面动作验证 |

## 历史实现与证据

- [旧桌面兼容说明](LEGACY-DESKTOP.md)：显式 `--desktop` 入口。
- [桌面开发轨与 Handoff](companion/README.md)：保留原计划、归属与未通过项。
- [历史真实调用报告](verification-report.md)、[运行检查](runtime-check-2026-10-11.md)：仅代表各自日期和验证范围。
- [WorkBuddy 开发记录](../workbuddy.md)：保留历史叙事，不作为当前默认入口说明。
- [麦当劳 schema 快照](mcp-schemas.json)：既有上游工具快照，非 McPet stdio 工具清单。

历史 GUI/foreground/heartbeat RED 不因文档整理或主分支合并变为通过；
宿主内 GIF 播放、真实订单以及真实宿主前台提醒的限制见当前接入验证记录。
