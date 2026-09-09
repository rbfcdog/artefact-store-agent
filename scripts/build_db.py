
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emporio import store
from emporio.config import DB_PATH, POLICY_PDF
from emporio.policies import load_policy_chunks

def main() -> None:
    if not POLICY_PDF.exists():
        raise SystemExit(f"policy manual not found: {POLICY_PDF}")
    con = store.connect(DB_PATH)
    counts = store.load_operational_data(con)
    counts["policy_chunks"] = load_policy_chunks(con, POLICY_PDF)
    print(f"built {DB_PATH}")
    for table, n in counts.items():
        print(f"  {table:>16}: {n}")
    active = store.active_promotions(con)
    print(f"  {'active promos':>16}: {len(active)}")
    for p in active:
        print(f"    - {p['product_name']}: -{p['discount_percent']}% "
              f"(R$ {p['price_brl']:.2f} → R$ {p['promo_price_brl']:.2f})")

if __name__ == "__main__":
    main()
