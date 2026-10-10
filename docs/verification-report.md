# 麦当劳 MCP 真实调用验证报告

- 生成时间：2026-10-10 22:34:01
- MCP Server：`https://mcp.mcd.cn`
- 结果：**7/7 项通过**
- 大模型：`step-3.5-flash`（阶跃星辰）

以下输出均已过脱敏（Token / 手机号 / 邮箱）。地址类信息需人工核对后再公开。

## 工具清单与参数名核对

退出码：`0`（通过）

```
真实工具数：35

参数名核对（assumed 是我们推测的字段名）：
  [OK ] query-my-coupons.page         实际字段：page, pageSize
  [OK ] query-my-coupons.pageSize     实际字段：page, pageSize
  [OK ] query-store-coupons.storeCode    实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-store-coupons.beType       实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-store-coupons.orderType    实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-store-coupons.beCode       实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-meals.storeCode    实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-meals.beType       实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-meals.orderType    实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-meals.beCode       实际字段：beCode, beType, orderType, reservationDate, storeCode
  [OK ] query-meal-detail.storeCode    实际字段：beCode, beType, code, orderType, reservationDate, storeCode
  [OK ] query-meal-detail.beType       实际字段：beCode, beType, code, orderType, reservationDate, storeCode
  [OK ] query-meal-detail.orderType    实际字段：beCode, beType, code, orderType, reservationDate, storeCode
  [OK ] query-meal-detail.beCode       实际字段：beCode, beType, code, orderType, reservationDate, storeCode
  [OK ] query-meal-detail.code         实际字段：beCode, beType, code, orderType, reservationDate, storeCode
  [OK ] calculate-price.storeCode    实际字段：beCode, beType, gmServiceCode, items, needTableware, orderType, reservationDate, storeCode, withOrder
  [OK ] calculate-price.beType       实际字段：beCode, beType, gmServiceCode, items, needTableware, orderType, reservationDate, storeCode, withOrder
  [OK ] calculate-price.orderType    实际字段：beCode, beType, gmServiceCode, items, needTableware, orderType, reservationDate, storeCode, withOrder
  [OK ] calculate-price.items        实际字段：beCode, beType, gmServiceCode, items, needTableware, orderType, reservationDate, storeCode, withOrder
  [OK ] calculate-price.beCode       实际字段：beCode, beType, gmServiceCode, items, needTableware, orderType, reservationDate, storeCode, withOrder
  [OK ] create-order.storeCode    实际字段：addressId, beCode, beType, gmServiceCode, items, needTableware, orderType, remark, reservationDate, storeCode, takeWayCode, withOrder
  [OK ] create-order.beType       实际字段：addressId, beCode, beType, gmServiceCode, items, needTableware, orderType, remark, reservationDate, storeCode, takeWayCode, withOrder
  [OK ] create-order.orderType    实际字段：addressId, beCode, beType, gmServiceCode, items, needTableware, orderType, remark, reservationDate, storeCode, takeWayCode, withOrder
  [OK ] create-order.items        实际字段：addressId, beCode, beType, gmServiceCode, items, needTableware, orderType, remark, reservationDate, storeCode, takeWayCode, withOrder
  [OK ] create-order.beCode       实际字段：addressId, beCode, beType, gmServiceCode, items, needTableware, orderType, remark, reservationDate, storeCode, takeWayCode, withOrder
  [OK ] create-order.takeWayCode  实际字段：addressId, beCode, beType, gmServiceCode, items, needTableware, orderType, remark, reservationDate, storeCode, takeWayCode, withOrder
  [OK ] cancel-order.orderId      实际字段：cancelReasonCode, orderId
  [OK ] cancel-order.cancelReasonCode 实际字段：cancelReasonCode, orderId
  [OK ] query-order.orderId      实际字段：orderId
  [OK ] query-nearby-stores.beType       实际字段：beType, city, keyword, searchType
  [OK ] query-nearby-stores.searchType   实际字段：beType, city, keyword, searchType
  [OK ] query-nearby-stores.city         实际字段：beType, city, keyword, searchType
  [OK ] query-nearby-stores.keyword      实际字段：beType, city, keyword, searchType
  [OK ] delivery-query-stores.addressId    实际字段：addressId, beType
  [OK ] delivery-query-stores.beType       实际字段：addressId, beType
```

## 服务端时间

退出码：`0`（通过）

