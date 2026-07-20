import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS = ROOT / "tools" / "robot_factory_bridge"

if str(BRIDGE_TOOLS) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS))
