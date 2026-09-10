
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio import store
from emporio.config import POLICY_PDF
from emporio.policies import load_policy_chunks
from emporio.tools import run_tool

@pytest.fixture()
def con(tmp_path):
    db = store.connect(tmp_path / "tools.db")
    store.load_operational_data(db)
    load_policy_chunks(db, POLICY_PDF)
    return db

def test_search_store_capabilities(con):
    # Auto-detects product query
    out = run_tool(con, "search_store", '{"query": "Takamine GD20"}')
    gd20 = next(p for p in out["produtos"] if p["name"].startswith("Takamine GD20"))
    assert gd20["price_brl"] == 2199.0
    
    # Phone and mask contact
    out = run_tool(con, "search_store", '{"query": "(67) 99812-3456"}')
    customer = out["clientes"][0]
    assert customer["name"] == "Lucas Mendes da Silva"
    assert "*" in customer["phone"]
    delivered = next(o for o in out["pedidos"] if o["deadlines"])
    assert delivered["deadlines"]["arrependimento_7d_expirado"] is True
    
    # Price filter
    out = run_tool(con, "search_store", '{"query": "violão", "max_price": 600}')
    assert all(p["price_brl"] <= 600 for p in out["produtos"])
    
    # Order by number
    out = run_tool(con, "search_store", '{"query": "8"}')
    assert out["pedidos"][0]["order_id"] == 8

def test_load_context_capabilities(con):
    # Manual by section
    out = run_tool(con, "load_context", '{"source": "manual", "section": "4"}')
    body = "\n".join(s["texto"] for s in out["secoes"])
    assert "arrependimento" in body.lower()
    
    # Unknown section lists available
    out = run_tool(con, "load_context", '{"source": "manual", "section": "xpto"}')
    assert out["secoes"] == []
    assert out["secoes_disponiveis"]
    
    # Keyword hits body
    out = run_tool(con, "load_context", '{"source": "manual", "section": "endereço"}')
    assert out["secoes"]
    
    # Catalogo full index
    out = run_tool(con, "load_context", '{"source": "catalogo"}')
    assert len(out["produtos"]) >= 60
    
    # Promocoes
    out = run_tool(con, "load_context", '{"source": "promocoes"}')
    assert out["promocoes"]
    assert out["promocoes"][0]["promo_price_brl"] < out["promocoes"][0]["original_price_brl"]
