# McPet（麦麦搭子）🍔

把写代码时的 AI 搭子换上麦当劳制服，养在桌面角落。

她住在系统托盘里。单击摸摸，双击打开非模态「麦麦小窝」，右键和托盘也进入同一个小窝。
每天 11:30 提醒吃饭并只读查询优惠券和报价；主动领券、下单与撤单另需勾选确认。

跑长任务时，她还能读本机各 Agent 的日志，告诉你**谁在跑、跑到哪、上下文用了多少**，
以及**这一轮烧了多少 token**——用量偏重会主动提醒。

餐品、券、价格与营养查询走**麦当劳官方 MCP**。会话辅助和本机控制无需模型 Key 或 MCP Token。
桌面应用不创建独立聊天，不向原 Agent 会话注入请求。服务端未营业或查询失败会显示原因，不能用模型记忆替代实时餐品事实。

> **AI 拟人 × 麦门文化**：用量有人盯，开发有人陪，干饭有人喊。

---

## 它到底做什么

| 能力 | 触发方式 | 背后真实调用的 MCP 工具 |
|---|---|---|
| **优惠券汇报** | 小窝「麦当劳」页 / 11:30 自动 | `available-coupons` + `query-my-coupons`，只查询 |
| **主动领券** | 小窝按钮勾选确认后 | `auto-bind-coupons`，会修改账号 |
| **今天最划算** | 小窝「麦当劳」页 / 11:30 自动 | `query-meals` + `query-store-coupons` + `calculate-price` 逐个试券 |
| **下单 / 撤单** | 核对摘要并勾选确认后 | `create-order`（返回订单号与支付链接） / `cancel-order`；本轮未执行真实订单 |
| **营养记账** | 小窝选择具体餐品及 0.25–20 份 | `list-nutrition-foods` 获取真实餐品，确认后按份数写本机台账，取消不写入 |
| **吃饭提醒** | 每天 11:30（`MCPET_LUNCH_TIME` 可改） | 本地调度器，补触发休眠期间错过的提醒 |
| **开发陪伴** | 启动后自动观测；小窝「会话」页 | 读本机配置目录中的日志，状态驱动动作；上下文占用不是任务完成百分比 |
| **用量提醒** | 启动后自动观测；小窝「会话」页 | 本机 token 台账及估算费用，不读取厂商余额 |
| **日常陪伴** | 单击摸摸、双击小窝；「陪伴」页闲逛 / 休息 | 本机行为与会话观测无模型请求 |

「最划算」不是猜的：它先用门店券的 `products[].productCode` 反查出「哪些餐品有券可用」，
再对这些餐品逐个试算实付价，用 `(无券价 − 用券价)` 取最大者。
调用量 ≈ 菜单 1 + 门店券 1 + 候选数 × 2，远低于 600 次/分钟的限流。

