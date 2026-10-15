# McPet 竖屏实际操作录屏

2026-10-15，分支 `codex/bubble-demo-20261015`。客户端为单个 Codex Agent；桌面操作使用 `computer-use` 技能与 `orca computer`，角色控制复用真实 MCP stdio 服务。

## 交付

- 气泡使用连续的圆角背景，通知、文字、按钮和输入框采用统一样式；透明边角、短内容高度、滚动和拖动跟随均已检查。
- [发布文案](POST.md)采用用户提供的原文，附 `#用ai做出一点小成果`。
- 本机成片：`.tmp-test-data/bubble-demo/McPet-douyin-1080x1920.mp4`。
- 成片为 **1080×1920、9:16、25 fps、65.12 秒**，包含 H.264 视频、AAC 单声道语音和烧录字幕。
- 原始桌面录屏、分段语音、ASS / SRT 字幕及剪辑脚本保存在 `.tmp-test-data/bubble-demo/`，由既有忽略规则保护。

## 实际素材与语音

运行现有 `MonsterApp`，使用独立本机演示数据目录，窗口为真实 PySide6 桌宠、菜单、气泡与输入控件。桌宠显示尺寸为 420 个逻辑像素。屏幕区域实际捕获为 810×1440；剪辑时调整主体位置和尺寸，导出 1080×1920。背景标题、字幕与桌面录屏分别排版。

通过 `orca computer` 实际打开设置、输入并保存饭点 `12:00`、查询麦当劳优惠券、查看本机用量并滚动报告。优惠查询实际返回券中心 7 张、已有 4 张，保持只读。角色动作经真实 MCP `mcpet_pet` 设置，已运行桌宠读取实际偏好并播放炸薯条、默认动作及本机导入姿态。

成片采用真实录屏中的默认动作、用量报告、炸薯条和余额告急姿态。画面中的用量是本机日志台账，金额为现有计价规则的估算；其含义与报告文字一致。余额告急 `ceta_nomoney` 为原始单帧姿态。

阶跃星辰请求使用 `POST https://api.stepfun.com/v1/audio/speech`，模型 `step-tts-2`，音色 `elegantgentle-female`，语速 `1.05`，WAV / 24 kHz。语音经 FFmpeg `dynaudnorm` 调整音量后编码为 AAC。调用方式依据[阶跃星辰官方技能脚本](https://github.com/stepfun-ai/StepAudio-Skills/blob/main/skills/step-tts/scripts/tts.sh)。本轮密钥仅保存在本机忽略文件中。

## 验证

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_bubble_layout.py tests/test_pet_behavior.py tests/test_states.py tests/test_main_startup.py -q
# 49 passed

$env:QT_QPA_PLATFORM = 'windows'
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_bubble_layout.py -q
# 4 passed；真实 Windows Qt，150% DPI

.\.venv\Scripts\python.exe -X utf8 -m compileall -q src/pet/window.py tests/test_bubble_layout.py
git diff --check
```

四项气泡回归覆盖透明边角和连续背景、真实输入与取消、长短报告切换及滚动复位、移动宠物时保留滚动位置。

成片使用本机 FFmpeg / FFprobe 检查尺寸、编码与时长，完整解码通过；视频与音频时长均为 65.12 秒。已查看开头、报告、工装、余额告急和结尾画面，检查主体位置、字幕、气泡边缘和遮挡。

## 当前限制与未执行操作

- `tests/test_window_render.py` 的五项动画断言仍失败；修改前的 `1be6592` 在独立工作树中复现相同五项失败，结果为 19 passed / 5 failed。本轮通过范围为上述气泡、行为、状态与启动检查。
- 领券需要展示范围并取得确认。用户文案中的个人经历和赛事排名规则由用户提供；本轮没有核验历史余额、历史用餐或赛事规则。
- 当前饭点自动路径查询优惠券和报价；工装、炸薯条通过动作设置触发。
- 本轮执行只读优惠查询，未领取优惠券、创建订单、付款或记录实际饮食。
- 桌宠与姿态沿用原素材并放大显示；本轮没有新增原画。
- 视频保存在本机，未发布抖音、未提交比赛、未重建发行包。源代码通过本次分支交付，主分支合并另按授权执行。
