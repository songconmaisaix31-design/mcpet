# 轨 A：画面与本机宠物行为交接

日期：2026-10-11。唯一 Worker，在 `C:/Users/DW/orca/workspaces/mcpet/mcpet-pet-20261011` 完成；未派发其他 Agent，未做集成。

- 分支：`songconmaisaix31-design/mcpet-pet-20261011`
- 起点：`6109eab4a767ec7a8ef46a7b0580aa538e381327`（包含 PLAN，产品基线为 `48014681c10dabfecff0104fdb0676f271e21f09`）。
- 实现及测试 Commit：`c339cd042a200792cf0f2f6380b5f05165bebc64`。
- 本文单独提交；交接文档 Commit 可通过 `git log -1 --format=%H -- docs/companion/HANDOFF-A.md` 查到。集成请普通 merge 整条分支。
- 修改仅在 PLAN 的 A write_paths 内：五个 pet 文件、四个测试文件、bench_render、本文。未改 main/dialogs/config/runtime/素材。

## 已完成

保留 PySide6、完整 atlas 单元和原有 80ms 默认间隔。修复构造后透明占位覆盖真实首帧；按图集行、帧数、尺寸、DPR 复用缩放帧，working/progress 等同一行别名保留帧号和计时相位。循环直接从最后帧返回首帧；延迟回调按 monotonic 时差追上播放相位。跨屏 DPR 重建固定缩放帧但不重启同一行相位。未知素材继续透明兜底，没有生成或改写素材。

基态由后台 `set_activity` 更新，前台 oneshot 保留独立截止时间。拒绝的低优先事件和重复事件均不延长 TTL，通知到期恢复最新基态。后台 waiting 后续可以变为 working；显式 `set_state('waiting')` 等确认保持到显式 clear。后台刷新不修改触摸气泡、不重置同一动画；上下文为 None/非有限/越界时明确未知，不生成百分比。控件预留固定 42 个逻辑像素，显隐不移动角色画布。

单击等待系统双击判断窗口后触摸反馈并发出 clicked；双击只发出 chat_requested；超过 Qt 拖拽距离才移动，拖拽释放不触发点击。跑动方向反转需离当前方向极值达到 8 个逻辑像素，连续真实反向 1px 移动可以累积，交替 1px 噪声不翻状态。

本机闲逛以时间差和小数位置累积按 28 逻辑像素/秒移动，随机行走/短休息；拖拽、气泡、菜单、前台事件、后台工作与主动休息时暂停。恢复保留行为阶段；长停顿最多补 100ms 移动，避免唤醒瞬移。主动休息结束回到最新活动状态，没有模型/MCP/账号调用。

位置及 roaming/resting 原子保存到 `$MCPET_DATA_DIR/pet-preferences.json`，默认 `~/.mcpet/pet-preferences.json`，独立于台账与凭证。记录屏幕名和 availableGeometry，重启按当前屏幕恢复并夹紧；支持负坐标、多屏、任务栏保留区、屏幕消失和逻辑 DPI。移动保存防抖，释放/偏好切换/关闭立即保存；损坏文件退回默认，IO 错误保存在 `_preferences.error`。气泡同样按所在可用屏幕夹紧。菜单 QAction 归 QMenu 所有，exec 返回后 deleteLater，回归断言重复菜单无残留。隐藏暂停播放/移动；关闭停止定时器、关闭气泡、解除屏幕信号。

## 素材与参考核对

本地参考 HEAD 实查：CeTaPet `d0725b0`，LLMPET `55f55f3`。读取 CeTaPet 原拖拽/暂停恢复/位置代码，以及 LLMPET shared/states.js；未搬用其单状态 PNG 播放器。longniang 远端不可达，本轨没有声称读取其播放器，也没有再尝试联网。

QImage alpha > 32 的实测边缘范围（原 atlas 1536×2288、8×11、192×208；所有声明使用帧非空）：

| 行 | 横中心范围 px | 底部范围 px |
|---|---:|---:|
| idle | 0.5 | 0（底部均 202） |
| running-right | 0.5 | 3 |
| running-left | 0.5 | 0 |
| waving | 0 | 0 |
| jumping | 0.5 | 46 |
| failed | 0.5 | 0 |
| waiting | 0.5 | 0 |
| running | 0.5 | 0 |
| review | 0.5 | 2 |
| look-row-9 | 8 | 0 |
| look-row-10 | 10 | 0 |

锚点总体稳定；look 行为视角旋转，jumping 为有意跳跃。没有逐帧裁边、居中、放大或校正。`SpriteSheet.anchor_bounds` 仅用于离线核查/bench，正常播放不运行像素扫描。

## 接口与 C/B 轨需要接线的事项

```python
pet.chat_requested.connect(open_chat)  # 无参数，仅发信号
pet.set_activity(state, context_percent=None, label='')
pet.set_roaming(True)
pet.set_resting(False)
pet.roaming_enabled  # bool，可读
pet.resting          # bool，可读
```

