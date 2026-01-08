from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

INVOICE_PATTERNS = [
    r"\bINV[-\s]?\d{3,}\b",
    r"\bINVOICE[-\s]?\d{3,}\b",
    r"\b\d{6,}\b",  # last resort
]

AMOUNT_PATTERN = r"(?:(?:USD|\$)\s?)\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b"


@dataclass(frozen=True)
class RemittanceSignals:
    invoice_nos: List[str]
    amounts: List[float]
    has_text: bool


def normalize_invoice(token: str) -> str:
    t = token.upper().strip()
    t = t.replace("INVOICE", "INV")
    t = re.sub(r"\s+", "", t)
    return t


def extract_signals(remittance_text: Optional[str]) -> RemittanceSignals:
    text = (remittance_text or "").strip()
    if not text:
        return RemittanceSignals(invoice_nos=[], amounts=[], has_text=False)

    inv_matches: List[str] = []
    for pat in INVOICE_PATTERNS[:2]:
        inv_matches += re.findall(pat, text.upper())

    # broad numeric pattern if no INV tokens
    if not inv_matches:
        inv_matches += re.findall(INVOICE_PATTERNS[2], text)

    invoice_nos = []
    for m in inv_matches:
        n = normalize_invoice(m)
        # numeric tokens to INVxxxxxx for consistency
        if n.isdigit():
            n = f"INV{n}"
        invoice_nos.append(n)

    invoice_nos = sorted(list(set(invoice_nos)))[:10]

    amt_matches = re.findall(AMOUNT_PATTERN, text.upper())
    amounts: List[float] = []
    for a in amt_matches:
        a = a.replace("USD", "").replace("$", "").strip()
        a = a.replace(",", "")
        try:
            amounts.append(float(a))
        except ValueError:
            continue
    amounts = amounts[:10]

    return RemittanceSignals(invoice_nos=invoice_nos, amounts=amounts, has_text=True)
