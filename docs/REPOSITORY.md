# 仓库结构与入口

当前源码保持原 Python 目录，不因入口切换而迁移业务模块。

| 路径 | 职责 |
|---|---|
| `.agents/skills/mcpet/` | 通用 Agent 技能源与餐饮操作引用；原生适配安装同一份内容 |
| `src/agent_mcp.py` | 面向原 Agent 的官方 MCP SDK stdio 服务、工具、资源与 prompt |
| `src/agent_service.py` | 接入现有业务、确认流程和本机状态，无 Qt 或独立模型 |
| `src/agent_install.py` | 默认输出通用 stdio 定义；显式原生适配保留其他 MCP/权限/hook |
| `src/agent_hook.py` / `src/agent_local.py` | 宿主事件 allowlist、本机跨进程写锁 |
| `src/mcd_mcp/` | 麦当劳 HTTP 客户端、业务、订单护栏；旧模型 Skill 保留 |
| `src/nutrition/` | 本机营养台账 |
| `src/accounts/` | 只读额度/余额来源和旧桌面 monitor |
| `src/agentbridge/` / `src/progress/` / `src/metering/` | 日志 provider、会话状态、本机用量台账 |
| `src/schedule/core.py` / `src/schedule/clock.py` | 共用定时逻辑 / 旧 Qt 适配 |
| `src/pet/` / `src/runtime/` / `src/main.py` | 旧桌面兼容与后台 monitor；默认模块入口提前进入 MCP |
| `src/cli.py` / `src/llm/` | 显式 CLI；独立模型问答仅保留为可选兼容 |
| `integrations/opencode/` | 原宿主插件模板，安装器填入机器路径后运行 |
| `scripts/` | 绝对路径启动器、显式本地素材预览、离线素材转换与既有诊断工具 |
| `assets/` | 图集、分页和 GIF、来源说明与上游许可证 |
| `tests/` | 现有协议、业务、台账、原生 Qt 与回归测试 |
| `docs/` | 当前使用说明、计划/验证记录与历史 Handoff |

## 运行入口

| 入口 | 用途 |
|---|---|
| `python -m src.agent_install` | 输出任意 MCP stdio 宿主可使用的 command/args，不写品牌配置 |
| `python -m src.agent_install --skill-dir PATH` | 显式复制可移植技能到指定 skills 目录，不要求品牌适配 |
| `python -m src.agent_install --client both --project PATH` | 显式安装指定项目的可选 OpenCode / Claude Code 适配 |
| `python scripts/demo_actions.py --frying-video PATH --outfit-video PATH` | 一次性本地素材演示，不由 MCP 服务启动 |
| `scripts/agent_host.py` | 宿主 stdio 启动器，不受宿主 cwd 影响 |
| `scripts/agent_hook.py --host claude/opencode` | 宿主原生命令 hook，输入 JSON 元数据 |
| `python -m src.main` / `python -m src.agent_mcp` | 默认 stdio 服务，通常由宿主启停 |
| `python -m src.main --desktop` | 显式旧桌面兼容 |
| `python -m src.cli ...` | 显式旧 CLI；不同命令的副作用按各命令说明 |

## 配置与依赖

- `requirements-agent.txt`：Agent 服务的最小运行依赖。
- `requirements.txt`：引用同一最小依赖，再加旧桌面与现有测试依赖。
- `.env.example`：配置占位符。默认 Agent 接入不需要 StepFun Key。
- `mcp-config.example.json`：历史麦当劳上游配置示例，与本项目生成的 stdio 配置区分。
- `.mcp.json`、`opencode.json`、`.claude/settings.local.json`、`.opencode/`：本机生成的宿主接线，不提交。
- 真实 `.env`、运行台账、测试输出和缓存由 `.gitignore` 排除。

根目录保留 README、贡献/Agent 约定与既有参赛材料。历史文档有明确索引与范围标记，
保留原链接和证据路径。旧开发分支与 worktree 保留，整理不删除贡献历史。
