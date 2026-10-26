"""Black Friday / Cyber Monday price-drop finder.

Compares each dupe's latest Amazon.ca price (data/prices.csv, logged by the daily check)
with its usual price (median of earlier checks) and lists the real drops.

  python bot/price_drops.py               # list drops of 15%+ (min 3 earlier checks)
  python bot/price_drops.py --min 10      # custom threshold (%)
  python bot/price_drops.py --roundup     # also write/refresh the "black-friday-dupe-deals"
                                          # roundup in data/roundups.json (top 8 drops), then
                                          # run `python bot/run.py --rebuild` to publish it
"""
import csv, json, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def drops(min_pct=15.0, min_history=3):
    hist = {}
    for row in csv.DictReader((ROOT / "data" / "prices.csv").open(encoding="utf-8")):
        hist.setdefault(row["id"], []).append(row)
    out = []
    for i, rows in hist.items():
        last, earlier = rows[-1], rows[:-1]
        prev = [float(r["price_cad"]) for r in earlier if r["in_stock"] == "1" and r["price_cad"]]
        if last["in_stock"] != "1" or not last["price_cad"] or len(prev) < min_history:
            continue
        usual, now = statistics.median(prev), float(last["price_cad"])
        pct = (usual - now) / usual * 100
        if pct >= min_pct:
            out.append({"id": i, "usual": usual, "now": now, "pct": round(pct)})
    return sorted(out, key=lambda x: -x["pct"])


def main():
    min_pct = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 15.0
    found = drops(min_pct)
    for d in found:
        print(f"{d['id']}: ${d['usual']:.2f} -> ${d['now']:.2f} ({d['pct']}% off)")
    if not found:
        print(f"No price drops of {min_pct:.0f}%+ right now")
    if "--roundup" in sys.argv and len(found) >= 3:
        items = {i["id"]: i for i in json.loads((ROOT / "data" / "dupes.json").read_text(encoding="utf-8"))}
        picks = [d for d in found if d["id"] in items][:8]
        rpath = ROOT / "data" / "roundups.json"
        rs = [r for r in json.loads(rpath.read_text(encoding="utf-8")) if r["id"] != "black-friday-dupe-deals"]
        rs.append({
            "id": "black-friday-dupe-deals", "eyebrow": "Black Friday", "kicker": "BLACK FRIDAY",
            "hook": ["Dupe deals", "this week"],
            "title": f"Black Friday Makeup Dupe Deals: {len(picks)} Viral Dupes on Sale at Amazon.ca",
            "intro": "Our viral dupes that dropped in price this week on Amazon.ca. Prices change fast, so check the current price before you buy.",
            "items": [d["id"] for d in picks],
            "labels": [f"{items[d['id']]['category']} - {d['pct']}% off" for d in picks],
        })
        rpath.write_text(json.dumps(rs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote black-friday-dupe-deals roundup with {len(picks)} picks")


if __name__ == "__main__":
    main()
