# McPet（麦麦搭子）🍔

把写代码时的 AI 搭子换上麦当劳制服，养在桌面角落。

她住在系统托盘里。11:30 她喊你干饭，顺手汇报「今天的麦麦省券已全领，
最划算的是巨无霸套餐减 8 元，要下单吗」，再用营养数据帮你把关这一餐。

跑长任务时，她还能读本机各 Agent 的日志，告诉你**谁在跑、跑到哪、上下文用了多少**，
以及**这一轮烧了多少 token**——用量偏重会主动提醒。

所有券、价、营养数据都来自**麦当劳官方 MCP**，真实调用、真实领券、真实下单——
没有一处是抓来的静态数据或拍脑袋的推荐。

> **AI 拟人 × 麦门文化**：余额有人盯，进度有人陪，干饭有人喊。

---

## 它到底做什么

| 能力 | 触发方式 | 背后真实调用的 MCP 工具 |
|---|---|---|
| **领券汇报** | 托盘菜单 / 11:30 自动 | `available-coupons` → `auto-bind-coupons` → `query-my-coupons` |
| **今天最划算** | 托盘菜单 / 11:30 自动 | `query-meals` + `query-store-coupons` + `calculate-price` 逐个试券 |
| **真实下单** | 勾选确认后 | `create-order`（返回支付链接），可 `cancel-order` 撤单 |
| **营养记账** | 托盘菜单 | `list-nutrition-foods`，写入本地每日台账 |
| **吃饭提醒** | 每天 11:30（`MCPET_LUNCH_TIME` 可改） | 本地调度器，补触发休眠期间错过的提醒 |
| **项目进度汇报** | 托盘菜单「项目进度」 | 不是 MCP——读本机各 Agent 的会话日志，见下节 |
| **账号余额提醒** | 托盘菜单「账号余额」 | 不是 MCP——读本机各 Agent 的 token 用量日志，见下节 |

「最划算」不是猜的：它先用门店券的 `products[].productCode` 反查出「哪些餐品有券可用」，
再对这些餐品逐个试算实付价，用 `(无券价 − 用券价)` 取最大者。
调用量 ≈ 菜单 1 + 门店券 1 + 候选数 × 2，远低于 600 次/分钟的限流。

## 进度汇报与余额提醒（Agent 桥接层）

