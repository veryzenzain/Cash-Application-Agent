from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

REAGENT_DRAFT_URL = "https://noggin.rea.gent/fashionable-guan-8580"
REAGENT_API_KEY = "rg_v1_sfupx5ipsaeqgcbczs2311u04xf2u3m89es7_ngk"


def _post_json(url: str, payload: Dict[str, Any], timeout_s: int = 12) -> Optional[Dict[str, Any]]:
    try:
        r = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {REAGENT_API_KEY}",
            },
            timeout=timeout_s,
        )
        r.raise_for_status()

        try:
            return r.json()
        except Exception:
            txt = (r.text or "").strip()
            return json.loads(txt) if txt else None

    except Exception:
        return None


def ai_draft_remittance_request(payer_name: str, amount: str, received_date: str) -> Optional[str]:
    out = _post_json(
        REAGENT_DRAFT_URL,
        {
            "payer_name": payer_name,
            "amount": amount,
            "received_date": received_date,
        },
    )
    if not out:
        return None

    return out.get("email") or out.get("draft") or out.get("output") or None
