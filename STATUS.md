# McPet 开发状态

更新日期：2026-10-14。仓库：`songconmaisaix31-design/mcpet`。本次整理基线为 `461c969`，工作分支为 `main`。`codex/docs-readme-guide-20261014` 已通过普通合并 `dc98ebd` 进入主分支。接管说明见 [HANDOFF.md](HANDOFF.md)。

## 发行与开发版本

| 项目 | 当前状态 | 证据 |
|---|---|---|
| v0.1.0 | 已发布 Windows x64 便携包与通用 Agent 包，现行 Python/Qt 版 | [首发记录](docs/FIRST-RELEASE.md)、[版本说明](docs/releases/v0.1.0.md) |
| main | 含现行业务与 M0、宣传视频、九姿态、GIF、README / 指南和状态整理；普通合并为 `dc98ebd` | `git log main` |
| 文档开发分支 | `000f47a` 已包含于 main；整理基线时在原主分支 `a52fd7d` 上增加 11 个阶段提交 | `git log a52fd7d..461c969 --oneline` |
| Tauri 参赛版本 | M0 报告与工具映射完成，等待阶段确认；M1～M5 尚未实施 | [M0 报告](docs/contest/M0-REPORT.md) |
| 新版发布视频 | 余额样板、双角色与九姿态预览已实现，等待画风与声音确认 | [视频说明](videos/mcpet-reel/README.md)、[验收报告](videos/mcpet-reel/REPORT.md) |

公开 v0.1.0 标签与上传包保持原版本。源码后续的门店选择修订、九姿态、GIF 资源及本轮文档变更未通过新发行包交付。

## 已实现的现行功能

| 功能 | 实现与验证状态 | 当前限制 |
|---|---|---|
| Agent 接入 | 通用 stdio、21 项工具、技能复制；OpenCode / Claude Code 可选原生适配；真实 stdio 已验证 | 原宿主信任与实际模型技能选择分别验收 |
| 桌面交互 | 宠物 / 托盘 / 右键 / 气泡；拖动、闲逛、休息、单实例与保存偏好 | 历史 Windows 心跳和前台性能仍有 RED |
| 角色与皮肤 | DeepSeek 娘默认、ChatGPT 娘切换、两套皮肤、炸薯条和双向换装 | 麦麦套装部分状态复用穿装待机 |
| 麦当劳 | 券、营养、门店、报价、准备 / 确认订单、撤单、金额护栏 | 最新真实核对到指定门店报价与准备摘要；实际创建、付款仍未执行 |
| 瑞幸 | 门店、商品、规格、预览、准备 / 确认、查单 / 取餐码、撤单 | 已有真实报价 / 准备摘要；订单创建、付款与取餐待验收 |
| 营养记录 | 查询真实餐品，确认份数后保存 JSON 台账，今日汇总 | 按实际食用明确记账，周报尚未交付 |
| 工作状态 / 用量 | Claude / Codex / generic 日志、可选宿主事件、本机 token 台账、明确完成事件 | idle / Stop 不表示成功；日志范围与过时标记影响结果 |
| 余额 / 额度 | Orca 缓存与 DeepSeek 官方只读余额，按来源 / 窗口 / 币种显示 | 未知保持 UNKNOWN；完整厂商实时额度验收未完成 |
| 提醒 | 默认 11:30 饭点、15:00 咖啡；时间 / 条件只读查询 | 依赖桌宠运行或宿主活动，自动路径不执行账号写入 |
| 早期九姿态 | `ceta_*` 动作、PNG 资源、桌宠菜单，本机导入与分类导出已验证 | 原素材为单帧姿态，完整运行包按本机导入处理 |
| 全动作 GIF | 两皮肤 56 项名称、192 / 512 两种尺寸，共 112 个本机 GIF；资源读取已验证 | 去重为 15 段动画和 9 张姿态；512 为放大版，宿主播放需独立验收 |
| README 与指南 | 首页、完整指南、快速开始与索引；24 份 GIF 展示副本已进入 main | 15 段动画、9 张静态姿态；旧发行包仍保留原说明 |

使用方式见 [USER-GUIDE](docs/USER-GUIDE.md)，实现目录见 [REPOSITORY](docs/REPOSITORY.md)。

## 分支与工作树

已核对本地 26 个分支 tip 均包含于 main。下表阶段提交已合并主分支，原开发分支保留。

| 阶段分支 | 已核对 tip | 内容 |
|---|---|---|
| `codex/contest-m0-20261014` | `06867f9` | 参赛 M0 工具、现状与里程碑 |
| `codex/promo-video-20261014` | `bc43e46` | 旧桌面功能介绍录制脚本与报告 |
| `codex/reel-v2-worry-20261014` | `74c94ca` | 新版视频样板及双角色形象记录 |
| `codex/cetapet-actions-20261014` | `ee51419` | 早期九姿态的本机导入与桌宠 / Agent 接入 |
| `codex/deepseek-gif-recording-20261014` | `f04b9dd` | 全动作 GIF 录制、资源及验收 |
| `codex/docs-readme-guide-20261014` | `000f47a` | README、使用指南、展示素材与仓库状态 |

另有四个保留的旧开发 worktree，核对时均无未提交改动，tip 均已包含于 main：

| 分支 | 已核对 tip |
|---|---|
| `songconmaisaix31-design/mcpet-app-20261011` | `8d2959a` |
| `songconmaisaix31-design/mcpet-data-20261011` | `fa96c57` |
| `songconmaisaix31-design/mcpet-pet-20261011` | `7d06474` |
| `songconmaisaix31-design/mcpet-companion-integration-20261011` | `8737bce` |

