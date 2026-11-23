import unittest
from contextlib import closing
from inventory import change, connect, initialize, snapshot
from forecast import evaluate, fit, planning, read_history


class ForecastTests(unittest.TestCase):
    def test_holdout(self):
        rows = read_history()
        result = evaluate(rows)
        self.assertEqual(result["cases"],16)
        self.assertLess(result["festival_mae"],result["baseline_mae"])
        self.assertEqual(result["year"],"2025")

    def test_fallback(self):
        rows = read_history()
        self.assertEqual(fit(rows,"New rice","Pantry")[1],"Category history")
        self.assertEqual(fit(rows,"New item","Other"),(1.0,"No festival history"))

    def test_recommendation_updates_after_order(self):
        with closing(connect(":memory:")) as db:
            initialize(db)
            def items():
                return planning(db,snapshot(db))["plans"]["Diwali"]
            rice = next(p for p in items() if p["name"]=="Basmati rice")
            self.assertGreater(rice["forecast"],rice["normal"])
            product = next(p for p in items() if p["order"]>0)
            change(db,"order",dict(product=product["id"],qty=product["order"]))
            updated = next(p for p in items() if p["id"]==product["id"])
            self.assertEqual(updated["order"],0)
            self.assertEqual(updated["forecast"],product["forecast"])
