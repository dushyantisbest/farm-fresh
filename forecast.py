"""Fit relative festival demand from paired seven-day historical observations."""
import csv
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HISTORY = Path(__file__).with_name("festival_history.csv")


def read_history():
    with HISTORY.open(encoding="utf8", newline="") as file:
        return list(csv.DictReader(file))


def fit(rows, product, category):
    selected = [r for r in rows if r["product"] == product]
    source = "Product history"
    if not selected:
        selected = [r for r in rows if r["category"] == category]
        source = "Category history"
    normal = sum(int(r["normal_units"]) for r in selected)
    if normal == 0:
        return 1.0, "No festival history"
    return sum(int(r["festival_units"]) for r in selected) / normal, source


def evaluate(rows):
    last = max(r["year"] for r in rows)
    train = [r for r in rows if r["year"] < last]
    results = []
    for r in rows:
        if r["year"] != last:
            continue
        past = [v for v in train if v["festival"] == r["festival"]]
        factor, _ = fit(past, r["product"], r["category"])
        baseline = int(r["normal_units"])
        actual = int(r["festival_units"])
        results.append((abs(round(baseline * factor)-actual), abs(baseline-actual)))
    return dict(year=last, cases=len(results), festival_mae=round(sum(x for x,_ in results)/len(results),2),
                baseline_mae=round(sum(y for _,y in results)/len(results),2))


def planning(db, state):
    history = read_history()
    today = date.fromisoformat(state["today"])
    lots = defaultdict(list)
    for pid, expiry, qty in db.execute("SELECT product,expiry,qty FROM lots WHERE qty>0 ORDER BY expiry"):
        lots[pid].append((expiry,qty))
    weekdays = defaultdict(dict)
    for pid, day, total in db.execute("SELECT product,day,SUM(qty) FROM sales WHERE day>=? AND day<? GROUP BY product,day",
                                      (str(today-timedelta(days=14)),str(today))):
        key = date.fromisoformat(day).weekday()
        weekdays[pid][key] = weekdays[pid].get(key,0) + total / 2
    plans = {}
    for festival in sorted({r["festival"] for r in history}):
        records = [r for r in history if r["festival"] == festival]
        products = []
        for item in state["items"]:
            pid = item["id"]
            factor, source = fit(records,item["name"],item["category"])
            batches = [[expiry,qty] for expiry,qty in lots[pid]]
            normal = forecast = shortage = 0
            first_gap = None
            incoming = sum(o["qty"] for o in state["orders"] if o["product"]==pid and not o["received"])
            for offset in range(7):
                day = today + timedelta(days=offset)
                average = weekdays[pid].get(day.weekday(),0)
                normal += average
                # Round cumulative demand so seven small daily forecasts do not disappear.
                target = round(normal * factor)
                need = target - forecast
                forecast = target
                for batch in batches:
                    if batch[0] >= str(day):
                        take = min(batch[1],need)
                        batch[1] -= take
                        need -= take
                if need and first_gap is None:
                    first_gap = day
                shortage += need
            products.append(dict(id=pid,name=item["name"],normal=round(normal),forecast=forecast,
                                 factor=round(factor,2),source=source,pending=incoming,
                                 shortage=shortage,order=max(0,shortage-incoming),
                                 order_by=str(first_gap-timedelta(days=2)) if first_gap else None))
        plans[festival] = sorted(products,key=lambda p:-p["order"])
    return dict(plans=plans,evaluation=evaluate(history))
