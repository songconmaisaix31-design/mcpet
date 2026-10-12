# ChatGPT 龙娘待机节奏（2026-10-13）

用户反馈 ChatGPT 娘“抽抽”。本机偏好及原生画面确认当前为白紫龙娘，代码角色 ID 为 `maimai`，
动作 idle、闲逛关闭。该角色沿用 `assets/longniang` 原图集；待机只有 6 帧，统一 80 ms
导致每 0.48 秒循环一次，眨眼与身体小幅姿态变化反复快速播放。
本轮处理这个可复现的待机节奏问题，不将其归因于用户误操作、素材损坏或前台权限。

单 Agent，分支 `codex/chatgpt-idle-cadence-20261013`。在原 `pet.json` 配置
待机帧间隔 160 ms、睁眼首帧额外停留 4000 ms，一轮为 4.96 秒。
播放器按帧截止时间保留停留；逾期只跳完整周期并定位当前帧，不快速补播。
同一视觉行的重复状态/别名刷新保留相位和截止时间，切跑动或动作立即使用其原时序。
切角色时比较停留配置，防止把长停留带到其他角色；环境变量帧间隔覆盖仍生效。
原图集像素、固定画布、状态 TTL、动作帧数和 DeepSeek 两套皮肤均保留。
复用待机行的 sleeping/eating 同样使用此待机节奏，没有增加新睡眠或吃饭素材。

## 验证

新回归首轮 **2 failed / 1.16 秒**，证明原播放没有睁眼停留，日志
`.tmp-test-data/chatgpt-motion/timing-first-red.log` 保留。修复后同项 **2 passed / 0.50 秒**。
覆盖实际原图集、眨眼帧续接、循环长停留、别名/后台刷新、延迟 20 周期后定位，
以及立即播放动作、切角色和环境变量覆盖。

适用回归命令：

```powershell
python -m pytest tests/test_deepseek_skins.py tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py tests/test_app_actions.py tests/test_pet_behavior.py tests/test_spritesheet.py tests/test_runtime_monitor.py -q
python -m compileall -q src scripts tests
git diff --check
```

回归 **375 passed / 59.17 秒**；编译与差异检查通过。
日志 `regression-first.log`。独立运行生产 PetWindow 的实际 Qt offscreen 定时器：
首帧停留到 4.164 秒，后续帧分别在 4.328 / 4.481 / 4.644 / 4.809 秒，
4.962 秒回到首帧；数据 `qt-live-cadence.json`。
这是实际 Qt 定时证据，独立于注入时钟的合同测试与 Windows 原生画面。

通过菜单退出旧桌宠后两个已知 PID 均消失；保留当前角色、皮肤选择及位置启动最新桌宠。
GUI 退出的工具后状态为 app_not_found，效果按进程读回记录，未标为工具 verified。
桌面进程使用空日志源及占位业务/模型凭证，不改用户配置，也不运行订单或模型调用。
新生产桌宠子进程 PID 33060，捕获白紫龙娘待机原生画面并目视检查，
证据 `native-after.json`，stderr 为空。文档本地相对链接检查 2 个文件、21 个链接，0 个缺失。
旧性能/foreground/heartbeat RED 及此前默认角色两个基线素材测试 RED 保留，
本轮不代表完整测试或所有类型的抖动均已解决。
