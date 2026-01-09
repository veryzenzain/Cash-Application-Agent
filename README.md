# Cash Application Agent Sandbox (Python, Streamlit, SQLite)

Application workflow: 

- ingest an incoming payment and remittance text
- propose invoice allocations with a confidence score
- route uncertain items to an exception and review queue
- Automatically generate emails via AI for remittance requests
- record every action in an audit log.

> Cash application matches an incoming customer payment to the correct customer account and corresponding invoice.

## demo: 
loom.com/share/e5f2d407bcc3428ca80a92414b552898


<img width="1470" height="507" alt="Screenshot 2026-01-08 at 12 04 56 PM" src="https://github.com/user-attachments/assets/e92306c7-4d74-4b28-b0c8-190ed3e411bf" />

<img width="1465" height="485" alt="Screenshot 2026-01-08 at 12 05 06 PM" src="https://github.com/user-attachments/assets/65222404-2842-4fd2-911e-d6bfb6b7a5df" />

<img width="1470" height="639" alt="Screenshot 2026-01-08 at 12 04 50 PM" src="https://github.com/user-attachments/assets/bc976ce9-8295-48f6-9792-0eb038f21966" />

<img width="1470" height="350" alt="Screenshot 2026-01-08 at 12 05 13 PM" src="https://github.com/user-attachments/assets/2e73b504-94b1-41f1-9fcf-9be024e71a8c" />

<img width="1470" height="392" alt="Screenshot 2026-01-08 at 12 05 19 PM" src="https://github.com/user-attachments/assets/3ca7cd1b-dfb0-4537-8d93-b89cbdb50cfa" />

## Tech stack

- **Streamlit** multipage app via the `pages/` directory.
- **SQLite** file-backed DB (`data/demo.db`) for demo persistence.

## Run it

```bash
pip install -r requirements.txt
python -m scripts.generate_demo_data
streamlit run app.py
```

## Project structure

```text
cashapp-agent/
  app.py
  pages/
    1_Payment_Inbox.py
    2_Payment_Review.py
    3_Audit_Log.py
    4_Metrics.py
  core/
    matching.py
    remittance.py
    reason_codes.py
    ai_client.py
    utils.py
  db/
    db.py
    schema.sql
  scripts/
    generate_demo_data.py
  data/              # created at runtime (demo.db)
  requirements.txt
  README.md
