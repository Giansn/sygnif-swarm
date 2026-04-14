from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT / "prediction_agent", _ROOT / "finance_agent", _ROOT / "trade_overseer"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
