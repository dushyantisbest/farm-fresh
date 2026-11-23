# Task 4 · Security integration and performance evaluation

**Project:** Fieldstock perishable-inventory application  
**Evaluation date:** 23 November 2026  
**Scope:** Application code, Python dependencies, SQLite runtime and local API performance. The assignment lists dependency scanning twice. This submission covers application/test dependencies and the packaged container as two distinct surfaces.

## Controls and evidence

| Check | Execution and result | Evidence |
|---|---|---|
| Static code analysis | Executed a targeted Python AST scan covering dynamic execution, shell calls, unsafe deserialization and nonliteral SQL. Checked browser JavaScript for dangerous DOM sinks. Zero matches in four application files. This limited rule set cannot establish absence of defects. | evidence/static.json |
| Runtime package inventory | Examined Python imports and runtime manifest. Zero third-party Python packages. SQLite and the interpreter are still runtime dependencies. | evidence/dependencies.json |
| SQLite dependency vulnerability check | Compared the loaded SQLite version, 3.45.3, with the upstream range for the concat_ws defect. One version match under two advisory IDs, CVE-2025-3277 and CVE-2025-29087. | evidence/sqlite-advisory.json |
| Functional verification | The two original assertions passed directly. Seven HTTP/SQLite workflow tests and three forecasting tests passed using unittest, including persistence, concurrent sales, expiry exclusion, input validation and duplicate-receipt rejection. | evidence/tests.txt |
| CI security gates | Windows Jenkinsfile runs Bandit, pip-audit against resolved test dependencies, Gitleaks and Trivy. Bandit fails at medium or higher severity, pip-audit on known vulnerabilities, Gitleaks on detected secrets, and Trivy on high or critical image findings. | Jenkinsfile; CI-issued scanner reports pending |
| API performance | 240 measured HTTP requests, zero request errors. | evidence/benchmark.json |

The SQLite match concerns a function absent from the application's SQL. All application queries use fixed SQL with bound input values. This reduces exposure through the tested API. Update the Python distribution or bundled SQLite to a supported patched release, then rerun the version check. The two advisory identifiers describe the same defect. The version check covers this one issue and does not account for distributor backports. [SQLite advisory table](https://sqlite.org/cves.html) · [SQLite release notes](https://sqlite.org/releaselog/3_49_1.html)

## Performance measurements

Windows 11, Python 3.13.1 and SQLite 3.45.3. The benchmark ran on loopback with a disposable database, eight products, fourteen days of synthetic sales and five excluded warm-up requests per scenario. Latency includes HTTP response decoding. P95 is the nearest-rank 95th percentile.

| Workload | Clients | Requests | Median | P95 | Requests/s | Errors |
|---|---:|---:|---:|---:|---:|---:|
| Dashboard read | 1 | 100 | 15.21 ms | 27.43 ms | 71.9 | 0 |
| Dashboard read | 4 | 100 | 7.79 ms | 9.58 ms | 487.4 | 0 |
| Supplier order creation | 4 | 40 | 25.53 ms | 84.25 ms | 100.5 | 0 |

Four readers produced greater aggregate throughput in this run. Concurrent order writes had a much higher tail latency. SQLite serializes writes, which is one plausible contributor. This short run did not isolate disk latency or lock wait time. The workload measures the local API with demonstration data. It does not estimate whole-page browser rendering time, internet latency or production capacity.

## Pipeline results still required

The local environment had no running Docker engine, Jenkins agent or downloadable scanner packages. Bandit, pip-audit, Gitleaks and Trivy results therefore need a run on the team's agent. The supplied Jenkinsfile saves reports even if a later stage fails. The SQLite version check blocks a matching agent runtime. After remediation, rerun to obtain remaining reports.

The presentation's deployment frequency, manual-versus-automated duration, failed deployment rate and rollback time require deployment histories. Record build IDs and actual stage/deployment times from the team's Jenkins installation before reporting those metrics.

