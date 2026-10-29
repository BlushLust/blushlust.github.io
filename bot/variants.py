"""Bold pin variants for top performers (ideas #38/#39) + a Pinterest bulk-upload CSV.

Reads data/variants.json:
  {"start": "2026-11-01", "slots": ["11:00", "19:00"],
   "pins": [{"id": "filter-glow", "theme": "hotpink", "hook": ["line 1", "line 2"]}, ...]}
Writes assets/pins/<id>-b<n>.png and data/bulk-pins.csv (Pinterest bulk create format,
Publish date in UTC). Pins are spread across the slots in file order, one per slot.

Run:  python bot/variants.py
"""
import csv, datetime as dt, json, sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

ROOT = run.ROOT
TZ = ZoneInfo("America/Toronto")


def main():
    spec = json.loads((ROOT / "data" / "variants.json").read_text(encoding="utf-8"))
    items = {i["id"]: i for i in json.loads(run.DATA.read_text(encoding="utf-8"))}
    day = dt.date.fromisoformat(spec["start"])
    slots = [dt.time.fromisoformat(s) for s in spec["slots"]]
    count, rows, titles = {}, [], set()
    for n, p in enumerate(spec["pins"]):
        item = items[p["id"]]
        count[p["id"]] = count.get(p["id"], 0) + 1
        name = f"{p['id']}-b{count[p['id']]}.png"
        run.render_pin_v3(item, ROOT / "assets" / "pins" / name, p.get("hook"), p.get("theme", "hotpink"))
        when = dt.datetime.combine(day + dt.timedelta(days=n // len(slots)), slots[n % len(slots)], TZ)
        hook = " ".join(p.get("hook") or item["hook"]).replace(",", "")
        title = f"{item['viral']} Dupe: {item['dupe']}"
        if title in titles or count[p["id"]] > 1:
            title = f"{hook} | {item['viral']} Dupe"
        title = title[:100]
        assert title not in titles, title
        titles.add(title)
        rows.append({"Title": title, "Media URL": f"{run.SITE}/assets/pins/{name}",
                     "Pinterest board": run.CATEGORY_BOARDS.get(item["category"], "DUPES"),
                     "Thumbnail": "", "Description": run.pin_description(item)[:500],
                     # Pinterest bulk upload rejects rows whose link is already used by another
                     # Pin ("Duplicate Pin link"), so each variant gets its own UTM tag.
                     "Link": f"{run.SITE}/posts/{item['id']}.html?utm_source=pinterest&utm_medium=pin&utm_content={name[:-4]}",
                     "Publish date": when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                     "Keywords": f"{item['viral']} dupe, drugstore makeup dupes, makeup dupes"})
    out = ROOT / "data" / "bulk-pins.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} pins -> {out}")


if __name__ == "__main__":
    main()
