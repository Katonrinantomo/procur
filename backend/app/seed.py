"""
Seed script for Procur.AI demo data.

Usage:
    python -m app.seed --reset              # wipe and recreate everything
    python -m app.seed --reset --empty-today  # skip today's 5 demo requests
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine
from app.models import (
    Action,
    Base,
    Flag,
    Item,
    Purchase,
    Request,
    RequestItem,
    Stock,
    Supplier,
    WebQuote,
)

# Fixed random seed so every run is identical.
RNG = random.Random(42)

# ---------------------------------------------------------------------------
# Jakarta timezone (UTC+7) — "today" is Jakarta today.
# ---------------------------------------------------------------------------
JAKARTA = timezone(timedelta(hours=7))


def now_jkt() -> datetime:
    return datetime.now(tz=JAKARTA)


def today_jkt() -> date:
    return now_jkt().date()


def jkt(d: date, hour: int = 0, minute: int = 0) -> datetime:
    """Return a timezone-aware datetime in Asia/Jakarta for the given date."""
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=JAKARTA)


# ---------------------------------------------------------------------------
# Static catalogue  (name, category, unit, aliases)
# ---------------------------------------------------------------------------
CATALOG: list[tuple[str, str, str, list[str]]] = [
    # spare parts (10)
    (
        "Hydraulic oil ISO VG 46, 20L",
        "lubricants",
        "drum",
        ["oli hidrolik 46", "hydraulic oil 46", "oli hidrolik 46 20L", "oli hidrolik iso vg 46"],
    ),
    (
        "Bearing 6205 ZZ",
        "spare parts",
        "pcs",
        ["bearing 6205", "laher 6205", "bearing 6205zz"],
    ),
    (
        "Bearing 6206 ZZ",
        "spare parts",
        "pcs",
        ["bearing 6206", "laher 6206"],
    ),
    (
        "V-belt type B 51",
        "spare parts",
        "pcs",
        ["v belt b51", "vbelt b51", "sabuk v b51"],
    ),
    (
        "V-belt type A 42",
        "spare parts",
        "pcs",
        ["v belt a42", "sabuk v a42"],
    ),
    (
        "Oil seal 25x42x7",
        "spare parts",
        "pcs",
        ["seal 25x42x7", "seal oli 25x42"],
    ),
    (
        "O-ring 3x50",
        "spare parts",
        "pcs",
        ["oring 3x50", "o ring 3x50"],
    ),
    (
        "Bolt M10x30 SS",
        "spare parts",
        "pcs",
        ["baut m10x30", "bolt m10"],
    ),
    (
        "Filter element hydraulic HF6553",
        "spare parts",
        "pcs",
        ["filter hidrolik hf6553", "hydraulic filter 6553"],
    ),
    (
        "Coupling jaw element 28",
        "spare parts",
        "pcs",
        ["jaw coupling 28", "kopling 28"],
    ),
    # lubricants (6)
    (
        "Grease EP2 1kg",
        "lubricants",
        "kg",
        ["grease ep2", "gemuk ep2", "grease ep 2 1kg"],
    ),
    (
        "Gear oil SAE 90 20L",
        "lubricants",
        "drum",
        ["oli gear 90", "gear oil 90 20l", "oli gearbox 90"],
    ),
    (
        "Compressor oil 10W-40 4L",
        "lubricants",
        "botol",
        ["oli kompresor 10w40", "compressor oil 10w40"],
    ),
    (
        "Brake fluid DOT3 500ml",
        "lubricants",
        "botol",
        ["minyak rem dot3", "brake fluid dot 3"],
    ),
    (
        "Chain lubricant spray 400ml",
        "lubricants",
        "kaleng",
        ["pelumas rantai spray", "chain lube spray"],
    ),
    (
        "Penetrating oil WD-40 450ml",
        "lubricants",
        "kaleng",
        ["wd40", "wd 40 450ml", "penetrating oil"],
    ),
    # safety gear (8)
    (
        "Work gloves, cotton dotted",
        "safety gear",
        "doz",
        ["sarung tangan katun dot", "sarung tangan cotton dotted", "gloves dotted cotton"],
    ),
    (
        "Safety helmet MSA V-Gard",
        "safety gear",
        "pcs",
        ["helm safety msa", "safety helmet v gard"],
    ),
    (
        "Safety shoes 6\" boot",
        "safety gear",
        "pair",
        ["sepatu safety 6 inch", "safety boot 6in"],
    ),
    (
        "Safety glasses clear lens",
        "safety gear",
        "pcs",
        ["kacamata safety bening", "safety goggle clear"],
    ),
    (
        "Ear plug foam 3M 1100",
        "safety gear",
        "pair",
        ["ear plug 3m", "earplug foam 3m 1100"],
    ),
    (
        "Dust mask N95",
        "safety gear",
        "pcs",
        ["masker n95", "dust mask n95"],
    ),
    (
        "Safety vest reflective",
        "safety gear",
        "pcs",
        ["rompi safety", "vest reflective"],
    ),
    (
        "First aid kit medium",
        "safety gear",
        "set",
        ["kotak p3k medium", "first aid medium"],
    ),
    # packaging (8)
    (
        "Packing tape 48mm, clear",
        "packaging",
        "box",
        ["selotip 48mm bening", "packing tape clear 48", "tape 48mm clear"],
    ),
    (
        "Stretch film 500mm x 300m",
        "packaging",
        "roll",
        ["plastik wrapping 500mm", "stretch wrap 500mm"],
    ),
    (
        "Cardboard box 40x30x30",
        "packaging",
        "pcs",
        ["kardus 40x30x30", "carton box 40x30"],
    ),
    (
        "Bubble wrap roll 50cm",
        "packaging",
        "roll",
        ["bubble wrap 50cm", "plastik gelembung 50cm"],
    ),
    (
        "Polybag 30x40 0.05mm",
        "packaging",
        "kg",
        ["kantong plastik 30x40", "polybag 30x40"],
    ),
    (
        "Foam sheet 1m x 2m x 5mm",
        "packaging",
        "lembar",
        ["busa sheet 5mm", "foam sheet 5mm"],
    ),
    (
        "Label sticker 10x5cm",
        "packaging",
        "roll",
        ["stiker label 10x5", "label roll 10x5cm"],
    ),
    (
        "Ziplock bag 20x30",
        "packaging",
        "pack",
        ["plastik ziplock 20x30", "ziplock 20x30"],
    ),
    # office (8)
    (
        "A4 paper 80gsm, 1 ream",
        "office",
        "ream",
        ["kertas a4 80gr", "hvs a4 80gsm", "paper a4"],
    ),
    (
        "Ballpoint pen blue 12pcs",
        "office",
        "box",
        ["pulpen biru 12pcs", "ballpoint biru"],
    ),
    (
        "Staple no. 10",
        "office",
        "box",
        ["staples no 10", "stepler no10"],
    ),
    (
        "Correction fluid 20ml",
        "office",
        "pcs",
        ["tip-ex 20ml", "tipe-x 20ml", "correction pen 20ml"],
    ),
    (
        "Whiteboard marker black",
        "office",
        "pcs",
        ["spidol whiteboard hitam", "marker whiteboard black"],
    ),
    (
        "Folder plastic A4",
        "office",
        "pcs",
        ["map plastik a4", "plastic folder a4"],
    ),
    (
        "Sticky notes 75x75mm",
        "office",
        "pack",
        ["post-it 75x75", "sticky note 75x75"],
    ),
    (
        "Printer ink HP 680 black",
        "office",
        "pcs",
        ["tinta hp 680 hitam", "cartridge hp 680 black"],
    ),
]

# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------
SUPPLIERS = [
    ("CV Sinar Pelumas", "0811-2345-6789", "Surabaya"),
    ("PT Mitra Oli Jaya", "0812-3456-7890", "Jakarta"),
    ("UD Teknik Makmur", "0813-4567-8901", "Bandung"),
    ("PT Berkat Abadi", "0814-5678-9012", "Surabaya"),
    ("CV Karya Sejati", "0815-6789-0123", "Semarang"),
    ("PT Indo Spare Parts", "0816-7890-1234", "Jakarta"),
    ("UD Anugrah Teknik", "0817-8901-2345", "Medan"),
    ("PT Global Safety", "0818-9012-3456", "Surabaya"),
]

# ---------------------------------------------------------------------------
# Base prices per catalog item (rupiah / unit)
# ---------------------------------------------------------------------------
BASE_PRICES: dict[str, int] = {
    "Hydraulic oil ISO VG 46, 20L": 1_110_000,
    "Bearing 6205 ZZ": 37_000,
    "Bearing 6206 ZZ": 42_000,
    "V-belt type B 51": 55_000,
    "V-belt type A 42": 48_000,
    "Oil seal 25x42x7": 12_000,
    "O-ring 3x50": 3_500,
    "Bolt M10x30 SS": 1_200,
    "Filter element hydraulic HF6553": 185_000,
    "Coupling jaw element 28": 95_000,
    "Grease EP2 1kg": 35_000,
    "Gear oil SAE 90 20L": 280_000,
    "Compressor oil 10W-40 4L": 75_000,
    "Brake fluid DOT3 500ml": 28_000,
    "Chain lubricant spray 400ml": 32_000,
    "Penetrating oil WD-40 450ml": 45_000,
    "Work gloves, cotton dotted": 98_000,
    "Safety helmet MSA V-Gard": 185_000,
    "Safety shoes 6\" boot": 320_000,
    "Safety glasses clear lens": 25_000,
    "Ear plug foam 3M 1100": 15_000,
    "Dust mask N95": 12_000,
    "Safety vest reflective": 45_000,
    "First aid kit medium": 120_000,
    "Packing tape 48mm, clear": 205_000,
    "Stretch film 500mm x 300m": 95_000,
    "Cardboard box 40x30x30": 8_500,
    "Bubble wrap roll 50cm": 45_000,
    "Polybag 30x40 0.05mm": 28_000,
    "Foam sheet 1m x 2m x 5mm": 65_000,
    "Label sticker 10x5cm": 22_000,
    "Ziplock bag 20x30": 18_000,
    "A4 paper 80gsm, 1 ream": 52_000,
    "Ballpoint pen blue 12pcs": 18_000,
    "Staple no. 10": 8_500,
    "Correction fluid 20ml": 7_500,
    "Whiteboard marker black": 12_000,
    "Folder plastic A4": 5_000,
    "Sticky notes 75x75mm": 15_000,
    "Printer ink HP 680 black": 95_000,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _drift_price(base: int, drift_factor: float) -> int:
    """Return base ± small random drift, no float money."""
    jitter = RNG.uniform(-0.04, 0.04)
    return round(base * (1 + drift_factor + jitter))


def _po(prefix: str, seq: int) -> str:
    return f"{prefix}{seq:04d}"


# ---------------------------------------------------------------------------
# main seed routine
# ---------------------------------------------------------------------------

def seed(empty_today: bool = False) -> None:
    from app.models import Request as Req
    from sqlalchemy import select as sa_select

    session = SessionLocal()
    try:
        _wipe(session)
        suppliers = _seed_suppliers(session)
        items = _seed_items(session)
        _seed_purchases_and_stock(session, suppliers, items)
        # Standalone cache rows are always seeded (even with --empty-today).
        _seed_solenoid_cache(session)
        _seed_past_requests(session, suppliers, items)
        if not empty_today:
            _seed_today(session, suppliers, items)
        session.commit()

        if not empty_today:
            # Run the check engine on the seeded request
            from app.services.checker import check_request
            req = session.execute(
                sa_select(Req).order_by(Req.id.desc()).limit(1)
            ).scalar_one()
            check_request(req.id, session)

        _print_summary(session, empty_today)
    finally:
        session.close()


def _wipe(session) -> None:
    """Drop all rows in dependency order."""
    for tbl in [
        "actions",
        "flags",
        "web_quotes",
        "request_items",
        "requests",
        "stock",
        "purchases",
        "items",
        "suppliers",
    ]:
        session.execute(text(f"DELETE FROM {tbl}"))
    session.commit()


def _seed_suppliers(session) -> list[Supplier]:
    suppliers = []
    for name, phone, city in SUPPLIERS:
        s = Supplier(name=name, phone=phone, city=city)
        session.add(s)
        suppliers.append(s)
    session.flush()
    return suppliers


def _seed_items(session) -> dict[str, Item]:
    items: dict[str, Item] = {}
    for name, category, unit, aliases in CATALOG:
        item = Item(name=name, category=category, unit=unit, aliases=aliases)
        session.add(item)
        items[name] = item
    session.flush()
    return items


def _seed_purchases_and_stock(
    session, suppliers: list[Supplier], items: dict[str, Item]
) -> None:
    """
    Seed ~300 purchase lines over 12 months with small price drift.
    Stock levels and quantities are chosen so ONLY the hydraulic oil row
    (seeded separately in _seed_today) can be flagged.
    """
    today = today_jkt()
    start = today - timedelta(days=365)

    supplier_map = {s.name: s for s in suppliers}
    sinar = supplier_map["CV Sinar Pelumas"]
    mitra = supplier_map["PT Mitra Oli Jaya"]

    # We'll collect (item_name, supplier, date, qty, price) tuples first,
    # then add Bearing / Gloves / Tape rows with exact expected averages.
    po_seq = 1

    # --- Exact history for demo items ---

    # Row 01: Hydraulic oil — 3 exact purchases (also added via _seed_today)
    # These are the purchase history records referenced by the plan.
    oil = items["Hydraulic oil ISO VG 46, 20L"]
    _add_purchase(session, oil, sinar,  date(2026, 3, 18), 6, 1_115_000, "PO-0318")
    _add_purchase(session, oil, mitra,  date(2026, 6, 3),  4, 1_115_000, "PO-0603")
    _add_purchase(session, oil, mitra,  date(2026, 8, 12), 4, 1_130_000, "PO-0812")
    # Stock: 3 drum, use 2 drum/month
    session.add(Stock(item_id=oil.id, qty_on_hand=3, avg_monthly_use=2))

    # Row 03: Bearing 6205 ZZ — 6 buys, last 3 average exactly 38,000
    bearing = items["Bearing 6205 ZZ"]
    sup_b = supplier_map["UD Teknik Makmur"]
    # older 3 (not in last-3 window) — slightly lower prices so they don't affect ref
    _add_purchase(session, bearing, sup_b, today - timedelta(days=340), 10, 36_000)
    _add_purchase(session, bearing, sup_b, today - timedelta(days=280), 15, 36_500)
    _add_purchase(session, bearing, sup_b, today - timedelta(days=220), 12, 37_000)
    # last 3: 38,000 + 38,000 + 38,000 = average 38,000
    _add_purchase(session, bearing, sup_b, today - timedelta(days=120), 20, 38_000)
    _add_purchase(session, bearing, sup_b, today - timedelta(days=60),  20, 38_000)
    _add_purchase(session, bearing, sup_b, today - timedelta(days=15),  20, 38_000)
    # Stock: safe level — qty_on_hand big enough so cover < 1 month
    session.add(Stock(item_id=bearing.id, qty_on_hand=10, avg_monthly_use=20))

    # Row 04: Work gloves — 4 buys, last 3 average exactly 98,000
    gloves = items["Work gloves, cotton dotted"]
    sup_g = supplier_map["PT Global Safety"]
    _add_purchase(session, gloves, sup_g, today - timedelta(days=300), 5, 95_000)
    # last 3: 98,000 + 98,000 + 98,000 → avg 98,000
    _add_purchase(session, gloves, sup_g, today - timedelta(days=90),  8, 98_000)
    _add_purchase(session, gloves, sup_g, today - timedelta(days=50),  10, 98_000)
    _add_purchase(session, gloves, sup_g, today - timedelta(days=20),  10, 98_000)
    # Ordered qty median is 10 — today's row wants 10 doz, so no QTY_UNUSUAL
    session.add(Stock(item_id=gloves.id, qty_on_hand=5, avg_monthly_use=10))

    # Row 05: Packing tape — 9 buys, last 3 average exactly 205,000
    tape = items["Packing tape 48mm, clear"]
    sup_t = supplier_map["PT Berkat Abadi"]
    older_prices = [200_000, 200_000, 200_000, 202_000, 204_000, 204_000]
    for i, price in enumerate(older_prices):
        _add_purchase(session, tape, sup_t, today - timedelta(days=360 - i * 30), 3, price)
    # last 3: 205,000 + 205,000 + 205,000 → avg 205,000
    _add_purchase(session, tape, sup_t, today - timedelta(days=60), 3, 205_000)
    _add_purchase(session, tape, sup_t, today - timedelta(days=30), 3, 205_000)
    _add_purchase(session, tape, sup_t, today - timedelta(days=10), 3, 205_000)
    # qty median is 3 — today's row wants 3 boxes, no QTY_UNUSUAL
    session.add(Stock(item_id=tape.id, qty_on_hand=2, avg_monthly_use=3))

    # --- Generic history for remaining items (no demo flags possible) ---
    remaining_names = set(items.keys()) - {
        "Hydraulic oil ISO VG 46, 20L",
        "Bearing 6205 ZZ",
        "Work gloves, cotton dotted",
        "Packing tape 48mm, clear",
        # Solenoid valve is not in catalog — no history needed
    }

    assigned: set[str] = set()
    po_seq = 1
    for name in sorted(remaining_names):  # deterministic order
        item = items[name]
        base = BASE_PRICES.get(name, 50_000)
        # Pick 2 random suppliers
        chosen_sups = RNG.sample(suppliers, k=2)
        num_buys = RNG.randint(3, 10)
        buys = []
        for b in range(num_buys):
            days_ago = RNG.randint(15, 360)
            d = today - timedelta(days=days_ago)
            drift = (num_buys - b) * 0.002  # gentle price drift upward
            price = _drift_price(base, drift)
            qty = RNG.randint(2, 15)
            sup = chosen_sups[b % 2]
            buys.append((d, qty, price, sup))
            po_seq += 1
        # sort by date
        buys.sort(key=lambda x: x[0])
        for d, qty, price, sup in buys:
            _add_purchase(session, item, sup, d, qty, price)
        # Stock: ensure cover < 1 month (no STOCK_COVER_HIGH flag)
        # avg_monthly_use > qty_on_hand means cover < 1 month
        avg_use = RNG.randint(5, 20)
        session.add(Stock(item_id=item.id, qty_on_hand=avg_use - 1, avg_monthly_use=avg_use))

    session.flush()


def _add_purchase(
    session,
    item: Item,
    supplier: Supplier,
    d: date,
    qty: int,
    price: int,
    po_number: str | None = None,
) -> Purchase:
    p = Purchase(
        po_number=po_number,
        purchase_date=jkt(d, 8, 0),
        item_id=item.id,
        supplier_id=supplier.id,
        qty=qty,
        unit_price_idr=price,
        source="seed",
    )
    session.add(p)
    return p


# Solenoid valve cache date (11 Oct 2026 Jakarta time, 07:30)
_VALVE_CACHE_DATE = datetime(2026, 10, 11, 7, 30, tzinfo=JAKARTA)


def _seed_solenoid_cache(session) -> None:
    """
    Seed 3 standalone web-quote cache rows for the solenoid valve.
    These rows are independent of any request_item_id — they exist as cache
    only, with item_key set for lookup via web_check.py.
    Seeded on every run including --empty-today.
    """
    from app.services.matcher import normalize_name as _norm
    valve_key = _norm('Solenoid valve 24V DC, 1/2"')
    # URL placeholder diganti None — URL asli belum tersedia.
    # Harga tetap valid untuk perhitungan referensi.
    valve_quotes = [
        ("Tokopedia", "Solenoid Valve 24VDC 1/2 inch", None, 398_000),
        ("Shopee",    "Solenoid Valve 24V 1/2 BSPP",   None, 425_000),
        ("Lazada",    "Solenoid Valve 24VDC 1/2",       None, 465_000),
    ]
    for seller, title, url, price in valve_quotes:
        session.add(WebQuote(
            request_item_id=None,
            item_key=valve_key,
            query=valve_key,
            title=title,
            url=url,
            seller=seller,
            price_idr=price,
            fetched_at=_VALVE_CACHE_DATE,
        ))
    session.flush()


# ---------------------------------------------------------------------------
# Past request days (10 dates spanning the last 90 days)
# ---------------------------------------------------------------------------

# Past request offsets in days (deterministic, never change).
_PAST_OFFSETS = [5, 10, 18, 25, 32, 40, 50, 60, 72, 85]

# Weighted pool for status assignment:
# approved × 6, checked × 4, flagged × 3, returned × 2, new × 2, pending × 1
_STATUS_POOL = (
    ["approved"] * 6
    + ["checked"] * 4
    + ["flagged"] * 3
    + ["returned"] * 2
    + ["new"] * 2
    + ["pending"] * 1
)

# Departments to choose from
_DEPARTMENTS = ["Warehouse", "Maintenance", "Production", "QC", "Logistics"]

# Items to use for past requests (a deterministic subset, avoids solenoid)
_PAST_ITEM_NAMES = [
    "Hydraulic oil ISO VG 46, 20L",
    "Bearing 6205 ZZ",
    "Bearing 6206 ZZ",
    "V-belt type B 51",
    "Work gloves, cotton dotted",
    "Safety helmet MSA V-Gard",
    "Grease EP2 1kg",
    "Packing tape 48mm, clear",
    "A4 paper 80gsm, 1 ream",
    "Gear oil SAE 90 20L",
    "Bolt M10x30 SS",
    "Filter element hydraulic HF6553",
]


def _seed_past_requests(
    session, suppliers: list[Supplier], items: dict[str, Item]
) -> None:
    """
    Seed 10 past Request records (at _PAST_OFFSETS days ago), each with
    3–6 RequestItems using deterministic RNG.  Statuses are assigned directly
    from a weighted pool so all 6 statuses appear across the dataset.
    Flagged items also get a Flag record (PRICE_ABOVE_REF).
    """
    today = today_jkt()
    JAKARTA_TZ = timezone(timedelta(hours=7))

    for offset in _PAST_OFFSETS:
        req_date = today - timedelta(days=offset)
        req = Request(
            requested_at=jkt(req_date, 8, 30),
            requested_by="Warehouse / Maintenance",
            raw_text=f"Past request {offset} days ago",
        )
        session.add(req)
        session.flush()  # get req.id

        n_rows = RNG.randint(3, 6)
        chosen_names = RNG.sample(_PAST_ITEM_NAMES, k=min(n_rows, len(_PAST_ITEM_NAMES)))

        for line_no, name in enumerate(chosen_names, start=1):
            item = items.get(name)
            base_price = BASE_PRICES.get(name, 50_000)
            # quoted price: base ± up to 15%
            quoted_price = round(base_price * RNG.uniform(0.90, 1.20))
            # reference price: base ± up to 5%
            ref_price = round(base_price * RNG.uniform(0.97, 1.03))
            # diff_pct computed in Python (never in SQL)
            dp = round((quoted_price - ref_price) / ref_price * 100, 1) if ref_price else None
            status = RNG.choice(_STATUS_POOL)
            dept = RNG.choice(_DEPARTMENTS)
            qty = RNG.randint(2, 20)
            unit = item.unit if item else "pcs"
            supplier = RNG.choice(suppliers)
            # checked_at: same day, random hour
            checked_at = datetime(
                req_date.year, req_date.month, req_date.day,
                RNG.randint(9, 17), RNG.randint(0, 59),
                tzinfo=JAKARTA_TZ,
            ) if status != "pending" else None

            ri = RequestItem(
                request_id=req.id,
                line_no=line_no,
                raw_name=name,
                item_id=item.id if item else None,
                department=dept,
                qty=qty,
                unit=unit,
                quoted_unit_price_idr=quoted_price,
                quoting_supplier_name=supplier.name,
                supplier_id=supplier.id,
                reference_unit_price_idr=ref_price,
                diff_pct=dp,
                checked_via="history",
                history_count=RNG.randint(3, 9),
                status=status,
                checked_at=checked_at,
            )
            session.add(ri)
            session.flush()  # get ri.id

            if status == "flagged":
                session.add(Flag(
                    request_item_id=ri.id,
                    code="PRICE_ABOVE_REF",
                    message=(
                        f"Quoted price Rp {quoted_price:,} is "
                        f"{dp:+.1f}% above reference Rp {ref_price:,}"
                    ),
                ))


def _seed_today(
    session, suppliers: list[Supplier], items: dict[str, Item]
) -> None:
    """Seed today's 5 demo request items exactly as in the plan table."""
    today = today_jkt()
    supplier_map = {s.name: s for s in suppliers}
    sinar = supplier_map["CV Sinar Pelumas"]

    req = Request(
        requested_at=jkt(today, 8, 0),
        requested_by="Warehouse / Maintenance",
        raw_text=(
            "1. Hydraulic oil ISO VG 46, 20L – 4 drum, Warehouse, "
            "Rp 1.450.000/drum, CV Sinar Pelumas\n"
            "2. Solenoid valve 24V DC, 1/2\" – 2 pcs, Maintenance\n"
            "3. Bearing 6205 ZZ – 20 pcs, Maintenance, Rp 38.500/pcs\n"
            "4. Work gloves, cotton dotted – 10 doz, Production, Rp 96.000/doz\n"
            "5. Packing tape 48mm, clear – 3 box, Warehouse, Rp 210.000/box"
        ),
    )
    session.add(req)
    session.flush()

    # ---- Row 01: Hydraulic oil ----
    oil = items["Hydraulic oil ISO VG 46, 20L"]
    ri_oil = RequestItem(
        request_id=req.id,
        line_no=1,
        raw_name="Hydraulic oil ISO VG 46, 20L",
        item_id=oil.id,
        department="Warehouse",
        qty=4,
        unit="drum",
        quoted_unit_price_idr=1_450_000,
        quoting_supplier_name="CV Sinar Pelumas",
        supplier_id=sinar.id,
        status="pending",
    )
    session.add(ri_oil)

    # ---- Row 02: Solenoid valve (new item — not in catalog) ----
    ri_valve = RequestItem(
        request_id=req.id,
        line_no=2,
        raw_name='Solenoid valve 24V DC, 1/2"',
        item_id=None,
        department="Maintenance",
        qty=2,
        unit="pcs",
        quoted_unit_price_idr=None,
        quoting_supplier_name=None,
        status="pending",
    )
    session.add(ri_valve)
    session.flush()
    # (Web quotes for the solenoid are seeded as standalone cache rows in
    # _seed_solenoid_cache(), called unconditionally from seed().)

    # ---- Row 03: Bearing 6205 ZZ ----
    bearing = items["Bearing 6205 ZZ"]
    sup_b = supplier_map["UD Teknik Makmur"]
    ri_bearing = RequestItem(
        request_id=req.id,
        line_no=3,
        raw_name="Bearing 6205 ZZ",
        item_id=bearing.id,
        department="Maintenance",
        qty=20,
        unit="pcs",
        quoted_unit_price_idr=38_500,
        quoting_supplier_name="UD Teknik Makmur",
        supplier_id=sup_b.id,
        status="pending",
    )
    session.add(ri_bearing)

    # ---- Row 04: Work gloves ----
    gloves = items["Work gloves, cotton dotted"]
    sup_g = supplier_map["PT Global Safety"]
    ri_gloves = RequestItem(
        request_id=req.id,
        line_no=4,
        raw_name="Work gloves, cotton dotted",
        item_id=gloves.id,
        department="Production",
        qty=10,
        unit="doz",
        quoted_unit_price_idr=96_000,
        quoting_supplier_name="PT Global Safety",
        supplier_id=sup_g.id,
        status="pending",
    )
    session.add(ri_gloves)

    # ---- Row 05: Packing tape ----
    tape = items["Packing tape 48mm, clear"]
    sup_t = supplier_map["PT Berkat Abadi"]
    ri_tape = RequestItem(
        request_id=req.id,
        line_no=5,
        raw_name="Packing tape 48mm, clear",
        item_id=tape.id,
        department="Warehouse",
        qty=3,
        unit="box",
        quoted_unit_price_idr=210_000,
        quoting_supplier_name="PT Berkat Abadi",
        supplier_id=sup_t.id,
        status="pending",
    )
    session.add(ri_tape)

    session.flush()


