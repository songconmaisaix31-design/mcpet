# 鲸鲸的 GIF 小相册

运行 `python scripts/record_deepseek_gifs.py --export <分类文件夹>`，完整录制本机项目中 DeepSeek 娘的两套皮肤与所有已装载动作。离线工具需要现有桌面依赖和 Pillow（`python -m pip install Pillow`）；Agent 读取 GIF 不依赖 Pillow 或 Qt。

项目素材输出到本目录；`index.json`、`index.html` 和 GIF 是可再生成的本机文件，不提交，不放入发行包。默认套装来自 [固定版 DSH 素材](../dsh-deepseek/SOURCE.md)，额外炸薯条和双向换装来自用户导入的视频；早期 `ceta_*` 来自 [CeTaPet 本机姿态包](../cetapet/SOURCE.md)。权利边界沿用 [素材来源](../CREDITS.md)，没有下载其他角色或更多仓库动作。

录制取同一 AnimationSheet 与 ScaledAnimationFrames 的显示帧，保留镜像方向、完整循环、生产帧间隔与首帧停留。192×192 是原尺寸；512×512 是 Qt 平滑放大显示版，不能补出原画细节。GIF 量化为共用调色板，最多 255 个可见颜色和一个透明色，alpha 小于 128 的像素透明；PNG 图集不修改。相邻相同帧可以合并停留时间，不缩短动作。

九种早期姿态是单帧 GIF，标记为静态；别名和麦麦套装复用待机的状态均在索引标明。完整录制一个周期，循环 GIF 包括单向换装的重新起播边界；不伪造不存在的过渡或工装动作。

`mcpet://recordings/deepseek` 读取全部清单；`mcpet://recording/deepseek/{skin}/{action}/{size}` 读取 GIF，size 为 192 或 512。现有动作工具的返回也带 `recording` URI；普通默认套装动作在相册装载后可直接返回 GIF。宿主是否播放取决于图像资源支持；相册缺失时维持既有入口。
