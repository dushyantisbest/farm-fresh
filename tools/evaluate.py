"""Generate Task 4 evidence from this checkout; no network needed."""
import ast
import json
import math
import platform
import re
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import Handler, create_server

SOURCES = ("app.py","inventory.py","forecast.py")


def static():
    findings = []
    rules = ["dynamic code execution", "shell or subprocess execution", "unsafe deserialization",
             "nonliteral SQL passed to execute", "unsafe HTML or script sink in browser code"]
    prohibited = {"eval","exec","os.system","os.popen","pickle.load","pickle.loads","yaml.load"}
    for filename in SOURCES:
        tree = ast.parse((ROOT/filename).read_text(encoding="utf8"))
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):
                continue
            name = ast.unparse(node.func)
            if name in prohibited or name.startswith("subprocess."):
                findings.append([filename,node.lineno,name])
            if name.endswith((".execute",".executescript",".executemany")) and (not node.args or not isinstance(node.args[0],ast.Constant)):
                findings.append([filename,node.lineno,"nonliteral SQL"])
    for n,line in enumerate((ROOT/"static/app.js").read_text(encoding="utf8").splitlines(),1):
        if re.search(r"\b(innerHTML|outerHTML|insertAdjacentHTML|eval|Function|document\.write)\b",line):
            findings.append(["static/app.js",n,"DOM or script sink"])
    return dict(files=[*SOURCES,"static/app.js"],rules=rules,findings=findings,passed=not findings)


def dependencies():
    imports=set()
    for name in SOURCES:
        for node in ast.walk(ast.parse((ROOT/name).read_text(encoding="utf8"))):
            if isinstance(node,ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            if isinstance(node,ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    external=sorted(imports-sys.stdlib_module_names-{"inventory","app","forecast"})
    declared=[v.strip() for v in (ROOT/"requirements.txt").read_text().splitlines() if v.strip() and not v.lstrip().startswith("#")]
    return dict(runtime_imports=sorted(imports),third_party_imports=external,runtime_requirements=declared,
                scope="Python application imports and runtime manifest. Test dependencies and image packages require the CI advisory scanners.",
                passed=not (external or declared))


def benchmark():
    results=[]
    with tempfile.TemporaryDirectory() as folder, create_server(Path(folder)/"bench.db",port=0) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url="http://127.0.0.1:%d" % server.server_port
        def request(path, payload):
            req=Request(url+path, data=json.dumps(payload).encode() if payload else None,headers={"Content-Type":"application/json"})
            start=time.perf_counter()
            try:
                with urlopen(req,timeout=10) as response:
                    body=json.load(response)
                    ok=response.status==200 and (body.get("ok") is True if payload else len(body.get("items",[]))==8)
            except OSError:
                ok=False
            return (time.perf_counter()-start)*1000,ok
        try:
            for endpoint,payload,count,workers in [("/api/dashboard",None,100,1),("/api/dashboard",None,100,4),("/api/order",{"product":1,"qty":1},40,4)]:
                for _ in range(5):
                    request(endpoint,payload)
                start=time.perf_counter()
                with ThreadPoolExecutor(workers) as pool:
                    samples=list(pool.map(lambda _:request(endpoint,payload),range(count)))
                elapsed=time.perf_counter()-start
                times=sorted(t for t,_ in samples)
                results.append(dict(endpoint=endpoint,workers=workers,requests=count,errors=sum(not ok for _,ok in samples),
                                    median_ms=round(statistics.median(times),2),p95_ms=round(times[math.ceil(.95*count)-1],2),
                                    requests_per_second=round(count/elapsed,1)))
        finally:
            server.shutdown()
            thread.join()
    return dict(platform=platform.platform(),python=platform.python_version(),dataset="8 products; 14 seeded sales days; 5 warmups per scenario",results=results,passed=all(r["errors"]==0 for r in results))


if __name__=="__main__":
    tasks={"static":static,"dependencies":dependencies,"benchmark":benchmark}
    for name in sys.argv[1:] or tasks:
        result=tasks[name]()
        result["generated_utc"]=datetime.now(timezone.utc).isoformat()
        target=ROOT/"reports"/(name+".json")
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(result,indent=2),encoding="utf8")
        print(json.dumps(result))
        if not result["passed"]:
            sys.exit(1)

