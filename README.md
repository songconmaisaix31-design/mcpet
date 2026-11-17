<div align="center">

# McPet

A desktop pet that watches your agent sessions, your local token usage, and your lunch.

一只桌宠：盯着 Agent 会话、本机用量，还有你的饭点。

[![Release](https://img.shields.io/badge/release-v0.1.0-2E8B57.svg)](https://github.com/songconmaisaix31-design/mcpet/releases/tag/v0.1.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](requirements-agent.txt)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-0078D4.svg)](docs/RELEASE-QUICKSTART.md)

<img src="docs/media/deepseek/default-idle.gif" width="150" alt="DeepSeek 娘待机动画 / DeepSeek pet idle animation" />
<img src="docs/media/deepseek/default-working.gif" width="150" alt="DeepSeek 娘忙碌工作动画 / DeepSeek pet working animation" />
<img src="docs/media/deepseek/maimai-idle.gif" width="150" alt="DeepSeek 娘麦麦套装待机动画 / McDonalds outfit idle animation" />

<sub>GIFs shipped in this repository under `docs/media/deepseek/`; sources and licenses are listed in `docs/media/deepseek/SOURCE.md`.<br/>动画文件就在本仓库 `docs/media/deepseek/` 下；来源与许可见 `docs/media/deepseek/SOURCE.md`。</sub>

</div>

> **How to read this page / 怎么读这页**
> English first, then the same content in Chinese — not a summary, not a separate half. Tables keep both languages in one cell.
> 每段英文在前、同一内容的中文紧跟在后；不是摘要，也没有单独的"中文版"。表格把两种语言放进同一格。

---

## At a glance · 一眼看懂

| | |
|---|---|
| **Problem<br/>问题** | A long agent run looks the same whether it is working, waiting for input, or already errored — and the token bill lives in yet another window.<br/>长时间运行的 Agent，在工作、等输入、已经出错这三种状态下看起来一样；而 token 账单又在另一个窗口里。 |
| **Fix<br/>做法** | A desktop pet + an MCP server over one shared data directory: session state drives the animation, a local ledger tracks usage, reminders fire on a schedule.<br/>桌宠加一个 MCP 服务，共用同一份数据目录：会话状态驱动动作，本机台账记录用量，提醒按时触发。 |
| **Cost<br/>代价** | Python 3.10+ and PySide6 for the desktop; the agent path only needs `requirements-agent.txt`. Dining features need McDonald's / Luckin tokens.<br/>桌面要 Python 3.10+ 与 PySide6；只走 Agent 路径只需 `requirements-agent.txt`。餐饮功能需要麦当劳/瑞幸凭据。 |
| **Not<br/>不是** | Not a hosted service, not a model provider, not an ordering bot that pays for you.<br/>不是托管服务，不是模型提供方，也不是替你付款的下单机器人。 |

## What it does · 能做什么

| Feature · 功能 | Desktop entry · 桌面入口 | Say this to the agent · 对 Agent 说 |
|---|---|---|
| Companion & skins<br/>陪伴与换装 | Character & actions → default / McD outfit | "DeepSeek 娘穿麦麦套装" |
| Session state<br/>会话状态 | Sessions & quota → session progress | "用 McPet 看当前会话状态" |
| Usage & balance<br/>用量与余额 | Sessions & quota → local ledger, Orca cache, DeepSeek balance | "余额还有多少" |
| McDonald's<br/>麦当劳 | McDonald's → coupons, store, live quote | "今天有什么麦当劳优惠？先查一下" |
| Luckin coffee<br/>瑞幸 | Luckin → store, item, spec, preview price | "选一杯拿铁，先预览价格" |
| Nutrition ledger<br/>营养记账 | Nutrition → pick item, confirm servings | "查询巨无霸营养，我吃了 1.5 份" |
| Reminders<br/>定时提醒 | Settings → time & location → lunch / coffee | "饭点改成 12:15" |

Every order, coupon claim and ledger write shows a concrete summary first and waits for explicit confirmation. The default order guardrails are 100 CNY per order and 3 orders per day, re-checked at confirmation time.

每一次领券、下单和记账都先展示具体摘要，等明确确认后才执行。默认订单护栏是单笔 100 元、每日 3 单，确认时再复核金额。

## The problem · 问题在哪

An agent session is a black box with a progress bar:

```text
agent  ──▶ working?          (no output for 6 minutes)
       ──▶ waiting for input? (a prompt is on screen)
       ──▶ stopped?           (idle / Stop)
```

`idle` and `Stop` are session states, not success. The pet shows the state it can actually read from logs or host events, and keeps unreadable fields unknown instead of guessing.

Agent 会话是个带进度条的盲盒：

```text
agent  ──▶ 在工作？        （六分钟没有输出）
       ──▶ 在等输入？      （屏幕上有提示）
       ──▶ 已停止？        （idle / Stop）
```

`idle` 与 `Stop` 是会话状态，不是成功。桌宠只显示它真能从日志或宿主事件读到的东西，读不到的字段保持未知。

## The idea · 思路

| Noun · 名词 | Path · 路径 | Rule · 规则 |
|---|---|---|
| **Pet** | `src/pet/`, `src/main.py --desktop` | Animation follows real state; a missing sprite falls back to an existing action rather than a broken frame.<br/>动作跟随真实状态；缺素材时回落到已有动作，不出现破图。 |
| **Host** | `src/agent_mcp.py`, `src/agent_install.py` | The MCP server is started by the host over stdio; the desktop pet is a separate process on the same data directory.<br/>MCP 服务由宿主以 stdio 启动；桌宠是另一个进程，共用同一份数据目录。 |
| **Progress** | `src/progress/`, `src/agentbridge/` | Session progress comes from readable logs and host events only; `idle` is not success.<br/>会话进度只来自可读日志与宿主事件；`idle` 不等于成功。 |
| **Guard** | `src/mcd_mcp/`, `src/luckin.py` | Order, claim and ledger writes require an explicit confirmation step.<br/>下单、领券与记账都需要显式确认步骤。 |
| **Ledger** | `src/metering/`, `src/accounts/` | Every number carries its source and update time; unknown stays unknown.<br/>每个数字都带来源与更新时间；未知保持未知。 |

## Quickstart · 快速开始

### 1. Portable release (no Python needed) · 便携包（免装 Python）

Download [McPet-v0.1.0-windows-x64.zip](https://github.com/songconmaisaix31-design/mcpet/releases/download/v0.1.0/McPet-v0.1.0-windows-x64.zip), unzip the whole folder and double-click `Start-Pet.vbs`. If the launcher misbehaves, run `.\McPet.exe --desktop` in that folder.

下载 [McPet-v0.1.0-windows-x64.zip](https://github.com/songconmaisaix31-design/mcpet/releases/download/v0.1.0/McPet-v0.1.0-windows-x64.zip)，解压整个文件夹后双击 `Start-Pet.vbs`。启动脚本不可用时，在解压目录运行 `.\McPet.exe --desktop`。

### 2. Connect your agent · 接入 Agent

The host needs MCP stdio support. From the agent package directory, or from a source checkout:

宿主需要支持 MCP stdio。在 Agent 包目录或源码目录运行：

```powershell
python -m pip install -r requirements-agent.txt
python -m src.agent_install
```

Put the printed `server.command` / `server.args` into the host's MCP settings, name it `mcpet`, transport `stdio`. Portable-package users can run `.\McPet.exe --install` for the same output.

把输出的 `server.command` / `server.args` 填进宿主的 MCP 设置，服务名 `mcpet`，传输方式 `stdio`。便携包用户可运行 `.\McPet.exe --install` 得到同样的连接信息。

### 3. From source · 从源码运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.main --desktop
```

Regression checks used by this repository:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_deepseek_skins.py tests/test_agent_host.py tests/test_guards.py -q
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

The commands above are copied from [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/USER-GUIDE.md](docs/USER-GUIDE.md); none of them were re-run while writing this page.

以上命令抄自 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [docs/USER-GUIDE.md](docs/USER-GUIDE.md)；写这页时没有重跑任何一条。

## Documentation · 文档

| Doc · 文档 | Read it when · 什么场景读它 |
|---|---|
| [docs/USER-GUIDE.md](docs/USER-GUIDE.md) | You need install, menus, account setup, dining flows, FAQ.<br/>需要安装、菜单、账号配置、餐饮流程与常见问题。 |
| [docs/RELEASE-QUICKSTART.md](docs/RELEASE-QUICKSTART.md) | First launch of the Windows portable or agent package.<br/>首次启动 Windows 便携包或 Agent 包。 |
| [docs/AGENT-HOST.md](docs/AGENT-HOST.md) | You are wiring the MCP host: tools, resources, host events.<br/>在接 MCP 宿主：工具、资源、宿主事件。 |
| [docs/AGENT-SKILL.md](docs/AGENT-SKILL.md) | You want the portable skill copy and its references.<br/>需要可移植技能副本与其引用文件。 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | You are changing code: env setup, checks, commit rules.<br/>要改代码：环境、检查、提交规则。 |
| [STATUS.md](STATUS.md) | You need current progress, branch ownership, unverified items.<br/>需要当前进度、分支归属、待验收事项。 |
| [assets/CREDITS.md](assets/CREDITS.md) | You are reusing art or reference code — read the per-asset licenses first.<br/>要复用素材或参考代码——先看各自的许可。 |

## Repository layout · 仓库结构

```text
mcpet/
├── src/
│   ├── pet/            # desktop pet window, sprites, behaviour
│   ├── agent_mcp.py    # MCP stdio server for the host
│   ├── agent_install.py# prints server.command / server.args
│   ├── progress/       # session state from logs + host events
│   ├── metering/       # local token ledger
│   ├── accounts/       # read-only quota / balance sources
│   ├── mcd_mcp/        # McDonald's client, business rules, order guard
│   ├── nutrition/      # local nutrition ledger
│   └── schedule/       # reminders
├── .agents/skills/     # portable agent skill source
├── assets/             # sprites, GIFs, credits
├── docs/               # user guide, agent docs, release notes, media
├── integrations/       # optional native adapters (OpenCode)
├── scripts/            # release build, asset import, diagnostics
└── tests/              # 38 pytest files
```

## Status · 状态

Shipped release: **v0.1.0**, Python/Qt, Windows x64 portable. The Tauri 2 + original-art redesign is still at M0 ([docs/contest/M0-REPORT.md](docs/contest/M0-REPORT.md)). Source is 70 Python modules; tests are 38 files.

现行发行：**v0.1.0**，Python/Qt，Windows x64 便携包。Tauri 2 与原创形象的重做仍在 M0（[docs/contest/M0-REPORT.md](docs/contest/M0-REPORT.md)）。源码 70 个 Python 模块；测试 38 个文件。

Known limits, stated rather than hidden:

- The v0.1.0 download still needs your own McDonald's / Luckin tokens; token-free trial only works from current source (`.env.trial`).
- macOS and Linux desktop/tray compatibility has not been fully accepted; only the agent path is cross-platform today.
- Desktop reminders need the pet running; agent reminders need host activity.
- `python -m pytest -q` has known open failures in legacy desktop and foreground-performance items; the curated regression set is the one the repo claims.
- No CI workflow exists in this repository, so nothing is checked automatically on push.
- Real-account orders, payments and full host conversations still need human acceptance.

边界写出来而不是藏起来：

- v0.1.0 下载包仍需自备麦当劳/瑞幸凭据；免 Token 试用只在当前源码（`.env.trial`）可用。
- macOS、Linux 的桌面与托盘兼容性尚未完整验收；目前只有 Agent 路径是跨平台的。
- 桌面提醒依赖桌宠运行；Agent 提醒依赖宿主活动。
- `python -m pytest -q` 在旧桌面与前台性能相关项上仍有已知失败；仓库只对整理出的回归集作承诺。
- 本仓库没有 CI 工作流，push 时不会自动检查。
- 真实账号下单、付款与完整宿主对话仍需人工验收。

## License · 许可

This repository declares **no project-wide license** at its root — there is no top-level LICENSE file. Per-asset and per-reference licenses are recorded in [assets/CREDITS.md](assets/CREDITS.md); the only LICENSE file in the tree is `assets/dsh-deepseek/LICENSE`, which covers that asset only. Treat the code as all-rights-reserved until the author states otherwise.

本仓库根目录**没有项目级许可**——没有顶层 LICENSE 文件。各素材与参考代码的许可记录在 [assets/CREDITS.md](assets/CREDITS.md)；树内唯一的 LICENSE 是 `assets/dsh-deepseek/LICENSE`，只覆盖该素材。在作者另行声明前，代码按保留所有权利对待。
