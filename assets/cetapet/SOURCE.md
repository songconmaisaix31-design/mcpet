# 早期鲸鲸的姿态小衣柜

来源：[kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek](https://github.com/kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek/tree/d0725b0e0aa58cd547c48b1681988ee708120d31)，固定提交 `d0725b0e0aa58cd547c48b1681988ee708120d31`。

用户明确要求早期代码参考仓库的全部动作接入，并在桌面按动作名称分类。上游 `CetaPet/main.py` 的 `IMAGE_RELS` 共九项，均为单张 PNG 姿态；没有把它们称作序列动画。

| 名称 | 原动作 | McPet 调用 |
|---|---|---|
| 待机 | nothing | ceta_nothing |
| 吃饭 | eat | ceta_eat |
| 思考 | think | ceta_think |
| 被提起来 | pickup | ceta_pickup |
| 摸摸回应 | touch | ceta_touch |
| 余额告急 | nomoney | ceta_nomoney |
| 元气登场 | cheerup | ceta_cheerup |
| 成功 | true | ceta_true |
| 失败 | wrong | ceta_wrong |

`actions.json` 是视频、桌宠与 Agent 共用的动作词表。图片在本地 `original/asset_library/` 按原路径存放，LICENSE 和原 README 一并保留。`runtime/` 使用既有 AnimationSheet 格式：原像素放入共用 192×192 透明画布，不放大、不按透明边裁切；12 列页的第一格是唯一姿态，保持到切换或停止。

导入与分类导出：

```powershell
python -X utf8 scripts/import_cetapet.py --source .tmp-test-data/references/cetapet --export '你的分类输出文件夹'
```

缺少参考缓存时，在 `videos/mcpet-reel` 执行 `npm run import:cetapet` 可下载参考仓库并复制原图；随后把下载的本地仓库目录作为上述 `--source`，生成桌宠运行资源和分类文件夹。导入程序校验固定版本、已跟踪文件未修改以及九张图片清单完整。桌面导出以动作中文名建文件夹；已有不同图片则拒绝覆盖。

仓库本地接入、桌面整理与视频预览可以使用这套素材。按 [现有素材记录](../CREDITS.md) 的边界，原始图片、运行图页和参考缓存均被 Git 忽略，不进入发行包；发布只携带动作词表与接入代码。上游 LICENSE 与 README 的原始说明不被改写。

显式导入完成后，右键“角色与动作 → 早期鲸鲸姿态”可选择九项；原 Agent 调用 `mcpet_pet`，例如 `character_id="deepseek", action="ceta_nomoney"`。资源 URI 为 `mcpet://pose/deepseek/cetapet/ceta_nomoney`（image/png）。现有 Agent 宿主重新加载 MCP 后发现新参数；已运行桌宠需重新加载动作资源。没有新增模型、账号或点餐请求。
