
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio import policies, store
from emporio.config import POLICY_PDF

@pytest.fixture(scope="module")
def con():
    con = store.connect(":memory:")
    store.load_operational_data(con)
    policies.load_policy_chunks(con, POLICY_PDF)
    yield con
    con.close()

def test_products_linked_to_categories(con):
    n = con.execute(
        "SELECT COUNT(*) FROM products WHERE category_id IS NULL").fetchone()[0]
    assert n == 0
    assert con.execute("SELECT COUNT(*) FROM products_fts").fetchone()[0] == \
        con.execute("SELECT COUNT(*) FROM products").fetchone()[0]

def test_search_violao_under_1000(con):
    hits = store.search_products(con, query="violao", max_price=1000, in_stock_only=True)
    assert hits, "FTS must find violões from the accent-free query 'violao'"
    assert "Violões" in {p["category"] for p in hits}

def test_get_product_by_fuzzy_name(con):
    p = store.get_product(con, name="Takamine GD20")
    assert p is not None
    assert p["name"].startswith("Takamine GD20")
    assert p["stock_quantity"] >= 0

def test_promo_carries_original_price_and_discount(con):
    p = store.get_product(con, name="Taylor 110e")
    assert p and p["promo"], "Taylor 110e has an active promotion in the dataset"
    assert p["promo"]["promo_price_brl"] < p["price_brl"]
    assert 0 < p["promo"]["discount_percent"] < 100

def test_find_customer_by_partial_phone(con):
    hits = store.find_customer(con, phone="99812-3456")
    assert [c["customer_id"] for c in hits] == [1]
    assert hits[0]["name"] == "Lucas Mendes da Silva"

def test_order_deadlines_computed_not_guessed(con):
    delivered = store.get_orders(con, order_id=4)[0]
    d = delivered["deadlines"]
    assert d is not None
    assert d["arrependimento_7d_expirado"] is True
    assert d["troca_defeito_30d_expirado"] is True
    assert "EXPIRADOS" in d["caminho_sugerido"]

    shipped = store.get_orders(con, order_id=8)[0]
    assert shipped["deadlines"] is None
    assert "recebimento" in shipped["deadlines_note"]

def test_orders_join_items_and_payment_label(con):
    orders = store.get_orders(con, order_id=1)
    assert len(orders) == 1
    o = orders[0]
    assert o["items"], "order must include product names"
    assert o["payment_method_label"] == "PIX"

