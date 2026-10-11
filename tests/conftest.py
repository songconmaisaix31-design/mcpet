import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试期间把本机数据目录指到临时目录，绝不碰用户真实台账
os.environ.setdefault("MCPET_DATA_DIR", str(PROJECT_ROOT / ".tmp-test-data"))
# 无头环境用 offscreen 平台，避免需要真实显示
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _qapplication():
    """全局唯一的 QApplication。

    必须是 QApplication，不能是 QGuiApplication —— PetWindow 是 QWidget，
    只有 QGuiApplication 时构造窗口会直接挂死（不是报错，是卡住）。
    session 级 autouse 保证它先于各模块自己的 fixture 建好。
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
