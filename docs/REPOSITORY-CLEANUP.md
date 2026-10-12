# 仓库整理（2026-10-12）

事实源：用户要求“仓库整理好”；当前产品入口是在原 Agent 中运行 McPet。
基线为已推送的 `codex/desktop-companion-20261011` / `24531f3f1f24f7b633ea57ac9f023b038249e9a3`。
`origin/main` 尚未包含该集成分支，共有 95 个已集成提交待归拢。

本任务单 Agent、单整理分支 `codex/repository-cleanup-20261012`。

1. 保持现有 Python 技术栈、目录与运行接线，补文档索引、仓库结构、贡献说明和项目 Agent 约定。
2. 更新配置示例及旧集成说明，使默认 Agent MCP、可选旧桌面/CLI 的边界一致。
3. 保留已有轨道、worktree、提交、素材来源、验证和首失败；只清理可解释的本地 Python/pytest 缓存。
4. 检查当前文档本地链接、配置示例、依赖包含关系、Git 排除规则、适用测试、compileall 与 diff。
5. 将整理分支普通 no-ff 合并到 `main`，push 两个分支，核对远端 SHA 与干净工作区。

不重新执行真实订单或模型请求。旧 GUI/foreground/heartbeat RED、Claude 初次信任、
宿主内动画播放等限制仍按原验证记录保留。本地配置与凭证不迁移到版本库。
