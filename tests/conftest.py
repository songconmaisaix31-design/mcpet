import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 测试期间把本机数据目录指到临时目录，绝不碰用户真实台账
os.environ.setdefault("MCPET_DATA_DIR", str(PROJECT_ROOT / ".tmp-test-data"))
# 无头环境用 offscreen 平台，避免需要真实显示
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