## 自动开发陪伴与用量提醒（Agent 桥接层）

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
python -m src.cli usage       # 本机用量：滚动窗口、今日、趋势、外推
```

桌面应用自动启动一个 `AgentMonitor`，默认每 10 秒观测进度、每 60 秒更新用量。
扫描在标准 spawn 子进程中运行，冷回填期间仍可操作窗口；大日志首次回填需等待，
详情会显示读取中或 UNKNOWN，不能把还未返回的数据解释成零用量。只有启动后新观察到的
明确完成事件才触发庆祝；历史完成、日志停更、进程退出不算新的成功。小窝「会话」页可请求刷新。

Orca 等工具可能把日志放在自己的账号目录，`~/.codex/sessions` 只是候选，不能代表当前账号。
在小窝「设置 → 高级 · Agent 日志目录」填入当前账号的实际 sessions root，保存后退出重启，再用 `python -m src.cli agents`
核对目录与来源。环境变量 `MCPET_AGENT_ROOTS` 优先于单独 root 设置；程序不枚举其他账号。
配置细节、显式 root 示例与冷扫描限制见 [AGENT_BRIDGE.md](docs/AGENT_BRIDGE.md)。

**口径纪律**：产出的是**本机日志台账，不等于厂商余额、配额或账单**。计价未精确命中的模型
会标「按家族估算」，窗口外推样本不足时明说「先不推算」，不硬凑一个好看的数字。

## 麦麦小窝（Agent 会话辅助）

双击桌宠、右键「麦麦小窝」或点击托盘，打开同一个可重用的非模态窗口。关闭后再打开仍是这个小窝，桌宠和唯一后台监控继续运行。

- **陪伴**：闲逛开关、休息 / 唤醒、显示 / 隐藏桌宠、安全退出。
- **小窝首页**：切换麦麦 / DeepSeek 娘，当前角色、预览与托盘同步；角色偏好由桌宠窗口保存。账号剩余额度按订阅窗口或桶独立展示已用、剩余、重置倒计时和来源更新时间；Cursor 两桶不相加。未知不画假 0%，失败保留旧值并标过时，重置时间经过也不会自动假定额度补满。
- **会话**：真实来源、会话标签、日志状态、新鲜度和上下文占用；本机用量与可展开的详细报告。未知显示 UNKNOWN，过时快照不推导任务成功；上下文上限推断时标「估算」。继续在原 Agent 应用操作即可。
- **麦当劳**：只读券查询、实时比价、主动领券、核对下单 / 撤单、真实餐品份数选择、今日营养和付款链接。
- **设置**：MCP 凭证、只读余额用的 DeepSeek Key、城市及可折叠的显式日志目录。已有凭证不回填、留空保留、清除需明确勾选；取消修改和关闭小窝均丢弃未保存输入。日志目录修改后退出重启；DeepSeek Key 保存后同一个账号监控更换源再刷新，旧 Key 的余额不会被当作新账号余额显示。

订阅额度来自 Orca 公共 CLI 的账号缓存，默认每 300 秒刷新，也可点顶部「刷新额度」。查询失败后再次刷新，旧值仍标为过时，收到成功的新快照才恢复正常。缓存不等于厂商即时结算。DeepSeek 只用 `DEEPSEEK_API_KEY` 查询官方余额接口，按币种保留 Decimal 金额及赠送/充值余额，不设虚构上限或百分比，不发模型请求。无 Key 明示未配置；本机日志 token 与估算费用只留在「会话」页，不能换算账号余额。未集成账号或角色模块的分支会显示不可用 / 禁用切换，不用设计示例填充。

视觉按主轨实际 [Pixso 首页稿](https://pixso.cn/app/design/c7aSBvfcRT5aEFJtF7vTmQ?node-id=3%3A1) 对照：奶油色小窝、橘/蓝角色卡、紧凑额度行和独立金额卡；其他三页延续同一视觉体系。设计里的数字是示意，应用仅呈现来源快照。PySide6 原生窗口支持 DPR1.5，页面滚动，四入口复用并恢复最小化的小窝。

桌面不显示会话输入框，不读取、迁移或发送既有 `chat.json`，不调用 StepFun / Skill 创建新的聊天，也不自动提取个人偏好。旧聊天模块和历史数据保留。

### CLI 高级工具（可选）

旧 Skill 命令保留，仅在用户显式执行 CLI 时使用阶跃星辰 OpenAI 兼容接口，默认 `step-3.5-flash`；写工具仍有闸门。它不是桌宠的小窝会话入口。

```bash
python -m src.cli models                      # 可选 StepFun Key
python -m src.cli ask "巨无霸有多少大卡"      # 显式新 CLI 问答；实时查询还需 MCP Token
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
STEPFUN_API_KEY=你的阶跃星辰Key      # 可选，仅旧 CLI models / ask 使用
DEEPSEEK_API_KEY=你的DeepSeekKey     # 可选，仅桌面只读查询余额，不发送模型请求
```

> Token 获取：到 https://open.mcd.cn/mcp 用手机号登录 → 右上角「控制台」→ 激活 → 复制。
> `.env` 已被 `.gitignore` 排除。也可在小窝「设置」填写 MCP Token：输入遮挡、已有凭证不回填，
> 留空保留，清除需勾选；保存到 `MCPET_DATA_DIR/.env`（默认 `~/.mcpet/.env`）。
> 加载顺序为进程环境 > 用户数据目录 > 项目配置。缺少 Token 不阻止摸摸、闲逛、休息或会话观测。

运行：

```bash
python -m src.main        # 启动桌宠
python -m src.cli tools    # 只验证 MCP 连通性，不启动界面
```

## 使用示例

```bash
# 拉真实工具清单，顺便核对代码里的参数名对不对
python -m src.cli tools --dump

# 只读券汇报；CLI 不带 --no-claim 会真实领券，桌面自动饭点始终只读
python -m src.cli coupons --no-claim
# 券中心可见：6 张（其中未领 0 张）
# （--no-claim：本次不执行领取）
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

