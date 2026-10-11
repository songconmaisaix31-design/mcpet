# A 双角色渲染交接（2026-10-12）

分支：`songconmaisaix31-design/mcpet-pet-20261011`。
起始工作树干净；fetch 后按授权 FF root 至计划 `067ceca814ca8e52e14ad39dd8dc472a32ee2b0a`，完整读取 PIXSO-QUOTA-DUAL-PET-PLAN 与旧交接。
只写计划 A 域；未修改主计划、main/dialogs/config/runtime、旧测试或 bench_render 脚本，未合其他轨、未集成。

代码提交：

- `a74cc21e911b43d54514b14ef04d0c79bb2eb2d5`：指定素材、双角色契约、切换与持久化、实际 Qt 回归。
- **`29a2ff1729959c970644e936f4edeb95f6e60659`**：根据原生连续动作探针 RED 改为按帧缩放、限制驻留内存，增加动作巡回回归。
- 本文为后续单独文档提交；最终推送 tip 由完成通知提供，可用 `git rev-parse HEAD` / `git ls-remote origin refs/heads/songconmaisaix31-design/mcpet-pet-20261011` 核对。请普通 merge 最终 tip，包含以上两个代码提交和本文；A 不合回 root。

## 完成与共享接口

```python
from src.pet.characters import CHARACTER_IDS, character_name, load_character
CHARACTER_IDS == ("maimai", "deepseek")
character_name("maimai")     # 麦麦
character_name("deepseek")   # DeepSeek 娘
sheet = load_character("deepseek")  # SpriteSheet 子类，frame/frames/row_for/frame_count 兼容
sheet.frame("idle", 0)             # 用于 C 面板预览和托盘图标
pet.character_id                  # 可读
pet.set_character("deepseek")     # GUI 线程；失败 SpriteLoadError，旧角色/帧/偏好不变
```

- maimai 继续用原 longniang 图集，不改原素材。DeepSeek 九个专用动作，包括睡眠与吃饭；右跑镜像左跑。未知动作回 idle；progress→working、remind→greet、coupon/balance/waiting→thinking、failed→error。
- 角色选择在本机 `MCPET_DATA_DIR/pet-preferences.json` 与 position/screen/available_geometry/roaming/resting 一并保存。旧偏好无 character_id 时兼容 maimai；现 main 传 maimai sheet 启动也能恢复 DeepSeek。恢复角色失败保留传入素材，可读 `_preferences.error`，未跨域加 UI 提示。
- 切换不调用状态机 set，不改基态/TTL/交互层、位置、休息、闲逛、上下文与触摸气泡；当前行相位按新旧帧数比例转换。同角色重复切换不重入、不续期；旧 set_spritesheet 同样只刷新呈现。
- 原拖拽阈值、1px 反向滞回、拖拽优先于前台事件、显式休息/唤醒、松手不点击、后台不覆盖触摸、过期回最新 Agent 基态、循环与时间差播放继续有效。chat_requested 仍只打开会话小窝，未创建聊天框或模型链路。
- 缩放/裁框固定，正常播放不扫描 alpha。DeepSeek 仅保留一个解码源图集；窗口最多两组动作索引、每组最多两张近期缩放帧，切角色清缓存。窗口内部 DeepSeek 帧集合是按索引访问的 Sequence；公开 sheet.frames(state) 仍返回标准列表。C 应用 load_character/单帧预览接口，不依赖私有窗口帧类型或 preview image 的图集布局。

## 素材、真实格式与限制

固定来源：[PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet/tree/92662190cdd4dee05e38a5151584cc6254cd7a43)，SHA `92662190cdd4dee05e38a5151584cc6254cd7a43`；上游 **MIT / Copyright (c) 2026 PC2005-cloud** 原文保留在 `assets/dsh-deepseek/LICENSE`，CREDITS 已更新。
只下载九个 `dsh-pet/assets/webm/` 透明动画，未安装、运行或复制宿主/聊天/模型。原始 640×360、VP9 alpha、24fps；完整原帧 alpha>32 没有空白帧，联合边界 `[120,6,469,336]`。

