# 麦麦新增动作验证（2026-10-12）

范围：仅用户提供的炸薯条与换装视频接入。单 Agent 完成，保留 Python/PySide6 技术栈、
既有角色与其他动作，未启动其他开发轨。基线 `8737bced4b0ca18a22697696982a96cae5bd9bf5`；
功能提交 `0c93a91e4252778822c59d7de810218876206a00`。
分支 `codex/maimai-video-actions-20261012`。

## 结果

- 每段 127 张 192×192 透明帧；每段 11 页，复用既有分页播放器。
- 炸薯条循环/停止、换装一次结束、最新后台状态恢复、通知 TTL 不被延长、
  休息/触摸/切角色取消、角色限制、小窝与真实 QAction 接线均有测试。
- 逐帧检查两个新动作的透明角落、非空内容、固定尺寸、循环回首帧；
  逐像素确认原麦麦所有图集状态与静态预览保持原样。
- Windows 原生 Qt 定时器实测：炸薯条播放并停止；换装经过全部 11 页，
  约 10.168 秒后恢复 `working`，`errors=[]`，每次最多驻留一个分页。
  这是实际原生窗口播放证据，不代表 Windows 前台焦点或人工观感验收。

## 命令与保留的结果

Python：`C:/Users/DW/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe`，
PySide6 6.12.0。测试用独立临时 `MCPET_DATA_DIR`，不读取项目 .env 或真实账号。
以下命令的 `python` 表示该解释器，转换脚本使用已有 Pillow/numpy/OpenCV 的本机 Python。

```powershell
python -m pytest -q tests/test_maimai_actions.py tests/test_characters.py tests/test_spritesheet.py tests/test_dual_pet_render.py tests/test_window_render.py tests/test_pet_behavior.py tests/test_states.py tests/test_companion_panel.py tests/test_dialogs.py tests/test_quota_panel.py tests/test_app_actions.py tests/test_main_startup.py
python .tmp-test-data/video-actions/native_playback.py
python -m compileall -q src scripts/import_maimai_actions.py
git diff --check
```

- 最终定向回归：**155 passed / 2 failed，46.62s**。新增的 8 个用例全部通过。
- 原生播放探针：**通过**，日志 `native-playback.log`，截图 `native-fries.png` / `native-outfit.png`。
- 编译与差异检查：**通过**。
- 首轮原角色回归 **87 passed / 1 failed**：麦麦补充图集被当作纯分页图集加载，
  原 transactional-switch 测试失败。已修为仅新动作使用分页，原帧路径保持原行为。
- 下一轮 **94 passed / 1 failed**：共享临时目录遗留角色偏好影响 placeholder 测试；
  后续每轮使用全新临时数据目录，保留第一次结果，不修改该测试断言。
- 首次扩大回归 `targeted-tests.log`：**152 passed / 5 failed**；
  静态预览及无 meta 夹具兼容性已修正，新增应用测试按真实素材和真实 activity 方法设置。
- 修正中间结果 `targeted-retest.log`：**154 passed / 3 failed**；最后修正应用测试
  原共享夹具替换的 activity 方法，最终结果保留于 `final-regression.log`。

日志、原生播放脚本与转换预览位于本机 `.tmp-test-data/video-actions/`，未加入 Git。
首失败不被后续通过覆盖。

## 剩余边界

最终两项失败均未删断言、skip 或修改门槛：

1. `test_small_panel_scrolls_without_clipping_quota_and_settings[560]`：offscreen 下要求
   560px 页面必须有纵向滚动条。对功能提交父版本的隔离 `git archive` 运行同一用例，
   **同样失败（0.59s）**，记录于 `baseline-size-test.log`。
2. `test_native_four_entries_restore_foreground_and_focused_keyboard_input`：原生前台
   句柄与面板不一致，Qt active/focus/input 可用。该失败已在既有
   `docs/companion/PIXSO-QUOTA-DUAL-PET-PLAN.md` 与 C Handoff 记录，仍保留 RED。

未运行整个仓库的完整测试、联合 monitor 性能验收、真实账号/MCP/模型路径或人工验收。
既有 heartbeat RED 仍未解决。本次未发布安装包、合并到 main 或重启用户常驻应用。
启动项目当前分支后在小窝或右键菜单选择动作即可。

原 MP4 无 alpha，抠图边缘/半透明光效为近似；两个新动作与原麦麦占位图集存在形象差异。
换装视频实际约 10 秒，本次未自行剪成文件名中的 1–2 秒。详见
`assets/maimai-actions/SOURCE.md`。

## 合并启动前的接线补验

用户要求合并并启动后，检查真实入口发现 `MonsterApp._load_sheet` 仍直接加载原图集，
首次启动的默认麦麦不能加载新增动作；此前单独角色加载/播放测试没有覆盖此入口。
现已改为复用 `load_character("maimai")`，新增真实默认加载器回归。

```powershell
python -m pytest -q tests/test_maimai_actions.py tests/test_main_startup.py tests/test_companion_panel.py tests/test_dual_pet_render.py
```

结果 **39 passed / 17.80s**；`compileall -q src` 与 `git diff --check` 通过。
该定向结果不覆盖前文两项既有失败或替代完整项目验收。
