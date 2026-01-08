from db.db import ensure_db_initialized
from scripts.generate_demo_data import main as seed
from core.matching import build_proposals

def test_build_proposals_runs():
    ensure_db_initialized()
    seed()
    props = build_proposals(1)
    assert len(props) >= 1
    assert 0.0 <= props[0].confidence <= 0.99
