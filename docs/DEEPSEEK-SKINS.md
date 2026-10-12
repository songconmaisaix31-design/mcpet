# DeepSeek 娘动作与可切换皮肤（2026-10-12）

事实源：用户要求两段视频做进桌宠、作为 DeepSeek 娘动作；麦麦套装为持久皮肤，
与默认套装可随时切换；视频剪成适合动作的长度。基线 main / 25845e0。
单 Agent、分支 codex/deepseek-actions-skins-20261012，复用 Python/Qt/MCP 和已有透明素材。

1. 保留原视频及旧导入页；另导出 DeepSeek 专用的短炸薯条循环、换装/反向换装、穿装待机。
2. 皮肤与动作分开保存：default / maimai 可立即切换；换装完成保存目标皮肤，重启恢复。
3. 原 Agent 的 mcpet_pet 增加可选皮肤参数，旧 URI 保留，提供新的 DeepSeek 动作资源。
4. 桌宠菜单和既有面板提供两套皮肤切换，切皮肤中止动作且不改角色身份。
5. 测试皮肤持久化、转场结束、随时中断、资源与计时；原生桌宠实际演示后提交并推送。

假设：炸薯条素材已经穿麦麦套装，启动该动作时穿此皮肤；停止后保留皮肤，可随时切回默认。
麦麦皮肤没有独立跑动/睡眠素材，这些逻辑状态复用穿装待机，保持服装；默认皮肤完整原动作保留。
转场只使用原视频已有画面，反向播放用于脱下麦麦套装，不生成新人物画面。
旧 GUI/foreground/heartbeat RED 与本轮动作验收分别记录，不执行真实订单或模型调用。

## 使用

在原 Agent 里说“DeepSeek 娘穿麦麦套装”“切回默认套装”“换装一次”“炸薯条循环”。
对应 `mcpet_pet` 的 `character_id="deepseek"`、`skin_id="maimai"` / `"default"`；
`action="outfit"` 正放/倒放切换到另一套，`action="frying", loop=true` 穿麦麦套装循环。
皮肤选择没有有效期；短动作结束不会把穿好的麦麦套装改回默认。

原生播放使用显式 `python -m src.main --desktop`；右键菜单和既有面板提供两套皮肤。
已运行的桌宠每秒检查自身偏好中的新 Agent 指令，不探测宿主进程、对话或其他文件。
MCP 默认不启动 Qt 窗口，服务仍兼容任意 stdio 宿主。

## 裁切与资源

- 炸薯条原片 7.68–10.08 秒：透明分页/GIF 30 帧，2.40 秒。
- 换装原片 0.48–4.32 秒：正/反各 48 帧，3.84 秒；移除长尾待机/转身。
- 麦麦皮肤待机取原片 4.64–5.68 秒，并增加 4 秒睁眼停留：63 帧，5.04 秒循环。
- 原视频和旧导入保留。所有新帧使用同一缩放与落点，靠近既有 DeepSeek 默认身高/脚底。
  无逐帧适配、合成中间帧或新人物生成；循环端点择近，不保证数学上完全无缝。
- 目录内 MP4 为有原背景、无音轨的短审看片；24 fps 编码后 2.42 / 3.88 秒。
  桌宠使用 12.5 fps 的透明页/GIF。详见 [动作来源](../assets/deepseek-actions/SOURCE.md)。

## 验证

第一组动作、皮肤、真实 stdio 和旧角色回归 **54 passed / 28.29 秒**。
首轮整组 **322 passed / 1 failed / 51.79 秒**：旧面板测试仍断言 DeepSeek 没有炸薯条按钮。
按新需求改为验证 DeepSeek 动作可用、两套皮肤按钮切换与实际 27 帧播放；保留原网络禁止断言。
首日志 `.tmp-test-data/deepseek-skins-full-regression.log` 保留。
同项与新皮肤测试 **8 passed / 3.11 秒**；整组重跑 **323 passed / 47.07 秒**，
日志 `deepseek-skins-panel-retest.log` / `deepseek-skins-full-regression-retest.log`。

完整适用命令见 [贡献指南](../CONTRIBUTING.md)，本轮增加了 `tests/test_deepseek_skins.py`。
另运行 `python -m pytest tests/test_app_actions.py tests/test_pet_behavior.py tests/test_spritesheet.py tests/test_runtime_monitor.py -q`，
结果 **49 passed / 11.11 秒**，日志 `.tmp-test-data/deepseek-skins-desktop-regression.log`。
`python -m compileall -q src scripts tests` 和 `git diff --check` 通过。

