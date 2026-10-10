# 素材与代码来源

本文件用于满足赛事的原创性声明要求：**参赛项目系原创开发，或已取得合法授权**。
每一项的授权状态如实标注，没有拿到授权的一律不用。

## 1. 占位形象：龙娘精灵图集 `assets/longniang/`

| 项 | 值 |
|---|---|
| 来源 | `caritivememory-ops/chatgpt-longniang` |
| 文件 | `spritesheet.webp`（1536×2288）、`pet.json`、`sprite-rows.json`（由上游 `pet_request.json` 生成） |
| 规格 | 8 列 × 11 行，单元 192×208，`spriteVersionNumber: 2`，11 个动作行 |
| **授权状态** | **已取得原作者授权**（2026-10-10，由本项目作者联系确认） |
| 用途 | 工程占位形象。**最终交付前替换为原创麦当劳主题素材** |

上游仓库本身**没有 LICENSE 文件**，默认视为版权保留。本项目是在取得作者明确授权后
才将其纳入的。若授权凭证需要在审核时出示，请补充：作者在 GitHub Issue 或仓库
README 中的书面授权说明截图，存放于本目录。

## 2. 占位形象：鲸鱼娘素材 `assets/cetapet-whale/`

| 项 | 值 |
|---|---|
| 来源 | `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek` 的 `CetaPet/asset_library` |
| 说明 | 上游 README 标注「角色图片为 ChatGPT AI 生成素材」 |
| **授权状态** | 上游 `LICENSE` 文件为 MIT，但 README 同时声明「仅允许个人学习使用；禁止商用」——**两处存在冲突** |
| 处理 | 已在上游仓库发起授权确认；在收到书面答复前，本目录素材仅用于本机开发，不用于对外发布物料 |

## 3. 代码参考

| 对象 | 借鉴了什么 | 处理方式 |
|---|---|---|
| `kmjs1915/CeTaPet-AI-DeskTopPet-DeepSeek` | 托盘常驻 + 状态机 + 气泡 + 拖拽的**架构** | 代码为本项目重写（Python / PySide6），未复制其源码文件 |
| `myunwang/LLMPET`（MIT） | 状态优先级与 oneshot TTL 衰减的**设计思路**（`shared/states.js`） | 思路移植，未复制代码；本项目未使用其任何素材 |
| `caritivememory-ops/chatgpt-longniang` | 精灵图规格与 QA 校验**流程** | 规格照用，素材在授权范围内使用 |

## 4. 原创部分

以下为本项目原创实现，无第三方来源：

- `src/mcd_mcp/` 全部：MCP Streamable HTTP 客户端、麦麦大脑、下单护栏
- `src/pet/spritesheet.py`：图集切片播放器
- `src/schedule/clock.py`：每日调度与休眠补触发
- `src/nutrition/ledger.py`：营养台账
- `src/pet/window.py`、`tray.py`、`dialogs.py`：窗口、托盘、确认对话框
- `assets/longniang/sprite-rows.json`：由上游 `pet_request.json` 重新生成的结构化行定义

## 5. 品牌合规

本项目不使用麦当劳官方商标、金色拱门标识或任何官方视觉元素，不暗示官方背书。
输出仅供参考，不构成医疗或营养建议。