- 全动作统一裁框 `[111,0,366,360]`，等比 192×189 后固定透明补到 192×192；保留真实转身、姿势、气泡、吃饭和跳跃（原 happy 底部变化36px，转换后仍有跳跃）。中心范围包含手发和特效，不据此逐帧居中。
- 统一采样12.5fps，每帧80ms；八段126帧/10.08秒，error61帧/4.88秒；相对原24fps做离线时间采样，不盲目提高播放 fps。
- 9 个无损 WebP 缓存共21,392,334字节（20.4MiB）。PNG→WebP 已逐像素核对所有 alpha 和非透明 RGB 一致，冗余 PNG 移除。每动画源文件名/哈希/原帧数/首尾边界保存在 manifest.json；固定工具/转换流程见 SOURCE.md、convert.py。
- 正常循环不经过占位或透明首帧。不改上游首尾姿势；error 首尾头部约12源像素差、eating底部约13源像素差是源动作差异，未插值或逐帧锚平伪造无缝。有些动作因此仍有源生首尾姿势变化，需要用户观感验收。

## 首 RED 与诊断（保留，不被 GREEN 覆盖）

1. **修改前全仓基线 RED：1 failed / 318 passed / 41.87s。** `tests/test_companion_integration.py::test_native_app_auto_monitor_gestures_single_writer_and_exit`：heartbeat_ticks=484、max_tick_gap_ms=150.04，要求 `<150`；auto_start/working/gestures/四入口恢复/110 tokens/单writer/stop_ms=5.23均通过。未放宽该测试、未修改其代码。
2. **新契约首 RED：1 collection error / 1.33s / exit1。** `tests/test_characters.py` 导入 src.pet.characters 时 ModuleNotFoundError；当时尚未实现新契约。
3. 初次转换诊断：上游配置误用 `dsh-pet/config.jsonc` 得404，修正为公开 `dsh-pet/assets/config.jsonc`；本机旧FFmpeg3.0.1输出PNG alpha全255，丢弃。使用临时FFmpeg9.0.2/libvpx-vp9正确解码，工具不入仓库、不成运行依赖。
4. 首轮适用61 passed / 18.88s，但638条 Qt QImage.mirrored 弃用警告；改为QTransform镜像，后续无警告。中间完整GREEN333/58.84s、334/60.94s不替代最终内存修复后的复验。
5. **扩展原生连续动作探针 RED：exit1。** `native_probe` 第212行断言 `_frames` 非空失败；随后首次原bench启动工具返回 `System.OutOfMemoryException`（未运行，不记通过）。当时整段126帧预缩放缓存占73,483,200字节，另有19,464,192字节源图集。这是本机观察到的内存/渲染失败，未审计其他用户进程，不能归因其负载。将缓存改为按帧缩放后，连续动作探针独立GREEN，新增真实Qt动作巡回与驻留回归。

## 最终验证（单列 GREEN）

所有测试固定 WorkBuddy Python。以下每次 run 使用不同的 TEMP 子目录，创建后显式设置 TEMP/TMP/MCPET_DATA_DIR；完整pytest加 --basetemp，数据、Qt窗口截图均不落用户台账。

```powershell
$petPython = 'C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe'
$runDir = 'C:/Users/DW/AppData/Local/Temp/mcpet-A-dual-lazy-full-20261012'
New-Item -ItemType Directory -Force "$runDir/temp" | Out-Null
$env:TEMP = "$runDir/temp"
$env:TMP = $env:TEMP
$env:MCPET_DATA_DIR = "$runDir/data"
$env:QT_QPA_PLATFORM = 'windows'
$env:PYTHONIOENCODING = 'utf-8'
& $petPython -m pytest -q --basetemp "$runDir/pytest"
& $petPython -m compileall -q src tests assets/dsh-deepseek/convert.py
git diff --check
# 适用测试：新建隔离runDir再执行
& $petPython -m pytest tests/test_characters.py tests/test_dual_pet_render.py tests/test_window_render.py tests/test_pet_behavior.py -q
# 双角色原生探针：新建隔离runDir再执行
$env:PYTHONPATH = (Get-Location).Path
& $petPython tests/test_dual_pet_render.py
# 保留原Windows基准：新建隔离runDir再执行
& $petPython scripts/bench_render.py 10
```

