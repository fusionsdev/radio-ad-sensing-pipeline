"""Inspect fresh keyword candidates structure."""
import json

with open("data/keyword_candidates_fresh.json") as f:
    data = json.load(f)

print(f"Total: {len(data['new_candidates'])}")

# Sample candidate at index 10
c = data["new_candidates"][10]
print(json.dumps(c, indent=2))

# Collect all stations
stations = set()
for c in data["new_candidates"]:
    stations.update(c["stations"])
print(f"Unique stations: {sorted(stations)}")

# Count companies by frequency range
counts = [c["detection_count"] for c in data["new_candidates"]]
print(f"Counts: min={min(counts)}, max={max(counts)}, median={sorted(counts)[len(counts)//2]}")

# Group by count tiers
tiers = {"100+": 0, "50-99": 0, "20-49": 0, "10-19": 0, "5-9": 0, "2-4": 0, "1": 0}
for cnt in counts:
    if cnt >= 100: tiers["100+"] += 1
    elif cnt >= 50: tiers["50-99"] += 1
    elif cnt >= 20: tiers["20-49"] += 1
    elif cnt >= 10: tiers["10-19"] += 1
    elif cnt >= 5: tiers["5-9"] += 1
    elif cnt >= 2: tiers["2-4"] += 1
    else: tiers["1"] += 1
print(f"\nFrequency tiers: {tiers}")
