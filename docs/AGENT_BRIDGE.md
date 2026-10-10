# Agent 桥接规范（AGENT_BRIDGE）

McPet的两项能力——**项目进度汇报**与**账号余额提醒**——都不是麦当劳 MCP 提供的，
它们来自「读本机其他 Agent 的日志」。这份文档说明**从哪读、读什么、不读什么**，
以及**任何一个 Agent 该怎么把自己的数据喂进来**。

---

## 0. 为什么要有这一层

参考项目 [LLMPET](https://github.com/myunwang/LLMPET) 里，计量与进度模块是直接写死
`~/.claude/projects` 的。那是在作者本机跑得通的写法，但一个要给别人跑的开源项目
不能这么写：别人机器上可能没装 Claude Code，可能用的是 Codex，也可能是自己写的
Agent。

所以这里把「数据从哪来」抽成 **provider**，内置三档：

| provider | 数据源 | 适用场景 |
|---|---|---|
| `claude` | Claude Code 的 transcript JSONL | 装了 Claude Code |
| `codex` | OpenAI Codex 的 rollout JSONL | 装了 Codex |
| `generic` | **本文件定义的收件箱规范** | 任何其他 Agent |

前两档是**被动兼容**（适配别人的格式，人家改了我们就得跟着改）；
第三档是**主动契约**——格式由我们自己定义并保持稳定，任何 Agent 只要按规范写，
不需要我们做适配就能接进来。

**一个 provider 都没有时，程序正常运行**，只是这两项功能显示「无可用数据源」。
这是刻意的：桌宠的主业是麦当劳 MCP，读别的 Agent 的日志是增值项，不是前置条件。

---

## 1. 根目录怎么定

解析顺序固定：**环境变量 > 配置文件 > 平台默认候选**。

平台默认候选（**只是候选，不存在就静默跳过**）：

| provider | 候选目录 |
|---|---|
| `claude` | `~/.claude/projects` |
| `codex` | `~/.codex/sessions` |
| `generic` | `~/.mcpet/inbox` |

### 环境变量

```bash
# 单个 provider
MCPET_AGENT_ROOT_CLAUDE=/path/to/claude/projects
MCPET_AGENT_ROOT_CODEX=/path/to/codex/sessions
MCPET_AGENT_ROOT_GENERIC=/srv/agent-inbox

# 批量（逗号或换行分隔；Windows 路径里的 `;` 会和 PATH 打架，所以不用它）
MCPET_AGENT_ROOTS="claude=/a/b,generic=/c/d"

# 配置文件位置
MCPET_CONFIG_PATH=~/.config/maimai/config.json

# 台账落盘目录（含用量历史与计价覆盖）
MCPET_DATA_DIR=~/.mcpet
```

### 配置文件

默认 `~/.mcpet/config.json`：

```json
{
  "agentRoots": {
    "claude": "~/my/custom/claude/projects",
    "generic": ["/srv/inbox-a", "/srv/inbox-b"]
  }
}
```

随时用下面这条命令核对「你以为配了」和「程序实际读到」是否一致：

```bash
python -m src.cli agents
```

输出会明确区分「代码里实现了几种」「这台机器上配了几种」「哪个目录不存在被跳过了」。

---

## 2. 通用收件箱规范

把 JSON 文件放进 `generic` 根目录即可。两种写法，按你的 Agent 方便哪种就用哪种。

### 2.1 用量事件（只追加）

一行一个事件，**写进去就不再修改**——程序靠文件字节偏移去重，改了会重复计数。

```jsonl
{"kind":"usage","ts":1760000000,"model":"step-3.5-flash","input":1200,"output":340,"cacheRead":0,"cacheWrite":0,"session":"run-42"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `kind` | ✅ | 固定 `"usage"`（也接受 `type` / `event` 作别名） |
| `ts` | ✅ | Unix 秒（数字）或 ISO-8601 字符串（如 `"2026-10-11T02:03:04Z"`） |
| `model` | 建议 | 原始模型名。计价时归一化（去厂商前缀、日期、版本尾巴） |
| `input` | ✅* | 输入 token（**不含**命中缓存的部分） |
| `output` | ✅* | 输出 token（**含**推理 token） |
| `cacheRead` | | 命中缓存的输入 token |
| `cacheWrite` | | 写入缓存的 token |
| `session` | | 会话标识 |
| `key` | | 稳定去重键。**给了就用你的，没给就用文件位置** |

\* 四个 token 字段加起来必须大于 0，否则该行被忽略。

字段名同时接受 camelCase 与 snake_case：`cacheRead` / `cache_read` 都可以，
`inputTokens` / `input_tokens` 也都可以。容错优先。

> **为什么要把缓存拆出来**：缓存读写的单价和普通输入不同（通常低一个数量级）。
> 混在一起算，金额会偏出好几倍。参考 Codex 的做法：`cached_input_tokens` 是
> `input_tokens` 的**子集**，不能相加——喂数据前请自行减掉。

### 2.2 进度（两种写法）

**追加式**——往同一个 jsonl 里写，取每个会话的最后一条：

```jsonl
{"kind":"progress","ts":"2026-10-11T02:03:04Z","session":"run-42","state":"working","project":"我的项目","title":"重构登录模块","contextUsed":120000,"contextLimit":200000,"backgroundTasks":2}
```

**覆盖式**——每个会话一个 `<session>.json`，每次整体覆盖。
只关心「当前值」的 Agent 用这种最省事：

```json
{
  "kind": "progress",
  "session": "run-42",
  "state": "working",
  "project": "我的项目",
  "title": "重构登录模块",
  "contextUsed": 120000,
  "contextLimit": 200000,
  "backgroundTasks": 2
}
```

| 字段 | 说明 |
|---|---|
| `state` | 建议取值：`working` / `thinking` / `waiting` / `idle` / `error` / `done`。未知值按 `idle` 处理，不会崩 |
| `project` | 项目名（列表里显示这个） |
| `title` | 当前任务描述。不填则退回 `project` |
| `contextUsed` / `contextLimit` | 上下文占用。**`contextLimit` 可以不给**，程序按模型名推断 |
| `backgroundTasks` | 后台任务数 |
| `model` | 模型名，用于推断上下文窗口 |
| `cwd` | 工作目录 |

时间戳缺失时用文件修改时间兜底。

### 2.3 最小示例

Python：

```python
import json, time, pathlib

inbox = pathlib.Path.home() / ".mcpet" / "inbox"
inbox.mkdir(parents=True, exist_ok=True)

# 一次模型调用结束
with (inbox / "my-agent.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps({
        "kind": "usage", "ts": time.time(), "model": "my-model",
        "input": 1200, "output": 340,
        "cacheRead": 0, "cacheWrite": 0,
        "session": "run-42",
    }, ensure_ascii=False) + "\n")