这两项能力复用自 [LLMPET](https://github.com/myunwang/LLMPET) 的基础设施思路，
但**重写成不绑死任何一台机器、任何一个 Agent 的形式**。

LLMPET 的计量模块是直接写死 `~/.claude/projects` 的；这个项目不能这么写——别人
机器上可能没装 Claude Code，可能用 Codex，也可能是自己写的 Agent。所以这里把
「数据从哪来」抽成 provider：

| provider | 数据源 | 说明 |
|---|---|---|
| `claude` | Claude Code transcript JSONL | 只读扫描 |
| `codex` | OpenAI Codex rollout JSONL | 只读扫描 |
| `generic` | **公开的收件箱规范** | 任何 Agent 按规范写就能接进来 |

根目录按 **环境变量 > 配置文件 > 平台默认候选** 解析，候选不存在就静默跳过——
**一个数据源都没有时程序照常运行**，只是这两项显示「无可用数据源」。
完整规范见 **[docs/AGENT_BRIDGE.md](docs/AGENT_BRIDGE.md)**。

```bash
python -m src.cli agents      # 这台机器上接了哪些数据源
python -m src.cli progress    # 项目进度：谁在跑、跑到哪、上下文用了多少
python -m src.cli usage       # 账号余额：滚动窗口用量、今日、趋势、外推
```

**口径纪律**：产出的是**本机日志台账，不等于厂商账单**。计价未精确命中的模型
会标「按家族估算」，窗口外推样本不足时明说「先不推算」，不硬凑一个好看的数字。

## 问麦麦（Skill 层）

除了固定菜单，你还可以直接问它自然语言问题。做法是**把麦当劳 MCP 的工具清单
交给大模型，让它自己决定调哪个**：

```
你的问题 → 真实 tools/list 转成 function 定义 → 阶跃星辰模型选工具
        → 真实 tools/call → 结果喂回模型 → 收敛成一句人话
```

用的是阶跃星辰（StepFun）的 OpenAI 兼容接口，默认 `step-3.5-flash`。
**写操作（领券 / 下单 / 撤单 / 抽奖）默认不交给模型自主执行**——它想调的时候会
停下来告诉你要做什么，等你确认。

```bash
python -m src.cli models                      # 看阶跃星辰有哪些对话模型可用
python -m src.cli ask "巨无霸有多少大卡"       # 没有 MCP Token 时退化为纯问答
```

## 安装

需要 Windows + Python 3.11+。

```bash
git clone https://github.com/songconmaisaix31-design/mcpet.git
cd mcpet
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

然后编辑 `.env`，填入你的麦当劳 MCP Token：

```
MCD_MCP_TOKEN=你的真实Token
STEPFUN_API_KEY=你的阶跃星辰Key      # 可选，只用于「问麦麦」
```

> Token 获取：到 https://open.mcd.cn/mcp 用手机号登录 → 右上角「控制台」→ 激活 → 复制。
> `.env` 已被 `.gitignore` 排除，不会进仓库。首次启动时若没有 Token，程序会弹窗让你录入，
> 并明文存到 `~/.mcpet/.env`（权限尽量设为仅本人可读）。

运行：

```bash
python -m src.main        # 启动桌宠
python -m src.cli tools    # 只验证 MCP 连通性，不启动界面
```

## 使用示例

```bash
# 拉真实工具清单，顺便核对代码里的参数名对不对
python -m src.cli tools --dump

# 领券汇报（会真实领券）
python -m src.cli coupons
# 券中心可见：6 张（其中未领 0 张）
# 一键领取：暂无可领取的优惠券
# 手上共：5 张
#   · 9.9元中杯冰美式
#   · 人气麦旋风买一送一
#   ...

# 今天最划算的一单（真实比价）
python -m src.cli deal
# 门店：麦当劳北京东单北大街餐厅 (1951035) beType=1 营业中=True 距离=1031m
# 1. 麦咖啡™美式 减 2.00 元（原价 11.90 → 实付 9.90）  [券：9.9元中杯冰美式]
# 2. 巨无霸 暂无可用券（25.50 元）  [券：无可用券]

# 下单链路：默认只展示摘要，加 --yes 才真正落单
python -m src.cli order
# 门店：麦当劳北京东单北大街餐厅
# 取餐方式：外带
# 商品：麦咖啡™美式
# 用券：9.9元中杯冰美式
# 实付：9.90 元
# 状态：needs_confirmation

# 查营养并记一笔
python -m src.cli nutrition --keyword 巨无霸 --log
# 巨无霸: 513 kcal（2146 kJ）| 蛋白 27.0 g | 脂肪 26.0 g | 碳水 42.0 g | 钠 961 mg | 钙 171 mg
# 今天记了 1 项：约 513 kcal，蛋白 27 g，脂肪 26 g，碳水 42 g，钠 961 mg

# 问麦麦（大模型自己挑 MCP 工具）
python -m src.cli ask "今天最划算的是哪个？"

# 看看这台机器上接了哪些 Agent 数据源
python -m src.cli agents
# 代码里实现的 provider：generic, claude, codex
# 根目录解析（环境变量 > 配置文件 > 平台默认候选）：
#     claude   /home/you/.claude/projects  [默认]
#     codex    /home/you/.codex/sessions   [默认]
#     generic  /home/you/.mcpet/inbox  [默认]  (不存在，已跳过)
# 本机可用：claude, codex

# 项目进度汇报
python -m src.cli progress
# 活跃会话（30 分钟内更新）：1 个
#     [claude ] McPet        干活中 上下文 ██████░░░░  62%  2 分钟前 claude-sonnet-4-5

# 账号余额提醒
python -m src.cli usage
#   近 5 小时（滚动窗口）: 527.5k token / $0.64 / 5 次调用
#     外推：按当前速率 5 小时约 684.9k token（最早一条记录还有 69 分钟滚出窗口）
#   今天: 36.01M token / $6.97 / 412 次调用
#     今日分时 token：▁▁▂▃▅▇█▆▄▃▂▁▁▂▄▆▇▅▃▂▁▁▁▁
#   本机留存历史（终生）: 30.04B token / $12,366 / 231715 次调用
# 口径说明：以上是本机日志的 token 台账，**不等于厂商账单**。
```

桌宠界面：左键点它看今日营养，右键出菜单（含「项目进度」「账号余额」），
按住拖动可以把它挪到屏幕任意角落。

## 目标用户

**忙到忘记吃饭的程序员与麦当劳爱好者。** 具体到三种场景：

- **写代码写到忘记吃饭的人**——11:30 有搭子叫你，不用自己盯表；
- **每天都在麦麦省领券、但懒得逐个算哪张最划算的人**——她替你穷举；
- **想控制热量又戒不掉麦当劳的人**——吃了就记，账目清楚；
- **跑长任务时反复切窗口看进度的人**——进度与余额都摊在桌面上，不用来回切。

## 项目结构

```
src/
  config.py              凭证与脱敏（Token 只从环境变量读，输出前必过 redact）
  cli.py                 命令行验证工具，MCP_INTEGRATION.md 的证据来源
  main.py                入口：托盘 + 窗口 + 调度器 + 大脑装配
  mcd_mcp/
    client.py            MCP Streamable HTTP 客户端（手写，无 SDK 依赖）
    tools.py             工具清单与参数名映射（已用真实 tools/list 校正）
    brain.py             麦麦大脑：领券 / 比价 / 营养 / 下单（含营养表解析器）
    skill.py             把 MCP 工具交给大模型调度（含写操作闸门）
    guards.py            下单护栏 + 本机审计台账
  llm/
    stepfun.py           阶跃星辰 OpenAI 兼容聊天客户端（手写，无 SDK 依赖）
  pet/
    spritesheet.py       精灵图集加载与切片播放
    states.py            状态词表、优先级、oneshot TTL 衰减
    window.py            桌宠窗口、气泡、拖拽、右键菜单
    tray.py  dialogs.py  托盘与对话框
  agentbridge/           跨 Agent 数据桥（可移植层，不绑死任何 Agent）
    paths.py             根目录解析（环境变量 > 配置 > 平台候选，候选不存在即跳过）
    context.py           上下文窗口推断（含 1M 启发式）
    records.py           归一化记录：UsageRecord / ProgressRecord
    registry.py          provider 注册与「本机可用」筛选
    providers/
      base.py            JSONL 增量读写（尾部 / 头部 / 字节偏移续读）
      claude.py          Claude Code transcript 适配
      codex.py           OpenAI Codex rollout 适配（含子集字段归一）
      generic.py         通用收件箱适配（任何 Agent 按规范写入）
  metering/              账号余额提醒
    usage.py             增量扫描 + 流式修正去重 + 日/时/终生聚合 + 原子落盘
    pricing.py           计价表（模型名归一化 + 家族兜底 + 用户覆盖）
    report.py            余额提醒文案（气泡 + 完整报告）
  progress/              项目进度汇报
    tracker.py           会话快照合并、新鲜度判定、可选进程采样
    report.py            进度文案（气泡 + 会话表）
  schedule/clock.py      每日定时调度（含休眠唤醒补触发）
  nutrition/ledger.py    每日营养台账
docs/
  AGENT_BRIDGE.md        跨 Agent 桥接规范（通用收件箱格式 + 配置速查）
  mcp-schemas.json       35 个 MCP 工具的真实 inputSchema
  verification-report.md 真实 Token 全链路验证报告（已脱敏）
scripts/
  dump_schemas.py        导出真实 MCP schema → docs/mcp-schemas.json
  probe_raw.py           打印各工具真实返回结构（只读）
  setup_token.py         一键写入 Token 并跑全部真实校验
tests/                   179 项离线测试
```

## 已实现 / 待验证 / 未实现

**已实现并有测试覆盖**：MCP 协议层（session 回带、SSE 解析、401、429 退避）、
阶跃星辰链路（对话 / 工具调用解析 / 401 / 429）、Skill 调度与写操作闸门、
精灵图切片与状态映射、调度器（准点 / 迟到补触发 / 跨天 / 宽限放弃）、
下单护栏与审计台账、营养台账、脱敏、麦麦大脑解析层（券 / 菜单 / 算价 / 营养表）、
**跨 Agent 桥接层（三档 provider + 根目录解析 + 通用收件箱规范）**、
**用量台账（流式修正去重 / 分日分时聚合 / 滚动窗口 / 外推）**、
**进度追踪（会话合并 / 新鲜度 / 状态映射）**。
**179 项离线测试全通过**。

**已用真实 Token 验证**（2026-10-10）：

- 35 个 MCP 工具的真实 inputSchema 全部抓取并核对，参数字段名已对齐；
- `available-coupons` / `auto-bind-coupons` / `query-my-coupons` 真实领券链路跑通；
- `query-meals` + `query-store-coupons` + `calculate-price` 真实比价跑通
  （实测：冰美式无券 11.90 元 → 用「9.9元中杯美式」券后 9.90 元）；
- `list-nutrition-foods` 的非 JSON 自定义表格格式解析跑通（160 条）；
- 下单链路 `order` 全流程跑到提交前一步（`MCD_DRY_RUN=1` 时不落单）。

实测校正的字段名、单位、坑位见 [`MCP_INTEGRATION.md` 第 4.1 节](./MCP_INTEGRATION.md)。

**已用真实本机数据验证**（2026-10-11）：桥接层在本机 1721 个真实日志文件上跑通——
首次回填 232k 条用量记录（约 35 秒），增量扫描 0.5 秒；进度快照 0.15 秒。
这两个数字是性能底线：增量路径必须比首次回填快两个数量级，否则桌宠会被拖住。

**未实现**：久坐提醒、历史订单统计、自选餐品的下单（当前「记一笔」取营养表第一项，
缺一个选择框）、麦当劳主题原创素材。

**进度/余额与桌宠的「自动」联动尚未接线**（这一点必须说清楚，别让它看起来像是做好了）：

- 数据层已完成——`progress` / `usage` 两条链路都能真实读出会话状态与用量；
- 但**目前是菜单手动触发**（「项目进度」「账号余额」），还没有一个定时器持续轮询、
  把活跃会话的状态自动映射成她的表情与动作；
- 也还没有**头顶进度条**这个可视控件，没有「任务完成自动跳起来庆祝」的转场；
- 「换上工服」与「播报当月活动」同理：前者需要原创素材，后者对应的
  `campaign-calendar` 工具已探明但尚未接入饭点流程。

接线所需的接口（`ProgressTracker.snapshot()` / `UsageMeter.snapshot()` /
`pet_state_for()`）都已就位并有测试覆盖，补的是一个 QTimer 与一个绘制控件。

## 关于当前形象

仓库里的形象（龙娘精灵图 + 鲸鱼娘素材）是**占位素材**，用于先把工程跑通：

- 龙娘图集来自 `caritivememory-ops/chatgpt-longniang`，规格为 8 列 × 11 行、
  单元 192×208、`spriteVersionNumber: 2`；已取得原作者授权，见 [`assets/CREDITS.md`](./assets/CREDITS.md)。
- 鲸鱼娘素材来自 `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek`。

最终交付前会替换为原创的麦当劳主题素材，图集行数按 `src/pet/states.py` 的
`TARGET_ROWS` 排即可，播放层无需改动。

## 技术与素材来源

- 桌面壳的架构参考了 `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek`（托盘常驻 + 状态机 +
  气泡 + 拖拽），代码为本项目重写：素材从「单张 PNG 切换」改为 spritesheet 切片播放，
  状态机带优先级与 TTL 衰减。
- 状态优先级与 oneshot 衰减的思路借鉴自 `myunwang/LLMPET` 的 `shared/states.js`。
- **进度汇报与余额提醒的机制来自 `myunwang/LLMPET`**（MIT）：字节偏移增量扫描、
  `message.id` 去重取最大快照 + 只记正增量的流式修正、5 小时滚动窗口、
  日/时/终生三级聚合、上下文窗口 1M 启发式、会话状态优先级。
  这些是**用 Python 重写的机制**，不是照搬代码；差异在于 LLMPET 写死
  `~/.claude/projects`，这里抽成了 provider（见 `docs/AGENT_BRIDGE.md`）。
- 精灵图规格与 QA 流程参考 `caritivememory-ops/chatgpt-longniang`。

详见 [`assets/CREDITS.md`](./assets/CREDITS.md)。

## 声明

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
输出仅供参考，不构成医疗或营养建议；餐品信息、价格及供应状态以麦当劳官方渠道的
实时结果为准。完整声明见 [`CONTEST_DECLARATION.md`](./CONTEST_DECLARATION.md)。

本项目会真实创建麦当劳订单并产生真实支付——请确认你愿意让宠物替你下单再启用。
