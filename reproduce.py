"""Recompute paper statistics from the published timing observations."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def read_csv(name):
    with (DATA / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def main():
    for name, expected in json.loads((ROOT / "checksums.json").read_text()).items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Input checksum mismatch: {name}")
    groups = defaultdict(dict)
    for row in read_csv("timings.csv"):
        key = (row["environment"], row["phase"], row["profile"], row["salt"],
               int(row["implementation"]))
        sample = int(row["session"]), int(row["call"])
        if sample in groups[key]:
            raise ValueError(f"Duplicate observation: {key} {sample}")
        groups[key][sample] = float(row["seconds"])
    protocol = json.loads((DATA / "protocol.json").read_text())
    profiles = list(protocol["profiles"])
    cases = [("main", p, s) for p in profiles for s in ("fixed", "distinct")]
    cases.append(("actual_salt", "private_photo_vault", "fixed32"))
    configs = range(1, 6)
    expected_keys = {(env, *case, i) for env in ("A", "B") for case in cases for i in configs}
    expected_samples = {(s, c) for s in range(5) for c in range(1, 6)}
    if groups.keys() != expected_keys or any(g.keys() != expected_samples for g in groups.values()):
        raise ValueError("Incomplete or unexpected timing matrix")
    rates = {key: protocol["batch"] / median(samples.values()) for key, samples in groups.items()}
    print("profile / salt | A rank | B rank | relative difference in B")
    matches = 0
    for phase, profile, salt in cases[:-1]:
        ranks = {}
        for env in ("A", "B"):
            ranks[env] = sorted(configs, key=lambda i: rates[env, phase, profile, salt, i], reverse=True)
        a, b = ranks["A"][0], ranks["B"][0]
        gap = 100 * (rates["B", phase, profile, salt, a] / rates["B", phase, profile, salt, b] - 1)
        matches += a == b
        print(f"{profile} / {salt} | {ranks['A']} | {ranks['B']} | {gap:.2f}%")
    print(f"Same top configuration: {matches}/6")
    print("\nTable 9: profile | CPU A (1) | GPU A (54) | ratio")
    gpu = {r["profile"]: float(r["throughput"]) for r in read_csv("additional-a.csv")
           if (r["phase"], r["mode"], r["batch"], r["config"]) == ("main", "fixed", "54", "1")}
    for r in read_csv("cpu-a.csv"):
        cpu = float(r["throughput"])
        g = gpu[r["profile"]]
        print(f"{r['profile']} | {cpu:.2f} | {g:.2f} | {g/cpu:.2f}x")


if __name__ == "__main__":
    main()