- `set_activity` 的百分比为真实 0..100，0 是有效值；未知传 None。在 GUI 线程调用。它只更新基态和控件，不能代替完成证据；只有明确完成事件才应触发 happy。
- 保留 `clicked/menu_requested/set_state/say/say_state/set_spritesheet` 兼容接口。`clicked` 现在是确认单击后的通知，内部已经展示触摸反馈。
- **C 域问题，未越界修复**：当前 main.py 仍 `window.move(1200, 700)`，会覆盖恢复位置；请删除该固定定位。当前 `clicked.connect(on_click)` 会用营养台账气泡覆盖触摸；请移到明确营养菜单操作，并连接 chat_requested 到异步聊天入口。为菜单/托盘增加闲逛与休息开关并读取两个布尔属性。
- **C/B 域接线**：周期巡检用 set_activity，不能每轮 say/say_state 或用 set_state 刷新后台状态。需要一次性错误/完成反馈时用 set_state；显式等待结束可 `pet.machine.clear('waiting')` 后调用 set_activity 刷新。如使用旧接口执行 thinking，再 set_state('idle')，仍受优先级保护，应由 C 明确结束对应状态，而非后台轮询强制覆盖前台。
- A 没有访问用户 Agent 日志、请求模型/MCP、读取 .env、执行账号写操作。运行时冷扫描与联网阻塞仍由 B/C 解决，窗口播放器无法消除 GUI 线程被其他模块长期占用造成的卡顿。

## 验证、首轮失败与最终结果

解释器固定为 `C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`。所有运行显式使用 TEMP 下独立 MCPET_DATA_DIR；没有使用用户台账。

```powershell
$petPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$env:MCPET_DATA_DIR = Join-Path $env:TEMP 'mcpet-A-final4-20261011'
$env:QT_QPA_PLATFORM = 'windows'
$env:PYTHONIOENCODING = 'utf-8'
& $petPython -m pytest -q
& $petPython -m compileall -q src/pet/window.py src/pet/states.py src/pet/spritesheet.py src/pet/behavior.py src/pet/preferences.py scripts/bench_render.py
git diff --check
$env:MCPET_DATA_DIR = Join-Path $env:TEMP 'mcpet-A-release-bench-20261011'
& $petPython scripts/bench_render.py 10
```

- 基线完整 pytest：200 passed / 4.44s。基线真实 Windows 5s bench：62 帧、12.4fps、平均 80.0ms、0 卡顿。计时本来已稳定，不能把帧率提高当作问题修复。
- 首轮新增 RED：4 failed / 23 passed。保留失败名称：`test_lower_priority_event_does_not_extend_notification`、`test_repeated_notification_does_not_renew_ttl`（均 tick 返回 None）、`test_constructor_keeps_real_first_frame`（透明 180×180 覆盖真实首帧）、`test_alias_change_keeps_animation_phase`（预期 2 实际 0）。修复后定向 32 passed。
- 行为回归首轮：1 failed / 49 passed，并有 11 条首次 screenChanged disconnect 的 RuntimeWarning。失败是浮点 `2.8000000000000003 <= 2.8`；改为合理 approx 断言。屏幕连接改为记录实际连接句柄，消除无连接时 disconnect 警告。
- 最终完整 pytest：**225 passed / 6.35s，无 skip、无 warning，exit 0**。涵盖真实 Qt 单击/双击/拖拽、噪声与真反向、后台与 TTL 恢复、上下文未知/0、固定控件锚点、定时移动/休息、位置重启、负坐标/任务栏、菜单销毁、DPR 固定缩放和相位、循环、延迟播放、原 atlas 锚点/跳跃。
- compileall、git diff --check：exit 0。
- 最终实现 Commit 上真实 Windows 10s bench：**DPR 1.5；124 帧、12.4fps（99%）、平均 80.0ms、中位 80.0ms、78.8..81.3ms、标准差 0.5ms、0 卡顿，exit 0**。120 次实际 Qt mouseMove + 1px 反向 + 后台活动更新：均值 0.23ms/事件，8/8 动画帧，状态切换仅 `['run-right']`，释放后等待双击间隔仍 0 clicked。
- Qt 窗口自身截图（未捕获其他桌面内容）在 TEMP/mcpet-A-visual-20261011/pet-render.png：已查看角色和上下文 37% 可见，画布逻辑坐标 (0,42)、窗口 180×222、DPR 1.5。首次截图目录尚未建立，save 无输出文件；创建目录后重拍。即时抓图还遇到一张未完成角色绘制的截图；运行 Qt 事件循环 200ms 后重新抓图确认角色可见，且单独 canvas PNG 有真实帧。自动首帧回归断言的是 canvas pixmap 内容，不等同于用户主观观感验收。

## 真实剩余限制 / 未执行操作

- 轨 A 的独立窗口、完整本分支测试和真实 Windows bench 已通过；**没有运行三轨集成后的应用，没有宣称开发陪伴/日常陪伴/麦当劳助手整体完成**。
- 实机使用现有 Windows 屏幕/DPR 1.5；负坐标、多屏断联、尺寸变化由坐标回归覆盖，尚未人工拔插物理显示器或现场更改 DPI、游戏全屏、远程桌面、长时间休眠/压力场景验收。
- 日常闲逛/主动休息使用现有动画别名：sleeping 复用 idle，没有专用睡觉素材。长期闲逛观感仍需用户接受；没有新增久坐提醒或修改素材授权声明。
- bench 测 Qt 回调时序与实际窗口/鼠标事件，不能测量显示器逐帧呈现或等同主观观感。它有明确 windows 平台门槛，offscreen 直接 exit 2。
- 偏好写入失败当前可通过 `_preferences.error` 查看，没有跨域增加应用提示。偏好屏幕名由 Qt/Windows 提供，不保证系统重编号后的物理屏幕身份。
- C 接线、B/C 后台性能与联网行为、账户操作及真人验收由主 Agent/相应 Worker 后续处理。本轨不启动任何网络验证或账号写操作。

本文提交后按授权普通 push 本分支；可核对 `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/songconmaisaix31-design/mcpet-pet-20261011`。完成即停止，不执行 merge、发布或集成。
