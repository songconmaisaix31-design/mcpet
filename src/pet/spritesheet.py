"""精灵图集加载与切片播放。

CeTaPet 原本的机制是「每个状态一张 PNG，切换时从磁盘重读」，没有切片能力。
而 longniang 规格是单张图集（1536×2288、8 列 × 11 行、单元 192×208），
两者接不上——所以这一层是新写的：按 pet.json + 行定义表把图集切成帧，
再按状态逐帧播放。

原创麦当劳素材做好后，只要行数按 states.TARGET_ROWS 排，这里不用改。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from collections import OrderedDict
from collections.abc import Sequence

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap, QTransform

from . import states


class SpriteLoadError(RuntimeError):
    pass


@dataclass
class SpriteSheet:
    image: QImage
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    row_of: dict[str, int] = field(default_factory=dict)
    frames_of: dict[str, int] = field(default_factory=dict)  # 按图集自带的状态名
    frames_by_row: dict[int, int] = field(default_factory=dict)  # 按行号，播别名状态时用
    frame_delay_ms: int = 80
    meta: dict = field(default_factory=dict)

    # ---------- 加载 ----------

    @classmethod
    def load(
        cls,
        image_path: str | Path,
        *,
        pet_json: str | Path | None = None,
        rows_json: str | Path | None = None,
        alias: dict[str, int] | None = None,
        frame_delay_ms: int | None = None,
    ) -> "SpriteSheet":
        image_path = Path(image_path)
        image = QImage(str(image_path))
        if image.isNull():
            raise SpriteLoadError(f"无法加载图集：{image_path}")

        meta: dict = {}
        if pet_json and Path(pet_json).exists():
            meta = json.loads(Path(pet_json).read_text(encoding="utf-8"))

        columns = int(meta.get("columns") or 8)
        rows_total = int(meta.get("rows") or 11)
        cell_w = int(meta.get("cell_width") or 0)
        cell_h = int(meta.get("cell_height") or 0)
        if not cell_w:
            cell_w = image.width() // columns
        if not cell_h:
            cell_h = image.height() // rows_total

        row_of: dict[str, int] = {}
        frames_of: dict[str, int] = {}
        frames_by_row: dict[int, int] = {}
        if rows_json and Path(rows_json).exists():
            row_defs = json.loads(Path(rows_json).read_text(encoding="utf-8"))
            for entry in row_defs.get("rows", []):
                row = int(entry["row"])
                row_of[entry["state"]] = row
                if entry.get("frames"):
                    frames_of[entry["state"]] = int(entry["frames"])
                    frames_by_row[row] = int(entry["frames"])

        if not row_of:
            row_of = dict(alias or states.LONGNIANG_ROW_ALIAS)

        sheet = cls(
            image=image,
            columns=columns,
            rows=rows_total,
            cell_width=cell_w,
            cell_height=cell_h,
            row_of=row_of,
            frames_of=frames_of,
            frames_by_row=frames_by_row,
            frame_delay_ms=frame_delay_ms or 80,
            meta=meta,
        )
        issues = sheet.validate()
        if issues:
            # 不抛异常：占位素材尺寸对不上时仍然让它能跑，问题如实报到日志。
            sheet.validation_issues = issues  # type: ignore[attr-defined]
        return sheet

    # ---------- 切片 ----------

    def row_for(self, state: str) -> int:
        if state in self.row_of:
            return self.row_of[state]
        alias = states.LONGNIANG_ROW_ALIAS.get(state)
        return alias if alias is not None else self.row_of.get("idle", 0)

    def frame_count(self, state: str) -> int:
        """帧数以「行」为准——别名状态（如 remind→行 3）也要能拿到正确的帧数。"""
        row = self.row_for(state)
        if row in self.frames_by_row:
            return self.frames_by_row[row]
        if state in self.frames_of:
            return self.frames_of[state]
        return self.columns  # 行定义缺失时保守地按整行播

    def frame(self, state: str, index: int) -> QPixmap:
        row = self.row_for(state)
        count = max(1, self.frame_count(state))
        column = index % count
        rect = QRect(column * self.cell_width, row * self.cell_height, self.cell_width, self.cell_height)
        pixmap = QPixmap.fromImage(self.image.copy(rect))
        return pixmap

    def frames(self, state: str) -> list[QPixmap]:
        return [self.frame(state, i) for i in range(self.frame_count(state))]

    def anchor_bounds(self, state: str, alpha_threshold: int = 32) -> list[tuple[int, int, int, int] | None]:
        """Audit only. Full fixed cells remain untouched, preserving jumps and poses.

        Coordinates are cell-local inclusive alpha bounds; no per-frame crop/scale.
        """
        result = []
        row = self.row_for(state)
        for index in range(self.frame_count(state)):
            cell = self.image.copy(QRect(index * self.cell_width, row * self.cell_height,
                                         self.cell_width, self.cell_height))
            cell = cell.convertToFormat(QImage.Format_RGBA8888)
            data = bytes(cell.constBits())
            stride = cell.bytesPerLine()
            left, top, right, bottom = cell.width(), cell.height(), -1, -1
            for y in range(cell.height()):
                for x in range(cell.width()):
                    if data[y * stride + x * 4 + 3] > alpha_threshold:
                        left, top = min(left, x), min(top, y)
                        right, bottom = max(right, x), max(bottom, y)
            result.append(None if right < 0 else (left, top, right, bottom))
        return result

    # ---------- 校验（对齐 longniang 的 QA 思路） ----------

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.image.width() != self.columns * self.cell_width:
            issues.append(
                f"图集宽度 {self.image.width()} 与 列数×单元宽 {self.columns}×{self.cell_width} 不符"
            )
        if self.image.height() < self.rows * self.cell_height:
            issues.append(
                f"图集高度 {self.image.height()} 小于 行数×单元高 {self.rows}×{self.cell_height}"
            )
        for state, row in self.row_of.items():
            if row >= self.rows:
                issues.append(f"状态 {state} 的行号 {row} 超出图集行数 {self.rows}")
        empty = self._empty_cells()
        if empty:
            issues.append("以下格子完全透明，可能没画到内容：" + "、".join(empty[:8]))
        return issues

    def _empty_cells(self) -> list[str]:
        empty: list[str] = []
        for state, row in sorted(self.row_of.items(), key=lambda kv: kv[1]):
            count = min(self.frame_count(state), self.columns)
            for column in range(count):
                cell = self.image.copy(
                    QRect(column * self.cell_width, row * self.cell_height, self.cell_width, self.cell_height)
                )
                if cell.hasAlphaChannel():
                    # Same 4px sample grid and >8 threshold. Read alpha bytes
                    # once, and stop at the first content instead of crossing
                    # the Python/Qt boundary for every pixel in every cell.
                    cell = cell.convertToFormat(QImage.Format_RGBA8888)
                    data = cell.constBits()
                    stride = cell.bytesPerLine()
                    opaque = False
                    for y in range(0, cell.height(), 4):
                        if any(alpha > 8 for alpha in data[y * stride + 3:y * stride + cell.width() * 4:16]):
                            opaque = True
                            break
                    if not opaque:
                        empty.append(f"{state}#{column}")
        return empty

    @property
    def has_alpha(self) -> bool:
        return self.image.hasAlphaChannel()


class AnimationSheet(SpriteSheet):
    """Fixed-cell pages; at most one decoded 12-frame page in memory.

    A logical row identifies an animation, not its physical atlas row. The public
    frame/frames/row_for/frame_count API is identical to SpriteSheet.
    """

    def __init__(self, directory: Path, *, base_sheet: SpriteSheet | None = None):
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            size, columns = int(manifest["cell_size"]), int(manifest["columns"])
            if size != 192 or columns != 12:
                raise ValueError("invalid animation geometry")
            animations = manifest["animations"]
            if not isinstance(animations, dict):
                raise ValueError("invalid animation manifest")
            paths, counts = {}, {}
            row_of = {}
            for row, (state, entry) in enumerate(animations.items(), start=base_sheet.rows if base_sheet else 0):
                filenames, count = entry["pages"], int(entry["frames"])
                if not isinstance(filenames, list) or len(filenames) != (count + columns - 1) // columns or count < 1 or count > 256 or size != 192 or columns != 12:
                    raise ValueError("invalid animation geometry")
                pages = []
                for filename in filenames:
                    if not isinstance(filename, str) or Path(filename).name != filename:
                        raise ValueError("invalid page path")
                    path = directory / filename
                    reader = QImageReader(str(path))
                    dimensions = reader.size()
                    if not reader.canRead() or dimensions.width() != size * columns or dimensions.height() != size:
                        raise ValueError(f"invalid animation: {state}")
                    pages.append(path)
                row_of[state], paths[row], counts[row] = row, tuple(pages), count
            required = ("idle", "run-left", "working", "thinking", "greet", "happy", "error", "sleeping", "eating")
            if base_sheet is None and any(state not in row_of for state in required):
                raise ValueError("missing animation")
            right = -1
            if base_sheet is None:
                right = len(paths)
                paths[right], counts[right] = paths[row_of["run-left"]], counts[row_of["run-left"]]
                row_of["run-right"] = right
                for alias, state in {"remind": "greet", "coupon": "thinking", "balance": "thinking",
                                     "progress": "working", "waiting": "thinking", "failed": "error"}.items():
                    row_of[alias] = row_of[state]
                preview_file = manifest["preview"]
                if not isinstance(preview_file, str) or Path(preview_file).name != preview_file:
                    raise ValueError("invalid preview path")
                preview = QImage(str(directory / preview_file))
                if preview.isNull() or preview.width() != size or preview.height() != size or not preview.hasAlphaChannel():
                    raise ValueError("invalid transparent preview")
                super().__init__(preview, columns, len(paths), size, size, row_of=row_of,
                                 frames_by_row=counts, frame_delay_ms=int(manifest["frame_delay_ms"]),
                                 meta={**manifest, "character_id": "deepseek"})
            else:
                # Supplement the original atlas without changing its pixels,
                # logical rows, previews, aliases or frame geometry.
                super().__init__(base_sheet.image, base_sheet.columns, base_sheet.rows + len(paths),
                                 base_sheet.cell_width, base_sheet.cell_height,
                                 row_of={**base_sheet.row_of, **row_of},
                                 frames_by_row={**base_sheet.frames_by_row, **counts},
                                 frame_delay_ms=base_sheet.frame_delay_ms,
                                 meta={**base_sheet.meta, "animations": animations})
            self._base_sheet = base_sheet
            self._page_size, self._page_columns = size, columns
            self._paths = paths
            self._mirrored_row = right
            self._atlases: OrderedDict[Path, QImage] = OrderedDict()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise SpriteLoadError("无法加载角色动画缓存") from exc

    def row_for(self, state: str) -> int:
        if self._base_sheet is not None:
            return self.row_of.get(state, self._base_sheet.row_for(state))
        return self.row_of.get(state, self.row_of["idle"])

    def is_paged(self, state: str) -> bool:
        return self.row_for(state) in self._paths

    def frame(self, state: str, index: int) -> QPixmap:
        row = self.row_for(state)
        if self._base_sheet is not None and row not in self._paths:
            return self._base_sheet.frame(state, index)
        cell = index % self.frame_count(state)
        path = self._paths[row][cell // self._page_columns]
        image = self._atlases.get(path)
        if image is None:
            image = QImage(str(path))
            if image.isNull() or image.width() != self._page_columns * self._page_size or image.height() != self._page_size or not image.hasAlphaChannel():
                raise SpriteLoadError("无法读取角色动作缓存")
            self._atlases.clear()
            self._atlases[path] = image
        frame = image.copy((cell % self._page_columns) * self._page_size,
                           0,
                           self._page_size, self._page_size)
        if row == self._mirrored_row:
            frame = frame.transformed(QTransform().scale(-1, 1))
        return QPixmap.fromImage(frame)

    def anchor_bounds(self, state: str, alpha_threshold: int = 32):
        # Offline auditing only, using the same real frames as the player.
        result = []
        table = bytes(255 if value > alpha_threshold else 0 for value in range(256))
        for index in range(self.frame_count(state)):
            image = self.frame(state, index).toImage().convertToFormat(QImage.Format_RGBA8888)
            data = bytes(image.constBits())
            left, top, right, bottom = image.width(), image.height(), -1, -1
            for y in range(image.height()):
                alpha = data[y * image.bytesPerLine() + 3:(y + 1) * image.bytesPerLine():4].translate(table)
                start = alpha.find(b"\xff")
                if start >= 0:
                    left, top = min(left, start), min(top, y)
                    right, bottom = max(right, alpha.rfind(b"\xff")), y
            result.append(None if right < 0 else (left, top, right, bottom))
        return result

    def validate(self) -> list[str]:
        # Geometry is validated at load. Scan every used frame only when requested.
        return [f"{state}: empty frame" for state in self.row_of
                if any(bound is None for bound in self.anchor_bounds(state))]


class ScaledAnimationFrames(Sequence[QPixmap]):
    """Scale on presentation; two resident frames instead of a 126-frame copy.

    Pages retain the same fixed cells. The first presented page is decoded
    synchronously on action change; later pages load only as playback reaches
    them. No alpha analysis or geometry adjustment occurs during playback.
    """

    def __init__(self, sheet: AnimationSheet, state: str, size: int, dpr: float):
        self.sheet, self.state, self.size, self.dpr = sheet, state, size, dpr
        self.resident: OrderedDict[int, QPixmap] = OrderedDict()

    def __len__(self) -> int:
        return self.sheet.frame_count(self.state)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        frame = self.resident.pop(index, None)
        if frame is None:
            frame = self.sheet.frame(self.state, index).scaled(
                round(self.size * self.dpr), round(self.size * self.dpr),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            frame.setDevicePixelRatio(self.dpr)
        self.resident[index] = frame
        while len(self.resident) > 2:
            self.resident.popitem(last=False)
        return frame