def _print_summary(session, empty_today: bool) -> None:
    from sqlalchemy import func as sqlfunc

    def count(model):
        return session.query(sqlfunc.count(model.id)).scalar()

    # Count past (non-today) request items
    today = today_jkt()
    JAKARTA_TZ = timezone(timedelta(hours=7))
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=JAKARTA_TZ)
    from sqlalchemy import select
    from app.models import Request as Req
    past_ri_count = session.execute(
        select(sqlfunc.count(RequestItem.id))
        .join(Req, Req.id == RequestItem.request_id)
        .where(Req.requested_at < today_start)
    ).scalar()

    print("\n=== Procur.AI seed summary ===")
    print(f"  suppliers    : {count(Supplier)}")
    print(f"  items        : {count(Item)}")
    print(f"  purchases    : {count(Purchase)}")
    print(f"  stock rows   : {session.query(sqlfunc.count(Stock.item_id)).scalar()}")
    print(f"  requests     : {count(Request)}")
    print(f"  request_items: {count(RequestItem)}  (past: {past_ri_count}, today: {count(RequestItem) - past_ri_count})")
    print(f"  web_quotes   : {count(WebQuote)}")
    print(f"  flags        : {count(Flag)}")
    print(f"  actions      : {count(Action)}")
    if not empty_today:
        # Verify the oil average
        from sqlalchemy import select
        from app.models import Purchase as P, Item as I
        oil_item = session.execute(
            select(I).where(I.name == "Hydraulic oil ISO VG 46, 20L")
        ).scalar_one()
        prices = session.execute(
            select(P.unit_price_idr)
            .where(P.item_id == oil_item.id)
            .order_by(P.purchase_date.desc())
            .limit(3)
        ).scalars().all()
        avg = round(sum(prices) / len(prices))
        print(f"\n  Oil last-3 avg : Rp {avg:,}  (expected 1,120,000)")
    print("==============================\n")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def _is_demo_environment() -> bool:
    """Return True only if the database host is localhost / 127.0.0.1."""
    from urllib.parse import urlparse
    db_url = settings.DATABASE_URL
    try:
        host = urlparse(db_url).hostname or ""
    except Exception:
        host = ""
    return host.lower() in ("localhost", "127.0.0.1", "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Procur.AI demo data")
    parser.add_argument("--reset", action="store_true", required=True,
                        help="Wipe and recreate all data")
    parser.add_argument("--empty-today", action="store_true",
                        help="Skip today's 5 demo request items")
    parser.add_argument(
        "--i-know-what-i-am-doing",
        action="store_true",
        help="Override the production/remote-host safety guard",
    )
    args = parser.parse_args()

    # Safety guard: refuse to reset if running against a non-demo environment.
    app_env = os.environ.get("APP_ENV", "").lower()
    if app_env == "production" or not _is_demo_environment():
        if not getattr(args, "i_know_what_i_am_doing", False):
            print(
                "ERROR: Reset hanya diizinkan di environment demo dengan database localhost.\n"
                "Gunakan flag --i-know-what-i-am-doing untuk override.",
                file=sys.stderr,
            )
            sys.exit(1)

    seed(empty_today=args.empty_today)