# 当前进度（覆盖式）
(inbox / "run-42.json").write_text(json.dumps({
    "kind": "progress", "session": "run-42", "state": "working",
    "project": "我的项目", "title": "重构登录模块",
    "contextUsed": 120000, "contextLimit": 200000,
}, ensure_ascii=False), encoding="utf-8")
```

Shell：

```bash
printf '%s\n' '{"kind":"usage","ts":'$(date +%s)',"model":"m","input":100,"output":20}' \
  >> ~/.mcpet/inbox/my-agent.jsonl
```

---

## 3. 读什么，不读什么

**读**：token 数量、模型名、时间戳、会话 id、工作目录、任务标题、状态。

**不读**：消息正文、代码内容、文件内容、任何凭据。

Claude / Codex 两档是**只读扫描**，不写、不改、不删任何源文件；不会安装 hook、
不会修改 Agent 的配置。唯一的写操作是自己的台账文件（`usage.json`）。

任务标题有一个例外：Claude 档会在没有自定义标题时，取用户首条提示的**第一行**
作为标题（≤40 字）。这一行在写入台账前会过一遍密钥样式检测，命中就整条丢弃。
如果你不希望任何提示文本被读取，用通用收件箱自己写标题即可。

台账落盘位置：`~/.mcpet/usage.json`（可用 `MCPET_DATA_DIR` 改）。
内含 token 与金额统计，**不含**任何提示或代码内容。

---

## 4. 口径声明

这一层产出的是**本机日志台账**，不是厂商账单。

- 只统计本机留存日志覆盖的范围；日志被清理的部分不在此列。
- 计价表是内置的手写摘录（非实时同步），未精确命中的模型按家族单价估算，
  报告里会明确列出哪些模型是估算的。
- 「近 5 小时窗口」是**我们自己划的观测窗口**（对齐 Claude 的限流主窗口），
  不是从厂商读来的配额。外推值是本项目的加工，样本不足时会明确标注而不硬算。

---

## 5. 相关命令

```bash
python -m src.cli agents      # 这台机器上接了哪些数据源，每个目录从哪来
python -m src.cli usage       # 账号余额提醒（--json 便于接入别的程序）
python -m src.cli progress    # 项目进度汇报（--json / --active-only）
```

## 6. 环境变量速查

| 变量 | 默认 | 作用 |
|---|---|---|
| `MCPET_AGENT_ROOT_<ID>` | 平台候选 | 单个 provider 的根目录 |
| `MCPET_AGENT_ROOTS` | 空 | 批量覆盖，`id=path` 逗号分隔 |
| `MCPET_CONFIG_PATH` | `~/.mcpet/config.json` | 配置文件位置 |
| `MCPET_DATA_DIR` | `~/.mcpet` | 台账与计价覆盖的目录 |
| `MCPET_USAGE_WINDOW_HOURS` | `5` | 滚动窗口长度 |
| `MCPET_PROGRESS_STALE_MINUTES` | `30` | 多久没更新算「停了」 |
| `MCPET_WATCH_PROCESSES` | `0` | 是否采样本机进程表（需 `psutil`） |
