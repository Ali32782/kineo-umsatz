"""Regression: /api/ytd must load umsatz rows before building umsatz_map."""
from pathlib import Path


def test_get_ytd_queries_umsatz_before_map():
    source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text()
    start = source.index("def get_ytd(")
    end = source.index("\n@app.", start)
    block = source[start:end]
    assert "umsatz_all = db.query(UmsatzData)" in block
    idx_query = block.index("umsatz_all = db.query(UmsatzData)")
    idx_map = block.index("umsatz_map = {(r.ma_name, r.month): r.umsatz for r in umsatz_all}")
    assert idx_query < idx_map
