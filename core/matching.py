from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.reason_codes import (
    AMOUNT_MISMATCH,
    CUSTOMER_LOOKUP_FAILURE,
    INVOICE_NOT_FOUND,
    LOW_CONFIDENCE,
    MISSING_REMITTANCE,
    MULTI_INVOICE,
    PARTIAL_PAYMENT,
)
from core.remittance import extract_signals
from core.utils import similarity

from db.db import execute, fetch_all, fetch_one, utc_now_iso


@dataclass
class Proposal:
    invoice_ids: List[int]
    alloc_cents: List[int]
    confidence: float
    reason_code: str
    explanation_lines: List[str]


def _open_invoices_for_customer_hierarchy(customer_id: int) -> List[Dict[str, Any]]:
    # includes customer & children
    rows = fetch_all("SELECT id FROM customers WHERE parent_customer_id = ?", (customer_id,))
    child_ids = [r["id"] for r in rows]
    ids = [customer_id] + child_ids
    q = f"""
      SELECT * FROM invoices
      WHERE status IN ('OPEN','PARTIAL')
        AND customer_id IN ({",".join(["?"]*len(ids))})
      ORDER BY due_date ASC
    """
    return fetch_all(q, tuple(ids))


def _guess_customer_id(payer_name: str) -> Tuple[Optional[int], float]:
    customers = fetch_all("SELECT * FROM customers")
    best = (None, 0.0)
    for c in customers:
        s = similarity(payer_name, c["name"])
        if s > best[1]:
            best = (c["id"], s)
    return best


def _find_invoices_by_numbers(invoice_nos: List[str]) -> List[Dict[str, Any]]:
    if not invoice_nos:
        return []
    placeholders = ",".join(["?"] * len(invoice_nos))
    rows = fetch_all(
        f"SELECT * FROM invoices WHERE upper(invoice_no) IN ({placeholders})",
        tuple([n.upper() for n in invoice_nos]),
    )
    return rows


def _amount_closeness(payment_cents: int, target_cents: int) -> float:
    if payment_cents <= 0 or target_cents <= 0:
        return 0.0
    diff = abs(payment_cents - target_cents)
    return max(0.0, 1.0 - (diff / max(payment_cents, target_cents)))


def _cap01(x: float) -> float:
    return max(0.0, min(0.99, x))


