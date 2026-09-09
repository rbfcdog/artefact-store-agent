
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Callable

from emporio import store
from emporio.policies import load_manual, normalize_text

def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    user, domain = email.split("@", 1)
    head = user[:2]
    return f"{head}{'*' * max(len(user) - 2, 1)}@{domain}"

def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    return phone[:4] + "*" * (len(phone) - 8) + phone[-4:]

def _product_brief(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_id": p["product_id"],
        "name": p["name"],
        "category": p["category"],
        "price_brl": p["price_brl"],
        "promo": p["promo"],
        "stock_quantity": p["stock_quantity"],
        "status": p["status"],
    }

def _product_full(p: dict[str, Any]) -> dict[str, Any]:
    specs = None
    if p.get("specs"):
        try:
            specs = json.loads(p["specs"])
        except (TypeError, ValueError):
            specs = p["specs"]
    return {**_product_brief(p), "description": p["description"], "specs": specs}

def _customer_payload(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "customer_id": c["customer_id"],
        "name": c["name"],
        "city": c["city"],
        "phone": _mask_phone(c["phone"]),
        "email": _mask_email(c["email"]),
    }

def _order_payload(o: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": o["order_id"],
        "customer_name": o["customer_name"],
        "order_date": o["order_date"],
        "status": o["status"],
        "total_brl": o["total_brl"],
        "payment_method": o["payment_method_label"],
        "tracking_code": o["tracking_code"],
        "estimated_delivery": o["estimated_delivery"],
        "deadlines": o["deadlines"],
        "deadlines_note": o["deadlines_note"],
        "items": [{"quantity": i["quantity"], "name": i["name"],
                   "price_brl": i["price_brl"]} for i in o["items"]],
        "notes": o["notes"],
    }

def _promo_payload(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": p["product_name"],
        "promo_name": p["description"],
        "original_price_brl": p["price_brl"],
        "discount_percent": p["discount_percent"],
        "promo_price_brl": p["promo_price_brl"],
    }

def _promos_for(con: sqlite3.Connection, query: str | None) -> list[dict[str, Any]]:
    promos = store.active_promotions(con)
    if not query:
        return [_promo_payload(p) for p in promos]
    key = normalize_text(query)
    terms = [t for t in re.findall(r"\w+", key) if len(t) >= 4]
    if not terms:
        return [_promo_payload(p) for p in promos]
    picked = [p for p in promos
              if any(t in normalize_text(p["product_name"]) for t in terms)]
    return [_promo_payload(p) for p in picked]

def _orders(con: sqlite3.Connection, **kw) -> list[dict[str, Any]]:
    return [_order_payload(o) for o in store.get_orders(con, **kw)]