当前分支与其他工作树的实时状态用 `git status -sb`、`git worktree list`、`git branch -vv` 查询。保留历史分支与工作树，原始验收记录在 [companion](docs/companion/README.md)。

## 本轮验证

文档与展示素材验证使用本仓库 `.venv`，Python 3.13.13、MCP 1.30.0、PySide6 6.12.0、Pillow 12.3.0；Markdown 使用 markdown-it-py 解析。中间脚本与数据位于已忽略的 `.tmp-test-data/docs-readme/`。

```powershell
.\.venv\Scripts\python.exe -X utf8 .tmp-test-data/docs-readme/validate_docs.py
# 仓库状态整理后只复核变动文档的链接
.\.venv\Scripts\python.exe -X utf8 .tmp-test-data/docs-readme/validate_docs.py --links-only
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_agent_skill.py tests/test_agent_host.py tests/test_main_startup.py tests/test_pet_menu.py tests/test_config.py -q
.\.venv\Scripts\python.exe -X utf8 -m compileall -q src scripts tests
git diff --check
```

- README 阶段的六份文档：114 处本地链接、图片与锚点检查通过，JSON 配置示例解析通过。
- 24 份 GIF 与用户提供文件逐字节相同；1,356 帧全部解码，尺寸、时长及静态标注检查通过。
- 隔离用户目录的实际通用安装器、真实 MCP stdio、21 工具发现、状态 / 设置 / 角色 / 皮肤 / 提醒时间操作通过。
- 现有五个适用测试文件：**65 passed / 39.04 秒**，包括离线契约与真实子进程测试，结果按各用例范围解释。
- 编译和 diff 检查通过；已解压 Windows 包执行 `McPet.exe --version` 返回 `McPet 0.1.0`。

本轮为文档和仓库状态整理，没有新增业务功能或重跑完整项目、原生前台性能、真实账号交易和视频构建。整理后的 11 份文档共 180 处已有本地链接、图片与锚点检查通过；新版协议引用的四份未提供业务文件单独列出，保持待提供状态。

### main 合并复核

```powershell
git merge --no-ff codex/docs-readme-guide-20261014
git diff --exit-code codex/docs-readme-guide-20261014 HEAD
.\.venv\Scripts\python.exe -X utf8 .tmp-test-data/docs-readme/validate_docs.py
git diff --check
```

普通合并无冲突，合并时文件树与来源分支相同。主分支复核的 180 处已有链接、24 份 GIF / 1,356 帧、真实 MCP stdio 与角色 / 设置操作均通过；四份未提供的协议业务文件继续单独标明。合并后仅更新交接与状态文字，现有 65 项适用测试的源码保持不变。

## 后续阶段与待确认项

| 项目 | 当前要求 / 剩余工作 | 推进条件 |
|---|---|---|
| M1 参赛基础 | Tauri 可构建启动、原创默认 / 本机皮肤导入、密钥链、SQLite、透明桌面与托盘 | 用户确认 M0 后开始 |
| M2 核心功能 | TS MCP、余额轮询、文件 / HTTP 进度、状态与提醒、通用技能 | 按 [M0 里程碑](docs/contest/M0-REPORT.md)逐阶段验收 |
| M3 餐饮与记录 | 餐饮真实流程、三次饭点、饮食记录与周报 | 实际账号写入仍需核对摘要并明确确认 |
| M4 / M5 | 干净安装、新包、原创素材检查、演示、报名稿和提交回执 | 最终用户验收后执行对应发布 / 报名 |
| 新版视频 | 样板画风和声音确认、后续七个行为、连续性、全片混音与成片 | 样板确认后推进；当前阶段仅为预览 bundle |
| 旧桌面宣传片 | 118 秒 / 18 场的本地介绍片有既有录制与解码记录 | 未发布；演示数值独立于真实账号效果 |
| main | 阶段提交、README 与 GIF 已普通合并 | 已取得本次用户合并授权 |
| 新发行包 | 按版本范围重新打包、验收与发布 | 本次未重建或更新 v0.1.0 发行包 |
| 通用协议的业务文件 | `docs/SPEC.md`、`docs/TASKS.md`、`docs/QUESTIONS.md`、`tasks/S0-plan.md` 当前缺失 | 需要用户提供对应业务事实，保持未决定 |

## 真实限制与保留证据

- Windows 联合验证的历史心跳 `385.04ms`，原门槛 `<150ms`，仍为 RED；部分 DeepSeek 素材边界 / 缓存断言未解决。见 [菜单与瑞幸验收](docs/PET-MENU-LUCKIN-VALIDATION.md)。
- 2026-10-13 真实麦当劳 / 瑞幸查询已到指定门店报价和 `needs_confirmation` 摘要。订单创建、付款页与实际支付未执行，见 [门店验证](docs/MCD-STORE-SELECTION.md)。
- Claude 原生首次信任、完整宿主对话、终端 GIF 内嵌播放与前台提醒仍需分别验收。既有 stdio 或离线测试只证明对应接口。
- 协议第 5 节所列 Codex 原生控制器、SQLite、HTTP 与逐条 `event_id` 的组合链路在本轮未执行；现有 Codex 日志 provider 和通用 stdio 的验证范围分别记录。
- 早期 CeTaPet 的 README 与 LICENSE 授权描述有差异；源码本机导入、README 展示副本及后续参赛素材分别记录来源，见 [CREDITS](assets/CREDITS.md)和[展示来源](docs/media/deepseek/SOURCE.md)。
- 首 RED、NOT_RUN、BLOCKED 与原始历史文档保留；本机输出、凭证、台账和宿主配置继续由忽略规则保护。
