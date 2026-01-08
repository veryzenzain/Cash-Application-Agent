import streamlit as st
from db.db import ensure_db_initialized

st.set_page_config(page_title="AR Cash Application Agent", layout="wide")
ensure_db_initialized()

st.title("AR Cash Application Agent")
st.caption("Agent loop: match → propose → approve → audit trail.")

st.markdown("""
**Demo flow**
1) Go to Payment Inbox → pick a payment  
2) Review agent proposals (confidence, reason code & explanation)  
3) Approve / Reject / Request remittance (writes to Audit Log)  
""")