# 本机用量提醒（以下数字为历史输出示例，不是厂商余额）
python -m src.cli usage
#   近 5 小时（滚动窗口）: 527.5k token / $0.64 / 5 次调用
#     外推：按当前速率 5 小时约 684.9k token（最早一条记录还有 69 分钟滚出窗口）
#   今天: 36.01M token / $6.97 / 412 次调用
#     今日分时 token：▁▁▂▃▅▇█▆▄▃▂▁▁▂▄▆▇▅▃▂▁▁▁▁
#   本机留存历史（终生）: 30.04B token / $12,366 / 231715 次调用
# 口径说明：以上是本机日志的 token 台账，**不等于厂商账单**。
```

桌宠界面：单击摸摸，双击麦麦小窝；按住移动超过拖拽阈值后拖动，松手不触摸。
右键与托盘进入同一小窝，四个页签提供陪伴控制、会话 / 用量、麦当劳快捷功能和设置。
位置及闲逛、休息选项存在 `pet-preferences.json`，重启恢复并约束到当前屏幕工作区。
同一数据目录只允许一个实例，重复启动唤醒原小窝；退出会安全结束已开始的请求并回收后台进程。

## 目标用户

**忙到忘记吃饭的程序员与麦当劳爱好者。** 具体到三种场景：

- **写代码写到忘记吃饭的人**——11:30 有搭子叫你，不用自己盯表；
- **每天都在麦麦省领券、但懒得逐个算哪张最划算的人**——她替你穷举；
- **想控制热量又戒不掉麦当劳的人**——吃了就记，账目清楚；
- **跑长任务时反复切窗口看进度的人**——进度与余额都摊在桌面上，不用来回切。

## 项目结构

```
src/
  config.py              环境/本机配置、设置与脱敏
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
  chat/                  保留的旧聊天模块；桌面入口不实例化或读历史
  runtime/               唯一自动 monitor、spawn 扫描与有界退出回收
  pet/
    spritesheet.py       精灵图集加载与切片播放
    states.py            状态词表、优先级、oneshot TTL 衰减
    window.py            桌宠窗口、气泡、触摸/双击/拖拽、上下文控件
    behavior.py          本机闲逛/短休息
    preferences.py       位置与闲逛/休息偏好
    tray.py  dialogs.py  统一小窝、托盘与必要业务确认框
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
  metering/              本机用量提醒
    usage.py             增量扫描 + 流式修正去重 + 日/时/终生聚合 + 原子落盘
    pricing.py           计价表（模型名归一化 + 家族兜底 + 用户覆盖）
    report.py            用量提醒文案（气泡 + 完整报告）
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
tests/                   离线契约、真实 Qt/手势/后台进程集成测试
```

## 已实现 / 待验证 / 未实现

**已实现并有测试覆盖**：MCP 协议层（session 回带、SSE 解析、401、429 退避）、
阶跃星辰链路（对话 / 工具调用解析 / 401 / 429）、Skill 调度与写操作闸门、
精灵图切片与状态映射、调度器（准点 / 迟到补触发 / 跨天 / 宽限放弃）、
下单护栏与审计台账、营养台账、脱敏、麦麦大脑解析层（券 / 菜单 / 算价 / 营养表）、
**跨 Agent 桥接层（三档 provider + 根目录解析 + 通用收件箱规范）**、
**用量台账（流式修正去重 / 分日分时聚合 / 滚动窗口 / 外推）**、
**进度追踪（会话合并 / 新鲜度 / 状态映射）**。
前轮集成结果见 [HANDOFF-INTEGRATION.md](docs/companion/HANDOFF-INTEGRATION.md)，本轮统一面板验证见 [HANDOFF-C-PANEL.md](docs/companion/HANDOFF-C-PANEL.md)。
离线与受控日志通过只证明对应契约，本轮真实模型/MCP、冷扫描与用户验收由主 Agent 独立执行。

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

**本轮已接线**：自动后台状态/用量观测、明确完成事件庆祝、上下文占用控件、双击统一小窝、
会话 / 用量 / 设置同窗页签、真实查询餐品与份数选择、本机行为/位置偏好、单实例、异步请求及安全退出。
上下文未知显式展示，日志刷新失败保留标注可能过时的最后成功快照。

**未实现 / 尚待人工验收**：久坐提醒、跨启动历史订单统计、自选多商品下单、麦当劳主题原创素材、
饭点活动日历播报、语音、开机启动、分发签名/自动更新。休息复用现有 idle 素材。
真实支付与账号写操作没有在本轮集成执行，历史演练不等于实际订单通过，整体产品验收仍待主 Agent。

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
