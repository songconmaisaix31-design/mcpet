# 素材与代码来源

本文件用于满足赛事的原创性声明要求：**参赛项目系原创开发，或已取得合法授权**。
每一项的授权状态如实标注，没有拿到授权的一律不用。

## 1. 占位形象：龙娘精灵图集 `assets/longniang/`

| 项 | 值 |
|---|---|
| 来源 | `caritivememory-ops/chatgpt-longniang` |
| 文件 | `spritesheet.webp`（1536×2288）、`pet.json`、`sprite-rows.json`（由上游 `pet_request.json` 生成） |
| 规格 | 8 列 × 11 行，单元 192×208，`spriteVersionNumber: 2`，11 个动作行 |
| **授权状态** | **已取得原作者授权**（2026-10-10，由本项目作者联系确认） |
| 用途 | 工程占位形象。**最终交付前替换为原创麦当劳主题素材** |

上游仓库本身**没有 LICENSE 文件**，默认视为版权保留。本项目是在取得作者明确授权后
才将其纳入的。若授权凭证需要在审核时出示，请补充：作者在 GitHub Issue 或仓库
README 中的书面授权说明截图，存放于本目录。

## 2. 占位形象：鲸鱼娘素材 `assets/cetapet-whale/`

| 项 | 值 |
|---|---|
| 来源 | `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek` 的 `CetaPet/asset_library` |
| 说明 | 上游 README 标注「角色图片为 ChatGPT AI 生成素材」 |
| **授权状态** | 上游 `LICENSE` 文件为 MIT，但 README 同时声明「仅允许个人学习使用；禁止商用」——**两处存在冲突** |
| 处理 | 已在上游仓库发起授权确认；在收到书面答复前，本目录素材仅用于本机开发，不用于对外发布物料 |

## 3. 代码参考

### 新增角色：DeepSeek 娘 `assets/dsh-deepseek/`

- 用户指定来源：[PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet)，固定上游 SHA `92662190cdd4dee05e38a5151584cc6254cd7a43`。
- 上游随仓库提供 **MIT**，版权 `Copyright (c) 2026 PC2005-cloud`；完整许可证随素材保留于 `assets/dsh-deepseek/LICENSE`。未另行声称作者身份或官方品牌授权。
- 仅复用九个必要透明 WebM 动作，离线转成现有 PySide6 播放的无损固定格 PNG 分页缓存（每页12帧）和同像素首帧预览；右跑由左跑镜像。分页由先前固定 WebP 缓存逐像素无损拆分，不另裁框或缩放。未安装/运行 DSH 插件或复制聊天/模型/账号实现。
- 原文件、SHA256、规格、alpha/固定裁框、工具与复现步骤见 `assets/dsh-deepseek/manifest.json` 和 `SOURCE.md`。该角色由用户选择切换，麦麦仍复用既有 longniang 授权素材。

| 对象 | 借鉴了什么 | 处理方式 |
|---|---|---|
| `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek` | 托盘常驻 + 状态机 + 气泡 + 拖拽的**架构** | 代码为本项目重写（Python / PySide6），未复制其源码文件 |
| `myunwang/LLMPET`（MIT） | ① 状态优先级与 oneshot TTL 衰减（`shared/states.js`）② **用量计量机制**（`backend/metering.js`、`backend/codex-metering.js`、`backend/usage-archive.js`）③ **进度机制**（`backend/transcript.js`、`backend/runtime-monitor.js`） | **机制移植，用 Python 重写，未复制任何 JS 源码文件**；本项目未使用其任何素材 |
| `caritivememory-ops/chatgpt-longniang` | 精灵图规格与 QA 校验**流程** | 规格照用，素材在授权范围内使用 |

### 3.1 从 LLMPET 移植的具体机制（第 ②③ 项的展开）

如实列出，便于审核对照。这些是**算法与数据结构层面的做法**，Python 实现为本项目独立编写：

| 机制 | LLMPET 出处 | 本项目落点 | 差异 |
|---|---|---|---|
| 字节偏移增量扫描 | `metering.js` 的 `cursors` | `agentbridge/providers/base.py::read_from_offset` | 抽成 provider 通用能力 |
| `message.id` 去重 + 逐分量取最大 + 只记正增量（流式修正） | `metering.js` `usageDelta` / `mergeUsage` | `metering/usage.py::_absorb` | 同 |
| 5 小时滚动窗口 | `metering.js` `WINDOW_MS` | `metering/usage.py` `recent` + `window_hours` | 窗口长度改为可配置 |
| 日 / 时 / 终生三级聚合，终生 = carried + 保留日 | `usage-archive.js` | `metering/usage.py::_prune` | 简化：不做 schema 归档层 |
| 上下文窗口 1M 启发式（用量顶穿 200k 即判 1M） | `transcript.js::contextLimit` | `agentbridge/context.py::context_limit` | 去掉 LiteLLM 在线同步，改内置表 + 显式 `1m` 标记 |
| Codex 记 `last_token_usage` 而非累计差值 | `codex-metering.js` | `agentbridge/providers/codex.py` | 同（累计计数器压缩后会重置，差值会放大 10 倍） |
| 进程表采样识别活跃 Agent | `runtime-monitor.js` | `progress/tracker.py::ProcessSampler` | 改为**可选且默认关闭**（依赖 `psutil`） |
| 会话状态 → 桌宠状态映射 | `adapter.js` | `progress/report.py::pet_state_for` | 状态词表按本项目需要重定义 |

**关键差异（这也是移植的主要原因）**：LLMPET 把数据源写死为 `~/.claude/projects`
与 `~/.codex/sessions`。本项目把它抽成 `agentbridge` 的 provider 层，并定义了
一份公开的通用收件箱规范（`docs/AGENT_BRIDGE.md`），使**任何 Agent** 都能接入，
且**一个数据源都没有时程序照常运行**。

## 4. 原创部分

以下为本项目原创实现，无第三方来源：

- `src/mcd_mcp/` 全部：MCP Streamable HTTP 客户端、麦麦大脑、下单护栏
- `src/agentbridge/` 全部：provider 抽象、根目录解析、通用收件箱规范、三档 provider 适配
- `src/metering/`、`src/progress/` 全部：Python 实现、计价表、文案与口径纪律
- `src/pet/spritesheet.py`：图集切片播放器
- `src/schedule/clock.py`：每日调度与休眠补触发
- `src/nutrition/ledger.py`：营养台账
- `src/pet/window.py`、`tray.py`、`dialogs.py`：窗口、托盘、确认对话框
- `assets/longniang/sprite-rows.json`：由上游 `pet_request.json` 重新生成的结构化行定义

## 5. 品牌合规

本项目不使用麦当劳官方商标、金色拱门标识或任何官方视觉元素，不暗示官方背书。
输出仅供参考，不构成医疗或营养建议。
