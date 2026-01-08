import json
import streamlit as st

from core.ai_client import ai_draft_remittance_request
from core.matching import build_proposals, persist_proposals
from core.utils import dollars
from db.db import execute, fetch_all, fetch_one, insert_audit_event, utc_now_iso

AUTO_APPLY_THRESHOLD = 0.85

st.title("Payment Review")

pid = st.session_state.get("selected_payment_id")
if not pid:
    st.warning("No payment selected. Go to Payment Inbox first.")
    st.stop()

payment = fetch_one("SELECT * FROM payments WHERE id = ?", (pid,))
if not payment:
    st.error("Payment not found.")
    st.stop()

actor = st.text_input("Actor (who is reviewing)", value=st.session_state.get("actor", "Zain"))
st.session_state["actor"] = actor

left, right = st.columns([1.1, 1.4], gap="large")

with left:
    st.subheader("Payment")
    st.write({
        "id": payment["id"],
        "payer": payment["payer_name"],
        "amount": dollars(int(payment["amount_cents"])),
        "date": payment["received_date"],
        "method": payment["method"],
        "status": payment["status"],
    })

    st.subheader("Remittance text")
    rem = (payment.get("remittance_text") or "").strip()
    st.text_area("remittance_text", value=rem, height=220, disabled=True)

    st.divider()
    if st.button("Run agent (generate match proposals)"):
        proposals = build_proposals(pid)
        persist_proposals(pid, proposals)
        insert_audit_event(
            entity_type="payment",
            entity_id=pid,
            action="agent_ran",
            actor=actor,
            before={"status": payment["status"]},
            after={"status": payment["status"], "proposal_count": len(proposals)},
        )
        st.success(f"Generated {len(proposals)} proposal(s).")

with right:
    st.subheader("Top match proposals")
    rows = fetch_all(
        "SELECT * FROM match_proposals WHERE payment_id = ? ORDER BY confidence DESC, proposal_rank ASC",
        (pid,),
    )
    if not rows:
        st.info("No proposals yet. Click **Run agent**.")
        st.stop()

    # pick a proposal
    labels = []
    for r in rows:
        labels.append(
            f"#{r['proposal_rank']} | conf={r['confidence']:.2f} | {r['reason_code']}"
        )

    choice = st.radio("Choose proposal", options=list(range(len(rows))), format_func=lambda i: labels[i])

    chosen = rows[int(choice)]
    invoice_ids = json.loads(chosen["invoice_ids_json"])
    allocs = json.loads(chosen["alloc_cents_json"])

    st.markdown("### Agent reasoning")
    st.code(chosen["explanation"], language="markdown")

    st.markdown("### Proposed allocations")
    if invoice_ids:
        inv_rows = fetch_all(
            f"SELECT id, invoice_no, amount_due_cents, status FROM invoices WHERE id IN ({','.join(['?']*len(invoice_ids))})",
            tuple(invoice_ids),
        )
        inv_map = {r["id"]: r for r in inv_rows}
        table = []
        for inv_id, cents in zip(invoice_ids, allocs):
            inv = inv_map.get(inv_id, {"invoice_no": "UNKNOWN", "amount_due_cents": 0, "status": "?"})
            table.append({
                "invoice_id": inv_id,
                "invoice_no": inv["invoice_no"],
                "current_due": dollars(int(inv["amount_due_cents"])),
                "allocate": dollars(int(cents)),
                "status": inv["status"],
            })
        st.dataframe(table, use_container_width=True)
    else:
        st.warning("This proposal did not select invoices (needs manual work).")

    st.divider()

    conf = float(chosen["confidence"])
    st.write(f"**Confidence:** {conf:.2f} (auto-apply threshold: {AUTO_APPLY_THRESHOLD:.2f})")

    c1, c2, c3 = st.columns(3)

    def set_payment_status(new_status: str):
        before = fetch_one("SELECT * FROM payments WHERE id = ?", (pid,))
        execute("UPDATE payments SET status = ? WHERE id = ?", (new_status, pid))
        after = fetch_one("SELECT * FROM payments WHERE id = ?", (pid,))
        insert_audit_event("payment", pid, f"status_set:{new_status}", actor, before=before, after=after)

    with c1:
        if st.button("Approve"):
            # apply allocs by reducing invoice amount_due
            if invoice_ids:
                for inv_id, alloc in zip(invoice_ids, allocs):
                    inv_before = fetch_one("SELECT * FROM invoices WHERE id = ?", (inv_id,))
                    new_due = max(0, int(inv_before["amount_due_cents"]) - int(alloc))
                    new_status = "PAID" if new_due == 0 else "PARTIAL"
                    execute(
                        "UPDATE invoices SET amount_due_cents = ?, status = ? WHERE id = ?",
                        (new_due, new_status, inv_id),
                    )
                    inv_after = fetch_one("SELECT * FROM invoices WHERE id = ?", (inv_id,))
                    insert_audit_event("invoice", inv_id, "allocation_applied", actor, before=inv_before, after=inv_after)

            decision_id = execute(
                """
                INSERT INTO decisions(payment_id, proposal_id, decision, approved_by, notes, created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (pid, chosen["id"], "APPROVED", actor, json.dumps({"invoice_ids": invoice_ids, "allocs": allocs}), utc_now_iso()),
            )
            insert_audit_event("decision", decision_id, "created", actor, after={"payment_id": pid, "proposal_id": chosen["id"], "decision": "APPROVED"})
            set_payment_status("AUTO_APPLIED" if conf >= AUTO_APPLY_THRESHOLD else "APPROVED")
            st.success("Approved + applied allocations + wrote audit events.")

    with c2:
        if st.button("Reject"):
            decision_id = execute(
                """
                INSERT INTO decisions(payment_id, proposal_id, decision, approved_by, notes, created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (pid, chosen["id"], "REJECTED", actor, "Rejected proposal; needs manual work.", utc_now_iso()),
            )
            insert_audit_event("decision", decision_id, "created", actor, after={"payment_id": pid, "proposal_id": chosen["id"], "decision": "REJECTED"})
            set_payment_status("REJECTED")
            st.warning("Rejected. Payment stays in exception state.")

    with c3:
        if st.button("Request remittance"):
            amt = dollars(int(payment["amount_cents"]))
            draft = ai_draft_remittance_request(payment["payer_name"], amt, payment["received_date"])
            if not draft:
                draft = f"""Subject: Remittance details needed for payment {amt}

Hi {payment['payer_name']},

We received your payment of {amt} on {payment['received_date']}. Could you please share the remittance details (invoice numbers and amounts) so we can apply it correctly?

Thank you,
AR Team
"""
            decision_id = execute(
                """
                INSERT INTO decisions(payment_id, proposal_id, decision, approved_by, notes, created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (pid, chosen["id"], "REQUESTED_REMITTANCE", actor, draft, utc_now_iso()),
            )
            insert_audit_event("decision", decision_id, "created", actor, after={"payment_id": pid, "decision": "REQUESTED_REMITTANCE"})
            set_payment_status("PENDING_REMITTANCE")
            st.info("Draft email generated (and logged). See decision notes below.")
            st.text_area("Email draft", draft, height=180)
