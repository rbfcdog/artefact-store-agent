
from __future__ import annotations

import csv
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from emporio.config import DATA_DIR, DB_PATH, STORE_TZ

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id     INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    category_id    INTEGER REFERENCES categories,
    price_brl      REAL NOT NULL,
    description    TEXT,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL,
    specs          TEXT,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    city        TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    order_id           INTEGER PRIMARY KEY,
    customer_id        INTEGER REFERENCES customers,
    order_date         TEXT,
    status             TEXT,
    total_brl          REAL,
    payment_method     TEXT,
    tracking_code      TEXT,
    estimated_delivery TEXT,
    notes              TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id   INTEGER REFERENCES orders,
    product_id INTEGER REFERENCES products,
    quantity   INTEGER
);

CREATE TABLE IF NOT EXISTS promotions (
    promotion_id     INTEGER PRIMARY KEY,
    product_id       INTEGER REFERENCES products,
    discount_percent REAL,
    description      TEXT,
    is_active        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id INTEGER PRIMARY KEY,
    section  TEXT NOT NULL,
    text     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS products_fts USING fts5(
    name, description, category,
    content='',  -- contentless: rebuilt on every load, tiny dataset
    tokenize='unicode61 remove_diacritics 2'
);


CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""

_PROMO_JOIN = """
LEFT JOIN (
    SELECT product_id, MAX(discount_percent) AS discount_percent, description AS promo_name
    FROM promotions
    WHERE is_active = 1
    GROUP BY product_id
) promo ON promo.product_id = p.product_id
"""

_PRODUCT_SELECT = f"""
SELECT p.product_id, p.name, p.price_brl, p.stock_quantity, p.status,
       p.description, p.specs, c.name AS category,
       promo.discount_percent, promo.promo_name
FROM products p
JOIN categories c ON c.category_id = p.category_id
{_PROMO_JOIN}
"""

PAYMENT_LABELS = {
    "pix": "PIX",
    "debit": "Cartão de Débito",
    "boleto": "Boleto Bancário",
}

def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con

def _read_csv(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / name
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            {k: (v.strip() or None) for k, v in row.items()}
            for row in csv.DictReader(fh)
        ]

def _int(value: Any) -> int | None:
    return int(value) if value not in (None, "") else None

def _float(value: Any) -> float | None:
    return float(value) if value not in (None, "") else None

def load_operational_data(con: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("order_items", "orders", "promotions", "products",
                  "categories", "customers"):
        con.execute(f"DELETE FROM {table}")

    rows = _read_csv("desafio_tecnico_ai_eng - categories.csv")
    con.executemany(
        "INSERT INTO categories VALUES (:category_id, :name, :description)", rows)
    counts["categories"] = len(rows)

    rows = _read_csv("desafio_tecnico_ai_eng - products.csv")
    con.executemany(
        """INSERT INTO products (product_id, name, category_id, price_brl,
                                 description, stock_quantity, status, specs, created_at)
           VALUES (:product_id, :name, :category_id, :price_brl,
                   :description, :stock_quantity, :status, :specs, :created_at)""",
        [{**r,
          "product_id": _int(r["product_id"]),
          "category_id": _int(r["category_id"]),
          "price_brl": _float(r["price_brl"]),
          "stock_quantity": _int(r["stock_quantity"])} for r in rows])
    counts["products"] = len(rows)

    rows = _read_csv("desafio_tecnico_ai_eng - customers.csv")
    con.executemany("INSERT INTO customers VALUES (:customer_id, :name, :phone, :email, :city)", rows)
    counts["customers"] = len(rows)

    rows = _read_csv("desafio_tecnico_ai_eng - orders.csv")
    con.executemany(
        "INSERT INTO orders VALUES (:order_id, :customer_id, :order_date, :status, :total_brl, :payment_method, :tracking_code, :estimated_delivery, :notes)",
        [{**r,
          "order_id": _int(r["order_id"]),
          "customer_id": _int(r["customer_id"]),
          "total_brl": _float(r["total_brl"])} for r in rows])
    counts["orders"] = len(rows)

    rows = _read_csv("desafio_tecnico_ai_eng - order_items.csv")
    con.executemany(
        "INSERT INTO order_items VALUES (:order_id, :product_id, :quantity)",
        [{**r,
          "order_id": _int(r["order_id"]),
          "product_id": _int(r["product_id"]),
          "quantity": _int(r["quantity"])} for r in rows])
    counts["order_items"] = len(rows)

    rows = _read_csv("desafio_tecnico_ai_eng - promotions.csv")
    con.executemany(
        """INSERT INTO promotions VALUES (:promotion_id, :product_id, :discount_percent, :description, :is_active)""",
        [{**r,
          "promotion_id": _int(r["promotion_id"]),
          "product_id": _int(r["product_id"]),
          "discount_percent": _float(r["discount_percent"]),
          "is_active": _int(r["is_active"])} for r in rows])
    counts["promotions"] = len(rows)

    rebuild_products_fts(con)
    con.commit()
    return counts

def rebuild_products_fts(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS products_fts")
    con.execute(
        """CREATE VIRTUAL TABLE products_fts USING fts5(
               name, description, category,
               content='',
               tokenize='unicode61 remove_diacritics 2'
        )"""
    )
    con.execute(
        """INSERT INTO products_fts(rowid, name, description, category)
           SELECT p.product_id, p.name, p.description, c.name
           FROM products p JOIN categories c ON p.category_id = c.category_id"""
    )
    con.commit()

def rebuild_products_fts(con: sqlite3.Connection) -> None:
    con.execute("DROP TABLE IF EXISTS products_fts")
    con.execute(
        """CREATE VIRTUAL TABLE products_fts USING fts5(
               name, description, category,
               content='',
               tokenize='unicode61 remove_diacritics 2'
           )""")
    con.execute(
        """INSERT INTO products_fts(rowid, name, description, category)
           SELECT p.product_id, p.name, p.description, c.name
           FROM products p JOIN categories c ON c.category_id = p.category_id""")
    con.commit()

def _fts_tokens(query: str, fuzzy_stems: bool = False) -> str:
    tokens = re.findall(r"\w+", query, re.UNICODE)[:8]
    terms = []
    for t in tokens:
        terms.append(f"{t}*")
        if fuzzy_stems and len(t) > 6:
            terms.append(f"{t[:6]}*")
    return " OR ".join(dict.fromkeys(terms))

def _product_row(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    discount = out.pop("discount_percent")
    promo_name = out.pop("promo_name")
    base = out["price_brl"]
    if discount:
        out["promo"] = {
            "name": promo_name,
            "discount_percent": discount,
            "promo_price_brl": round(base * (1 - discount / 100), 2),
        }
    else:
        out["promo"] = None
    return out

def list_categories(con: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = con.execute(
        """SELECT c.category_id, c.name, c.description,
                  COUNT(p.product_id) AS product_count
           FROM categories c
           LEFT JOIN products p ON p.category_id = c.category_id AND p.status = 'active'
           GROUP BY c.category_id ORDER BY c.name""").fetchall()
    return [dict(r) for r in rows]

def search_products(
    con: sqlite3.Connection,
    query: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    in_stock_only: bool = False,
    include_discontinued: bool = False,
    limit: int = 6,
) -> list[dict[str, Any]]:
    where, params = [], []
    if not include_discontinued:
        where.append("p.status IN ('active', 'coming_soon')")
    else:
        where.append("1 = 1")
    if query and (tokens := _fts_tokens(query)):
        where.append(f"p.product_id IN (SELECT rowid FROM products_fts WHERE products_fts MATCH ?)")
        params.append(tokens)
    if category:
        where.append("LOWER(c.name) LIKE ?")
        params.append(f"%{category.lower()}%")
    if max_price is not None:
        where.append("p.price_brl <= ?")
        params.append(max_price)
    if min_price is not None:
        where.append("p.price_brl >= ?")
        params.append(min_price)
    if in_stock_only:
        where.append("p.stock_quantity > 0")

    sql = _PRODUCT_SELECT + f"WHERE {' AND '.join(where)} ORDER BY p.price_brl LIMIT {int(limit)}"
    return [_product_row(r) for r in con.execute(sql, params).fetchall()]

def get_product(
    con: sqlite3.Connection,
    product_id: int | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    if product_id is not None:
        row = con.execute(_PRODUCT_SELECT + "WHERE p.product_id = ?", (product_id,)).fetchone()
        if row:
            return _product_row(row)
    if name:
        tokens = _fts_tokens(name)
        row = con.execute(
            _PRODUCT_SELECT + "WHERE p.product_id IN "
            "(SELECT rowid FROM products_fts WHERE products_fts MATCH ?) LIMIT 1",
            (tokens,),
        ).fetchone()
        if row:
            return _product_row(row)
    return None

def _digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")

def find_customer(
    con: sqlite3.Connection,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> list[dict[str, Any]]:
    if phone and (digits := _digits(phone)):
        rows = con.execute("SELECT * FROM customers").fetchall()
        hits = [r for r in rows if digits in _digits(r["phone"])]
        if hits:
            return [dict(r) for r in hits]
    if email:
        rows = con.execute(
            "SELECT * FROM customers WHERE email = ? COLLATE NOCASE", (email,)).fetchall()
        if rows:
            return [dict(r) for r in rows]
    if name:
        rows = con.execute(
            "SELECT * FROM customers WHERE name LIKE ? COLLATE NOCASE",
            (f"%{name}%",)).fetchall()
        if rows:
            return [dict(r) for r in rows]
    return []

def payment_label(method: str | None) -> str:
    if not method:
        return "-"
    if method in PAYMENT_LABELS:
        return PAYMENT_LABELS[method]
    m = re.match(r"credit_(\d+)x", method)
    return f"Cartão de Crédito {m.group(1)}x" if m else method

def get_orders(
    con: sqlite3.Connection,
    order_id: int | None = None,
    tracking_code: str | None = None,
    customer_id: int | None = None,
) -> list[dict[str, Any]]:
    if order_id is not None:
        cond, params = "o.order_id = ?", (order_id,)
    elif tracking_code:
        cond, params = "o.tracking_code = ? COLLATE NOCASE", (tracking_code.strip(),)
    elif customer_id is not None:
        cond, params = "o.customer_id = ?", (customer_id,)
    else:
        return []

    orders = con.execute(
        f"""SELECT o.*, c.name AS customer_name, c.phone AS customer_phone
            FROM orders o JOIN customers c ON c.customer_id = o.customer_id
            WHERE {cond} ORDER BY o.order_date DESC""", params).fetchall()

    today = datetime.now(ZoneInfo(STORE_TZ)).date()

    result = []
    for o in orders:
        items = con.execute(
            """SELECT oi.quantity, p.product_id, p.name, p.price_brl, p.stock_quantity
               FROM order_items oi JOIN products p ON p.product_id = oi.product_id
               WHERE oi.order_id = ?""", (o["order_id"],)).fetchall()
        result.append({
            **dict(o),
            "payment_method_label": payment_label(o["payment_method"]),
            "items": [dict(i) for i in items],
            **_policy_deadlines(o, today),
        })
    return result

def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None

def _policy_deadlines(order: sqlite3.Row, today: date) -> dict[str, Any]:
    if order["status"] != "delivered":
        return {"deadlines": None,
                "deadlines_note": ("pedido não consta como entregue; prazos de "
                                   "troca/devolução correm a partir do recebimento")}
    ref = _parse_date(order["estimated_delivery"]) or _parse_date(order["order_date"])
    if ref is None:
        return {"deadlines": None, "deadlines_note": "data de entrega indisponível"}
    repentance_end = ref + timedelta(days=7)
    defect_end = ref + timedelta(days=30)
    if today > defect_end:
        caminho = ("prazos de arrependimento (7d) e troca por defeito (30d) EXPIRADOS; "
                   "orientar garantia junto ao fabricante via certificado do produto, "
                   "com a loja intermediando mediante solicitação (§4.2)")
    elif today > repentance_end:
        caminho = ("arrependimento (7d) expirado, mas troca por defeito ainda possível "
                   "até a data indicada (§4.2)")
    else:
        caminho = "direito de arrependimento (7d) e troca por defeito (30d) vigentes (§4.1/§4.2)"
    return {
        "deadlines": {
            "referencia": f"entrega estimada em {ref.strftime('%d/%m/%Y')}",
            "arrependimento_7d_ate": repentance_end.strftime("%d/%m/%Y"),
            "arrependimento_7d_expirado": today > repentance_end,
            "troca_defeito_30d_ate": defect_end.strftime("%d/%m/%Y"),
            "troca_defeito_30d_expirado": today > defect_end,
            "caminho_sugerido": caminho,
            "hoje": today.strftime("%d/%m/%Y"),
        },
        "deadlines_note": None,
    }

def active_promotions(con: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = con.execute(
        f"""SELECT pr.promotion_id, pr.description, pr.discount_percent,
                   p.product_id, p.name AS product_name, p.price_brl
            FROM promotions pr
            JOIN products p ON p.product_id = pr.product_id
            WHERE pr.is_active = 1
            ORDER BY pr.discount_percent DESC""").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["promo_price_brl"] = round(d["price_brl"] * (1 - d["discount_percent"] / 100), 2)
        out.append(d)
    return out
