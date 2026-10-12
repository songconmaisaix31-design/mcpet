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

## 整理结果与验证

- 增加 README 导航、docs 索引、目录/入口说明、贡献指南与根 AGENTS 约定。
- 旧桌面、历史 WorkBuddy 和桌面 Handoff 标明历史范围；内容与证据保留在原位。
- 修复旧桌面说明迁移后的 9 个相对链接。40 份 Markdown 的 80 个本地链接检查通过，
  记录为 `.tmp-test-data/repository-cleanup-links.json`，未请求外部页面或检查远程链接/锚点。
- `.env.example` 补最小 Agent 配置、只读余额与城市示例，StepFun 标为显式旧 CLI 可选；
  修正“演练完全离线”及两个不展开字面量 `~` 的目录覆盖示例。
- `requirements.txt` 引用 `requirements-agent.txt`，公共依赖约束只有一个来源。
- 真实 .env、生成接线、台账、`.tmp-test-data` 首失败记录和其他 worktree 均保留。
- 本地 Python/pytest 缓存删除被自动审批检查拒绝，原因仅返回 blocked by policy；
  未执行删除或改用其他路径绕过。缓存已由 Git 忽略，未进入版本库。

适用回归命令采用 CONTRIBUTING.md 列出的 15 个文件：
`python -m pytest ... -q`，结果 **315 passed in 39.96s**。
完整命令见 [贡献指南](../CONTRIBUTING.md)，日志 `.tmp-test-data/repository-cleanup-regression.log`。
`python -m compileall -q src scripts tests`、`git diff --check` 和排除规则检查通过。
索引不包含真实 `.env`、机器路径配置、pyc 或测试日志。

依赖检查：

```powershell
python -m pip --isolated install --dry-run --disable-pip-version-check --index-url https://pypi.org/simple -r requirements.txt
```

解析通过，仅提出补齐 PySide6 6.12.0 元包，未实际安装或修改现有解释器。
首次 `--no-index` 检查失败保留：当前解释器有 PySide6_Essentials 6.12.0 等组件，
缺少 PySide6 元包且无离线 wheel 来源；它不代表 Qt 无法导入，也不代表在线解析失败。
原日志 `repository-cleanup-dependencies.log` 与在线解析日志 `repository-cleanup-dependency-resolution.log` 分别保留。

本轮不运行真实模型、账号写操作、全仓旧桌面动态验收或前台动画；当前宿主接入的待人工项与
历史 RED 继续见 [Agent 接入记录](AGENT-HOST-VALIDATION.md)。本机缓存整理不构成运行性能验收。
