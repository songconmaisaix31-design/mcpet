# DeepSeek 娘：固定来源与离线转换

来源：[PC2005-cloud/dsh-pet](https://github.com/PC2005-cloud/dsh-pet)，固定提交
`92662190cdd4dee05e38a5151584cc6254cd7a43`，上游 MIT 许可证原文见 [LICENSE](LICENSE)。
只复用 `dsh-pet/assets/webm/` 下 manifest.json 所列九个透明动画，不安装、运行或复制第三方宿主、聊天、模型、账号功能。未使用 GIF 预览作为动画来源。

原始 WebM 为 640×360、24fps、VP9/ALPHA_MODE=1；八段 241 帧，失败动作 118 帧。
`manifest.json` 保存各片段源文件名、SHA256、原帧数及 alpha>32 的首尾边界/底部与中心范围。
完整原帧 alpha 巡检没有空白帧，所有动作并集为 `[120,6,469,336]`。横中心范围包含头发、手和气泡等真实动作变化，不能把该值当作角色整体漂移自动抹平。

统一一次裁框 `x=111,y=0,width=366,height=360`，所有帧和动作均相同，保留边缘余量。
等比缩为 192×189 后透明填充到 192×192，固定锚点；不逐帧裁边、居中、放大、对齐脚底。
庆祝保留原生 36px 的跳跃，奔跑保留转身和运动。右跑仅镜像左跑，使用同一源动画和时长。
以 `fps=25/2` 等间隔采样，Qt 每帧 80ms；每个常规片段 126 帧（10.08秒），失败 61帧（4.88秒）。
保留源首尾帧和自然循环，不添加透明过渡；上游个别首尾姿势本来不同（尤其失败动作），没有通过逐帧矫正伪造无缝循环。

最初九份无损 WebP 图集共 21,392,334 字节（约20.4MiB），转换时逐像素核对过 alpha 和所有非透明 RGB。
组合性能实测发现必要整图解码超过150ms，于2026-10-12原A返修将原图逐行拆为94份无损 PNG：每页12列×1行（2304×192），另存同像素192×192首帧预览。全部1069个有效帧与原 WebP 完整像素相等，未再缩放、裁边、平移、改节奏或插值；原图先备份至本轮隔离证据目录再移除。
PNG 页共33,264,844字节（约31.7MiB），是磁盘体积换取较小的按需解码。运行时仍仅 PySide6；不分发原 WebM、FFmpeg 或另一宿主。每次只驻留一页（1,769,472像素字节）、一张静态预览（147,456字节），窗口最多两组动作索引、每组两张近期缩放帧。切换同步准备实际呈现相位页；后续分页在正常播放到达时解码，不预热其他动作，切角色释放旧缓存。

复现：从上述固定提交下载 manifest 中九个源文件到独立临时目录后，执行：

```powershell
python assets/dsh-deepseek/convert.py SOURCE_DIR FFMPEG_EXE
# 从本项目旧九份WebP缓存无损重打包（证据目录必须全新）：
python assets/dsh-deepseek/convert.py --repack NEW_EVIDENCE_DIR
```

本次使用 FFmpeg 9.0.2 essentials（Gyan，FFmpeg 官方下载页链接的 Windows 构建），临时目录内直接调用，不安装。
下载包：[ffmpeg-release-essentials.zip](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip)，SHA256
`60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba`；该 latest 链接可能更新，复现须核对版本与哈希。
强制 `-c:v libvpx-vp9` 解码 alpha。旧 FFmpeg 3.0.1 的首次试转丢失 alpha，未纳入任何缓存。
