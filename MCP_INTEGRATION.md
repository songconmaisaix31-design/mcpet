# MCP 集成说明

## 1. 使用的 MCP Server

| 项 | 值 |
|---|---|
| Server | 麦当劳中国 MCP Server（`mcd-mcp`） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP（MCP `2025-06-18`） |
| 认证 | `Authorization: Bearer ${MCD_MCP_TOKEN}`，Token 只从环境变量读取 |
| 限流 | 600 次/分钟/Token；客户端再做 540 次/分钟滑动窗口 |
| 配置示例 | [`mcp-config.example.json`](./mcp-config.example.json)（仅环境变量占位符） |

## 2. 调用流程

```
启动 → 读 .env / 环境变量拿 Token
     → POST initialize（取 mcp-session-id 并回带）
     → POST notifications/initialized
     → tools/list（拿真实 inputSchema，用于校正参数名）
     → tools/call（按场景调具体工具）
```

本项目没有使用任何第三方 MCP SDK，协议层在
[`src/mcd_mcp/client.py`](./src/mcd_mcp/client.py) 里手写实现，覆盖：
session 回带、单条 JSON 响应与 SSE 流两种响应体、401 直接失败、429 退避重试。

## 3. 用到的 Tool 与业务价值

| Tool | 在麦麦小怪兽里做什么 | 是否有副作用 |
|---|---|---|
| `available-coupons` | 领券前先看今天有哪些券可领 | 只读 |
| `auto-bind-coupons` | 一键领全部麦麦省券 | **会真实领券** |
| `query-my-coupons` | 领完核对手上券的总数 | 只读 |
| `query-store-coupons` | 看当前门店可用券，用于挑最优组合 | 只读 |
| `query-meals` / `query-meal-detail` | 拉菜单、看套餐组成 | 只读 |
| `calculate-price` | 逐个餐品逐个券试算实付价，找出优惠最大的一单；同时提供下单所需的 `takeWayCode` | 只读 |
| `create-order` | 用户确认后真实下单，返回订单号与支付链接 | **会真实下单并产生支付** |
| `cancel-order` | 一键撤单 | **会真实撤单** |
| `list-nutrition-foods` | 查餐品营养数据，写入每日台账 | 只读 |
| `campaign-calendar` | 让大模型知道当下有哪些活动 | 只读 |
| `delivery-query-addresses` / `delivery-query-stores` | 推出默认门店，避免让用户手填门店号 | 只读 |
| `query-nearby-stores` | 无配送地址时按城市搜附近门店，优先挑营业中的 | 只读 |
| `now-time-info` | 对齐服务端时间 | 只读 |

核心业务价值：把「领券 → 比价 → 下单 → 记账」这条原本要在麦当劳 App 里点
七八次的链路，压缩成宠物托盘菜单里的三次点击，且每一次比价都是对真实券和真实
价格的穷举，不是拍脑袋推荐。

## 4. 验证状态（三分法，如实标注）

| 项目 | 状态 | 说明 |
|---|---|---|
| MCP 协议层（initialize / session / tools / SSE / 401 / 429） | **已验证** | 离线测试覆盖，见 `tests/test_client.py` |
| 精灵图切片与状态映射 | **已验证** | `tests/test_spritesheet.py`，用真实图集跑 |
| 调度器（准点 / 迟到补触发 / 跨天 / 宽限放弃） | **已验证** | `tests/test_schedule.py` |
| 下单护栏（金额上限 / 每日次数 / 审计 / 撤单） | **已验证** | `tests/test_guards.py` |
| 营养台账与脱敏 | **已验证** | `tests/test_ledger.py`、`tests/test_config.py` |
| 阶跃星辰接口（`/v1/models`、`/chat/completions`、工具调用解析、401、429） | **已验证** | 用真实 Key 调通，见 `tests/test_stepfun.py`（离线重放） |
| Skill 调度与写操作闸门 | **已验证** | `tests/test_skill.py`，断言「未确认前绝不真领券」 |
| 麦麦大脑解析层（券 / 菜单 / 算价 / 营养表） | **已验证** | `tests/test_brain.py`，样本取自真实返回 |
| **工具名与参数名** | **已验证** | 用真实 Token 跑 `python -m src.cli tools` 逐项核对，35 个工具全部对齐；完整 schema 见 [`docs/mcp-schemas.json`](./docs/mcp-schemas.json) |
| **真实调用返回结构** | **已验证** | 见下方「实测校正表」，`scripts/probe_raw.py` 可复现 |
| 真实领券（`auto-bind-coupons`） | **已验证** | 真实调用成功；无新券时返回 `code=499 暂无可领取的优惠券`（良性，非错误） |
| 真实比价（`calculate-price` 带券 / 不带券） | **已验证** | 冰美式 1190 分 → 990 分，与「9.9元中杯冰美式」券面一致 |
| 真实下单（`create-order`） | **已验证（演练模式）** | 全链路跑到提交前一步；`MCD_DRY_RUN=1` 时不落单 |

复现命令（需要真实 Token）：

```bash
python -m src.cli tools --dump      # 拉真实工具清单，逐项核对参数名
python scripts/probe_raw.py         # 打印各工具真实返回结构（只读）
python -m src.cli coupons           # 领券汇报（真实领券）
python -m src.cli deal              # 今天最划算的一单
python -m src.cli nutrition --keyword 巨无霸
python -m src.cli order             # 下单链路；默认只展示摘要，加 --yes 才落单
python -m src.cli ask "今天最划算的是哪个？"
```

