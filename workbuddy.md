# WorkBuddy 对话上下文

本文件记录「麦麦小怪兽」在腾讯 WorkBuddy 智能体中的开发过程，用于活动联动。
本项目从立项调研到真实验证，全程在 WorkBuddy 中完成。

## 1. 项目是怎么被 WorkBuddy 做出来的

### 阶段一：立项调研（决策层对齐）

起点是一句产品叙事：「一个住在系统托盘的麦当劳小宠物，11:30 提醒你吃饭，
顺手汇报今天最划算的券，帮你记营养」。

WorkBuddy 先做了三件事，而不是直接写代码：

1. 克隆并通读大赛官方仓库，提取出**赛制硬事实**——排名按 GitHub Star 而非评审、
   报名 Issue 截止 2026-10-25、必须提交 `README.md` / `CONTEST_DECLARATION.md` /
   `MCP_INTEGRATION.md` / `mcp-config.example.json` 等文件；
2. 逐个调研三个待复用仓库，给出**可复用性分级**（哪些是代码底座、哪些只是素材包）；
3. 反过来向开发者提出**开发决策层问题**（底座选型 / 交付切分 / MCP 调用边界 / 素材方案），
   而不是替开发者拍板。

这一步的产出直接决定了后面所有工作的方向：选定 CeTaPet 作为 Python/PySide6 底座，
砍掉久坐提醒与历史订单统计，聚焦「领券汇报 + 11:30 提醒 + 算价下单 + 营养记账」。

### 阶段二：风险前置

在动工前，WorkBuddy 主动指出了三个会被忽略的坑：

- **许可证冲突**：CeTaPet 的 LICENSE 写 MIT，但 README 明确写「仅允许个人学习使用」，
  参赛公开发布存在冲突；
- **`chatgpt-longniang` 仓库没有任何 LICENSE 文件**，默认版权保留，素材法律上不可直接复用；
- **占位素材入库**的风险。

这些都在写第一行代码之前就摆到了台面上。

### 阶段三：工程实现

WorkBuddy 建了完整工程骨架并跑了 91 项离线测试：

| 模块 | 内容 |
|---|---|
| `src/mcd_mcp/client.py` | 手写 MCP Streamable HTTP 客户端（零 SDK 依赖）：session 回带、SSE 与单条 JSON 双解析、401 直失败、429 退避、540 次/分钟客户端限流 |
| `src/mcd_mcp/brain.py` | 麦麦大脑：领券汇报 / 门店解析 / 穷举比价 / 营养表解析 / 下单 |
| `src/mcd_mcp/guards.py` | 下单护栏：单笔金额上限 + 每日次数上限 + 本机审计台账 + 撤单标记 |
| `src/mcd_mcp/skill.py` | 把 MCP 工具清单交给大模型自主调度，含**写操作闸门** |
| `src/pet/` | spritesheet 切片播放器（按行号取帧数）、状态优先级 + oneshot TTL 衰减、窗口/气泡/托盘/勾选式确认框 |
| `src/schedule/clock.py` | 每日定时调度（纯逻辑可测 + QTimer 驱动，含休眠唤醒补触发） |
| `src/llm/stepfun.py` | 阶跃星辰 OpenAI 兼容客户端（手写，无 SDK） |
| `src/nutrition/ledger.py` | 每日营养台账 |

一个具体的调试例子：精灵图播放时，别名状态（如 `remind` → 行 3 的挥手动作，只有 4 帧）
会按状态名取到 8 帧，多出来的 4 帧是空格，表现为闪烁。WorkBuddy 定位到根因是
「帧数按状态名索引而非行号索引」，改为 `frames_by_row` 后修复。

### 阶段四：真实 Token 接入与全面校正（本项目最有价值的部分）

拿到真实 `MCD_MCP_TOKEN` 后，WorkBuddy 做了**逐工具实测校正**，而不是假设文档准确。
官方 README 只给了工具名和中文说明，**没有公开 inputSchema 字段表**，所以此前的参数名
全是按命名惯例推测的——实测后发现**几乎全错**：