原生演示使用生产 `src.main --desktop`、隔离演示偏好与显式空日志源，未提供业务/模型凭证。
初次记录启动器 PID 10604 无可见窗口，定位其子进程 PID 49936 后捕获真实桌宠：
默认皮肤 → 炸薯条麦麦皮肤 → 带光环的反向换装 → 默认套装，画面已目视检查。
两张炸薯条截图只比较所有帧共同不透明的桌宠区域，17708 像素变化，排除了背景文字变化。
原生右键菜单显示两个套装和两个动作；选择麦麦套装后偏好读回 `skin_id=maimai`、`action=idle`。
截图/状态/偏好位于 `.tmp-test-data/deepseek-native-demo/`；不是浏览器预览或 QTest 替代原生画面。
GUI 操作工具报告未断言，以上菜单效果按偏好读回记录，不标作工具 verified。
菜单退出后旧窗口 selector 短暂不可用；重列窗口恢复。续跑时演示进程已关闭，偏好仍为麦麦套装。
保留该偏好再次启动生产桌宠（子进程 PID 32928），实际恢复麦麦套装并捕获
`maimai-restarted.png` / `maimai-restarted.json`，证明本机进程重启恢复，不只依赖 fixture。

补充覆盖桌宠位置保存发生在新 Agent 指令到达后、轮询前的情况：保存位置必须保留尚未读取的
皮肤/动作指令，不能清掉它。最终合并验证增加这一项，与桌面补充回归一起运行共 373 项。
首轮 **372 passed / 1 failed / 30.65 秒**：原额度测试把毫秒转秒的浮点值严格相等比较，
相差约 0.00000024 秒；未修改额度实现或该断言，日志 `deepseek-skins-final-regression.log` 保留。
同项原样重跑 **1 passed / 0.11 秒**；完整 20 文件原样重跑 **373 passed / 26.61 秒**，
日志 `deepseek-skins-clock-retest.log` / `deepseek-skins-final-regression-retest.log`。
最终命令（项目运行环境 Python）：

```powershell
python -m pytest tests/test_deepseek_skins.py tests/test_agent_host.py tests/test_brain.py tests/test_guards.py tests/test_client.py tests/test_ledger.py tests/test_agentbridge.py tests/test_progress.py tests/test_metering.py tests/test_account_balances.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py tests/test_maimai_actions.py tests/test_schedule.py tests/test_config.py tests/test_app_actions.py tests/test_pet_behavior.py tests/test_spritesheet.py tests/test_runtime_monitor.py -q
```

文档本地相对链接检查：44 个文件、91 个链接，0 个缺失。

交付启动使用默认本机桌宠偏好目录，设为 DeepSeek 娘 / 麦麦套装，仍可随时选默认套装；
与默认启动的 MCP 服务共享皮肤/动作指令。启动时空日志源及空业务/模型凭证仅作用于该进程，
不修改用户凭证或宿主配置。隔离演示进程已通过菜单退出，两个已知 PID 随后均不存在。
退出动作的工具后状态返回 app_not_found，进程退出效果按 PID 读回记录。
合并后默认偏好启动的桌宠子进程 PID 39852 实际显示麦麦套装。用同一 AgentService 发炸薯条循环、
切默认套装、正向换装，逐项捕获原生画面并目视检查；最后读回 `skin_id=maimai`、`action=idle`、
无待完成皮肤，进程仍在运行且 stderr 为空。证据为演示目录 `delivery-*.json` / `delivery-stderr.log`。
真实 stdio 工具调用由上述测试单独验证；本机服务指令演示不等于特定宿主会话已重新加载 MCP。

GIF 实际编码时长分别 2160 / 3840 / 3840 ms，炸薯条 loop=0，两个换装无 loop。
真实 stdio 验证新参数及四个新资源、默认依赖仍不导入 Qt/独立模型。
业务回归仅离线 fixture；未执行真实订单、模型会话或宿主终端内图像播放验收。
本轮不代表旧 GUI/foreground/heartbeat RED 已修复；麦麦皮肤缺少独立跑动/睡眠等姿势是素材限制。

## 2026-10-13 裁切返修

