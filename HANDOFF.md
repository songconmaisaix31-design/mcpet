# McPet 开发交接

更新日期：2026-10-15。先读本文件与 [STATUS.md](STATUS.md)，再读 [AGENTS.md](AGENTS.md)、用户当前任务及对应计划 / 验收记录。

## 当前任务与交付

新增[免 Token 在线试用](docs/PUBLIC-TRIAL.md)：用户明确确认将麦当劳与瑞幸两枚真实 Token 一起公开，`.env.trial` 已提交，个人环境变量或本机配置优先。SOURCE 为 `fff7298803d974d2401e633457fcd170a36ddb04`，工作分支 `codex/public-trial-20261015` 已推送并通过普通合并 `095ef1b` 进入 main。真实连接、stdio、个人配置优先级和解压验证包启动通过；公开 v0.1.0 下载包保持原版本。

用户同时要求修改照片文字并生成 README 顶部 `assets/banner.svg`。当前消息没有照片附件，仓库没有该文件；已询问原照片的本机路径，等待用户提供。横幅内容和图片尚未决定，不添加替代图片。

2026-10-14 文档阶段交付为 README、使用指南、用户提供的 DeepSeek 娘 GIF 展示、仓库状态和新版执行协议。用户已授权合并 main，主分支包含该阶段与既有提交。

- [README](README.md)：功能、下载、首次启动、日常操作和版本边界；展示 15 段动画、9 张静态姿态。
- [使用指南](docs/USER-GUIDE.md)：安装、角色、菜单、Agent 接入、配置、餐饮、营养、提醒、更新、卸载与常见问题。
- [STATUS](STATUS.md)：现行功能、分支归属、验证结果、未完成阶段与待确认事项。
- [文档索引](docs/README.md)：用户、开发、参赛、视频和历史证据的入口。

README 与使用指南提交为 `461c969`，仓库状态整理提交为 `000f47a`；`codex/docs-readme-guide-20261014` 已通过普通合并 `dc98ebd` 进入 `main`。当前工作分支为 `main`，最新提交与推送状态从 Git 核对。

## 当前产品入口

默认模块入口是现有 Agent 会话中的 MCP stdio 服务，使用宿主原有模型。桌面入口为 `python -m src.main --desktop`；Windows 便携包为 `Start-Pet.vbs`。独立 CLI 模型问答需要显式运行 `src.cli`。

现行应用使用 Python / PySide6，营养与用量等台账为本机文件，个人凭证保存在本机 `.env`，公开试用凭证位于项目 `.env.trial`。Tauri 2、TypeScript MCP SDK、SQLite、原创默认角色与系统密钥链属于 [M0 后续里程碑](docs/contest/M0-REPORT.md)，尚未实施。

## 事实源与范围

| 工作 | 先读文件 |
|---|---|
| 安装和日常使用 | [使用指南](docs/USER-GUIDE.md)、[发行包快速开始](docs/RELEASE-QUICKSTART.md) |
| 业务与 MCP 接入 | [Agent 技术说明](docs/AGENT-HOST.md)、[技能说明](docs/AGENT-SKILL.md)、[麦当劳集成](MCP_INTEGRATION.md) |
| 桌宠与餐饮 | [菜单与瑞幸](docs/PET-MENU-LUCKIN.md)、[门店选择](docs/MCD-STORE-SELECTION.md)、[皮肤](docs/DEEPSEEK-SKINS.md) |
| 参赛版本 | [M0 报告](docs/contest/M0-REPORT.md)、[实际工具清单](docs/contest/M0-ACTUAL-TOOLS.md) |
| 新版发布视频 | [视频计划](videos/mcpet-reel/PLAN.md)、[视频说明](videos/mcpet-reel/README.md)、[样板报告](videos/mcpet-reel/REPORT.md) |
| 旧桌面与历史失败 | [历史 Handoff 索引](docs/companion/README.md)、[菜单验收](docs/PET-MENU-LUCKIN-VALIDATION.md) |

新版执行协议引用的 `docs/SPEC.md`、`docs/TASKS.md`、`docs/QUESTIONS.md` 与 `tasks/S0-plan.md` 当前未提供。相应业务规格、S0 范围和决定需由用户补充；当前已有功能与阶段以本表对应文件为事实源。

## 接续工作时的约束

- M0 报告已交付，M1 开始前仍需用户确认；新版视频仍待样板画风和声音确认后制作后续七段与成片。
- main 包含 M0、宣传视频、九姿态、GIF、README 与仓库状态的阶段提交；根状态文档列出对应分支。旧工作树和历史贡献继续保留。
- 本机 `.env`、宿主生成配置、个人台账、完整相册与构建输出由现有忽略规则保护。README 展示 GIF 位于 `docs/media/deepseek/`，保留素材说明与许可证；完整相册仍为本机生成文件。
- 外部账号写入先展示摘要并取得明确确认，`delivery_unknown` 先核对官方订单；订单生成后由用户完成付款。
- 原生信任、真实账号写入、宿主图像播放、Windows 前台性能与历史 RED 分别记录。当前适用检查通过只覆盖对应范围。

本次整理由单个 Codex Agent 执行，文档与展示素材已合并 main。发行包重建、业务开发和视频后续制作按各自任务授权与验收条件推进。
