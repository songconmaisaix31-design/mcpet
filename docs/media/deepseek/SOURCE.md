# README 动作展示来源

本目录按用户要求，从用户提供的「DeepSeek娘GIF动作全集」分类文件夹复制 GIF，用于 README 展示。保留原尺寸 192×192 的文件字节、透明、帧顺序和停留时间；页面设置显示宽度，图片未重新编码。

去掉重复别名后，保留 15 段动画和 9 张单帧姿态。默认套装的业务别名分别复用工作、思考、挥手与错误动画；麦麦套装缺少独立动作的状态复用穿装待机。完整录制清单与再生成步骤见[GIF 小相册](../../../assets/deepseek-recordings/SOURCE.md)。

| 文件 | 来源 |
|---|---|
| `default-idle`、`run-left`、`run-right`、`working`、`thinking`、`greet`、`happy`、`error`、`sleeping`、`eating` | [固定版本 DSH 素材](../../../assets/dsh-deepseek/SOURCE.md)，右跑由左跑镜像；许可证副本为 [DSH-LICENSE](DSH-LICENSE) |
| `default-frying`、`outfit`、`outfit-default` | 用户提供视频的[短动作](../../../assets/deepseek-actions/SOURCE.md)，正向 / 反向换装分别保留 |
| `maimai-idle`、`maimai-run-right` | 用户提供视频的[麦麦套装](../../../assets/deepseek-skins/maimai/SOURCE.md)，右跑状态为穿装待机镜像 |
| `default-ceta_*` | 用户本机导入的 [CeTaPet 九姿态](../../../assets/cetapet/SOURCE.md)；许可证副本为 [CeTaPet-LICENSE](CeTaPet-LICENSE)，上游 README 与许可证的授权差异沿用原来源说明 |

九种早期姿态是静态画面。换装 GIF 在 README 中循环展示；桌宠的实际换装播放一次后保存目标套装。

这些文件属于文档展示副本，现有发行脚本仅选择运行素材目录。完整相册、用户本机偏好与订单数据仍按原规则保存在本机。各项来源及授权状态见[素材说明](../../../assets/CREDITS.md)。