- **最终完整 pytest：335 passed / 55.18s / exit0，无 skip、无 warning**，包含原联合 heartbeat<150ms、stop<50ms 与单writer测试。最终代码之后仅写本文。
- **最终适用测试64 passed /15.96s /exit0，无警告**，runDir=`mcpet-A-dual-applicable-final-20261012`，包含全部原触摸/窗口回归及新角色/动作巡回回归。compileall src/tests/转换脚本、git diff --check 均exit0。内存修复首轮适用63 passed /15.57s为独立先前证据。
- **双角色原生探针：Windows / DPR1.5 / exit0**，runDir=`mcpet-A-dual-lazy-bench-20261012`。每角色5s：均63次回调/12.6fps、0卡顿；maimai平均80.00ms、78.87..81.25ms；DeepSeek平均79.88ms、72.95..81.16ms、标准差1.03ms。切换DeepSeek36.01ms；九动作冷加载17.34..35.98ms。
- 120次真实Qt拖拽+反向1px+后台刷新：maimai8帧、0.143ms/事件；DeepSeek11帧推进、0.428ms/事件；均仅run-right、释放等待双击窗口仍0 clicked，拖拽前greet未到期。
- DeepSeek实际驻留像素缓存：缩放1,166,400字节、源图集19,464,192字节，合计约19.7MiB；这是像素缓冲计数，**不是整个应用RSS或GPU开销**，动作解码切换仍有短暂新旧源共存峰值。最多四张缩放帧与一个源图集通过回归断言。
- 仅截取自己的Qt窗口，未抓桌面其他内容：`TEMP/mcpet-A-dual-lazy-bench-20261012/data/{maimai,deepseek}-native.png`。已查看这两份DPR1.5截图，两角色可见，DeepSeek截图含37%上下文；不能替代用户长期观感或C面板/Pixso验收。
- **原 `scripts/bench_render.py 10` 独立GREEN / exit0**，runDir=`mcpet-A-dual-original-bench2-20261012`：Windows/DPR1.5，124帧/12.4fps（目标达成99%），平均80.0ms、中位80.1ms、78.8..81.4ms、标准差0.5ms、0卡顿；120次拖拽0.16ms/事件、8/8帧推进、仅run-right、0 clicked。原atlas锚点仍稳定，jumping46px仍保留。

## 剩余限制与主轨操作

- 本分支只有A双角色功能；未合B/C，未做双角色额度组合验收、Pixso设计、真实余额/MCP/模型请求，不宣称产品整体完成。原唯一集成Worker普通merge最终A tip后验证C选择器、预览、托盘与重启接线。
- 原动画不同角色的画面占比与动作持续时间不同；没有扩大单帧或改形象。未知上下文继续显示未知，0为有效测量。
- 原生测试为本机Windows/DPR1.5，尚未人工切物理屏/DPI、游戏全屏/远程桌面/长期休眠；既有边界/多屏负坐标/锚点回归仍通过。计时器回调与缓存证明不等于显示器逐帧呈现或主观自然度。
- 加载检查全部文件头和几何、预解码当前动作；全动作像素由回归检查，不在GUI一次性全部解码。若安装后素材被删除/破坏，后续动作可能显示原有占位兜底；切换时失败保留旧角色。
- 未操作GUI49784/launcher38676/monitors23860/48728；未读.env、凭证、用户既有日志/ledger，未安装第三方宿主、未发模型/MCP账号网络请求。仅下载公开固定素材和临时转换工具。
- 完成commit+普通push，通知主terminal `term_0dcc55fd-ccc4-4567-be46-3d441ca0ec24` 后停止。通知采用 [orca-cli skill](C:/Users/DW/.agents/skills/orca-cli/SKILL.md) 的公开terminal send；receipt只说明输入accepted，不声称对方已集成。
