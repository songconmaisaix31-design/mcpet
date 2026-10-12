# 常驻容器移除与角色名称补齐（2026-10-13）

用户要求：删除桌宠上方常驻容器，将原麦麦角色改名为 ChatGPT 娘。单 Agent 在既有 Python/Qt 目录完成。

- 删除 PetWindow 的活动标签、上下文进度条及 42 逻辑像素占位；窗口与精灵画布同尺寸。
- 后台活动仍更新动画基础状态，不覆盖触摸动作、临时气泡或待确认交互。详细进度继续在右键菜单和原 Agent 中查看，未知上下文与 0% 的业务区分保持不变。
- 角色名称复用既有共享映射，补齐兼容面板初始化及旧聊天/CLI 的残留称呼。旧配置角色 ID `maimai` 继续显示 ChatGPT 娘；DeepSeek 的 `maimai` 皮肤仍叫麦麦套装，皮肤随时可切。
- 历史集成测试对已删除控件的读取改为核对真实进度快照；性能阈值、历史失败记录不变。

## 验证

```powershell
python -m pytest tests/test_first_release.py tests/test_pet_behavior.py tests/test_dual_pet_render.py tests/test_pet_menu.py tests/test_companion_panel.py tests/test_app_actions.py tests/test_quota_panel.py tests/test_deepseek_skins.py tests/test_main_startup.py tests/test_progress.py tests/test_chat.py tests/test_characters.py::test_shared_character_contract -q
python -m compileall -q src scripts tests
git diff --check
```

- 适用回归 **136 passed / 23.09 秒**，记录 `pet-cleanup-first.log`；编译及 diff 检查通过。仅运行角色资产的共享名称契约，未把历史素材边界失败算作通过。
- 隔离目录下实际创建两角色的旧 CompanionPanel，名称均与共享映射相同；`pet-cleanup-legacy-labels.log`。生产菜单仍不创建大面板。
- Windows 原生：原常驻实例经退出菜单正常结束，再启动修改后的源码桌宠；只检查本进程窗口。相同位置、DPR 1.5 下窗口从 270×333 变成 **270×270**，树与画面均无常驻状态文字；当前 DeepSeek/default 和已保存位置保持。实际右键“角色与动作”显示 **ChatGPT 娘** 与独立 **麦麦套装**。新实例 stderr 为 0 字节。
- 原生读回记录 `pet-cleanup-old-state.json`、`pet-cleanup-new-state.json`、`pet-cleanup-character-menu.json` 在忽略目录中。操作工具的调用结果与实际窗口读回分别判断，不以未断言的输入事件代替验收。

本次未重跑历史原生联合性能、完整测试或真实账号操作；既有 heartbeat/cold-show RED 与素材边界 RED 未解决。公开 v0.1.0 标签及发行包不覆盖，本次更新源码与当前运行实例。
