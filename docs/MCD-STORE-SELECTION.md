# 指定麦当劳门店与真实报价验证（2026-10-13）

用户要在北京西红门荟聚验证麦当劳、瑞幸至付款入口，每家不超过 30 元，测试凭证留在仓库外。

首个真实发现：麦当劳旧报价入口只能选默认门店，返回中粮广场餐厅，与明确指定的荟聚不符。没有在错误门店创建订单。

单 Agent 在既有业务层修复：`mcpet_deals(keyword, store_keyword)` 新增可选门店名称/地址关键词。明确指定时直接查询到店门店，名称或地址必须匹配且营业状态已知为真；不采用其他默认门店、配送地址或无关的近店。未指定关键词时保持原解析路径。准备和确认继续绑定本会话真实报价，原有预算、过期、价格变化与未知提交护栏不变。

```powershell
python -m pytest tests/test_brain.py tests/test_agent_host.py tests/test_agent_skill.py tests/test_pet_menu.py tests/test_luckin.py -q
python -m compileall -q src scripts tests
git diff --check
```

- 回归 **122 passed / 31.04 秒**，含缓存默认门店不匹配、近店干扰、关闭/未知营业门店及写入护栏；编译和 diff 检查通过。
- 真实 MCP stdio：实时 schema 含 `store_keyword`，查询并准备荟聚三层门店的巨无霸 1 个/外带，实付 **26.50 元**。
- 同一 MCP 连接查询瑞幸荟聚食通天3F店商品并准备生椰拿铁 1 杯，大杯/冰/意式拼配/默认浓度/不另外加糖/无奶油，实付 **16.60 元**。
- 本记录截至订单摘要准备完成，两家状态均为 `needs_confirmation`。创建订单、实际付款页与支付尚未执行，不能把报价或接口认证称作支付链路通过。

凭证、原始服务数据与本机测试驱动保存在仓库外的隔离测试目录，不提交。适用回归与真实报价不代表历史完整桌面/性能 RED 已解决；发行包尚未更新。