| 原先推测 | 实测真实字段 |
|---|---|
| `storeId` | `storeCode` |
| `mealCode` | `productCode` |
| `couponId` 放在 `calculate-price` 顶层 | 放在**每个 `items[]` 元素里** |
| 只传 `couponId` | `couponId` + `couponCode` **两个都必须给**（否则报 600010） |
| 算价结果字段 `payAmount` / `totalAmount` | 真实字段是 `price`（原字段名根本不存在 → 算价静默返回 0） |

还挖出几个文档里没写、但会让功能直接失效的坑：

- **`create-order` 在到店场景（`orderType=1`）必传 `takeWayCode`**，取值来自
  `calculate-price` 返回的 `data.takeWayList[].code`（`eat-in` 堂食 / `take-in-store` 外带）；
- **`list-nutrition-foods` 返回的是字符串，不是 JSON**，格式为
  `[160]{productName,nutritionDescription,...}:\n  巨无霸,null,2146,513,...`，
  需要专门写解析器；
- **价格单位是「分」**（`price: 3350` = 33.50 元），但 `query-meals` 里的 `currentPrice`
  又是**元**的字符串，两个工具单位不一致；
- `query-nearby-stores` 中 `businessStatus: false` 的门店调 `query-meals` 会报 600057，
  必须优先挑营业中的门店；
- `canWithOrder` 是「随单购资格」**不是**「能否下单」，误当阻断条件会导致全部商品不可下单；
- `auto-bind-coupons` 无新券时返回 `success: false, code: 499`，这是**良性结果不是错误**；
- 统一响应壳 `{success, code, message, datetime, traceId, data}` 剥壳时
  **不能顺手折叠 `data` 本身**（`query-store-coupons` 的 data 就是长度恰好为 1 的券列表）。

这些校正全部沉淀在 [`MCP_INTEGRATION.md` 第 4.1 节](./MCP_INTEGRATION.md) 与
[`docs/verification-report.md`](./docs/verification-report.md)。

## 2. 真实验证结果

`docs/verification-report.md` 记录了 **7/7 项真实调用通过**：

| 验证项 | 结果 |
|---|---|
| 工具清单与参数名核对 | 通过（35 个工具真实 inputSchema 全部抓取对齐） |
| 服务端时间 | 通过 |
| 营养数据（含自定义表格解析） | 通过（160 条） |
| 领券汇报（真实领券） | 通过 |
| 今天最划算的一单（真实比价） | 通过 |
| 下单链路（演练，不落单） | 通过 |
| Skill：让模型自己调工具 | 通过 |

实测样例：

- 门店：麦当劳北京东单北大街餐厅（1951035），营业中，1031m
- 最优：麦咖啡™美式 原价 11.90 元 → 用「9.9元中杯冰美式」券后 **9.90 元**
- 巨无霸：513 kcal / 蛋白 27g / 脂肪 26g / 碳水 42g / 钠 961mg / 钙 171mg

## 3. WorkBuddy 在本项目里承担的实质工作

- **调研与事实核查**：读官方仓库、提取消赛制约束、评估三个参考仓库的许可证与可复用性
- **架构设计**：确定「MCP 协议层 / 麦麦大脑 / 桌面壳 / 调度器」四层切分，
  并明确三层参考仓库都缺的「麦麦大脑」是必须新写的核心
- **代码实现**：从零写出可运行工程，91 项离线测试
- **真实联调与纠错**：用真实 Token 逐工具校正参数名与返回结构，修复算价静默返回 0、
  下单缺 `takeWayCode`、营养表解析失败等实际缺陷
- **安全与合规**：凭证只走环境变量 + 输出脱敏 + 占位值拦截 + 下单护栏，
  并在合规检查中主动提示许可证风险

## 4. 关键提示词（可复现）

```
调研一下这几个项目，我想直接复用这些底层，但是要换一身麦当劳主题的服装
<三个参考仓库地址>
```

```
<麦当劳 MCP Token>
```

```
你不能去申请一下吗        # → WorkBuddy 说明 MCP Token 需手机号短信验证且会创建真实会员账户，
                          #   超出其权限范围，改为打开登录页 + 写好一键配置脚本
```

## 5. 声明

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
完整声明见 [`CONTEST_DECLARATION.md`](./CONTEST_DECLARATION.md)。
