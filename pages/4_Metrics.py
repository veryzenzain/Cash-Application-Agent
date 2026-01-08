import streamlit as st
from db.db import fetch_all, fetch_one

st.title("Metrics")

tot = fetch_one("SELECT COUNT(*) AS c FROM payments")["c"]
auto = fetch_one("SELECT COUNT(*) AS c FROM payments WHERE status = 'AUTO_APPLIED'")["c"]
needs = fetch_one("SELECT COUNT(*) AS c FROM payments WHERE status = 'NEEDS_REVIEW'")["c"]

st.metric("Total payments", tot)
st.metric("Auto-applied", auto)
st.metric("Needs review", needs)

st.subheader("Exceptions by reason code (latest proposal per payment)")
rows = fetch_all("""
  WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY payment_id ORDER BY confidence DESC, proposal_rank ASC) rn
    FROM match_proposals
  )
  SELECT reason_code, COUNT(*) AS c
  FROM ranked
  WHERE rn = 1
  GROUP BY reason_code
  ORDER BY c DESC
""")
st.dataframe(rows, use_container_width=True)
