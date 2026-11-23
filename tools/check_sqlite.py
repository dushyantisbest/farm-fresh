"""Targeted advisory check for the SQLite runtime actually loaded by Python."""
import json
import sqlite3
import sys
from pathlib import Path

version = tuple(map(int, sqlite3.sqlite_version.split(".")))
affected = (3, 44, 0) <= version < (3, 49, 1)
report = {
    "component": "SQLite",
    "detected_version": sqlite3.sqlite_version,
    "scope": "One vendor-documented defect, tracked under two IDs; matches upstream version ranges. Distributor backports need separate verification.",
    "advisory_ids": ["CVE-2025-3277", "CVE-2025-29087"],
    "affected_from": "3.44.0",
    "fixed_in": "3.49.1",
    "version_match": affected,
    "source": "https://sqlite.org/cves.html",
    "release_note": "https://sqlite.org/releaselog/3_49_1.html",
}
target = Path(__file__).resolve().parents[1]/"reports"/"sqlite-advisory.json"
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(report,indent=2),encoding="utf8")
print(json.dumps(report))
sys.exit(1 if affected else 0)

