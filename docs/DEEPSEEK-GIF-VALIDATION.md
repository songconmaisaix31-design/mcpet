# 鲸鲸全部动作 GIF 录制验收

2026-10-14。分支 `codex/deepseek-gif-recording-20261014`。SOURCE：`44f15ca08430e03fbe1d57be8b01b4b478f9a363`。

## 完成内容

按用户最新“录制 GIF，将 DeepSeek 娘所有动作录制”，以项目当前两套皮肤的真实 AnimationSheet 为清单。每套 28 个动作名称，共 56 项；每项原尺寸 192×192 与平滑放大 512×512 各一份，共 **112 个透明 GIF**。去重后是 **15 段独立动画与 9 张早期静态姿态**，不是 56 种独立动画。

完整包含默认待机、向左/右跑、忙碌、思考、挥手、庆祝、叹气、睡觉、吃饭、炸薯条、双向换装、业务别名与九个 `ceta_*` 姿态。麦麦套装没有独立跑步等动作的状态复用穿装待机，向右状态取其镜像；索引和资源返回明确标注。没有制造缺失动作。

本机项目 `assets/deepseek-recordings/` 含 GIF、清单和网页预览。桌面“DeepSeek娘GIF动作全集”按默认套装/麦麦套装，再按中文动作名分类，附“打开动作预览.html”、动作索引、来源与许可证。此前九张 PNG 的分类文件夹保留。

现有 Agent 动作返回增加 `recording`，普通默认套装动作现在可返回 GIF URI；原 PNG/换装 URI 保留。新增 `mcpet://recordings/deepseek` 清单和 `mcpet://recording/deepseek/{skin}/{action}/{size}` 只读资源，大小为 192/512。不增加产品界面、不更改当前用户的套装、不调用餐饮或模型账号。

录制代码、读取代码、技能说明与素材来源入 Git；实际 GIF、清单与本机网页被忽略，既有发行清单不带这些文件。Pillow 只加入桌面开发/测试依赖；Agent 最小依赖不增加 Pillow/Qt。

## 如何验证

- `python -X utf8 scripts/record_deepseek_gifs.py --export <桌面分类文件夹>`：成功导出 56 项 / 112 文件。重跑成功，桌面已有 GIF 与重录结果逐字节相同；不同内容的用户文件会拒绝覆盖。
- `python -X utf8 -m pytest tests/test_deepseek_recordings.py tests/test_agent_host.py tests/test_deepseek_skins.py tests/test_cetapet_actions.py tests/test_agent_skill.py -q`：首轮 **53 PASS / 38.48 秒**；增加 Agent 不导入 Qt/Pillow 的验证后，**54 PASS / 50.89 秒**。
- 补齐麦麦套装复用/镜像的元数据后，`python -X utf8 -m pytest tests/test_deepseek_recordings.py -q`：**6 PASS / 7.88 秒**。其他实现未改，未把此项称作全项目回归。
- 实际素材审计：两套动作清单与运行加载器完全匹配；112 个桌面/项目 GIF 逐字节相同；48 个去重尺寸文件解码成功，时长、循环和透明一致；**2912 个实际源帧的透明阈值轮廓与 GIF 解码帧精确相同**，原片顺序与停留时间保留，静态姿态不称动画。GIF 相邻相同帧合并时仍保留全部时间。
- 独立的真实 stdio 进程：读取完整实际清单与 **112/112 GIF**，mimeType 正确、解码后逐字节相同；隔离数据下调用 idle 的返回包含新 GIF URI。没有操作个人台账。
- Qt/Pillow 导出并非前台录屏。另目视检查默认待机、双向跑、庆祝、工装待机、薯条、换装与早期余额姿态的代表帧；不据此宣称所有宿主已经播放。
- `python -X utf8 -m compileall -q src scripts tests` 与 `git diff --check`：PASS。Git 忽略检查确认实际 GIF/index 不入提交；发行排除测试通过。

本机首轮及完成证据保存在 `.tmp-test-data/deepseek-gif-*.log`，实际审计工具也在同一忽略目录；不提交宿主绝对路径或任何凭证。

## 已知问题与未执行

1. 工具准备阶段发现 Pillow 未安装；配置的镜像安装首次报 `No matching distribution found`，改用 PyPI 安装 Pillow 12.3.0 后完成导出。保留初始工具不可用与安装失败记录，不当作产品测试通过。
2. 原动画画布是 192×192；512 是放大显示版，早期原 PNG 甚至小于该画布。没有把放大称作新增原生高清。GIF 上限为 255 个可见颜色和一个透明色，半透明阈值为 128；原 RGBA 图集不修改。
3. 单向换装 GIF 循环时会从终点重新起播，这是该动作本身的边界，不承诺无缝衔接。麦麦套装的缺失独立动作仍复用待机。
4. 原宿主若已启动旧 MCP 进程，需要重载服务才能发现新资源；宿主是否内联播放 GIF 尚待用户现场确认。未执行 Windows foreground 屏幕捕获、全项目测试或旧 GUI/heartbeat 性能验收；历史 RED 保留。
5. 新要求已按当前项目动作执行，本次不再等待旧高清来源选择。没有导入后期仓库的更多动作，没有发起收费生成，也没有渲染宣传视频完整 MP4；后续宣传片仍保留样板画风确认步骤。
