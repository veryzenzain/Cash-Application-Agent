from __future__ import annotations

import json
from difflib import SequenceMatcher
from typing import Any, Dict, List

def similarity(a: str, b: str) -> float:
    a = (a or "").lower().strip()
    b = (b or "").lower().strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

def dollars(cents: int) -> str:
    return f"${cents/100:,.2f}"

def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