用户反馈待机末尾泡泡/转头及原炸薯条段瑕疵。单 Agent 在
`codex/deepseek-clip-fix-20261013` 重选片段；当前资源时长以上述“裁切与资源”为准，
2026-10-12 验证记录保留其当时的帧数和时长。
待机只保留源帧 58–70 的正面眨眼（4.64–5.68 秒），不包含前缘转场残留或后段动作；
炸薯条使用源帧 96–125（7.68–10.08 秒），避开早期放篮段瑕疵，保留稳定提篮后的轻微动作。
选用帧已全部逐帧目视检查；两套皮肤选择/持久化、完整换装及旧导入不变。
重新导出透明分页、GIF、待机预览及炸薯条短 MP4，并同步 MCP 时长和现有帧数断言。

验证沿用上方完整 20 文件命令：首轮 **373 passed / 39.56 秒**，
日志 `.tmp-test-data/deepseek-clip-fix/regression-first.log`。`compileall` 与 `git diff --check` 通过；
本次检查 37 个文档、83 个相对链接，0 个缺失。
逐帧比较新 PNG 与指定源帧的固定缩放结果全部相同；实际 GIF 分别为 30 / 13 帧、2400 / 1040 ms，
均循环，审看 MP4 编码后 2.42 秒，证据 `asset-verification.json`。
通过菜单退出旧桌宠后两个已知 PID 均消失（工具后状态 app_not_found 不作工具 verified）；
原偏好和位置保持，再启动生产桌宠，实际子进程 PID 43844。
捕获新的正面眨眼、后段提篮画面，目视检查通过；通用 AgentService 下发循环后停止，
读回仍是 DeepSeek 娘 / 麦麦皮肤 / idle，stderr 为空。证据 `native-idle.json` / `native-frying.json`。
这次重启只刷新桌宠；已运行的旧 MCP 服务需要重载才能刷新其内存中的时长。
后段提篮动作幅度小于原放篮段；旧 GUI/foreground/heartbeat RED 未重测，不代表已修复。

## 2026-10-13 待机节奏

根据用户要求拉长待机、减少眨眼，单 Agent 在 `codex/maimai-idle-pacing-20261013`
给麦麦套装的干净睁眼首帧增加 4 秒停留（50 个 80 ms 帧），之后原样播放 13 帧眨眼。
待机变为 63 帧、5.04 秒循环，约每 5 秒眨眼一次；眨眼本身速度保持 80 ms/帧。
GIF 会合并相同画面，实际编码为首帧 4080 ms、其余 12 帧各 80 ms，总长同为 5040 ms。
离线逐帧比较确认所有停留帧等于原睁眼首帧、眨眼 13 帧像素不变；证据
`.tmp-test-data/maimai-idle-pacing/asset-verification.json`。

验证命令：

```powershell
python -m pytest tests/test_deepseek_skins.py tests/test_maimai_actions.py tests/test_dual_pet_render.py tests/test_companion_panel.py tests/test_agent_host.py tests/test_main_startup.py tests/test_spritesheet.py tests/test_characters.py -q
python -m compileall -q src scripts tests
git diff --check
```

首轮 **87 passed / 2 failed / 28.83 秒**，日志 `regression-first.log` 保留。
两个失败来自 `test_characters.py`：默认角色的所有动画都按原图集边缘约束检查，
以及假定所有页来自 `dsh-deepseek`、只在外层缓存的像素比较。
在修改前 `a0ff665` 的 `git archive` 副本中原样运行同两项，**2 failed / 1.99 秒**，
同一断言复现；见 `baseline-failures.log`。默认角色素材、角色加载/分页实现和这两个测试
均未修改，不放宽或跳过断言；本轮不能标成 89 项全通过或完整测试通过。
编译与差异检查通过。

通过旧桌宠菜单退出后两个已知 PID 均消失；保持原偏好/位置重启生产桌宠，
新子进程 PID 15892，实际画面为麦麦套装正面待机，读回资源时长 5.04 秒、动作 idle。
截图 `native-idle.json`，stderr 为空；运行仍使用原 Agent 共用的偏好，空日志源/占位凭证
仅作用于此次桌面进程。原生画面检查不代替精确周期测量；周期依据实际分页/GIF 的帧数和时间。
已运行的旧 MCP 服务仍需重载时长；历史性能 RED 保留。
