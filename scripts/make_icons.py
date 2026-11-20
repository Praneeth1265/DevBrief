"""Draw the DevBrief app icons (coffee cup + code brackets). Run once: python scripts/make_icons.py"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "docs" / "icons"
OUT.mkdir(parents=True, exist_ok=True)
BG, CUP, ACC = (29, 39, 64), (250, 248, 244), (240, 181, 90)


def icon(size, pad_ratio=0.0, rounded=True, mono=False):
    S = 1024
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if not mono:
        if rounded:
            d.rounded_rectangle([0, 0, S, S], radius=230, fill=BG)
        else:
            d.rectangle([0, 0, S, S], fill=BG)
    k = 1 - pad_ratio
    o = S * pad_ratio / 2
    T = lambda x, y: (o + x * k, o + y * k)
    fg = (255, 255, 255) if mono else CUP
    # cup body
    d.rounded_rectangle([*T(250, 400), *T(700, 800)], radius=int(90 * k), fill=fg)
    # handle
    d.ellipse([*T(620, 470), *T(840, 690)], outline=fg, width=int(55 * k))
    d.rectangle([*T(250, 400), *T(700, 520)], fill=fg)
    # saucer
    d.rounded_rectangle([*T(190, 820), *T(830, 870)], radius=int(25 * k), fill=fg)
    # steam as code brackets  < / >
    acc = (255, 255, 255) if mono else ACC
    w = int(42 * k)
    d.line([T(390, 200), T(320, 270), T(390, 340)], fill=acc, width=w, joint="curve")
    d.line([T(500, 190), T(450, 350)], fill=acc, width=w)
    d.line([T(560, 200), T(630, 270), T(560, 340)], fill=acc, width=w, joint="curve")
    if not mono:  # code lines on cup
        d.rounded_rectangle([*T(320, 560), *T(560, 600)], radius=int(20 * k), fill=BG)
        d.rounded_rectangle([*T(320, 650), *T(480, 690)], radius=int(20 * k), fill=ACC)
    return im.resize((size, size), Image.LANCZOS)


icon(192).save(OUT / "icon-192.png")
icon(512).save(OUT / "icon-512.png")
icon(512, pad_ratio=0.22, rounded=False).save(OUT / "maskable-512.png")
icon(180, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png")
icon(96, mono=True).save(OUT / "badge-96.png")
print("icons written to", OUT)
