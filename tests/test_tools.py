
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

def test_auto_detects_product_query(con):
    out = run_tool(con, "search_store", '{"query": "Takamine GD20"}')
    gd20 = next(p for p in out["produtos"] if p["name"].startswith("Takamine GD20"))
    assert gd20["price_brl"] == 2199.0
    assert gd20["description"]
    assert gd20["specs"]

def test_auto_detects_phone_and_masks_contact(con):
    out = run_tool(con, "search_store", '{"query": "(67) 99812-3456"}')
    customer = out["clientes"][0]
    assert customer["name"] == "Lucas Mendes da Silva"
    assert "*" in customer["phone"]
    orders = out["pedidos"]
    assert orders
    delivered = next(o for o in orders if o["deadlines"])
    assert delivered["deadlines"]["arrependimento_7d_expirado"] is True
    assert "EXPIRADOS" in delivered["deadlines"]["caminho_sugerido"]

def test_price_filter_is_deterministic(con):
    out = run_tool(con, "search_store", '{"query": "violão", "max_price": 600}')
    prices = [p["price_brl"] for p in out["produtos"]]
    assert prices
    assert all(p <= 600 for p in prices)

def test_order_by_number(con):
    out = run_tool(con, "search_store", '{"query": "8"}')
    assert out["pedidos"][0]["order_id"] == 8
    assert out["pedidos"][0]["deadlines"] is None
    assert "recebimento" in out["pedidos"][0]["deadlines_note"]

def test_load_manual_section_by_number(con):
    out = run_tool(con, "load_context", '{"source": "manual", "section": "4"}')
    titles = " ".join(s["secao"] for s in out["secoes"])
    assert "Trocas" in titles or "Devolu" in titles
    body = "\n".join(s["texto"] for s in out["secoes"])
    assert "arrependimento" in body.lower()

def test_load_manual_unknown_section_lists_available(con):
    out = run_tool(con, "load_context", '{"source": "manual", "section": "xpto"}')
    assert out["secoes"] == []
    assert out["secoes_disponiveis"]

def test_load_manual_full(con):
    out = run_tool(con, "load_context", '{"source": "manual"}')
    assert len(out["secoes"]) >= 8

def test_load_manual_keyword_hits_body_text(con):
    out = run_tool(con, "load_context", '{"source": "manual", "section": "endereço"}')
    assert out["secoes"]
    body = "\n".join(s["texto"] for s in out["secoes"])
    assert "14 de maio" in body.lower()

def test_load_catalogo_full_index(con):
    out = run_tool(con, "load_context", '{"source": "catalogo"}')
    assert out["categorias"]
    assert len(out["produtos"]) >= 60
    assert all({"nome", "categoria", "preco_brl"} <= set(p) for p in out["produtos"])
    names = " ".join(p["nome"].lower() for p in out["produtos"])
    assert "takamine" in names

def test_partial_product_match_warns_to_load_catalog(con):
    out = run_tool(con, "search_store", '{"query": "Yamaha Stratocaster"}')
    assert out["produtos"]
    assert all("Yamaha" in p["name"] for p in out["produtos"])
    assert all("Stratocaster" not in p["name"] for p in out["produtos"])
    assert "catálogo" in out["aviso"]

def test_load_promocoes(con):
    out = run_tool(con, "load_context", '{"source": "promocoes"}')
    assert out["promocoes"]
    assert out["promocoes"][0]["promo_price_brl"] < out["promocoes"][0]["original_price_brl"]
