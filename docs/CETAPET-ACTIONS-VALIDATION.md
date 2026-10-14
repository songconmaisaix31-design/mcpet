# 早期鲸鲸姿态：仓库接入与桌面分类

日期：2026-10-14。分支：`codex/cetapet-actions-20261014`。

SOURCE：`66539b0bfcf17855c90787004f9822609f9adc23`。验收报告单独提交；推送结果见交付消息。

用户最终明确两项落点：动作装载进项目，全部动作按名字整理到桌面文件夹；随后追加“用高清动图”。本阶段已完成早期姿态的本地接入、分类导出与验证；高清连续动画尚待素材来源选择，不把静态 PNG 称作高清动图。

## 完成内容

- 经早期项目文档核对，来源为 `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek`，固定 `d0725b0e0aa58cd547c48b1681988ee708120d31`，不是后期 `dsh-pet` 的扩展素材集。
- 九项原始姿态全部导入：待机、吃饭、思考、被提起来、摸摸回应、余额告急、元气登场、成功、失败。原图、LICENSE、README 原样留存。
- `assets/cetapet/actions.json` 统一视频、桌宠与 Agent 的动作名称；本地原图和运行页分别位于 `assets/cetapet/original/`、`assets/cetapet/runtime/`。运行页沿用已有 AnimationSheet，原图不放大、不裁边，放入共用透明画布。
- 九个 `ceta_*` 动作已接到 `mcpet_pet`、PNG 资源模板、现有桌宠动作通道和右键“角色与动作 → 早期鲸鲸姿态”。单帧姿态保持到切换或停止；现有皮肤选择仍可切换。
- 桌面新建“DeepSeek娘动作（早期CeTaPet）”，九个中文子目录各含对应原始 PNG，附动作索引、LICENSE、原仓库说明。
- 视频有完整九宫格预览；余额样板使用 `nomoney`。Aliyun 语音保持现有合成结果，没有新增账号/餐饮调用。
- 按既有素材记录，原图、运行页与缓存不新增到 Git 或发行包；发行代码携带接入词表与说明。本地用户导入后可调用。

## 验证结果

- Python 适用回归：`python -X utf8 -m pytest tests/test_cetapet_actions.py tests/test_deepseek_skins.py tests/test_maimai_actions.py tests/test_agent_host.py tests/test_agent_skill.py tests/test_pet_menu.py tests/test_app_actions.py tests/test_pet_behavior.py tests/test_spritesheet.py -q`：**113 PASS / 59.86 秒**。
- 增加菜单回调、发行文件边界和半透明像素检查后，`python -X utf8 -m pytest tests/test_cetapet_actions.py -q`：**6 PASS / 21.41 秒**。此结果不是全项目测试或旧性能门槛验收。
- 新用例使用隔离的九姿态 fixture，覆盖完整导入/分类、Qt 页与显示、Agent 指令轮询、真实 stdio 的 schema/九个调用/九个 PNG 资源、菜单每项独立回调、发行清单排除本地图片。
- 实际早期素材另核对：9/9 桌面原图与仓库本地原图一致；9/9 运行页与共用画布的预期像素相同；9/9 Qt 显示帧与预期 QPixmap 相同。这是实际素材检查，不依赖 fixture 替代原图。
- 视频 `npm run prepare` / `npm test`：**9 PASS**；早期固定版本动作清单与 Git 树中的全部 PNG 路径一致，九图复制逐字节相同。
- 视频 `npm run lint` / `npm run build`：PASS；仅构建预览 bundle。
- Studio 九图、双角色与余额/气泡页面已加载并目视检查；未渲染 MP4，不代表人工画风与声音验收。
- `python -X utf8 -m compileall -q src scripts tests`、`git diff --check`：PASS。

## 保留的首次失败与未执行

1. 初次定位到了后期 `dsh-pet`；用户补充“早期参考”后，依据早期文档改用 CeTaPet。后期仓库一次素材元数据读取遇 GitHub 连接失败；该非目标拉取已停止，没有纳入本阶段导入。
2. 首次新 Python 用例 **3 PASS / 1 RED**：测试误写 `_check_agent_commands`，正确方法为 `_receive_agent_command`。修正方法名后，以上适用回归通过；未改动轮询实现来迎合测试。
3. 为先取得首轮结果，中止过一个并发启动的回归命令，属于 PARTIAL，不计作通过。后续单独命令的完整结果为上述 113 PASS。
4. 实际素材的首次比较把 Qt 预乘 alpha 显示格式直接与 PNG 直通 RGBA 比较，出现不相等。改为分别验证 PNG 页的完整 RGBA 与预期 PNG 画布、Qt 帧与预期 QPixmap；全部逐像素相等，没有加容差。测试补入半透明 fixture 覆盖该格式差异。
5. 首次网页检查遇旧 Studio 服务已停止的 `ERR_CONNECTION_REFUSED`；重启服务后九图及样板页面通过。
6. 首次导入的终端提示有编码乱码；文件夹中文名称、原图与索引验证正常。后续命令使用 `-X utf8`。

## 高清动图待办

CeTaPet 的早期固定版本只有九张静态 PNG。另已只读验证 `dsh-pet` 固定 `92662190cdd4dee05e38a5151584cc6254cd7a43` 的一个现成源动画：原生 **640×360、24 fps、VP9 alpha**，这不是原生 1080p。等待用户选择使用这套现成透明动画，或保留早期形象生成新动作。当前没有把 PNG 放大伪称高清，没有生成或装载新的高清 GIF，也没有发起收费视频生成。

未执行：新的高清动图装载、完整八段成片、原 Agent 宿主重新加载、用户本机前台桌宠操作验收、全项目回归与历史 GUI/heartbeat 性能门槛。以上未知边界保留。
