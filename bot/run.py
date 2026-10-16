"""Blush Lust daily bot.

Each run:
  1. Picks the next un-posted dupe from data/dupes.json
  2. Renders a 1000x1500 pin image into assets/pins/
  3. Writes a blog post page into posts/ and rebuilds index.html
  4. Posts the pin to Pinterest if API secrets are set; otherwise adds it
     to data/pins-to-post.csv so it can be posted by hand.

Run locally:  python bot/run.py           (one new dupe)
              python bot/run.py --rebuild (only rebuild pages, no new dupe)
              python bot/run.py --rerender (re-draw every pin image + rebuild pages)
"""
import base64, csv, datetime as dt, html, json, os, sys
from pathlib import Path
from urllib.parse import quote_plus

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dupes.json"
SITE = "https://blushlust.github.io"
TAG = "blushlust-20"
DISC = "As an Amazon Associate I earn from qualifying purchases."
BOARD_NAME = os.environ.get("PINTEREST_BOARD", "Makeup Dupes")

# ---------------------------------------------------------------- pin image
INK, PLUM, TEAL, NAVY = (60, 12, 38), (98, 26, 64), (32, 90, 107), (42, 51, 62)
DEEP = TEAL  # card labels
MARK = ROOT / "assets" / "mark.png"
FONT_DIRS = ["/usr/share/fonts/truetype/liberation", "/usr/share/fonts/truetype/liberation2"]
W, H, K = 1000, 1500, 2


def font(name, size):
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size * K)
    raise SystemExit(f"Font {name} not found - install fonts-liberation")


def _ctext(d, txt, f, y, fill=INK):
    b = d.textbbox((0, 0), txt, font=f)
    d.text(((W * K - (b[2] - b[0])) / 2 - b[0], y * K), txt, font=f, fill=fill)
    return (b[3] - b[1]) / K


def _wrap(d, txt, f, maxw):
    lines, cur = [], ""
    for w in txt.split():
        t = (cur + " " + w).strip()
        if d.textbbox((0, 0), t, font=f)[2] > maxw * K and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + [cur]


