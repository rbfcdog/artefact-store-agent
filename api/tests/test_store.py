
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

def test_product_catalog(con):
    # Products linked to categories and FTS populated
    assert con.execute("SELECT COUNT(*) FROM products WHERE category_id IS NULL").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM products_fts").fetchone()[0] == con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    
    # Search under 1000
    hits = store.search_products(con, query="violao", max_price=1000, in_stock_only=True)
    assert hits, "FTS must find violões from the accent-free query 'violao'"
    
    # Get by fuzzy name
    p = store.get_product(con, name="Takamine GD20")
    assert p["name"].startswith("Takamine GD20")
    
    # Promo carries original price and discount
    p_promo = store.get_product(con, name="Taylor 110e")
    assert p_promo["promo"]["promo_price_brl"] < p_promo["price_brl"]
    assert 0 < p_promo["promo"]["discount_percent"] < 100

def test_customer_orders(con):
    # Find by phone
    hits = store.find_customer(con, phone="99812-3456")
    assert hits[0]["name"] == "Lucas Mendes da Silva"
    
    # Order deadlines computed
    delivered = store.get_orders(con, order_id=4)[0]
    assert delivered["deadlines"]["arrependimento_7d_expirado"] is True
    assert "EXPIRADOS" in delivered["deadlines"]["caminho_sugerido"]
    
    shipped = store.get_orders(con, order_id=8)[0]
    assert shipped["deadlines"] is None
    assert "recebimento" in shipped["deadlines_note"]
    
    # Join items
    orders = store.get_orders(con, order_id=1)
    assert orders[0]["items"], "order must include product names"
    assert orders[0]["payment_method_label"] == "PIX"
