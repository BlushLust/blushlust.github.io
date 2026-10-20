"""Make a 1080x1920 TikTok / Reels / Pinterest video for a dupe (v2 template).

Four scenes, each with a slow zoom ("Ken Burns") and slide/fade transitions:
  1. Hook      - big hook line on brand gradient ("Pocket-sized flush for less")
  2. The pin   - the dupe's pin image
  3. The dupe  - dupe name + price badge
  4. CTA       - "Shop the dupe - link in bio" + logo
Plus an original, royalty-free background track generated here (no copyright issues).

Usage:  python bot/video.py <dupe-id> ["<price> on Amazon.ca"]  -> assets/videos/<id>.mp4
Needs ffmpeg, numpy, Pillow and the same fonts as run.py.
"""
import json, math, struct, subprocess, sys, tempfile, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

VW, VH, FPS = 1080, 1920, 30
SCENES = [2.6, 3.2, 2.8, 2.4]          # seconds per scene
FADE = 0.35                            # transition length
TRANSITIONS = ["slideleft", "smoothup", "fade"]
WHITE, BLUSH = (255, 255, 255), (246, 196, 214)


# ----------------------------------------------------------------- drawing helpers
def _font(name, px):
    return run.font(name, px / run.K)


def _center(d, txt, f, y, fill):
    b = d.textbbox((0, 0), txt, font=f)
    d.text(((VW - (b[2] - b[0])) / 2 - b[0], y), txt, font=f, fill=fill)
    return b[3] - b[1]


def _wrap(d, txt, f, maxw):
    return run._wrap(d, txt, f, maxw / run.K)


