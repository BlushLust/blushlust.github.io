"""Blush Lust link check - runs before every publish.

Fails (exit 1) if any page or queued dupe would send readers to the wrong place:
  - an Amazon link that isn't amazon.ca, is missing tag=blushlust-20,
    or points to a search page for a dupe that has an ASIN
  - a malformed or duplicate-looking ASIN in data/dupes.json
  - an un-posted dupe in the queue with no ASIN (it would publish a search link)
Warns (doesn't fail) for older posts that still use a search link because no
matching product was found on Amazon.ca.

Run locally:  python bot/validate.py
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
TAG = "blushlust-20"
ASIN_RE = re.compile(r"^B0[0-9A-Z]{8}$|^[0-9]{9}[0-9X]$")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if "amazon." in href or "amzn." in href:
                self.hrefs.append(href)


def main():
    errors, warnings = [], []
    items = json.loads((ROOT / "data" / "dupes.json").read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in items}

    for i in items:
        asin = i.get("asin")
        if asin and not ASIN_RE.match(asin):
            errors.append(f"dupes.json: '{i['id']}' has a malformed ASIN '{asin}'")
        if not asin:
            if i.get("posted"):
                warnings.append(f"dupes.json: '{i['id']}' ({i['dupe']}) has no ASIN - its post uses a search link")
            else:
                errors.append(f"dupes.json: queued dupe '{i['id']}' ({i['dupe']}) has no ASIN")

    # Roundups (gift guides): every item must exist, have an ASIN, and respect the roundup's price cap
    # using the latest price logged by the daily check in data/prices.csv.
    latest = {}
    prices_csv = ROOT / "data" / "prices.csv"
    if prices_csv.exists():
        import csv
        for row in csv.DictReader(prices_csv.open(encoding="utf-8")):
            latest[row["id"]] = row
    rpath = ROOT / "data" / "roundups.json"
    for r in (json.loads(rpath.read_text(encoding="utf-8")) if rpath.exists() else []):
        for x in r["items"]:
            if x not in by_id or not by_id[x].get("asin"):
                errors.append(f"roundups.json: '{r['id']}' item '{x}' missing or has no ASIN")
                continue
            cap, row = r.get("max_price"), latest.get(x)
            if cap and row:
                if row["in_stock"] != "1" or not row["price_cad"]:
                    errors.append(f"roundups.json: '{r['id']}' item '{x}' is out of stock on Amazon.ca")
                elif float(row["price_cad"]) > cap:
                    errors.append(f"roundups.json: '{r['id']}' item '{x}' is ${row['price_cad']}, over the ${cap} cap")
            elif cap:
                warnings.append(f"roundups.json: no logged price yet for '{x}' in '{r['id']}'")

    pages = [ROOT / "index.html", ROOT / "dupe-finder.html", *sorted((ROOT / "posts").glob("*.html"))]
    total = direct = 0
    for p in pages:
        parser = Links()
        parser.feed(p.read_text(encoding="utf-8"))
        name = p.relative_to(ROOT)
        item = by_id.get(p.stem)
        for href in parser.hrefs:
            total += 1
            u = urlparse(href)
            q = parse_qs(u.query)
            if u.netloc != "www.amazon.ca":
                errors.append(f"{name}: Amazon link not on www.amazon.ca -> {u.netloc}")
            if q.get("tag") != [TAG]:
                errors.append(f"{name}: Amazon link missing tag={TAG} -> {u.path}")
            m = re.fullmatch(r"/dp/([0-9A-Z]{10})/?", u.path)
            if m:
                direct += 1
                if item and item.get("asin") and m.group(1) != item["asin"]:
                    errors.append(f"{name}: links to {m.group(1)} but dupes.json says {item['asin']}")
            elif u.path == "/s":
                if item and item.get("asin"):
                    errors.append(f"{name}: search link used even though '{item['id']}' has an ASIN")
                elif not item:
                    errors.append(f"{name}: search link on a hand-made page - use a /dp/ASIN link")
            else:
                errors.append(f"{name}: unrecognised Amazon link path {u.path}")

    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(f"Checked {len(pages)} pages: {total} Amazon links, {direct} direct to product, "
          f"{total - direct} search. {len(errors)} errors, {len(warnings)} warnings.")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
