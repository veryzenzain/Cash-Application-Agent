from core.remittance import extract_signals

def test_extract_invoice_numbers():
    s = extract_signals("Payment for INV-1042 and INV 1043. Total $1,200.00")
    assert "INV-1042" in s.invoice_nos
    assert "INV1043" in s.invoice_nos or "INV-1043" in s.invoice_nos
    assert s.has_text is True
