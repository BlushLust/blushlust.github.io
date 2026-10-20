"""Make a 1080x1920 slideshow video (TikTok / Reels / Pinterest video pin) for a dupe.

Slides: the pin image -> "viral vs dupe + price" card -> "link in bio" card.
Usage:  python bot/video.py <dupe-id> [price]      -> assets/videos/<id>.mp4
Needs ffmpeg and the same fonts as run.py.
"""
import json, subprocess, sys, tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

VW, VH = 1080, 1920
SECS = [3.5, 3.5, 2.5]   # per slide
FADE = 0.4


def _bg():
    im = Image.new("RGB", (VW, VH))
    d = ImageDraw.Draw(im)
    top, bot = (244, 246, 248), (204, 211, 219)
    for y in range(VH):
        t = y / VH
        d.line([(0, y), (VW, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return im, d


def _center(d, txt, f, y, fill):
    b = d.textbbox((0, 0), txt, font=f)
    d.text(((VW - (b[2] - b[0])) / 2 - b[0], y), txt, font=f, fill=fill)
    return b[3] - b[1]


def _font(name, size):
    return run.font(name, size / run.K)  # run.font multiplies by K


def _mark(im, y):
    if run.MARK.exists():
        m = Image.open(run.MARK).convert("RGBA").resize((180, 180), Image.LANCZOS)
        im.paste(m, ((VW - m.width) // 2, y), m)


def slide_pin(item, out):
    im, _ = _bg()
    pin = Image.open(run.ROOT / "assets" / "pins" / f"{item['id']}.png").convert("RGB")
    pin = pin.resize((VW, int(pin.height * VW / pin.width)), Image.LANCZOS)
    im.paste(pin, (0, (VH - pin.height) // 2))
    im.save(out)


def slide_compare(item, price, out):
    im, d = _bg()
    y = 620
    y += _center(d, "THE VIRAL PICK", _font("LiberationSans-Bold.ttf", 44), y, run.TEAL) + 30
    for ln in run._wrap(d, item["viral"], _font("LiberationSerif-Bold.ttf", 72), (VW - 140) / run.K)[:3]:
        y += _center(d, ln, _font("LiberationSerif-Bold.ttf", 72), y, run.INK) + 18
    y += 70
    y += _center(d, "vs.", _font("LiberationSerif-BoldItalic.ttf", 120), y, run.RED) + 90
    y += _center(d, "THE DRUGSTORE DUPE", _font("LiberationSans-Bold.ttf", 44), y, run.TEAL) + 30
    for ln in run._wrap(d, item["dupe"], _font("LiberationSerif-Bold.ttf", 72), (VW - 140) / run.K)[:3]:
        y += _center(d, ln, _font("LiberationSerif-Bold.ttf", 72), y, run.INK) + 18
    if price:
        y += 80
        _center(d, price, _font("LiberationSans-Bold.ttf", 64), y, run.PLUM)
    im.save(out)


def slide_cta(out):
    im, d = _bg()
    _mark(im, 560)
    _center(d, "Shop the dupe", _font("LiberationSerif-BoldItalic.ttf", 110), 820, run.INK)
    _center(d, "link in bio", _font("LiberationSans-Bold.ttf", 70), 990, run.PLUM)
    _center(d, "B L U S H   L U S T", _font("LiberationSans-Bold.ttf", 48), 1180, run.NAVY)
    _center(d, "G O U R M E T   B E A U T Y", _font("LiberationSans-Bold.ttf", 28), 1250, run.TEAL)
    im.save(out)


def make(item_id, price=None):
    items = {i["id"]: i for i in json.loads(run.DATA.read_text(encoding="utf-8"))}
    item = items[item_id]
    outdir = run.ROOT / "assets" / "videos"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{item_id}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        s = [Path(tmp) / f"s{n}.png" for n in range(3)]
        slide_pin(item, s[0])
        slide_compare(item, price, s[1])
        slide_cta(s[2])
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for p, secs in zip(s, SECS):
            args += ["-loop", "1", "-t", str(secs), "-i", str(p)]
        args += ["-f", "lavfi", "-t", str(sum(SECS) - 2 * FADE), "-i", "anullsrc=r=44100:cl=stereo"]
        off1 = SECS[0] - FADE
        off2 = off1 + SECS[1] - FADE
        fc = (f"[0][1]xfade=transition=fade:duration={FADE}:offset={off1}[a];"
              f"[a][2]xfade=transition=fade:duration={FADE}:offset={off2},format=yuv420p[v]")
        args += ["-filter_complex", fc, "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-r", "30",
                 "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out)]
        subprocess.run(args, check=True)
    return out


if __name__ == "__main__":
    print(make(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
