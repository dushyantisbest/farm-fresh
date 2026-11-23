# Fieldstock inventory dashboard

Run from this folder on Windows with Python 3.11 or newer:

```powershell
python app.py
```

Open http://127.0.0.1:8000. The first start creates eight grocery products, dated batches and fourteen days of synthetic sales in `data/inventory.db`. Changes survive restarts. No pip installation is needed for the dashboard. This is a single-user, local assignment demo with no login.

## Festival demand planning

Open **Demand planning** and switch between Diwali and Holi. Both are what-if scenarios for the next seven days. Compare the predicted units for whole milk and basmati rice. Select an order recommendation, place it and return to the planner to see open stock deducted. Receive the order with a batch expiry date in Orders.

The included festival_history.csv has 48 synthetic paired observations covering eight products, two festivals and three years. Each row compares a seven-day normal reference period with the same product's festival week. forecast.py fits the festival-to-normal sales ratio from those observations. It applies that ratio to weekday averages from the last 14 completed days of live sales. Days without a sale count as zero. The planner consumes sellable batches in expiry order in its daily simulation. Existing open orders count as incoming supply; the demo assumes timely delivery and a two-day supplier lead time. Dates on or before today display as Today. New products use category history where available and need sales history to establish a normal level.

The expandable evaluation fits on 2023–2024, holds out 2025 and uses each held-out week's normal reference as the baseline. This isolates the festival adjustment. The simulated history cannot establish real-world demand or financial savings.

## Three-minute demonstration

1. On **Overview**, note the available units, low-stock products and earliest expiry dates.
2. Choose **Record sale** and sell two units of baby spinach. Its available stock falls and today's sales rise. A sale uses the earliest unexpired batch first.
3. Choose **Order** beside baby spinach. The suggested quantity covers the next seven days of forecast demand after subtracting sellable stock and open orders.
4. Open **Orders** and choose **Receive**. Enter the delivery's expiry date. Available stock rises only when the order is received. Refresh to demonstrate persistence.
5. Open **Inventory** and filter for **Expiring soon**. The alert counts positive-quantity batches expiring from today through seven days ahead. Review those products for a discount. Expired units stay visible for review and are excluded from sales.

Forecasts use the average daily units sold across the previous seven completed calendar days. The seven-day projection equals that seven-day total. A new product starts at zero projected demand until completed-day sales exist. Low stock means available units are at or below three days' forecast demand, rounded up.

## Run with Docker

```powershell
docker build -t inventory-app:latest .
docker run --rm -p 127.0.0.1:8000:8000 -v fieldstock-data:/data inventory-app:latest
```

## Use with your team's repository

Copy the contents of this folder into a feature branch of the supplied repository, retaining `tests/test_app.py`. The included Jenkinsfile extends the Windows pipeline, keeps the pytest stage and gives the image its original `inventory-app:latest` tag after the image scan succeeds. Run Jenkins on a Windows agent with Python on PATH, Docker with a running Linux-container engine, Gitleaks v8.19+ and Trivy. The agent needs package-index access and scanner database access. The machine-specific Python path from the original Jenkinsfile has been removed.

Use the Jenkins **Build Now** action on that branch. Under **Build Artifacts**, collect the XML test output and JSON reports. A first failed gate stops later stages. Resolve each finding and rerun for a complete set. The Jenkinsfile polls SCM for changes and deploys the scanned build to local staging via Docker Compose on port 8088. Configure the job as Pipeline from SCM on your project branch. The Windows agent needs Docker Compose v2 with --wait support. Staging reuses a named volume and verifies the live forecast endpoint after deployment.

## Reproduce Task 4

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-ci.txt bandit pip-audit
.\.venv\Scripts\python -m pytest tests/
python tools/evaluate.py static dependencies benchmark
python tools/check_sqlite.py
.\.venv\Scripts\python -m bandit -ll app.py inventory.py -f json -o reports/bandit.json
.\.venv\Scripts\python -m pip_audit -r requirements-ci.txt -f json -o reports/pip-audit.json
```

The SQLite check exits with code 1 on a version match. The other checks can be run individually. Run the pipeline for the secret and image scans. See **TASK4.md** for the submitted evaluation and **evidence/** for measured results.

# farm-fresh
