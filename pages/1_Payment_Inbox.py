import streamlit as st
from db.db import fetch_all

st.title("Payment Inbox")

status_filter = st.selectbox(
    "Filter",
    ["ALL", "NEEDS_REVIEW", "AUTO_APPLIED", "APPROVED", "REJECTED", "PENDING_REMITTANCE"],
    index=0,
)

q = "SELECT * FROM payments ORDER BY received_date DESC, id DESC"
rows = fetch_all(q)
if status_filter != "ALL":
    rows = [r for r in rows if r["status"] == status_filter]

st.write(f"Payments: **{len(rows)}**")

if not rows:
    st.stop()

# show table
st.dataframe(
    [{
        "id": r["id"],
        "payer": r["payer_name"],
        "amount": f"${r['amount_cents']/100:,.2f}",
        "date": r["received_date"],
        "method": r["method"],
        "status": r["status"],
        "has_remittance": bool((r.get("remittance_text") or "").strip()),
    } for r in rows],
    use_container_width=True,
)

selected = st.selectbox("Open payment ID", [r["id"] for r in rows])
if st.button("Review selected payment →"):
    st.session_state["selected_payment_id"] = int(selected)
    st.switch_page("pages/2_Payment_Review.py")