def _customer_with_orders(con: sqlite3.Connection, customers: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if customers:
        out["clientes"] = [_customer_payload(c) for c in customers]
        orders: list[dict[str, Any]] = []
        for c in customers:
            orders += _orders(con, customer_id=c["customer_id"])
        if orders:
            out["pedidos"] = orders
    return out

def _search_store(
    con: sqlite3.Connection,
    query: str | None = None,
    entity: str = "auto",
    max_price: float | None = None,
    min_price: float | None = None,
    in_stock_only: bool = False,
    limit: int = 6,
) -> dict[str, Any]:
    q = (query or "").strip()
    digits = re.sub(r"\D", "", q)
    tracking = q if re.fullmatch(r"[A-Za-z0-9]{10,}", q) else None
    out: dict[str, Any] = {}

    def add_products():
        hits = store.search_products(
            con,
            query=q or None,
            max_price=max_price,
            min_price=min_price,
            in_stock_only=bool(in_stock_only),
            limit=int(limit),
        )
        if hits:
            terms = [t for t in re.findall(r"\w+", normalize_text(q)) if len(t) >= 2]
            covering = [h for h in hits
                        if terms and all(t in normalize_text(h["name"]) for t in terms)]
            payloads = []
            for p in hits:
                full = len(hits) == 1 or (len(covering) == 1
                                          and p["product_id"] == covering[0]["product_id"])
                payloads.append(_product_full(p) if full else _product_brief(p))
            out["produtos"] = payloads
        promos = _promos_for(con, q or None)
        if promos and q:
            out["promocoes"] = promos

    def find_customers():
        return store.find_customer(
            con,
            phone=q,
            email=q if "@" in q else None,
            name=q,
        )

    if entity == "produtos":
        add_products()
    elif entity == "promocoes":
        out["promocoes"] = _promos_for(con, q or None)
    elif entity == "clientes":
        out.update(_customer_with_orders(con, find_customers()))
    elif entity == "pedidos":
        if q.isdigit():
            out["pedidos"] = _orders(con, order_id=int(q))
        elif tracking:
            out["pedidos"] = _orders(con, tracking_code=tracking.upper())
        else:
            out.update(_customer_with_orders(con, find_customers()))
    else:
        if "@" in q:
            out.update(_customer_with_orders(con, store.find_customer(con, email=q)))
        elif len(digits) >= 8:
            out.update(_customer_with_orders(con, store.find_customer(con, phone=q)))
        elif q.isdigit():
            out["pedidos"] = _orders(con, order_id=int(q))
        elif tracking:
            out["pedidos"] = _orders(con, tracking_code=tracking.upper())
        elif len(q) >= 5 and (customers := find_customers()):
            out.update(_customer_with_orders(con, customers))
        else:
            add_products()

    if not out:
        out["aviso"] = ("nenhum resultado; tente outro termo, ou use load_context "
                        "para carregar o catálogo ou o manual completo")
    return out

def _load_context(
    con: sqlite3.Connection,
    source: str,
    section: str | None = None,
) -> dict[str, Any]:
    if source == "manual":
        return load_manual(con, section=section)
    if source == "catalogo":
        if section:
            rows = store.search_products(con, category=section, limit=100)
            return {"categoria": section,
                    "produtos": [_product_brief(p) for p in rows],
                    "total": len(rows)}
        return {"categorias": store.list_categories(con)}
    if source == "promocoes":
        return {"promocoes": _promos_for(con, None)}
    return {"error": f"fonte desconhecida: {source}"}

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_store",
            "description": (
                "Busca determinística por palavra-chave nos dados da loja (planilhas: produtos, "
                "pedidos, clientes, promoções). Detecta sozinha o tipo de consulta: nome de produto "
                "ou categoria, telefone, e-mail, número de pedido, código de rastreamento ou nome de "
                "cliente. Preços são sempre efetivos (promoção vigente aplicada). "
                "Use para TODA pergunta sobre preço, estoque, pedido, cliente ou promoção."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Termo da busca: produto, categoria, telefone, e-mail, nº do pedido, rastreio ou nome"},
                    "entity": {"type": "string", "enum": ["auto", "produtos", "pedidos", "clientes", "promocoes"],
                               "description": "Força o tipo de dado quando a detecção automática não servir"},
                    "max_price": {"type": "number", "description": "Preço máximo em R$ (filtro de produto)"},
                    "min_price": {"type": "number", "description": "Preço mínimo em R$ (filtro de produto)"},
                    "in_stock_only": {"type": "boolean", "description": "True para apenas itens em estoque"},
                    "limit": {"type": "integer", "description": "Máximo de produtos no resultado (padrão 6)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_context",
            "description": (
                "Carrega informação completa na janela de contexto (sem busca por similaridade): "
                "manual de políticas inteiro ou por seção (texto integral), catálogo de uma categoria "
                "com todos os produtos e preços, ou a lista de promoções vigentes. "
                "Use para TODA pergunta sobre regras da loja (trocas, devolução, frete, pagamento, "
                "garantia, horários, endereço) e para listar categorias."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "enum": ["manual", "catalogo", "promocoes"]},
                    "section": {"type": "string", "description": "Seção do manual (número como '4'/'4.2' ou palavra-chave como 'devolução') ou nome da categoria"},
                },
                "required": ["source"],
            },
        },
    },
]

_DISPATCH: dict[str, Callable[..., Any]] = {
    "search_store": _search_store,
    "load_context": _load_context,
}

def run_tool(con: sqlite3.Connection, name: str, arguments: str | None = None) -> Any:
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"ferramenta desconhecida: {name}"}
    try:
        kwargs = json.loads(arguments) if arguments else {}
        return fn(con, **kwargs)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
