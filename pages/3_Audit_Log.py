import streamlit as st
from db.db import fetch_all

st.title("Audit Log")
st.caption("Append-only events.")

rows = fetch_all(
    "SELECT * FROM audit_events ORDER BY created_at DESC, id DESC LIMIT 400"
)

st.dataframe(
    [{
        "time": r["created_at"],
        "actor": r["actor"],
        "entity": f"{r['entity_type']}:{r['entity_id']}",
        "action": r["action"],
        "before": r["before_json"],
        "after": r["after_json"],
    } for r in rows],
    use_container_width=True,
)
