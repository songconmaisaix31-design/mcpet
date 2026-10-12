# 宠物菜单与瑞幸验证

## 核心路径

2026-10-13，Python 3.13 / PySide6 6.12，隔离数据、明确 fixture 日志来源、无真实账号写入。

```powershell
python -m pytest tests/test_deepseek_skins.py tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py tests/test_pet_behavior.py tests/test_settings.py tests/test_app_actions.py tests/test_quota_panel.py tests/test_luckin.py tests/test_pet_menu.py tests/test_skill.py -q
python -m compileall -q src scripts tests
git diff --check
```

结果：**426 passed / 40.02s**；编译与 diff 检查通过。源代码完成后执行，包含新的订单状态自动查询、跨宿主金额/次数护栏、两个支付来源独立、菜单与气泡、取消/退出、皮肤与原素材、旧麦当劳业务。

真实 stdio 验证：默认入口与绝对启动器 initialize → 21 工具 → 调用 → 7 资源 → prompt → EOF；通用配置接入无宿主品牌配置改写。新进程不导入 Qt 或旧 LLM。瑞幸账号业务仍为离线 fixture。

瑞幸 fixture 检查：官方 URL/Bearer/session、无自动重试、实时 schema 失败前拒绝、元转分、真实选择、预览 SKU/数量匹配、明确确认、报价/账号/规格/优惠/时效变化拒绝、共享日限额、未知提交/撤单消费并持久化、重启禁止重复发送。

Qt 检查：实际 QMenu / QAction / 气泡按钮与输入，取消不写、密钥输入遮蔽并清空、不覆盖待确认内容、不创建 QDialog/CompanionPanel；自动查单状态不变时不重复气泡。

## 保留的失败与限制

- 第一轮：8 failed / 50 passed；旧面板断言、工具数量和 LLM 导入边界失败。修正模型导入，旧布局断言依据最新产品形态替换，保留原日志。
- 第二轮：2 failed / 78 passed；刷新报告断言时机与启动导入耗时问题。保留原日志；延迟 JSON Schema 库导入后启动回归通过。
- 第一次后台菜单迁移验证：9 failed / 8 passed；发现旧回调覆盖新处理、金额被身份证规则误遮蔽、报告缺少过时/样本不足标识、旧 native 探针依赖面板。修复实际代码和探针呈现入口；保留首失败。
- Windows 联合验证：17 passed / 1 failed；**max_tick_gap_ms=385.04，原要求 <150ms，仍 RED**。恢复入口改为宠物，心跳/退出阈值没有放宽。独立原生退出与子进程回收检查通过，不能抵消该 RED。
- 原有 DeepSeek 素材严格边距/缓存断言的历史 RED 未在本轮修改；完整全套不是本次通过结论。
- 官方无凭证 initialize：HTTP 401。瑞幸认证账号、真实下单、撤单、支付和人工取餐验收 **NOT_RUN**。

原始日志在本机 `.tmp-test-data/luckin-menu/`，只提交聚合记录。用户 Token、日志原文、个人台账与本机宿主路径不入 Git。

Windows 可见菜单/气泡：已启动正式 `--desktop` 入口（保留当前角色、皮肤和位置）。原生截图/树确认 9 个根菜单操作项、5 项设置分组；点击“查看设置”后实际读取气泡中的饭点、咖啡时间与凭证配置状态，没有 CompanionPanel。气泡为 260 逻辑像素（当前 1.5 DPR 下 390 像素），保留长报告滚动。

原生菜单与气泡 JSON/截图在同目录；输入遮蔽/清空/取消经过真实 Qt 控件验证，本轮没有向 Windows UI 输入真实 Token。不能把这些结果算作 Windows 前台性能或真实账号人工验收。

初次暂存 diff 检查发现新验证模块的 EOF 空行，未更改业务代码；追加格式修复后，整个分支相对父主分支的 `git diff --check` 通过。历史提交与首失败日志均保留。
