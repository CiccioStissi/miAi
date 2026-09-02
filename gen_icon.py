"""Genera reattore.ico - icona arc reactor per il launcher desktop.
Disegna a 256px con supersampling 4x (bordi lisci), salva multi-size ico.
Uso: python gen_icon.py
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).parent
S = 1024                      # canvas grande = supersampling
C = S // 2
CY = (56, 225, 255, 255)     # ciano HUD
CY_SOFT = (56, 225, 255, 90)
GOLD = (255, 210, 120, 255)
WHITE = (255, 250, 235, 255)


def draw():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def circle(r, fill=None, outline=None, w=1):
        d.ellipse([C - r, C - r, C + r, C + r], fill=fill, outline=outline, width=w)

    # base scura tonda (corpo del reattore)
    circle(int(S * 0.46), fill=(8, 20, 30, 255))
    circle(int(S * 0.46), outline=CY, w=int(S * 0.012))
    # anello glow
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r2 = int(S * 0.40)
    gd.ellipse([C - r2, C - r2, C + r2, C + r2], outline=CY, width=int(S * 0.02))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.02))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)

    circle(int(S * 0.40), outline=CY_SOFT, w=int(S * 0.006))
    circle(int(S * 0.34), outline=CY, w=int(S * 0.008))

    # bobine: 6 trapezi radiali tra r=0.20 e r=0.32
    r_in, r_out = S * 0.20, S * 0.325
    for k in range(6):
        a = math.radians(k * 60)
        aw = math.radians(20)
        pts = []
        for rr, sign in ((r_out, 1), (r_out, -1), (r_in, -1), (r_in, 1)):
            ang = a + sign * aw * (r_in / rr)
            pts.append((C + rr * math.cos(ang), C + rr * math.sin(ang)))
        d.polygon(pts, fill=(56, 225, 255, 60), outline=CY)

    # nucleo triangolo (esagramma stilizzato) + core acceso
    core_glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cg = ImageDraw.Draw(core_glow)
    rc = int(S * 0.13)
    cg.ellipse([C - rc, C - rc, C + rc, C + rc], fill=GOLD)
    core_glow = core_glow.filter(ImageFilter.GaussianBlur(S * 0.03))
    img = Image.alpha_composite(img, core_glow)
    d = ImageDraw.Draw(img)

    def tri(rot):
        pts = [(C + S * 0.15 * math.cos(math.radians(rot + a)),
                C + S * 0.15 * math.sin(math.radians(rot + a))) for a in (0, 120, 240)]
        d.polygon(pts, outline=CY, width=int(S * 0.007))
    tri(-90)
    tri(90)
    circle(int(S * 0.085), fill=GOLD, outline=WHITE, w=int(S * 0.01))
    circle(int(S * 0.035), fill=WHITE)
    return img


def main():
    img = draw().resize((256, 256), Image.LANCZOS)
    out = ROOT / "reattore.ico"
    img.save(out, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    img.save(ROOT / "reattore.png")
    print("scritto", out)


if __name__ == "__main__":
    main()
