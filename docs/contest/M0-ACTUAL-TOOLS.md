# M0：实际工具清单与功能映射表

采样日期：2026-10-14。沿用本机已配置的测试凭证，分别通过 Streamable HTTP 完成初始化和 `tools/list`。麦当劳 **35 项**，瑞幸 **8 项**，认证和工具发现均 PASS。本次业务工具调用数为 **0**，没有领券、创建订单、撤单或扣减积分。

下表的“读取/写入”是客户端根据业务效果采用的分类；不是服务端 annotations 的实测结论。必填字段来自这次工具 schema，业务流程还须检查餐品、规格、门店、预算与明确确认，不能因 schema 未声明某字段就省略订单内容。接口存在不等于该业务已验收。

## 麦当劳

服务：`https://mcp.mcd.cn`。表中的“—”表示 schema 未声明必填参数。

| 实际工具名 | 功能映射 | 业务类别 | schema 必填字段 |
|---|---|---|---|
| `campaign-calendar` | P0 活动日历 | 读取 | — |
| `available-coupons` | P0 可领券展示；计划缓存 10 分钟 | 读取 | — |
| `query-my-coupons` | P0 已有券；P1 点餐比价 | 读取 | — |
| `auto-bind-coupons` | P0 用户确认后领券、庆祝/气泡 | 写入 | — |
| `now-time-info` | 时间信息；饭点调度仍用本机时钟 | 读取 | — |
| `query-nearby-stores` | P0/P1 查询并核对门店 | 读取 | `beType, searchType` |
| `query-meals` | P1 门店菜单 | 读取 | `storeCode, orderType, beType` |
| `query-meal-detail` | P1 餐品详情/规格 | 读取 | `storeCode, orderType, beType, code` |
| `query-store-coupons` | P1 门店可用券 | 读取 | `orderType, beType, storeCode` |
| `query-promotions` | P1 门店促销 | 读取 | `storeCode, orderType, beType` |
| `calculate-price` | P1 下单前实付比价与复核 | 读取 | `storeCode, orderType, beType` |
| `create-order` | P1 确认后生成订单及品牌渠道入口 | 写入 | `storeCode, orderType, beType` |
| `query-order` | P1 只查已知订单状态 | 读取 | `orderId` |
| `cancel-order` | 核对具体订单后撤单；不自动执行 | 写入 | `orderId, cancelReasonCode` |
| `list-nutrition-foods` | P1 饮食记录营养数据来源 | 读取 | — |
| `delivery-query-addresses` | 配送地址；仅用户选择配送时使用 | 读取 | — |
| `delivery-query-stores` | 配送可用门店 | 读取 | `beType, addressId` |
| `delivery-create-address` | 地址写入；本期不纳入 | 写入 | `address, addressDetail, city, contactName, phone` |
| `query-meal-assistance` | 企业团餐助餐服务；本期不纳入 | 读取 | `storeCode` |
| `order-list` | 用户主动查看历史订单；默认不读取 | 读取 | — |
| `query-survey-coupon` | 已知订单答卷/关联券信息；本期不纳入 | 读取 | `orderId` |
| `query-my-account` | 积分账户；不是模型余额 | 读取 | — |
| `mall-points-products` | 积分商品；本期不纳入 | 读取 | — |
| `mall-product-detail` | 积分商品详情；本期不纳入 | 读取 | `spuId` |
| `mall-create-order` | 积分兑换订单；本期不纳入 | 写入 | `skuId, spuCategory` |
| `mall-order-list` | 积分商品历史订单；本期不纳入 | 读取 | — |
| `mall-order-detail` | 积分商品订单详情；本期不纳入 | 读取 | `orderId` |
| `query-party-city` | 派对活动城市；本期不纳入 | 读取 | `spuId` |
| `query-party-store` | 派对门店；本期不纳入 | 读取 | `code` |
| `query-party-store-date` | 派对可约日期；本期不纳入 | 读取 | `spuId, storeCode` |
| `query-party-store-session` | 派对场次；本期不纳入 | 读取 | `spuId, storeCode, dateStr` |
| `party-order-create` | 派对订单；本期不纳入 | 写入 | `partyType` |
| `query-lottery-info` | 抽奖规则/资源；本期不纳入 | 读取 | — |
| `query-my-prizes` | 奖品记录；本期不纳入 | 读取 | — |
| `draw-lottery` | 扣减次数或积分抽奖；本期不纳入 | 写入 | — |

名称修正：参考名称 `campaign-calender` 实际为 `campaign-calendar`；`my-coupons` 实际为 `query-my-coupons`。营养、菜单、算价及订单接口均存在，后续采用实测名字与实时 schema。

## 瑞幸

服务：`https://gwmcp.lkcoffee.com/order/user/mcp`。

| 实际工具名 | P1 功能映射 | 业务类别 | schema 必填字段 |
|---|---|---|---|
| `queryShopList` | 按用户给定位置查店 | 读取 | `longitude, latitude` |
| `searchProductForMcp` | 在已选店搜商品 | 读取 | `deptId, query` |
| `queryProductDetailInfo` | 商品及规格 | 读取 | `deptId, productId` |
| `switchProduct` | 切换规格后重新核价 | 读取 | `deptId, productId, skuCode, attrOperationParam, amount` |
| `previewOrder` | 实付预览；核对券及商品 | 读取 | `deptId, productList` |
| `createOrder` | 确认后生成订单/跳转品牌渠道 | 写入 | `deptId, productList, longitude, latitude` |
| `queryOrderDetailInfo` | 已知订单状态/取餐信息 | 读取 | `orderId` |
| `cancelOrder` | 核对具体订单后撤单 | 写入 | `orderId` |

参考名称 `quickOrder/confirmOrder/orderStatus/searchProduct/findShop` 未出现在此次清单里，不按这些名字开发。券匹配是否由预览结果提供，须在 M3 真实业务验收，不能把返回字段存在称作已完成优惠功能。

## 验证边界

- 采样使用现有 Python 客户端，是复用当前配置完成的接口发现；不是 Tauri/TypeScript 客户端验收。
- 往期已在同一 MCP 连接准备过荟聚的两份报价；仅为准备成功，未创建订单或验证付款入口，过期报价不复用。
- M0 未读取个人订单、收货资料或模型余额。本次发现的完整 schema 留在仓库外测试目录；公开文档只记录工具名、必填字段、计数和功能映射。
- DeepSeek 的余额文档确认 `GET /user/balance` 与 `balance_infos` 结构；本次未携带模型 Key 请求余额。[接口说明](https://api-docs.deepseek.com/api/get-user-balance/)

阶段计划、差距及下一阶段验收见 [M0 报告](M0-REPORT.md)。