def build_proposals(payment_id: int) -> List[Proposal]:
    payment = fetch_one("SELECT * FROM payments WHERE id = ?", (payment_id,))
    if not payment:
        return []

    payer = payment["payer_name"]
    amount_cents = int(payment["amount_cents"])
    rem_text = payment.get("remittance_text") or ""

    signals = extract_signals(rem_text)

    # customer resolution
    customer_id = payment.get("customer_id")
    payer_sim = 0.0
    if not customer_id:
        customer_id, payer_sim = _guess_customer_id(payer)
    else:
        c = fetch_one("SELECT * FROM customers WHERE id = ?", (int(customer_id),))
        payer_sim = similarity(payer, c["name"] if c else "")

    if not customer_id:
        return [
            Proposal(
                invoice_ids=[],
                alloc_cents=[],
                confidence=0.25,
                reason_code=CUSTOMER_LOOKUP_FAILURE,
                explanation_lines=[
                    "Could not resolve payer → customer.",
                    "Needs manual customer selection / remittance request.",
                ],
            )
        ]

    open_invoices = _open_invoices_for_customer_hierarchy(int(customer_id))

    proposals: List[Proposal] = []

    # proposal A, invoice no.
    inv_rows = _find_invoices_by_numbers(signals.invoice_nos)
    if signals.invoice_nos and inv_rows:
        # greedy alloca matched invoices by due_date
        inv_rows_sorted = sorted(inv_rows, key=lambda r: r["due_date"])
        remaining = amount_cents
        invoice_ids: List[int] = []
        allocs: List[int] = []
        total_due = 0
        for inv in inv_rows_sorted:
            if remaining <= 0:
                break
            due = int(inv["amount_due_cents"])
            take = min(due, remaining)
            if take <= 0:
                continue
            invoice_ids.append(int(inv["id"]))
            allocs.append(int(take))
            remaining -= take
            total_due += due

        closeness = _amount_closeness(amount_cents, min(total_due, amount_cents))
        base = 0.55
        amt_component = 0.25 * closeness
        payer_component = 0.20 * payer_sim
        conf = _cap01(base + amt_component + payer_component)

        reason = MULTI_INVOICE if len(invoice_ids) > 1 else "EXACT_INVOICE_MATCH"
        if remaining > 0 and invoice_ids:
            reason = PARTIAL_PAYMENT

        proposals.append(
            Proposal(
                invoice_ids=invoice_ids,
                alloc_cents=allocs,
                confidence=conf,
                reason_code=reason,
                explanation_lines=[
                    f"Detected invoice references in remittance: {', '.join(signals.invoice_nos[:5])}",
                    f"Matched {len(invoice_ids)} invoice(s) by invoice_no.",
                    f"Payer↔Customer name similarity: {payer_sim:.2f}",
                    f"Allocation built greedily by due date; leftover={remaining/100:.2f}" if remaining else "Allocation covers payment amount.",
                ],
            )
        )
    elif signals.invoice_nos and not inv_rows:
        proposals.append(
            Proposal(
                invoice_ids=[],
                alloc_cents=[],
                confidence=0.35,
                reason_code=INVOICE_NOT_FOUND,
                explanation_lines=[
                    f"Found invoice-like tokens in remittance ({', '.join(signals.invoice_nos[:5])}) but none matched open invoices.",
                    "Likely needs customer remittance clarification or invoice mapping.",
                ],
            )
        )

    # proposal B, amount match
    if open_invoices:
        best = None
        best_score = -1.0
        for inv in open_invoices:
            closeness = _amount_closeness(amount_cents, int(inv["amount_due_cents"]))
            score = 0.55 * closeness + 0.45 * payer_sim
            if score > best_score:
                best = inv
                best_score = score

        if best:
            closeness = _amount_closeness(amount_cents, int(best["amount_due_cents"]))
            conf = _cap01(0.20 + 0.55 * closeness + 0.24 * payer_sim)
            reason = AMOUNT_MISMATCH if closeness < 0.90 else "AMOUNT_MATCH"
            proposals.append(
                Proposal(
                    invoice_ids=[int(best["id"])],
                    alloc_cents=[min(amount_cents, int(best["amount_due_cents"]))],
                    confidence=conf,
                    reason_code=reason,
                    explanation_lines=[
                        "No strong invoice references; attempting amount-based match.",
                        f"Best candidate invoice amount closeness: {closeness:.2f}",
                        f"Payer↔Customer name similarity: {payer_sim:.2f}",
                    ],
                )
            )

    # proposal C, multi-invoice greedy
    if open_invoices and amount_cents > 0:
        remaining = amount_cents
        invoice_ids: List[int] = []
        allocs: List[int] = []
        for inv in open_invoices:
            if remaining <= 0:
                break
            due = int(inv["amount_due_cents"])
            if due <= 0:
                continue
            take = min(due, remaining)
            if take <= 0:
                continue
            invoice_ids.append(int(inv["id"]))
            allocs.append(int(take))
            remaining -= take

        if invoice_ids:
            coverage = 1.0 - (remaining / amount_cents) if amount_cents else 0.0
            conf = _cap01(0.15 + 0.45 * coverage + 0.25 * payer_sim)
            reason = MULTI_INVOICE if len(invoice_ids) > 1 else "GREEDY_SINGLE"
            if remaining > 0:
                reason = PARTIAL_PAYMENT
            proposals.append(
                Proposal(
                    invoice_ids=invoice_ids,
                    alloc_cents=allocs,
                    confidence=conf,
                    reason_code=reason,
                    explanation_lines=[
                        "Fallback: allocate across open invoices by due date (greedy).",
                        f"Coverage of payment amount: {coverage:.2f}",
                        f"Payer↔Customer name similarity: {payer_sim:.2f}",
                    ],
                )
            )

    # if remittance missing; reason code
    if not signals.has_text:
        for p in proposals:
            p.reason_code = MISSING_REMITTANCE if p.confidence < 0.85 else p.reason_code

    proposals = sorted(proposals, key=lambda p: p.confidence, reverse=True)

    # if everything low, low confidence
    if proposals and proposals[0].confidence < 0.60:
        proposals[0].reason_code = LOW_CONFIDENCE

    return proposals


def persist_proposals(payment_id: int, proposals: List[Proposal]) -> List[int]:
    # clear old proposals
    execute("DELETE FROM match_proposals WHERE payment_id = ?", (payment_id,))
    ids: List[int] = []
    for i, p in enumerate(proposals, start=1):
        pid = execute(
            """
            INSERT INTO match_proposals(payment_id, proposal_rank, invoice_ids_json, alloc_cents_json,
                                        confidence, explanation, reason_code, created_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                payment_id,
                i,
                json.dumps(p.invoice_ids),
                json.dumps(p.alloc_cents),
                float(p.confidence),
                "\n".join([f"- {line}" for line in p.explanation_lines]),
                p.reason_code,
                utc_now_iso(),
            ),
        )
        ids.append(pid)
    return ids
