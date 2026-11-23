"""SQLite stock ledger and seven-day moving-average forecast."""
import math
import sqlite3
from datetime import date, timedelta

SEED = [
    ("Whole milk", "Dairy", "Meadow Dairy", 36, 4, 9),
    ("Sourdough loaf", "Bakery", "Field Bakery", 18, 2, 7),
    ("Baby spinach", "Produce", "Green Acre", 9, 3, 6),
    ("Greek yoghurt", "Dairy", "Meadow Dairy", 65, 12, 8),
    ("Cherry tomatoes", "Produce", "Green Acre", 42, 8, 5),
    ("Rolled oats", "Pantry", "North Mill", 84, 95, 4),
    ("Farm eggs", "Dairy", "Meadow Dairy", 72, 15, 6),
    ("Basmati rice", "Pantry", "North Mill", 56, 120, 3),
]


def calculate_stock(current_stock, sold):
    return current_stock - sold


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT UNIQUE COLLATE NOCASE, category TEXT, supplier TEXT);
        CREATE TABLE IF NOT EXISTS lots(product INTEGER REFERENCES products, qty INTEGER CHECK(qty>=0), expiry TEXT);
        CREATE TABLE IF NOT EXISTS sales(product INTEGER REFERENCES products, qty INTEGER, day TEXT);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, product INTEGER REFERENCES products, qty INTEGER, placed TEXT, received TEXT);
    """)
    with db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
            return
        today = date.today()
        for index, (name, category, supplier, qty, days, rate) in enumerate(SEED):
            pid = db.execute("INSERT INTO products(name,category,supplier) VALUES(?,?,?)", (name,category,supplier)).lastrowid
            db.execute("INSERT INTO lots VALUES(?,?,?)", (pid, qty, today+timedelta(days=days)))
            for offset in range(1, 15):
                units = rate + (index + offset * 2) % 5 - 2 + (2 if offset < 5 else 0)
                db.execute("INSERT INTO sales VALUES(?,?,?)", (pid, units, today-timedelta(days=offset)))


def snapshot(db):
    today = date.today()
    week_start = today - timedelta(days=7)
    trend_start = today - timedelta(days=13)
    quantities = db.execute("""
        SELECT p.*, COALESCE(SUM(l.qty),0) stock,
        COALESCE(SUM(CASE WHEN l.expiry>=? THEN l.qty END),0) available,
        COALESCE(SUM(CASE WHEN l.expiry BETWEEN ? AND ? THEN l.qty END),0) expiring,
        MIN(CASE WHEN l.qty>0 THEN l.expiry END) expiry
        FROM products p LEFT JOIN lots l ON l.product=p.id GROUP BY p.id ORDER BY p.id
    """, (today,today,today+timedelta(days=7)))
    sales = dict(db.execute("SELECT product,SUM(qty) FROM sales WHERE day>=? AND day<? GROUP BY product", (week_start,today)))
    orders = [dict(o) for o in db.execute("SELECT o.*,p.name,p.supplier FROM orders o JOIN products p ON p.id=o.product ORDER BY o.id DESC")]
    pending = {}
    for o in orders:
        if not o["received"]:
            pending[o["product"]] = pending.get(o["product"],0) + o["qty"]
    items = []
    for row in quantities:
        item = dict(row)
        demand = sales.get(item["id"],0)
        item.update(demand=demand, reorder=max(0,demand-item["available"]-pending.get(item["id"],0)),
                    low=item["available"] <= math.ceil(demand*3/7), expired=item["stock"]-item["available"])
        items.append(item)
    totals = dict(db.execute("SELECT day,SUM(qty) FROM sales WHERE day BETWEEN ? AND ? GROUP BY day",(trend_start,today)))
    trend = [{"date": str(trend_start+timedelta(days=i)), "units": totals.get(str(trend_start+timedelta(days=i)),0)} for i in range(14)]
    return dict(items=items, orders=orders, trend=trend, today=str(today))


def integer(value):
    if type(value) is not int or not 1 <= value <= 1000000:
        raise ValueError("Enter a whole number between 1 and 1,000,000.")
    return value


def label(data, key):
    val = data.get(key)
    if not isinstance(val,str) or not 1 <= len(val.strip()) <= 80:
        raise ValueError("Enter a valid " + key + " (up to 80 characters).")
    return val.strip()


def expiry_date(data):
    try:
        expiry = date.fromisoformat(data.get("expiry",""))
    except (TypeError, ValueError):
        raise ValueError("Choose a valid expiry date.") from None
    if expiry < date.today():
        raise ValueError("New stock must have a current or future expiry date.")
    return expiry


def change(db, action, data):
    today = date.today()
    with db:
        db.execute("BEGIN IMMEDIATE")
        if action == "receive":
            oid = integer(data.get("order"))
            order = db.execute("SELECT * FROM orders WHERE id=? AND received IS NULL",(oid,)).fetchone()
            if not order:
                raise ValueError("This order is unavailable or already received.")
            db.execute("INSERT INTO lots VALUES(?,?,?)",(order["product"],order["qty"],expiry_date(data)))
            db.execute("UPDATE orders SET received=? WHERE id=?",(today,oid))
            return
        qty = integer(data.get("qty"))
        if action == "product":
            values = [label(data,key) for key in ("name","category","supplier")]
            pid = db.execute("INSERT INTO products(name,category,supplier) VALUES(?,?,?)",values).lastrowid
            db.execute("INSERT INTO lots VALUES(?,?,?)",(pid,qty,expiry_date(data)))
            return
        pid = integer(data.get("product"))
        if not db.execute("SELECT 1 FROM products WHERE id=?",(pid,)).fetchone():
            raise ValueError("Select an existing product.")
        if action == "order":
            db.execute("INSERT INTO orders(product,qty,placed) VALUES(?,?,?)",(pid,qty,today))
            return
        if action != "sale":
            raise ValueError("Unknown action.")
        lots = db.execute("SELECT rowid,qty FROM lots WHERE product=? AND qty>0 AND expiry>=? ORDER BY expiry,rowid",(pid,today)).fetchall()
        if sum(row["qty"] for row in lots) < qty:
            raise ValueError("Sale exceeds available, unexpired stock.")
        remaining = qty
        for row in lots:
            used = min(row["qty"],remaining)
            db.execute("UPDATE lots SET qty=? WHERE rowid=?",(calculate_stock(row["qty"],used),row["rowid"]))
            remaining -= used
            if remaining == 0:
                break
        db.execute("INSERT INTO sales VALUES(?,?,?)",(pid,qty,today))

