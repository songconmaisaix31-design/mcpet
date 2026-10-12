# 旧桌面开发轨与 Handoff

这里保留 2026-10-11 起的旧桌面开发计划、接口约定、验收和首次失败。
它们仅适用于各自记录的工作树、SHA 与阶段，不是当前 Agent 模式的运行说明。
当前入口见 [Agent 使用说明](../AGENT-HOST.md)，文档总览见 [索引](../README.md)。

| 阶段 | 计划 | 集成交接 |
|---|---|---|
| 桌面基础 | [PLAN](PLAN.md) | [HANDOFF-INTEGRATION](HANDOFF-INTEGRATION.md) |
| 原会话辅助 / 统一小窝 | [SESSION-PANEL-PLAN](SESSION-PANEL-PLAN.md) | [HANDOFF-INTEGRATION-PANEL](HANDOFF-INTEGRATION-PANEL.md) |
| 双角色 / 额度 | [PIXSO-QUOTA-DUAL-PET-PLAN](PIXSO-QUOTA-DUAL-PET-PLAN.md) | [HANDOFF-INTEGRATION-QUOTA](HANDOFF-INTEGRATION-QUOTA.md) |

原 Worker Handoff：

- A：[基础](HANDOFF-A.md)、[触摸提示](HANDOFF-A-PANEL-HINT.md)、[双角色](HANDOFF-A-DUAL-PET.md)。
- B：[基础](HANDOFF-B.md)、[额度](HANDOFF-B-QUOTA.md)。
- C：[基础](HANDOFF-C.md)、[统一面板](HANDOFF-C-PANEL.md)、[额度面板](HANDOFF-C-QUOTA-PANEL.md)。

其余本目录设计和验证文件保持在原位。静态合并、fixture 验证、Qt/QTest、真实 Windows
foreground、人工验收分别记录；历史未通过项仍未通过。
