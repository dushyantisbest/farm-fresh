import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server
from inventory import connect


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/"demo.db"
        self.server = create_server(self.path,port=0)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever,kwargs={"poll_interval":0.01},daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%d" % self.server.server_port

    def call(self,path,data=None,headers=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.url+path,data=body,headers=headers or {"Content-Type":"application/json"})
        try:
            with urlopen(request,timeout=4) as reply:
                return reply.status,json.load(reply)
        except HTTPError as error:
            with error:
                return error.code,json.load(error)

    def state(self):
        return self.call("/api/dashboard")[1]

    def test_sale_and_reopen(self):
        old = self.state()["items"][0]["available"]
        self.assertEqual(self.call("/api/sale",{"product":1,"qty":3})[0],200)
        self.assertEqual(self.state()["items"][0]["available"],old-3)
        with create_server(self.path,port=0) as reopened, closing(connect(reopened.database)) as db:
            self.assertEqual(db.execute("SELECT SUM(qty) FROM lots WHERE product=1").fetchone()[0],old-3)

    def test_order_receipt_once(self):
        old = self.state()["items"][0]
        self.assertEqual(self.call("/api/order",{"product":1,"qty":5})[0],200)
        state = self.state()
        self.assertEqual(state["items"][0]["available"],old["available"])
        self.assertEqual(state["items"][0]["reorder"],max(0,old["reorder"]-5))
        receipt = {"order":state["orders"][0]["id"],"expiry":str(date.today()+timedelta(days=30))}
        self.assertEqual(self.call("/api/receive",receipt)[0],200)
        self.assertEqual(self.call("/api/receive",receipt)[0],400)
        self.assertEqual(self.state()["items"][0]["available"],old["available"]+5)

    def test_new_product_validation_and_unique_name(self):
        product = dict(name="Test apples",category="Produce",supplier="Local",qty=6,expiry=str(date.today()))
        self.assertEqual(self.call("/api/product",{**product,"expiry":"yesterday"})[0],400)
        self.assertEqual(self.call("/api/product",product)[0],200)
        self.assertEqual(self.call("/api/product",product)[0],409)
        self.assertEqual(self.state()["items"][-1]["demand"],0)

    def test_expired_lots_and_partial_fulfilment(self):
        with closing(connect(self.path)) as db, db:
            db.execute("UPDATE lots SET expiry=? WHERE product=1",(date.today()-timedelta(days=1),))
            db.execute("INSERT INTO lots VALUES(1,2,?)",(date.today(),))
            db.execute("INSERT INTO lots VALUES(1,3,?)",(date.today()+timedelta(days=40),))
        self.assertEqual(self.call("/api/sale",{"product":1,"qty":6})[0],400)
        self.assertEqual(self.call("/api/sale",{"product":1,"qty":3})[0],200)
        item = self.state()["items"][0]
        self.assertEqual((item["available"],item["expiring"],item["expired"]),(2,0,36))

    def test_concurrent_sales(self):
        with ThreadPoolExecutor(2) as pool:
            codes = list(pool.map(lambda _: self.call("/api/sale",{"product":1,"qty":30})[0],range(2)))
        self.assertEqual(sorted(codes),[200,400])
        self.assertEqual(self.state()["items"][0]["available"],6)

    def test_http_validation(self):
        self.assertEqual(self.call("/health")[0],200)
        for qty in (-1,0,True,1.5,"2"):
            self.assertEqual(self.call("/api/sale",{"product":1,"qty":qty})[0],400)
        self.assertEqual(self.call("/api/order",{"product":999,"qty":3})[0],400)
        self.assertEqual(self.call("/api/sale",{},{"Content-Type":"text/plain"})[0],415)
        self.assertEqual(self.call("/api/sale",{},{"Content-Type":"application/json","Origin":"https://example.org"})[0],403)
        self.assertEqual(self.call("/missing")[0],404)
        for path in ("/","/style.css","/app.js"):
            with urlopen(self.url+path) as r:
                self.assertEqual(r.status,200)
                self.assertEqual(r.headers["X-Content-Type-Options"],"nosniff")

    def test_forecast_uses_closed_days(self):
        before = self.state()
        self.assertEqual(self.call("/api/sale",{"product":1,"qty":1})[0],200)
        after = self.state()
        self.assertEqual(after["items"][0]["demand"],before["items"][0]["demand"])
        self.assertEqual(after["trend"][-1]["units"],before["trend"][-1]["units"]+1)