## 4.1 实测校正表（2026-10-10 用真实 Token 抓取）

> 官方 README 只给了工具名与中文说明，**没有公开 inputSchema 字段表**。
> 下面每一条都是实测出来的，不是按命名惯例猜的。

### 参数名

| 我们原本以为 | 真实字段 | 影响 |
|---|---|---|
| `storeId` | **`storeCode`** | 所有门店类查询 |
| `mealCode` | **`productCode`** | 菜单 / 算价 / 下单 |
| `couponId` 放 calculate-price 顶层 | **放在每个 `items[]` 元素里** | 券不生效 |
| 只传 `couponId` | **`couponId` + `couponCode` 两个都要** | 否则报 600010 |
| — | 每个门店查询都要带 `beType` + `orderType` | 否则报参数缺失 |
| — | 到店(beType=1) **不传** `beCode` | 传了会报错 |
| — | `create-order` 在 `orderType=1` 时**必传 `takeWayCode`** | 否则下单失败 |

### 返回结构（data 字段的真实形状）

```
query-nearby-stores  → [{storeCode, storeName, address, distance,
                         businessStatus(bool), businessStartTime, businessEndTime, ...}]
                       ⚠ businessStatus=False 的门店调 query-meals 会报 600057，必须优先挑 True 的

query-meals          → {categories:[{name, meals:[{code, tags}]}],
                        meals:{productCode:{name, image, currentPrice,
                                           originalPrice, canWithOrder}}}
                       ⚠ currentPrice/originalPrice 是**元**的字符串（"33.5"），
                         与 calculate-price 的**分**单位不同

query-store-coupons  → [{title, couponId, couponCode, tradeDateTime,
                         products:[{productCode, productName}], promotionId}]
                       ⚠ products[].productCode 是「这张券能用在哪些餐品」的索引

query-my-coupons     → {coupons:[{id, code, title, discountInfo:{...}, ...}],
                        totalCount, currentPage, pageSize, totalPages}
                       ⚠ 字段名是 id/code/title，不是 couponId/couponCode/couponName

available-coupons    → [{couponName, couponImage, couponStatus, label}]
                       ⚠ couponStatus=HAVING_RECEIVE 表示已领，不算「可领」

calculate-price      → {productOriginalPrice, productPrice, originalPrice, discount,
                        price, productList:[{productCode, productName, quantity,
                        originalSubtotal, subtotal}], takeWayList:[{code,title}]}
                       ⚠ 单位是**分**：price=3350 即 33.50 元
                       ⚠ takeWayList[].code（eat-in / take-in-store）是 create-order 的必填入参

list-nutrition-foods → data 是**字符串**（不是 JSON！），自定义表格格式：
                       "[160]{productName,nutritionDescription,energyKj,energyKcal,
                        protein,fat,carbohydrate,sodium,calcium}:\n
                         猪柳麦满分,null,1288,308,16,16,24,781,213\n  ..."
                       解析器：brain.parse_nutrition_table()
```

### 响应壳

所有工具统一返回 `{success, code, message, datetime, traceId, data}`，
`src/mcd_mcp/client.py` 的 `ToolResult.unwrap()` 负责剥壳。
注意：**只剥壳，不折叠 `data` 本身**——`query-store-coupons` 的 data 就是一张券的
列表，长度恰好为 1 时若顺手折叠，调用方会拿到券对象而不是列表。

`success=false` 不一定是错误：`auto-bind-coupons` 在「没有新券可领」时返回
`code=499 / message=暂无可领取的优惠券`，业务上属于正常结束。


## 5. 大模型调度层（阶跃星辰 StepFun）

固定菜单之外，用户可以用自然语言直接提问。做法是**把 MCP 的工具清单交给大模型，
让它自己决定调哪个**，而不是把工具写死在分支里：

```
提问
 → tools/list（真实）转成 OpenAI function 定义（写操作默认剔除）
 → 阶跃星辰 step-3.5-flash 选工具
 → tools/call（真实）
 → 结果回灌模型，最多 6 步
 → 输出一句人话
```

接口：`https://api.stepfun.com/v1`，OpenAI 兼容，同样手写实现无 SDK 依赖
（[`src/llm/stepfun.py`](./src/llm/stepfun.py)）。

**写操作闸门**：`auto-bind-coupons` / `create-order` / `cancel-order` /
`mall-create-order` / `draw-lottery` 在 `src/mcd_mcp/skill.py` 里被标记为写工具。
默认不生成它们的 function 定义；即使模型要求调用，也会停下来返回
`pending_write` 交人工确认，不会自动执行。测试 `tests/test_skill.py` 对此有断言。

## 6. 真实调用的护栏

宠物会替你领券，但不会替你决定下单：

1. 下单前弹确认框，必须展示**门店 + 商品 + 实付金额**，且要勾选确认才能点「下单」；
2. 单笔金额上限、每日下单次数上限在 `src/mcd_mcp/guards.py`，超了直接拒绝；
3. 每次下单（含演练）都写本机审计台账 `~/.maimai-monster/order-audit.json`；
4. 托盘菜单常驻「撤销上一单」；
5. `MCD_DRY_RUN=true` 时仍真实调用算价与全部查询，只跳过 `create-order` 提交——
   这是真实链路的演练，不是 mock。

> 本项目会真实创建麦当劳订单并产生真实支付。请确认你愿意让宠物替你下单再启用。
