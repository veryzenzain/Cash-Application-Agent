from __future__ import annotations

import random
from datetime import date, timedelta

from db.db import executemany, execute, fetch_one, ensure_db_initialized

random.seed(7)

def cents(dollars: float) -> int:
    return int(round(dollars * 100))

def main():
    ensure_db_initialized()

    # wipe tables
    execute("DELETE FROM audit_events")
    execute("DELETE FROM decisions")
    execute("DELETE FROM match_proposals")
    execute("DELETE FROM payments")
    execute("DELETE FROM invoices")
    execute("DELETE FROM customers")

    # customers with parent child struct
    cust_ids = {}
    cust_ids["Kencor Holdings"] = execute("INSERT INTO customers(name, parent_customer_id) VALUES(?,NULL)", ("Kencor Holdings",))
    cust_ids["Kencor West"] = execute("INSERT INTO customers(name, parent_customer_id) VALUES(?,?)", ("Kencor West", cust_ids["Kencor Holdings"]))
    cust_ids["Kencor East"] = execute("INSERT INTO customers(name, parent_customer_id) VALUES(?,?)", ("Kencor East", cust_ids["Kencor Holdings"]))

    cust_ids["Delta Star Manufacturing"] = execute("INSERT INTO customers(name, parent_customer_id) VALUES(?,NULL)", ("Delta Star Manufacturing",))
    cust_ids["Delta Star Parts"] = execute("INSERT INTO customers(name, parent_customer_id) VALUES(?,?)", ("Delta Star Parts", cust_ids["Delta Star Manufacturing"]))

    cust_ids["Regus Retail"] = execute("INSERT INTO customers(name, parent_customer_id) VALUES(?,NULL)", ("Regus Retail",))

    # invoices
    today = date.today()
    invoice_rows = []
    inv_no = 1000

    def add_invoices(customer_name: str, n: int):
        nonlocal inv_no
        cid = cust_ids[customer_name]
        for _ in range(n):
            inv_no += 1
            amt = random.choice([1250, 1800, 2400, 3100, 5200, 7900, 12000]) / 10.0
            due = today + timedelta(days=random.randint(-45, 30))
            invoice_rows.append((
                cid,
                f"INV-{inv_no}",
                f"PO-{random.randint(100,999)}",
                cents(amt),
                due.isoformat(),
                "OPEN",
            ))

    add_invoices("Kencor West", 30)
    add_invoices("Kencor East", 25)
    add_invoices("Delta Star Parts", 20)
    add_invoices("Regus Retail", 20)

    executemany(
        "INSERT INTO invoices(customer_id, invoice_no, po_no, amount_due_cents, due_date, status) VALUES(?,?,?,?,?,?)",
        invoice_rows,
    )

    # pick random open invoice
    def pick_invoices(prefix: str, k: int):
        all_invs = []
        from db.db import fetch_all
        all_invs = fetch_all("SELECT * FROM invoices WHERE status='OPEN'")
        chosen = random.sample(all_invs, k)
        return chosen

    payment_rows = []

    #exact multi invoice parent payer
    invs = pick_invoices("", 2)
    amt = sum(int(i["amount_due_cents"]) for i in invs)
    rem = f"Payment for {invs[0]['invoice_no']}, {invs[1]['invoice_no']} (Kencor Holdings)"
    payment_rows.append(("Kencor Holdings", None, amt, today.isoformat(), "ACH", rem, "NEEDS_REVIEW"))

    #partial payment
    invs = pick_invoices("", 1)
    amt = int(invs[0]["amount_due_cents"] * 0.6)
    rem = f"Partial for {invs[0]['invoice_no']} - will pay remainder next week"
    payment_rows.append(("Delta Star Manufacturing", None, amt, (today - timedelta(days=1)).isoformat(), "WIRE", rem, "NEEDS_REVIEW"))

    #missing remittance
    payment_rows.append(("Regus Retail", None, cents(520.00), (today - timedelta(days=2)).isoformat(), "CHECK", "", "NEEDS_REVIEW"))

    #amount match
    invs = pick_invoices("", 1)
    amt = int(invs[0]["amount_due_cents"])
    rem = "March invoice payment - thanks"
    payment_rows.append(("Kencor West", None, amt, (today - timedelta(days=3)).isoformat(), "ACH", rem, "NEEDS_REVIEW"))

    #mixed  payments
    payers = ["Kencor Holdings", "Kencor West", "Kencor East", "Delta Star Manufacturing", "Delta Star Parts", "Regus Retail"]
    methods = ["ACH", "WIRE", "CHECK"]
    for i in range(16):
        payer = random.choice(payers)
        inv_count = random.choice([1, 1, 2, 3])
        invs = pick_invoices("", inv_count)
        total = sum(int(x["amount_due_cents"]) for x in invs)
        # some noise,edge cases
        kind = random.choice(["clean", "no_inv", "partial", "overpay"])
        if kind == "clean":
            rem = "Payment for " + ", ".join([x["invoice_no"] for x in invs])
            amt = total
        elif kind == "no_inv":
            rem = "Invoice payment"
            amt = total
        elif kind == "partial":
            rem = f"Partial payment for {invs[0]['invoice_no']}"
            amt = int(total * random.choice([0.5, 0.7, 0.8]))
        else:  # overpay
            rem = "Payment for " + ", ".join([x["invoice_no"] for x in invs]) + " incl. credit adj"
            amt = int(total * 1.1)

        payment_rows.append((payer, None, amt, (today - timedelta(days=4+i)).isoformat(), random.choice(methods), rem, "NEEDS_REVIEW"))

    executemany(
        "INSERT INTO payments(payer_name, customer_id, amount_cents, received_date, method, remittance_text, status) VALUES(?,?,?,?,?,?,?)",
        payment_rows,
    )

    print("Seeded demo.db with customers, invoices, payments.")


if __name__ == "__main__":
    main()
