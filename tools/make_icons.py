"""Draws the Dead Ahead icon (bow-arrow over a horizon) at every size the iPhone needs."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "site" / "icons"
NAVY_TOP, NAVY_BOT, CORAL, CREAM = (20, 28, 56), (8, 11, 24), (255, 90, 78), (238, 241, 248)


def draw(size: int, pad: float = 0.0) -> Image.Image:
    S = size * 4  # supersample for smooth edges
    img = Image.new("RGB", (S, S))
    px = img.load()
    for y in range(S):
        t = y / S
        row = tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TOP, NAVY_BOT))
        for x in range(S):
            px[x, y] = row
    d = ImageDraw.Draw(img)
    inner = S * (1 - 2 * pad)
    o = S * pad
    u = lambda v: o + v * inner

    # glow
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse([u(.22), u(.18), u(.78), u(.74)], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(S * .08))
    img.paste(Image.new("RGB", (S, S), CORAL), (0, 0), glow)

    # horizon lines (receding)
    for i, (y, w, a) in enumerate([(.70, .64, 255), (.79, .48, 150), (.87, .32, 80)]):
        col = tuple(int(c * a / 255 + n * (1 - a / 255)) for c, n in zip(CREAM, NAVY_BOT))
        h = inner * .035
        d.rounded_rectangle([u(.5 - w / 2), u(y) - h / 2, u(.5 + w / 2), u(y) + h / 2], radius=h / 2, fill=col)

    # bold arrow pointing straight ahead
    d.polygon([(u(.5), u(.16)), (u(.77), u(.56)), (u(.5), u(.45)), (u(.23), u(.56))], fill=CORAL)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (180, 192, 512):
        draw(size).save(OUT / f"icon-{size}.png")
    draw(512, pad=0.1).save(OUT / "icon-maskable-512.png")
    print("icons ->", OUT)