def _canvas():
    im = Image.new("RGB", (W * K, H * K))
    d = ImageDraw.Draw(im)
    top, bot = (248, 243, 246), (226, 207, 219)
    for y in range(H * K):
        t = y / (H * K)
        d.line([(0, y), (W * K, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    g = Image.new("L", im.size, 0)
    ImageDraw.Draw(g).ellipse((100 * K, 200 * K, 900 * K, 1100 * K), fill=140)
    im = Image.composite(Image.new("RGB", im.size, (255, 252, 253)), im, g.filter(ImageFilter.GaussianBlur(160 * K)))
    return im, ImageDraw.Draw(im)


def _kicker(d, kick):
    f = font("LiberationSans-Bold.ttf", 30)
    b = d.textbbox((0, 0), kick, font=f)
    w = (b[2] - b[0]) / K + 70
    x0 = (W - w) / 2
    d.rounded_rectangle((x0 * K, 110 * K, (x0 + w) * K, 174 * K), radius=32 * K, fill=PLUM)
    _ctext(d, kick, f, 125, (255, 255, 255))


def _footer(im):
    d = ImageDraw.Draw(im)
    if MARK.exists():
        m = Image.open(MARK).convert("RGBA").resize((150 * K, 150 * K), Image.LANCZOS)
        im.paste(m, ((W * K - m.width) // 2, 1195 * K), m)
    _ctext(d, "B L U S H   L U S T", font("LiberationSans-Bold.ttf", 36), 1352, NAVY)
    _ctext(d, "G O U R M E T   B E A U T Y", font("LiberationSans-Bold.ttf", 20), 1402, TEAL)
    _ctext(d, "blushlust.github.io", font("LiberationSans-Regular.ttf", 24), 1442, PLUM)


def render_roundup(title, hook, entries, out):
    im, d = _canvas()
    _kicker(d, title)
    y = 225
    for ln in hook:
        y += _ctext(d, ln, font("LiberationSerif-BoldItalic.ttf", 96), y) + 16
    y += 50
    f = font("LiberationSerif-Bold.ttf", 46)
    fn = font("LiberationSans-Bold.ttf", 28)
    for n, label in enumerate(entries, 1):
        cx, cy = 245, y + 26
        d.ellipse(((cx - 26) * K, (cy - 26) * K, (cx + 26) * K, (cy + 26) * K), fill=TEAL)
        b = d.textbbox((0, 0), str(n), font=fn)
        d.text((cx * K - (b[2] + b[0]) / 2, cy * K - (b[3] + b[1]) / 2), str(n), font=fn, fill=(255, 255, 255))
        d.text((295 * K, (y + 1) * K), label, font=f, fill=INK)
        y += 84
    _footer(im)
    im.resize((W, H), Image.LANCZOS).save(out)


def render_pin(item, out):
    im = Image.new("RGB", (W * K, H * K))
    d = ImageDraw.Draw(im)
    im, d = _canvas()
    _kicker(d, "VIRAL DUPE ALERT")

    y = 230
    size = 104
    while size > 70 and max(d.textbbox((0, 0), ln, font=font("LiberationSerif-BoldItalic.ttf", size))[2]
                            for ln in item["hook"]) > 880 * K:
        size -= 4
    for ln in item["hook"]:
        y += _ctext(d, ln, font("LiberationSerif-BoldItalic.ttf", size), y) + 18

    def card(label, name, cy):
        d.rounded_rectangle((110 * K, cy * K, 890 * K, (cy + 190) * K), radius=28 * K,
                            fill=(255, 255, 255), outline=(226, 208, 218), width=2 * K)
        _ctext(d, label, font("LiberationSans-Bold.ttf", 26), cy + 30, DEEP)
        f2 = font("LiberationSerif-Bold.ttf", 44)
        lines = _wrap(d, name, f2, 700)
        if len(lines) > 1:  # two-line names: smaller type so they sit inside the card
            f2 = font("LiberationSerif-Bold.ttf", 38)
            lines = _wrap(d, name, f2, 700)
        yy = cy + (76 if len(lines) > 1 else 95)
        for ln in lines[:2]:
            _ctext(d, ln, f2, yy)
            yy += 46

    card("THE VIRAL PICK", item["viral"], y + 60)
    _ctext(d, "vs.", font("LiberationSerif-BoldItalic.ttf", 80), y + 290, TEAL)
    card("THE DRUGSTORE DUPE", item["dupe"], y + 410)
    _ctext(d, item["cta"] + " →", font("LiberationSans-Bold.ttf", 36), y + 660, PLUM)

    _footer(im)
    im.resize((W, H), Image.LANCZOS).save(out)


# ---------------------------------------------------------------- web pages
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700'
         '&family=Montserrat:wght@700;800&family=Playfair+Display:ital,wght@0,700;1,700&display=swap" rel="stylesheet">')


def page(title, desc, body, root="", og_image=None):
    og = f'<meta property="og:image" content="{SITE}/{og_image}">' if og_image else ""
    return f'''<!doctype html>
<html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="p:domain_verify" content="fdaa1a79643781f0e78cbfea120224f9"/>
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">{og}<meta name="theme-color" content="#3c0c26">
<link rel="icon" href="{root}assets/favicon.png">{FONTS}<link rel="stylesheet" href="{root}style.css"></head>
<body>
<header class="site-head"><div class="wrap">
<a class="brand" href="{root}index.html"><img src="{root}assets/mark.png" alt="Blush Lust logo"><span><b>Blush Lust</b><small>Gourmet Beauty</small></span></a>
<nav><a href="{root}index.html">Dupes</a><a href="{root}about.html">About</a></nav>
</div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap">&copy; {dt.date.today().year} Blush Lust &middot; Gourmet beauty &middot; Viral makeup looks for less.<br>{DISC} Prices and availability change often &mdash; always check the retailer for current details.<br><a href="{root}privacy.html">Privacy</a></div></footer>
</body></html>'''


def amazon(q):
    return f"https://www.amazon.ca/s?k={quote_plus(q)}&tag={TAG}"


def post_title(item):
    return f"{item['viral']} Dupe: {item['dupe']}"


def write_post(item):
    body = f'''
<article><span class="eyebrow">Dupe Alert &middot; {html.escape(item["category"])}</span>
<h1>{html.escape(item["title"][0].upper() + item["title"][1:])}, for less</h1>
<p class="lede">{html.escape(item["blurb"])}</p>
<p class="disclose">This post contains affiliate links. If you buy through them, we may earn a small commission at no extra cost to you. {DISC}</p>
<section class="dupe"><h2>{html.escape(item["dupe"])}</h2>
<div class="vs"><div><b>The viral pick</b>{html.escape(item["viral"])}</div><div class="arrow">vs.</div><div><b>The dupe</b>{html.escape(item["dupe"])}</div></div>
<a class="btn" href="{amazon(item["dupe"])}" rel="sponsored nofollow noopener" target="_blank">Find the dupe on Amazon.ca &rarr;</a></section>
<img src="../assets/pins/{item["id"]}.png" alt="{html.escape(post_title(item))}" style="max-width:420px;margin:32px auto;border-radius:18px">
<p style="font-size:.9rem;color:var(--ink-soft)">Comparisons reflect what beauty shoppers commonly say, not lab testing. Shades and formulas vary &mdash; check reviews before you buy.</p>
<p><a href="viral-makeup-dupes.html">See all 6 viral makeup dupes &rarr;</a></p>
</article>'''
    (ROOT / "posts" / f"{item['id']}.html").write_text(
        page(post_title(item) + " — Blush Lust", item["blurb"], body, root="../",
             og_image=f"assets/pins/{item['id']}.png"), encoding="utf-8")


def write_index(items):
    posted = sorted([i for i in items if i.get("posted")], key=lambda i: i["posted"], reverse=True)
    cards = ['<a class="card" href="posts/viral-makeup-dupes.html"><span class="tag">Dupe Edit</span>'
             '<h2>6 Viral Makeup Dupes Worth the Hype</h2><p>The drugstore swaps beauty lovers keep comparing to the cult favourites.</p></a>']
    for i in posted:
        cards.append(f'<a class="card" href="posts/{i["id"]}.html"><span class="tag">{html.escape(i["category"])}</span>'
                     f'<h2>{html.escape(i["viral"])} dupe</h2><p>{html.escape(i["dupe"])}</p></a>')
    body = ('<section class="hero"><img class="hero-logo" src="assets/logo-full.png" alt="Blush Lust — Gourmet Beauty" width="320"><h1>Same glow,<br><em>smaller price.</em></h1>'
            '<p>We hunt down the drugstore dupes for the makeup going viral on TikTok and Pinterest &mdash; '
            'so you get the look without the luxury price tag.</p></section>'
            f'<section class="grid">{"".join(cards)}</section>')
    (ROOT / "index.html").write_text(
        page("Blush Lust — Viral Makeup Dupes for Less",
             "Drugstore dupes for the viral makeup everyone is obsessed with.", body), encoding="utf-8")


# ---------------------------------------------------------------- pinterest
def pinterest_post(item):
    """Returns the new pin id, or None if API secrets are not configured."""
    app_id, secret = os.environ.get("PINTEREST_APP_ID"), os.environ.get("PINTEREST_APP_SECRET")
    refresh = os.environ.get("PINTEREST_REFRESH_TOKEN")
    if not (app_id and secret and refresh):
        return None
    import requests
    api = "https://api.pinterest.com/v5"
    auth = base64.b64encode(f"{app_id}:{secret}".encode()).decode()
    r = requests.post(f"{api}/oauth/token", headers={"Authorization": f"Basic {auth}"},
                      data={"grant_type": "refresh_token", "refresh_token": refresh}, timeout=30)
    r.raise_for_status()
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}

    board_id = os.environ.get("PINTEREST_BOARD_ID")
    if not board_id:
        boards = requests.get(f"{api}/boards", headers=hdr, params={"page_size": 100}, timeout=30).json()
        board_id = next((b["id"] for b in boards.get("items", []) if b["name"].lower() == BOARD_NAME.lower()), None)
        if not board_id:
            raise SystemExit(f"Board '{BOARD_NAME}' not found on the Pinterest account")

    img = base64.b64encode((ROOT / "assets" / "pins" / f"{item['id']}.png").read_bytes()).decode()
    body = {
        "board_id": board_id,
        "title": post_title(item)[:100],
        "description": f"{item['blurb']} {item['tags']}"[:500],
        "link": f"{SITE}/posts/{item['id']}.html",
        "alt_text": f"{item['viral']} versus drugstore dupe {item['dupe']}"[:500],
        "media_source": {"source_type": "image_base64", "content_type": "image/png", "data": img},
    }
    r = requests.post(f"{api}/pins", headers=hdr, json=body, timeout=60)
    if r.status_code >= 300:
        raise SystemExit(f"Pinterest error {r.status_code}: {r.text}")
    return r.json().get("id")


def queue_manual(item):
    path = ROOT / "data" / "pins-to-post.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "image", "title", "description", "link"])
        w.writerow([dt.date.today().isoformat(), f"{SITE}/assets/pins/{item['id']}.png",
                    post_title(item), f"{item['blurb']} {item['tags']}", f"{SITE}/posts/{item['id']}.html"])


# ---------------------------------------------------------------- main
def main():
    items = json.loads(DATA.read_text(encoding="utf-8"))
    # backfill pages/images for anything already posted
    rerender = "--rerender" in sys.argv
    if rerender:
        render_roundup("THE DUPE EDIT", ["6 viral makeup", "dupes worth", "the hype"],
                       ["Glow filter", "Liquid blush", "Lip oil", "Skinny brow pencil",
                        "Lengthening mascara", "Setting powder"],
                       ROOT / "assets" / "pins" / "viral-makeup-dupes.png")
    for i in items:
        if i.get("posted"):
            if rerender or not (ROOT / "assets" / "pins" / f"{i['id']}.png").exists():
                render_pin(i, ROOT / "assets" / "pins" / f"{i['id']}.png")
            write_post(i)

    if "--rebuild" not in sys.argv and not rerender:
        nxt = next((i for i in items if not i.get("posted")), None)
        if not nxt:
            print("Queue empty - add more dupes to data/dupes.json")
        else:
            render_pin(nxt, ROOT / "assets" / "pins" / f"{nxt['id']}.png")
            write_post(nxt)
            nxt["posted"] = dt.date.today().isoformat()
            pin_id = pinterest_post(nxt)
            if pin_id:
                nxt["pin_id"] = pin_id
                print(f"Pinned {nxt['id']} -> {pin_id}")
            else:
                queue_manual(nxt)
                print(f"Created {nxt['id']} (no Pinterest secrets yet - added to data/pins-to-post.csv)")

    write_index(items)
    DATA.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    left = sum(1 for i in items if not i.get("posted"))
    print(f"{left} dupes left in the queue")


if __name__ == "__main__":
    main()