def _gradient(top, bot):
    im = Image.new("RGB", (VW, VH))
    d = ImageDraw.Draw(im)
    for y in range(VH):
        t = y / VH
        d.line([(0, y), (VW, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return im, ImageDraw.Draw(im)


def _pill(im, d, txt, y, fg=WHITE):
    f = _font("LiberationSans-Bold.ttf", 44)
    b = d.textbbox((0, 0), txt, font=f)
    w, h = b[2] - b[0] + 80, 84
    x0 = (VW - w) // 2
    d.rounded_rectangle((x0, y, x0 + w, y + h), radius=42, fill=run.PLUM)
    _center(d, txt, f, y + (h - (b[3] - b[1])) / 2 - b[1], fg)


def _logo(im, y, size=200):
    if run.MARK.exists():
        m = Image.open(run.MARK).convert("RGBA").resize((size, size), Image.LANCZOS)
        disc = Image.new("RGBA", m.size, (0, 0, 0, 0))
        ImageDraw.Draw(disc).ellipse((0, 0, size - 1, size - 1), fill=(255, 255, 255, 240))
        disc.alpha_composite(m)
        im.paste(disc, ((VW - size) // 2, y), disc)


def _fit_lines(d, lines, name, start, maxw):
    size = start
    while size > 60 and max(d.textbbox((0, 0), ln, font=_font(name, size))[2] for ln in lines) > maxw:
        size -= 4
    return _font(name, size)


# ----------------------------------------------------------------- scenes
def scene_hook(item, out):
    im, d = _gradient((60, 12, 38), (24, 60, 72))
    _pill(im, d, "VIRAL DUPE ALERT", 520)
    hook = item.get("hook") or [item["title"], "for less"]
    f = _fit_lines(d, hook, "LiberationSerif-BoldItalic.ttf", 150, VW - 120)
    y = 700
    for ln in hook:
        y += _center(d, ln, f, y, WHITE) + 34
    y += 70
    fl = _font("LiberationSans-Bold.ttf", 44)
    _center(d, "SKIP THE SPLURGE ON", fl, y, BLUSH)
    y += 70
    fv = _font("LiberationSerif-Bold.ttf", 60)
    for ln in _wrap(d, item["viral"], fv, VW - 160)[:2]:
        y += _center(d, ln, fv, y, WHITE) + 16
    im.save(out)


def scene_pin(item, out):
    pin = Image.open(run.ROOT / "assets" / "pins" / f"{item['id']}.png").convert("RGB")
    bg = pin.resize((VW, int(pin.height * VW / pin.width))).resize((VW, VH)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (VW, VH), (40, 10, 30)), 0.35)
    w = int(VW * 0.92)
    p = pin.resize((w, int(pin.height * w / pin.width)), Image.LANCZOS)
    shadow = Image.new("RGBA", (p.width + 60, p.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((30, 30, p.width + 30, p.height + 30), radius=36, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    x, y = (VW - p.width) // 2, (VH - p.height) // 2
    bg.paste(shadow, (x - 30, y - 10), shadow)
    mask = Image.new("L", p.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, p.width - 1, p.height - 1), radius=36, fill=255)
    bg.paste(p, (x, y), mask)
    bg.save(out)


def scene_dupe(item, price, out):
    im, d = _gradient((250, 244, 247), (214, 226, 232))
    _center(d, "THE DRUGSTORE DUPE", _font("LiberationSans-Bold.ttf", 46), 470, run.TEAL)
    f = _font("LiberationSerif-Bold.ttf", 92)
    lines = _wrap(d, item["dupe"], f, VW - 140)
    if len(lines) > 2:
        f = _font("LiberationSerif-Bold.ttf", 76)
        lines = _wrap(d, item["dupe"], f, VW - 140)
    y = 570
    for ln in lines[:3]:
        y += _center(d, ln, f, y, run.INK) + 22
    if price:
        amount = price.split(" ")[0]
        y += 90
        r = 190
        cx, cy = VW // 2, y + r
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=run.PLUM)
        fa = _font("LiberationSans-Bold.ttf", 120 if len(amount) <= 6 else 100)
        b = d.textbbox((0, 0), amount, font=fa)
        d.text((cx - (b[2] - b[0]) / 2 - b[0], cy - (b[3] - b[1]) / 2 - b[1] - 20), amount, font=fa, fill=WHITE)
        fo = _font("LiberationSans-Bold.ttf", 38)
        b = d.textbbox((0, 0), "on Amazon.ca", font=fo)
        d.text((cx - (b[2] - b[0]) / 2 - b[0], cy + 70), "on Amazon.ca", font=fo, fill=BLUSH)
        y = cy + r + 70
    _center(d, item.get("cta", "Same look, smaller price"), _font("LiberationSerif-BoldItalic.ttf", 60), y, run.RED)
    im.save(out)


def scene_cta(out):
    im, d = _gradient((24, 60, 72), (60, 12, 38))
    _logo(im, 560, 240)
    _center(d, "Shop the dupe", _font("LiberationSerif-BoldItalic.ttf", 130), 880, WHITE)
    _center(d, "link in bio →", _font("LiberationSans-Bold.ttf", 78), 1060, BLUSH)
    _center(d, "B L U S H   L U S T", _font("LiberationSans-Bold.ttf", 50), 1280, WHITE)
    _center(d, "Follow for a new dupe every day", _font("LiberationSans-Regular.ttf", 40), 1360, BLUSH)
    im.save(out)


# ----------------------------------------------------------------- original music
def make_music(path, seconds, sr=44100, bpm=112):
    """Upbeat pop loop: pad chords (C-G-Am-F), plucked arpeggio, kick, hats. Generated, so royalty-free."""
    n = int(seconds * sr)
    t = np.arange(n) / sr
    beat = 60 / bpm
    out = np.zeros(n)
    chords = [[261.63, 329.63, 392.00], [196.00, 246.94, 293.66], [220.00, 261.63, 329.63], [174.61, 220.00, 261.63]]
    bar = beat * 4
    for i in range(int(seconds / bar) + 1):
        ch = chords[i % 4]
        s, e = int(i * bar * sr), min(n, int((i + 1) * bar * sr))
        if s >= n:
            break
        tt = t[s:e] - t[s]
        env = np.minimum(1, tt / 0.15) * np.exp(-tt * 0.35)
        pad = sum(np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.003 * tt) for f in ch)
        out[s:e] += 0.08 * env * pad
        for k in range(8):                                    # 8th-note arpeggio
            a = int((i * bar + k * beat / 2) * sr)
            if a >= n:
                break
            f = ch[k % 3] * (2 if k % 4 == 3 else 1)
            L = min(n - a, int(0.35 * sr))
            ta = np.arange(L) / sr
            out[a:a + L] += 0.10 * np.exp(-ta * 9) * (np.sin(2 * np.pi * f * 2 * ta) + 0.3 * np.sin(2 * np.pi * f * 4 * ta))
    for k in range(int(seconds / beat) + 1):                 # kick on every beat
        a = int(k * beat * sr)
        if a >= n:
            break
        L = min(n - a, int(0.25 * sr))
        ta = np.arange(L) / sr
        out[a:a + L] += 0.45 * np.exp(-ta * 18) * np.sin(2 * np.pi * (55 + 90 * np.exp(-ta * 30)) * ta)
        h = int((k + 0.5) * beat * sr)                        # off-beat hat
        if h < n:
            L = min(n - h, int(0.05 * sr))
            out[h:h + L] += 0.06 * np.exp(-np.arange(L) / sr * 80) * np.random.default_rng(k).uniform(-1, 1, L)
    fade = int(0.6 * sr)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / (np.abs(out).max() + 1e-9) * 0.7
    pcm = (out * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ----------------------------------------------------------------- assemble
def make(item_id, price=None):
    items = {i["id"]: i for i in json.loads(run.DATA.read_text(encoding="utf-8"))}
    item = items[item_id]
    outdir = run.ROOT / "assets" / "videos"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{item_id}.mp4"
    total = sum(SCENES) - FADE * (len(SCENES) - 1)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        s = [tmp / f"s{n}.png" for n in range(4)]
        scene_hook(item, s[0])
        scene_pin(item, s[1])
        scene_dupe(item, price, s[2])
        scene_cta(s[3])
        music = tmp / "music.wav"
        make_music(music, total)
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for p in s:
            args += ["-loop", "1", "-framerate", str(FPS), "-i", str(p)]
        args += ["-i", str(music)]
        parts = []
        for n, secs in enumerate(SCENES):
            frames = int(secs * FPS)
            zin = n != 1  # pin scene zooms out a touch for variety
            z = "min(1+0.0009*on,1.10)" if zin else "max(1.10-0.0009*on,1.0)"
            parts.append(f"[{n}]scale={VW*2}:{VH*2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                         f":d={frames}:s={VW}x{VH}:fps={FPS},trim=duration={secs},setpts=PTS-STARTPTS[v{n}]")
        off, prev = 0.0, "v0"
        for n in range(1, len(SCENES)):
            off += SCENES[n - 1] - FADE
            tr = TRANSITIONS[(n - 1) % len(TRANSITIONS)]
            parts.append(f"[{prev}][v{n}]xfade=transition={tr}:duration={FADE}:offset={off:.2f}[x{n}]")
            prev = f"x{n}"
        parts.append(f"[{prev}]format=yuv420p[v]")
        args += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", f"{len(SCENES)}:a",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
                 "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)]
        subprocess.run(args, check=True)
    return out


if __name__ == "__main__":
    print(make(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
