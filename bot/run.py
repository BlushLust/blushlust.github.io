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
INK, PLUM, TEAL, NAVY, RED = (78, 20, 52), (98, 26, 64), (32, 90, 107), (42, 51, 62), (143, 29, 51)
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
    top, bot = (244, 246, 248), (204, 211, 219)
    for y in range(H * K):
        t = y / (H * K)
        d.line([(0, y), (W * K, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    g = Image.new("L", im.size, 0)
    ImageDraw.Draw(g).ellipse((100 * K, 200 * K, 900 * K, 1100 * K), fill=140)
    im = Image.composite(Image.new("RGB", im.size, (252, 253, 254)), im, g.filter(ImageFilter.GaussianBlur(160 * K)))
    return im, ImageDraw.Draw(im)


def _kicker(d, kick):
    f = font("LiberationSans-Bold.ttf", 30)
    b = d.textbbox((0, 0), kick, font=f)
    w = (b[2] - b[0]) / K + 70
    x0 = (W - w) / 2
    im = d._image
    box = (int(x0 * K), 110 * K, int((x0 + w) * K), 174 * K)
    grad = Image.new("RGB", (box[2] - box[0], box[3] - box[1]))
    gd = ImageDraw.Draw(grad)
    for x in range(grad.width):
        t = x / max(grad.width - 1, 1)
        gd.line([(x, 0), (x, grad.height)], fill=tuple(int(PLUM[i] + (TEAL[i] - PLUM[i]) * t) for i in range(3)))
    m = Image.new("L", grad.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, grad.width - 1, grad.height - 1), radius=32 * K, fill=255)
    im.paste(grad, box[:2], m)
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
                            fill=(255, 255, 255), outline=(208, 214, 222), width=2 * K)
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
    _ctext(d, "vs.", font("LiberationSerif-BoldItalic.ttf", 80), y + 290, RED)
    card("THE DRUGSTORE DUPE", item["dupe"], y + 410)
    _ctext(d, item["cta"] + " →", font("LiberationSans-Bold.ttf", 36), y + 660, PLUM)

    _footer(im)
    im.resize((W, H), Image.LANCZOS).save(out)


def render_pin_v2(item, out):
    """Fresh-design variant (dark plum, price-led hook) so the same dupe can be re-pinned as new content."""
    im = Image.new("RGB", (W * K, H * K))
    d = ImageDraw.Draw(im)
    top, bot = (60, 12, 38), (24, 60, 72)
    for y in range(H * K):
        t = y / (H * K)
        d.line([(0, y), (W * K, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    white, blush = (255, 255, 255), (246, 196, 214)
    _ctext(d, "SKIP THE SPLURGE", font("LiberationSans-Bold.ttf", 36), 190, blush)
    y = 290
    hook = item.get("hook2") or [item["title"][0].upper() + item["title"][1:], "for way less"]
    size = 100
    while size > 64 and max(d.textbbox((0, 0), ln, font=font("LiberationSerif-BoldItalic.ttf", size))[2]
                            for ln in hook) > 880 * K:
        size -= 4
    for ln in hook:
        y += _ctext(d, ln, font("LiberationSerif-BoldItalic.ttf", size), y, white) + 18
    y += 120
    f_lab, f_name = font("LiberationSans-Bold.ttf", 30), font("LiberationSerif-Bold.ttf", 54)
    for label, name in (("INSTEAD OF", item["viral"]), ("GET", item["dupe"])):
        _ctext(d, label, f_lab, y, blush)
        y += 58
        for ln in _wrap(d, name, f_name, 840)[:2]:
            y += _ctext(d, ln, f_name, y, white) + 16
        y += 90
    _ctext(d, "Find it on Amazon.ca \u2192", font("LiberationSans-Bold.ttf", 42), y + 30, blush)
    if MARK.exists():
        m = Image.open(MARK).convert("RGBA").resize((140 * K, 140 * K), Image.LANCZOS)
        bg = Image.new("RGBA", m.size, (255, 255, 255, 0))
        ImageDraw.Draw(bg).ellipse((0, 0, m.width - 1, m.height - 1), fill=(255, 255, 255, 235))
        bg.alpha_composite(m)
        im.paste(bg, ((W * K - m.width) // 2, 1215 * K), bg)
    _ctext(d, "B L U S H   L U S T", font("LiberationSans-Bold.ttf", 34), 1372, white)
    _ctext(d, "blushlust.github.io", font("LiberationSans-Regular.ttf", 24), 1420, blush)
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
<nav><a href="{root}index.html">Dupes</a><a href="{root}dupe-finder.html">Dupe finder</a><a href="{root}about.html">About</a></nav>
</div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap">&copy; {dt.date.today().year} Blush Lust &middot; Gourmet beauty &middot; Viral makeup looks for less.<br>{DISC} Prices and availability change often &mdash; always check the retailer for current details.<br><a href="{root}privacy.html">Privacy</a></div></footer>
</body></html>'''


def amazon(item):
    """Direct product link when the dupe has an ASIN; search link only as a fallback."""
    if item.get("asin"):
        return f"https://www.amazon.ca/dp/{item['asin']}?tag={TAG}"
    return f"https://www.amazon.ca/s?k={quote_plus(item['dupe'])}&tag={TAG}"


def post_title(item):
    return f"{item['viral']} Dupe: {item['dupe']}"


def _related(item, items, n=3):
    """Same-category dupes (internal links) to keep shoppers browsing."""
    same = [i for i in items if i["id"] != item["id"] and i["category"] == item["category"]]
    start = sum(ord(c) for c in item["id"]) % max(len(same), 1)
    return (same[start:] + same[:start])[:n]


def write_post(item, items=(), roundups=()):
    link = amazon(item)
    rel = _related(item, items)
    rel_html = ""
    if rel:
        cards = "".join(
            f'<li><a href="{i["id"]}.html"><b>{html.escape(i["viral"])}</b> dupe: {html.escape(i["dupe"])} &rarr;</a></li>'
            for i in rel)
        rel_html = f'<section class="dupe"><h2>More {html.escape(item["category"].lower())} dupes</h2><ul>{cards}</ul></section>'
    guides = [r for r in roundups if item["id"] in r["items"]]
    guide_html = "".join(f'<p><a href="{r["id"]}.html">Featured in: {html.escape(r["title"])} &rarr;</a></p>' for r in guides)
    body = f'''
<article><span class="eyebrow">Dupe Alert &middot; {html.escape(item["category"])}</span>
<h1>{html.escape(item["title"][0].upper() + item["title"][1:])}, for less</h1>
<p class="lede">{html.escape(item["blurb"])}</p>
<p class="disclose">This post contains affiliate links. If you buy through them, we may earn a small commission at no extra cost to you. {DISC}</p>
<section class="dupe"><h2>{html.escape(item["dupe"])}</h2>
<div class="vs"><div><b>The viral pick</b>{html.escape(item["viral"])}</div><div class="arrow">vs.</div><div><b>The dupe</b>{html.escape(item["dupe"])}</div></div>
<a class="btn" href="{link}" rel="sponsored nofollow noopener" target="_blank">{"Shop" if item.get("asin") else "Find"} the dupe on Amazon.ca &rarr;</a></section>
<a href="{link}" rel="sponsored nofollow noopener" target="_blank"><img src="../assets/pins/{item["id"]}.png" alt="{html.escape(post_title(item))}" style="max-width:420px;margin:32px auto;border-radius:18px"></a>
<p style="text-align:center"><a class="btn" href="{link}" rel="sponsored nofollow noopener" target="_blank">See today&rsquo;s price on Amazon.ca &rarr;</a></p>
<p style="font-size:.9rem;color:var(--ink-soft)">Comparisons reflect what beauty shoppers commonly say, not lab testing. Shades and formulas vary &mdash; check reviews before you buy.</p>
{rel_html}{guide_html}
<p><a href="../dupe-finder.html">Search every viral dupe &rarr;</a></p>
</article>'''
    (ROOT / "posts" / f"{item['id']}.html").write_text(
        page(post_title(item) + " — Blush Lust", item["blurb"], body, root="../",
             og_image=f"assets/pins/{item['id']}.png"), encoding="utf-8")


ROUNDUPS = ROOT / "data" / "roundups.json"


def load_roundups():
    return json.loads(ROUNDUPS.read_text(encoding="utf-8")) if ROUNDUPS.exists() else []


def write_roundups(items, rerender=False):
    """Gift guides / themed edits built from dupes in dupes.json (data/roundups.json)."""
    by_id = {i["id"]: i for i in items}
    for r in load_roundups():
        picks = [by_id[x] for x in r["items"]]
        img = ROOT / "assets" / "pins" / f"{r['id']}.png"
        if rerender or not img.exists():
            render_roundup(r["kicker"], r["hook"], (r.get("labels") or [i["category"] for i in picks])[:8], img)
        rows = "".join(
            f'<section class="dupe"><span class="eyebrow">{n}. {html.escape(i["category"])}</span>'
            f'<h2>{html.escape(i["dupe"])}</h2>'
            f'<div class="vs"><div><b>The viral pick</b>{html.escape(i["viral"])}</div><div class="arrow">vs.</div>'
            f'<div><b>The dupe</b>{html.escape(i["dupe"])}</div></div>'
            f'<p>{html.escape(i["blurb"])}</p>'
            f'<a class="btn" href="{amazon(i)}" rel="sponsored nofollow noopener" target="_blank">Shop the dupe on Amazon.ca &rarr;</a>'
            f'<p style="font-size:.9rem"><a href="{i["id"]}.html">Full comparison &rarr;</a></p></section>'
            for n, i in enumerate(picks, 1))
        body = (f'<article><span class="eyebrow">{html.escape(r["eyebrow"])}</span><h1>{html.escape(r["title"])}</h1>'
                f'<p class="lede">{html.escape(r["intro"])}</p>'
                f'<p class="disclose">This post contains affiliate links. If you buy through them, we may earn a small commission at no extra cost to you. {DISC}</p>'
                f'{rows}<img src="../assets/pins/{r["id"]}.png" alt="{html.escape(r["title"])}" style="max-width:420px;margin:32px auto;border-radius:18px">'
                '<p style="font-size:.9rem;color:var(--ink-soft)">Prices change often &mdash; check Amazon.ca for the current price.</p></article>')
        (ROOT / "posts" / f"{r['id']}.html").write_text(
            page(r["title"] + " — Blush Lust", r["intro"], body, root="../", og_image=f"assets/pins/{r['id']}.png"),
            encoding="utf-8")


def write_finder(items):
    """Searchable 'viral product -> drugstore dupe' finder (dupe-finder.html)."""
    posted = sorted([i for i in items if i.get("posted")], key=lambda i: i["viral"].lower())
    cats = sorted({i["category"] for i in posted})
    chips = '<button class="chip on" data-cat="">All</button>' + "".join(
        f'<button class="chip" data-cat="{html.escape(c)}">{html.escape(c)}</button>' for c in cats)
    cards = "".join(
        f'<div class="fcard" data-cat="{html.escape(i["category"])}" '
        f'data-q="{html.escape((i["viral"] + " " + i["dupe"] + " " + i["category"] + " " + i["title"]).lower())}">'
        f'<span class="tag">{html.escape(i["category"])}</span>'
        f'<p class="fv">{html.escape(i["viral"])}</p><p class="fa">&darr; dupe</p>'
        f'<h2>{html.escape(i["dupe"])}</h2>'
        f'<a class="btn" href="{amazon(i)}" rel="sponsored nofollow noopener" target="_blank">Shop on Amazon.ca</a> '
        f'<a class="more" href="posts/{i["id"]}.html">Compare &rarr;</a></div>'
        for i in posted)
    body = ('<section class="hero"><h1>Dupe <em>finder</em></h1>'
            '<p>Type a viral product or brand (Charlotte Tilbury, Rare Beauty, Dior...) to find its drugstore dupe.</p>'
            '<input id="q" type="search" placeholder="Search e.g. Pillow Talk, blush, Fenty" autocomplete="off" '
            'style="width:100%;max-width:520px;margin-top:18px;padding:14px 18px;border-radius:999px;border:1px solid var(--line);font:inherit">'
            f'<div class="chips">{chips}</div><p id="count" class="lede" style="font-size:.95rem"></p></section>'
            f'<p class="disclose">This page contains affiliate links. {DISC}</p>'
            f'<section class="grid" id="list">{cards}</section>'
            '<style>.chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:14px}'
            '.chip{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 14px;font:600 .85rem Inter,sans-serif;color:var(--plum);cursor:pointer}'
            '.chip.on{background:var(--plum);color:#fff;border-color:var(--plum)}'
            '.fcard{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px}'
            '.fcard .tag{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--blush-deep);font-weight:700}'
            '.fcard .fv{margin:8px 0 0;color:var(--ink-soft);font-size:.92rem}.fcard .fa{margin:2px 0;color:var(--red);font-size:.8rem}'
            '.fcard h2{font-family:"Playfair Display",Georgia,serif;font-size:1.2rem;margin:0 0 10px;color:var(--ink)}'
            '.fcard .more{font-size:.9rem;margin-left:8px}</style>'
            '<script>(function(){var q=document.getElementById("q"),cards=[].slice.call(document.querySelectorAll(".fcard")),'
            'chips=[].slice.call(document.querySelectorAll(".chip")),cat="",n=document.getElementById("count");'
            'function f(){var t=q.value.toLowerCase().trim(),c=0;cards.forEach(function(e){var ok=(!cat||e.dataset.cat===cat)&&'
            '(!t||t.split(/\\s+/).every(function(w){return e.dataset.q.indexOf(w)>-1}));e.style.display=ok?"":"none";if(ok)c++});'
            'n.textContent=c+" dupe"+(c===1?"":"s")}chips.forEach(function(b){b.onclick=function(){chips.forEach(function(x){x.classList.remove("on")});'
            'b.classList.add("on");cat=b.dataset.cat;f()}});q.oninput=f;var p=new URLSearchParams(location.search).get("q");if(p)q.value=p;f()})();</script>')
    (ROOT / "dupe-finder.html").write_text(
        page("Makeup Dupe Finder — Drugstore Dupes for Viral Makeup | Blush Lust",
             f"Search {len(posted)} drugstore dupes for viral luxury makeup from Charlotte Tilbury, Rare Beauty, Dior, Fenty and more.", body),
        encoding="utf-8")


def write_index(items):
    posted = sorted([i for i in items if i.get("posted")], key=lambda i: i["posted"], reverse=True)
    cards = [f'<a class="card" href="posts/{r["id"]}.html"><span class="tag">{html.escape(r["eyebrow"])}</span>'
             f'<h2>{html.escape(r["title"])}</h2><p>{html.escape(r["intro"])}</p></a>' for r in load_roundups()]
    cards += ['<a class="card" href="posts/viral-makeup-dupes.html"><span class="tag">Dupe Edit</span>'
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


def write_sitemap(items):
    """sitemap.xml + robots.txt so search engines (and Pinterest) find every post."""
    today = dt.date.today().isoformat()
    urls = [("", today), ("dupe-finder.html", today), ("about.html", None), ("posts/viral-makeup-dupes.html", None)]
    urls += [(f"posts/{r['id']}.html", today) for r in load_roundups()]
    urls += [(f"posts/{i['id']}.html", min(i["posted"], today)) for i in items if i.get("posted")]
    body = "".join(f"<url><loc>{SITE}/{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>\n"
                   for u, m in urls)
    (ROOT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      f"{body}</urlset>\n", encoding="utf-8")
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")


# ---------------------------------------------------------------- pinterest
API = os.environ.get("PINTEREST_API") or "https://api.pinterest.com/v5"
SANDBOX = "api-sandbox." in API


def pinterest_post(item):
    """Returns the new pin id, or None if API secrets are not configured
    (or the app is still on Trial access and this is a production run)."""
    app_id, secret = os.environ.get("PINTEREST_APP_ID"), os.environ.get("PINTEREST_APP_SECRET")
    refresh = os.environ.get("PINTEREST_REFRESH_TOKEN")
    if not (app_id and secret and refresh):
        return None
    import requests
    api = API
    print(f"Pinterest API: {api}" + (" (Sandbox)" if SANDBOX else ""))
    if os.environ.get("PINTEREST_ACCESS_TOKEN"):
        # OAuth access token issued via the authorization-code flow (used for Sandbox demo runs)
        tok = {"access_token": os.environ["PINTEREST_ACCESS_TOKEN"]}
        print("OAuth: signed in to Pinterest with the account's OAuth access token")
    else:
        auth = base64.b64encode(f"{app_id}:{secret}".encode()).decode()
        r = requests.post(f"{api}/oauth/token", headers={"Authorization": f"Basic {auth}"},
                          data={"grant_type": "refresh_token", "refresh_token": refresh}, timeout=30)
        if r.status_code >= 300:
            raise SystemExit(f"Pinterest OAuth error {r.status_code}: {r.text}")
        tok = r.json()
        print(f"OAuth: signed in to Pinterest with refresh token (scopes: {tok.get('scope')})")
    hdr = {"Authorization": f"Bearer {tok['access_token']}"}

    me = requests.get(f"{api}/user_account", headers=hdr, timeout=30)
    if me.ok:
        print(f"Pinterest account: {me.json().get('username')}")

    board_id = os.environ.get("PINTEREST_BOARD_ID")
    if not board_id:
        def find_board(name):
            for privacy in (None, "ALL"):
                params = {"page_size": 100}
                if privacy:
                    params["privacy"] = privacy
                res = requests.get(f"{api}/boards", headers=hdr, params=params, timeout=30)
                if not res.ok:
                    print(f"Board list ({privacy or 'default'}) -> {res.status_code}: {res.text[:200]}")
                    continue
                hit = next((b["id"] for b in res.json().get("items", []) if b["name"].lower() == name.lower()), None)
                if hit:
                    return hit
            return None

        board_id = find_board(BOARD_NAME)
        if not board_id and SANDBOX:
            # Sandbox starts empty - create a board there so the demo can pin to it
            for name in (BOARD_NAME, f"{BOARD_NAME} Sandbox"):
                board_id = find_board(name)
                if board_id:
                    break
                b = requests.post(f"{api}/boards", headers=hdr, json={"name": name}, timeout=30)
                if b.ok:
                    board_id = b.json()["id"]
                    print(f"Created Sandbox board '{name}' -> {board_id}")
                    break
                print(f"Could not create Sandbox board '{name}': {b.status_code} {b.text[:200]}")
        if not board_id:
            raise SystemExit(f"Board '{BOARD_NAME}' not found on the Pinterest account")
    print(f"Board '{BOARD_NAME}' -> {board_id}")

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
    if r.status_code == 403 and not SANDBOX and '"code":29' in r.text.replace(" ", ""):
        print("Pinterest app is on Trial access - production Pins not allowed yet; queuing for manual posting")
        return None
    if r.status_code >= 300:
        raise SystemExit(f"Pinterest error {r.status_code}: {r.text}")
    pin = r.json()
    print(f"Pin created: id={pin.get('id')} title={pin.get('title')!r} link={pin.get('link')}")
    return pin.get("id")


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
            write_post(i, items, load_roundups())

    if "--demo" in sys.argv:
        # Demo / review run: pin the next queued dupe (normally to the Sandbox) and change nothing on the site
        nxt = next((i for i in items if not i.get("posted")), None) or items[-1]
        render_pin(nxt, ROOT / "assets" / "pins" / f"{nxt['id']}.png")
        pin_id = pinterest_post(nxt)
        print(f"Demo: pinned {nxt['id']} -> {pin_id}" if pin_id else "Demo: no pin created")
        return

    if "--rebuild" not in sys.argv and not rerender:
        nxt = next((i for i in items if not i.get("posted")), None)
        if not nxt:
            print("Queue empty - add more dupes to data/dupes.json")
        elif not nxt.get("asin"):
            raise SystemExit(f"'{nxt['id']}' has no Amazon ASIN - add \"asin\" to data/dupes.json "
                             "so the pin links to the product page, not a search page")
        else:
            render_pin(nxt, ROOT / "assets" / "pins" / f"{nxt['id']}.png")
            write_post(nxt, items, load_roundups())
            nxt["posted"] = dt.date.today().isoformat()
            pin_id = pinterest_post(nxt)
            if pin_id:
                nxt["pin_id"] = pin_id
                print(f"Pinned {nxt['id']} -> {pin_id}")
            else:
                queue_manual(nxt)
                print(f"Created {nxt['id']} (no Pinterest secrets yet - added to data/pins-to-post.csv)")

    write_roundups(items, rerender)
    write_finder(items)
    write_index(items)
    write_sitemap(items)
    DATA.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    left = sum(1 for i in items if not i.get("posted"))
    print(f"{left} dupes left in the queue")


if __name__ == "__main__":
    main()
