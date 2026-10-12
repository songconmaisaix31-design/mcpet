# 餐饮操作

只使用工具返回的门店、餐品、券、规格和订单编号。以下是 McPet 外层参数；瑞幸查询的 `arguments` 按官方实时 schema 校验，缺参数或校验错误时补齐用户选择，不猜测默认规格或坐标。

## 麦当劳

1. `mcpet_coupons()` 查可领券和已有券；要领取时说明“领取全部当前可领券”，已获明确确认再调用 `mcpet_claim_coupons(confirmed=true)`。
2. `mcpet_deals(keyword=用户需求)` 查询真实报价；使用其中的 `store` 和餐品/券字段。当前服务只接受本会话查询结果中的选择。
3. 用户选定方案后调用 `mcpet_prepare_order(product_codes, meal_names, store, coupon_id, coupon_code, coupon_name, take_way_code)`。没有券时券字段留空；取餐方式仅 `eat-in`（堂食）或 `take-in-store`（外带）。
4. 展示返回 `summary`：门店、餐品、券、取餐方式、实付金额。`amount_cents` 单位是分；如需自行格式化，用十进制除以 100。准备仅算价，不创建订单。
5. 用户确认后 `mcpet_confirm_order(confirmed=true)`；报价有效期 5 分钟，金额变化会重新要求确认。返回已知订单号与付款入口后在当前会话呈现，创建订单不等于已付款。
6. 撤单先核对用户选定的具体订单号及影响，已确认后 `mcpet_cancel_order(order_no=真实订单号, confirmed=true)`。

## 瑞幸

所有查询由 `mcpet_luckin_query(tool=官方工具名, arguments=参数对象)` 执行，只支持以下选择：

| tool | 用途与已知参数 |
|---|---|
| `queryShopList` | 根据用户指定的 `longitude` / `latitude` 查询门店 |
| `searchProductForMcp` | 选定真实 `deptId` 后用 `query` 搜商品 |
| `queryProductDetailInfo` | 查询真实商品的规格；沿用返回的门店/商品字段并遵守实时 schema |
| `switchProduct` | 选择规格；沿用实际商品/规格选择并遵守实时 schema |
| `previewOrder` | 只读预览；购买流程优先用外层 `mcpet_luckin_prepare` 冻结待确认摘要 |
| `queryOrderDetailInfo` | 用已知 `orderId` 查订单状态或取餐码 |

先选真实门店，再查该店商品和规格；没有位置时请求城市/门店所需的位置，不从日志或其他账号推断。`products` 中每项的 `productId`、`skuCode` 来自当前查询，`amount` 是杯数（1–10），不是金额。

调用 `mcpet_luckin_prepare(dept_id, products, longitude, latitude)`，展示返回的摘要、门店、商品规格、数量、实付；`amount_cents` 仍是分，上游瑞幸报价则是元，不混用单位。
待用户明确确认后 `mcpet_luckin_confirm(confirmed=true)`，最多提交一次。5 分钟过期、重新连接、价格或规格变化时重新预览并确认。
返回订单编号、取餐码或付款链接时按工具结果展示；支付由用户完成。查询订单仅用 `queryOrderDetailInfo`，不得通过下单尝试查状态。
撤单展示具体订单号及影响，已获确认后 `mcpet_luckin_cancel(order_id=真实订单号, confirmed=true)`。

## 统一结果处理

- `needs_confirmation`：显示当前摘要并等待确认，不自动补 `confirmed=true`。
- `expired`：重新准备并确认新摘要。
- `delivery_unknown`：保留已返回的编号/回执，停止重发；只读核对官方账号订单。没有编号也不能重新提交试探。
- `error` 或护栏拒绝：说明工具原因；不得替换账号、规避限额或运行其他创建订单入口。
- 已知创建成功：展示工具提供的编号/付款入口，区分创建、支付与完成；不伪造缺失字段。
