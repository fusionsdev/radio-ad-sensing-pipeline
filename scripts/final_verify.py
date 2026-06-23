"""Verify station rotation outputs."""
import csv

print("=== STATION ROTATION — FINAL VERIFICATION ===\n")

# 1. Station performance report
with open("exports/loan_only_station_performance.md") as f:
    report = f.read()
print(f"1. loan_only_station_performance.md: {len(report)} chars")

# 2. Rotation plan CSV
with open("exports/loan_only_station_rotation_plan.csv") as f:
    plan = list(csv.DictReader(f))
print(f"2. loan_only_station_rotation_plan.csv: {len(plan)} rows")
from collections import Counter
decisions = Counter(r["decision"] for r in plan)
print(f"   keep={decisions['keep']}, watch={decisions.get('watch',0)}, rotate_out={decisions.get('rotate_out',0)}")

# 3. Add candidates
with open("exports/loan_station_add_candidates.md") as f:
    add = f.read()
print(f"3. loan_station_add_candidates.md: {len(add)} chars")
print(f"   Keep count in report: {report.count('✅ keep')}")
print(f"   Watch count in report: {report.count('👁️ watch')}")
print(f"   Rotate Out count in report: {report.count('❌ rotate_out')}")

# Cross-check decisions
print(f"\n  Cross-check: CSV keep={decisions['keep']} == Report keep={report.count('✅ keep')} " + 
      f"{'✅' if decisions['keep'] == report.count('✅ keep') else '❌'}")