```
# API Response Information

Below is the response from an API call. To help you understand the data, I've provided:

1. A detailed description of all fields in the response structure
2. The complete API response

## Response Structure

> Content-Type: application/json

- **data**: 服务器时间信息 (Type: object)
  - **data.date**: 日期字符串 (yyyy-MM-dd) (Type: string)
  - **data.datetime**: ISO格式日期时间 (Type: string)
  - **data.day**: 日期 (1-31) (Type: integer)
  - **data.dayOfWeek**: 星期几 (Type: string)
  - **data.formatted**: 格式化时间字符串 (yyyy-MM-dd HH:mm:ss) (Type: string)
  - **data.month**: 月份 (1-12) (Type: integer)
  - **data.offset**: 时区偏移量 (Type: string)
  - **data.timestamp**: 毫秒级时间戳 (Type: integer)
  - **data.timezone**: 时区ID (Type: string)
  - **data.utc**: UTC时间 (Type: string)
  - **data.year**: 年份 (Type: integer)

## Original Response

{"success":true,"code":200,"message":"请求成功","datetime":"2026-10-10 22:33:30","traceId":"ec260f9b80af2df754613e48f8c1e572","data":{"timestamp":1791642810916,"datetime":"2026-10-10T22:33:30.916","formatted":"2026-10-10 22:33:30","date":"2026-10-10","year":2026,"month":10,"day":10,"dayOfWeek":"SATURDAY","timezone":"GMT+08:00","offset":"+08:00","utc":"2026-10-10T14:33:30.916Z"}}
```

## 营养数据（含自定义表格解析）

退出码：`0`（通过）

```
共 1 条营养数据（本地过滤 keyword=巨无霸）
巨无霸: 513 kcal（2146 kJ）| 蛋白 27.0 g | 脂肪 26.0 g | 碳水 42.0 g | 钠 961 mg | 钙 171 mg
```

## 领券汇报（会真实领券）

退出码：`0`（通过）

```
券中心可见：6 张（其中未领 0 张）
一键领取：暂无可领取的优惠券
本次新领：0 张
手上共：5 张
  · 9.9元中杯冰美式
  · 巧克力味厚松饼猪柳蛋套餐
  · 人气麦旋风买一送一
  · 巧克力味厚松饼猪柳蛋套餐
  · 巧克力味厚松饼猪柳蛋套餐
```

## 今天最划算的一单（真实比价）

退出码：`0`（通过）

```
门店：麦当劳北京雅宝路餐厅 (1950973) beType=1 营业中=True 距离=1155m
1. 麦咖啡™美式 减 2.00 元（原价 11.90 → 实付 9.90）  [券：9.9元中杯冰美式]
2. 【美汁源】“黄金橙橙” 暂无可用券（13.00 元）  [券：无可用券]
3. 纯牛奶(盒装) 暂无可用券（10.50 元）  [券：无可用券]
4. 纯悦 暂无可用券（7.50 元）  [券：无可用券]
5. 100% 苹果汁(盒装) 暂无可用券（11.50 元）  [券：无可用券]
6. 雪碧 暂无可用券（9.50 元）  [券：无可用券]
7. 培根蔬萃双层牛堡 暂无可用券（24.50 元）  [券：无可用券]
8. 巨无霸 暂无可用券（25.50 元）  [券：无可用券]
```

## 下单链路（演练：不落单）

退出码：`0`（通过）

```
门店：麦当劳北京雅宝路餐厅 (1950973) beType=1
最优：麦咖啡™美式 减 2.00 元（原价 11.90 → 实付 9.90）
     券：9.9元中杯冰美式（couponId=264B97DBE02BE6CF996AA6914151C4A9）
取餐方式：堂食(eat-in)、外带(take-in-store)

门店：麦当劳北京雅宝路餐厅
取餐方式：外带
商品：麦咖啡™美式
用券：9.9元中杯冰美式
实付：9.90 元

状态：needs_confirmation
（未落单。加 --yes 才会真正提交 create-order）
```

## Skill：让模型自己调工具

退出码：`0`（通过）

```
· 调用 campaign-calendar {}
[已调用] campaign-calendar → ### 当前时间：2026-10-10 22:33:56

### 活动列表：


#### 2026年10月7日 往期回顾




-   **活动标题**：超值𝟗.𝟗元早餐两件套陪你开工啦😋
    **活动内容介绍**：早八的快乐，一堡一咖已就位🍔☕
𝟏𝟎月𝟖日至𝟏𝟎月𝟐𝟏日
🍔周一至周五早餐堡轮流上早班
🤩今天这堡 明天那堡
☕鲜萃咖啡搭档到位
凭券两件套只要9.9元
速戳👇快定好闹钟一起

回答： 今天最划算的来啦！🎉

**11.9元蘸酱炸鸡** 是今天单点最划算的～韩式烟熏芝士风味酱配炸鸡，香到跺脚！

还有 **15.9元鸡薯双全盒** 也很值，鸡块+薯条+韩式辣椒黄油酱，GD同款花式比心get～

对了，今天还有 **麦金喜抽奖**，用积分就能抽免费汉堡（龙焰鸡腿堡/麦辣鸡腿堡），运气好的话直接白嫖最划算！要不要我帮你看看怎么抽？
```
