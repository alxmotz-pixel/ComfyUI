"""Design set for a faceless "comparison" TikTok account.

Writes every asset as SVG into ./svg and, with --chrome, renders PNGs into ./png
using a headless Chromium binary (no extra Python dependencies).

    python generate.py --chrome /path/to/headless_shell
"""

import argparse
import math
import os
import random
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# Palette
OUT = "#2B2F36"          # outline, one weight everywhere
SW = 8                   # outline width (px at 1024/1080 canvas width)
WHITE = "#FFFFFF"
G1, G2, G3, G4, G5 = "#F2F3F5", "#E6E8EC", "#D9DCE1", "#9AA1AB", "#4A505A"
BLUE = {"base": "#2F7BFF", "light": "#8DB8FF", "dark": "#1A4FBF", "deep": "#173E8C"}
RED = {"base": "#EE3340", "light": "#FF8F96", "dark": "#B41E2A", "deep": "#7C121B"}
BG = G2                  # flat neutral background behind characters
BLUSH = "#FF9E7A"
GOLD = "#FFC83D"          # only for the "rich" costume


def _rgb(c):
    c = c.lstrip("#")
    return [int(c[i:i + 2], 16) for i in (0, 2, 4)]


def mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join("%02X" % round(x + (y - x) * t) for x, y in zip(ra, rb))


class Svg:
    def __init__(self, w, h, bg=None):
        self.w, self.h = w, h
        self.defs = {}
        self.body = []
        self.n = 0
        self.defs["soft"] = '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>'
        self.defs["glow"] = '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="30"/></filter>'
        if bg:
            self.add('<rect width="%d" height="%d" fill="%s"/>' % (w, h, bg))

    def add(self, s):
        self.body.append(s)

    def uid(self, p):
        self.n += 1
        return "%s%d" % (p, self.n)

    def ball(self, base):
        """Radial 'soft 3D' shading, key light from the top left (same for every asset)."""
        key = "ball" + base[1:]
        if key not in self.defs:
            self.defs[key] = ('<radialGradient id="%s" cx="0.36" cy="0.28" r="0.85">'
                              '<stop offset="0" stop-color="%s"/><stop offset="0.5" stop-color="%s"/>'
                              '<stop offset="1" stop-color="%s"/></radialGradient>'
                              % (key, mix(base, WHITE, 0.4), base, mix(base, "#000000", 0.28)))
        return "url(#%s)" % key

    def vgrad(self, top, bottom):
        key = "v" + top[1:] + bottom[1:]
        if key not in self.defs:
            self.defs[key] = ('<linearGradient id="%s" x1="0" y1="0" x2="0" y2="1">'
                              '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>'
                              % (key, top, bottom))
        return "url(#%s)" % key

    def svg(self):
        return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
                '<defs>%s</defs>%s</svg>' % (self.w, self.h, self.w, self.h, "".join(self.defs.values()), "".join(self.body)))

    # primitives -----------------------------------------------------------
    def shape(self, tag, fill, outline=True, extra=""):
        st = ' stroke="%s" stroke-width="%d" stroke-linejoin="round"' % (OUT, SW) if outline else ""
        self.add('<%s fill="%s"%s %s/>' % (tag, fill, st, extra))

    def ell(self, cx, cy, rx, ry, fill, outline=True, extra=""):
        self.shape('ellipse cx="%g" cy="%g" rx="%g" ry="%g"' % (cx, cy, rx, ry), fill, outline, extra)

    def path(self, d, fill, outline=True, extra=""):
        self.shape('path d="%s"' % d, fill, outline, extra)

    def tube(self, d, width, color):
        """Thick rounded stroke with the shared outline (limbs, handles, letters)."""
        self.add('<path d="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round"/>' % (d, OUT, width + 2 * SW))
        self.add('<path d="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round"/>' % (d, color, width))

    def line(self, d, width=SW, color=OUT, extra=""):
        self.add('<path d="%s" fill="none" stroke="%s" stroke-width="%g" stroke-linecap="round" stroke-linejoin="round" %s/>' % (d, color, width, extra))

    def shine(self, cx, cy, rx, ry, rot=-25, op=0.45):
        self.add('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="#FFFFFF" opacity="%g" transform="rotate(%g %g %g)"/>' % (cx, cy, rx, ry, op, rot, cx, cy))

    def shadow(self, cx, cy, rx, ry=None, op=0.16):
        self.add('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="#000" opacity="%g" filter="url(#soft)"/>' % (cx, cy, rx, ry or rx * 0.13, op))


# Faces -------------------------------------------------------------------

def eye(s, cx, cy, rx, ry, expr, lid, side, look=(0, 0)):
    s.ell(cx, cy, rx, ry, WHITE)
    pr = min(rx, ry) * (0.36 if expr == "surprised" else 0.58)
    px, py = cx + look[0] * rx * 0.3, cy + look[1] * ry * 0.3 + ry * 0.08
    s.add('<circle cx="%g" cy="%g" r="%g" fill="%s"/>' % (px, py, pr, OUT))
    s.add('<circle cx="%g" cy="%g" r="%g" fill="#FFF"/>' % (px - pr * 0.35, py - pr * 0.4, pr * 0.32))
    s.add('<circle cx="%g" cy="%g" r="%g" fill="#FFF" opacity="0.8"/>' % (px + pr * 0.35, py + pr * 0.35, pr * 0.14))
    cover = {"proud": 0.42, "annoyed": 0.5}.get(expr)
    if cover:
        cid = s.uid("eye")
        s.defs[cid] = '<clipPath id="%s"><ellipse cx="%g" cy="%g" rx="%g" ry="%g"/></clipPath>' % (cid, cx, cy, rx, ry)
        tilt = side * (-10 if expr == "proud" else 6)
        y = cy - ry + 2 * ry * cover
        s.add('<g clip-path="url(#%s)"><g transform="rotate(%g %g %g)"><rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>'
              '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="%d"/></g></g>'
              % (cid, tilt, cx, y, cx - rx * 2, cy - ry * 2, rx * 4, y - cy + ry * 2, lid, cx - rx * 2, y, cx + rx * 2, y, OUT, SW))
        if expr == "annoyed":
            s.add('<g clip-path="url(#%s)"><rect x="%g" y="%g" width="%g" height="%g" fill="%s"/>'
                  '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="%d"/></g>'
                  % (cid, cx - rx, cy + ry * 0.7, rx * 2, ry, lid, cx - rx, cy + ry * 0.7, cx + rx, cy + ry * 0.7, OUT, SW))
        s.ell(cx, cy, rx, ry, "none")


def brow(s, cx, cy, w, expr, side):
    # side=-1 for the eye on the image left; inner end is towards the face centre
    x0, x1 = cx - w / 2, cx + w / 2
    if expr == "surprised":
        d = "M%g,%g Q%g,%g %g,%g" % (x0, cy - 22, cx, cy - 52, x1, cy - 22)
    elif expr == "annoyed":
        inner, outer = (x1, x0) if side < 0 else (x0, x1)
        d = "M%g,%g L%g,%g" % (outer, cy - 14, inner, cy + 16)
    elif expr == "proud":
        inner, outer = (x1, x0) if side < 0 else (x0, x1)
        d = "M%g,%g Q%g,%g %g,%g" % (outer, cy - 4, cx, cy - 30, inner, cy - 20)
    else:
        d = "M%g,%g Q%g,%g %g,%g" % (x0, cy, cx, cy - 16, x1, cy)
    s.line(d, 14)


def mouth(s, cx, cy, w, expr):
    h = w / 2
    if expr == "surprised":
        s.ell(cx, cy + 10, w * 0.24, w * 0.3, OUT)
        s.add('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="#E8707A"/>' % (cx, cy + 10 + w * 0.16, w * 0.15, w * 0.1))
    elif expr == "annoyed":
        s.line("M%g,%g Q%g,%g %g,%g Q%g,%g %g,%g" % (cx - h, cy + 8, cx - h / 2, cy - 4, cx, cy + 4, cx + h / 2, cy + 12, cx + h, cy + 2), 10)
    elif expr == "proud":
        s.path("M%g,%g Q%g,%g %g,%g Q%g,%g %g,%g Z" % (cx - h, cy + 4, cx + h * 0.1, cy + 6, cx + h * 1.1, cy - 18,
                                                       cx + h * 0.6, cy + h * 0.9, cx - h, cy + 4), OUT)
        s.path("M%g,%g Q%g,%g %g,%g L%g,%g Q%g,%g %g,%g Z" % (cx - h * 0.8, cy + 6, cx, cy + 9, cx + h * 0.95, cy - 12,
                                                              cx + h * 0.85, cy + 2, cx, cy + 22, cx - h * 0.8, cy + 6), WHITE, False)
    elif expr == "happy":
        s.path("M%g,%g Q%g,%g %g,%g Q%g,%g %g,%g Z" % (cx - h, cy, cx, cy + 8, cx + h, cy, cx, cy + w * 0.75, cx - h, cy), OUT)
        s.add('<ellipse cx="%g" cy="%g" rx="%g" ry="%g" fill="#E8707A"/>' % (cx, cy + w * 0.4, w * 0.22, w * 0.11))
    else:
        s.line("M%g,%g Q%g,%g %g,%g" % (cx - h, cy, cx, cy + w * 0.35, cx + h, cy), 10)


def face(s, cx, cy, gap, rx, ry, mouth_dy, mouth_w, expr, lid, brow_dy, look=(0, 0)):
    for side in (-1, 1):
        ex = cx + side * gap / 2
        eye(s, ex, cy, rx, ry, expr, lid, side, look)
        brow(s, ex, cy - ry - brow_dy, rx * 1.4, expr, side)
    mouth(s, cx, cy + mouth_dy, mouth_w, "happy" if expr == "neutral" and mouth_w > 100 else expr)


def mirror(pts):
    return [(1024 - x, y) for x, y in pts]


def arm(s, pts, width, color, hand_r):
    (x0, y0), (x1, y1), (x2, y2) = pts
    s.tube("M%g,%g Q%g,%g %g,%g" % (x0, y0, x1, y1, x2, y2), width, color)
    s.add('<circle cx="%g" cy="%g" r="%g" fill="%s" stroke="%s" stroke-width="%d"/>' % (x2, y2, hand_r, s.ball(color), OUT, SW))


# 1. Narrator mascot "Pip" --------------------------------------------------

PIP_BODY = "#ECEEF2"
PIP_LIMB = "#D5D9E0"
EGG = "M512,560 C720,560 800,860 800,1040 C800,1240 680,1360 512,1360 C344,1360 224,1240 224,1040 C224,860 304,560 512,560 Z"


def pip_front(bg):
    s = Svg(1024, 1536, bg)
    s.shadow(512, 1405, 270, 34)
    for x in (440, 584):
        s.ell(x, 1368, 82, 40, s.ball(G4))
    for pts in ([(262, 1030), (185, 1120), (200, 1235)],):
        arm(s, pts, 54, PIP_LIMB, 42)
        arm(s, mirror(pts), 54, PIP_LIMB, 42)
    s.path(EGG, s.ball(PIP_BODY))
    s.add('<ellipse cx="512" cy="1235" rx="150" ry="95" fill="#FFF" opacity="0.6"/>')
    s.shine(380, 700, 60, 30)
    s.tube("M512,566 C500,500 560,470 582,512 C596,545 560,566 545,540", 22, G5)
    for x in (340, 684):
        s.add('<ellipse cx="%d" cy="985" rx="42" ry="22" fill="%s" opacity="0.4"/>' % (x, BLUSH))
    face(s, 512, 845, 204, 64, 78, 140, 120, "neutral", PIP_LIMB, 50)
    for x in (410, 614):  # oversized round glasses = signature feature
        s.add('<circle cx="%d" cy="845" r="96" fill="#FFF" fill-opacity="0.15" stroke="%s" stroke-width="16"/>' % (x, OUT))
        s.line("M%d,790 Q%d,768 %d,772" % (x - 56, x - 40, x - 18), 9, "#FFF", 'opacity="0.8"')
    s.line("M506,835 Q512,820 518,835", 16)
    s.path("M512,1110 L432,1068 Q410,1110 432,1152 Z", s.ball(BLUE["base"]))
    s.path("M512,1110 L592,1068 Q614,1110 592,1152 Z", s.ball(RED["base"]))
    s.add('<circle cx="512" cy="1110" r="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    return s


def pip_side(bg):
    s = Svg(1024, 1536, bg)
    s.shadow(530, 1405, 270, 34)
    s.ell(470, 1366, 88, 38, s.ball(G5))
    s.path(EGG, s.ball(PIP_BODY))
    s.add('<ellipse cx="610" cy="1235" rx="110" ry="92" fill="#FFF" opacity="0.6"/>')
    s.shine(400, 700, 60, 30)
    s.ell(585, 1372, 98, 40, s.ball(G4))
    s.tube("M500,566 C488,500 548,470 570,512 C584,545 548,566 533,540", 22, G5)
    s.add('<ellipse cx="705" cy="985" rx="32" ry="20" fill="%s" opacity="0.4"/>' % BLUSH)
    eye(s, 668, 845, 46, 78, "neutral", PIP_LIMB, 1, look=(1, 0))
    brow(s, 668, 845 - 78 - 50, 60, "neutral", 1)
    s.line("M612,822 L452,800 Q432,800 432,826", 14)
    s.add('<ellipse cx="672" cy="845" rx="64" ry="96" fill="#FFF" fill-opacity="0.15" stroke="%s" stroke-width="16"/>' % OUT)
    s.line("M640,790 Q650,768 664,770", 9, "#FFF", 'opacity="0.8"')
    s.line("M705,990 Q745,1012 772,982", 10)
    s.path("M705,1110 L640,1070 Q622,1110 640,1150 Z", s.ball(RED["base"]))
    s.path("M705,1110 L752,1086 Q760,1110 752,1134 Z", s.ball(BLUE["base"]))
    s.add('<ellipse cx="708" cy="1110" rx="18" ry="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    arm(s, [(520, 1040), (540, 1150), (575, 1240)], 54, PIP_LIMB, 42)
    return s


# 2. Comparison figures ----------------------------------------------------

POSES_A = {
    "neutral":   [(382, 860), (330, 1000), (325, 1140)],
    "proud":     [(382, 860), (255, 960), (368, 1070)],
    "surprised": [(382, 850), (270, 740), (250, 560)],
    "annoyed":   [(382, 860), (300, 975), (290, 1100)],
}
POSES_B = {
    "neutral":   [(262, 1060), (205, 1150), (210, 1245)],
    "proud":     [(262, 1060), (150, 1120), (255, 1205)],
    "surprised": [(262, 1040), (175, 940), (190, 810)],
    "annoyed":   [(262, 1060), (180, 1140), (165, 1225)],
}


def figure_a(expr, bg):
    """Side A: tall, slim, a bit of a show-off. Blue."""
    c = BLUE
    s = Svg(1024, 1536, bg)
    s.shadow(512, 1418, 200, 30)
    for x0, x1 in ((470, 462), (554, 562)):
        s.tube("M%d,1240 L%d,1385" % (x0, x1), 42, c["dark"])
    s.ell(452, 1404, 54, 26, s.ball(G5))
    s.ell(572, 1404, 54, 26, s.ball(G5))
    s.path("M362,510 A150,150 0 0 1 662,510 L662,1130 A150,150 0 0 1 362,1130 Z", s.ball(c["base"]))
    s.shine(420, 470, 46, 24)
    s.path("M392,800 Q512,880 632,800 L632,842 Q512,922 392,842 Z", s.ball(WHITE))
    s.path("M512,882 L488,912 L512,1020 L536,912 Z", s.ball(c["dark"]))
    s.path("M372,478 C350,330 520,250 704,300 C636,320 650,362 656,446 C600,384 480,384 372,478 Z", s.ball(c["deep"]))
    for x in (430, 594):
        s.add('<ellipse cx="%d" cy="682" rx="30" ry="15" fill="%s" opacity="0.35"/>' % (x, BLUSH))
    face(s, 512, 600, 116, 40, 50, 98, 84, expr, c["dark"], 34)
    arm(s, POSES_A[expr], 36, mix(c["base"], c["dark"], 0.3), 30)
    arm(s, mirror(POSES_A[expr]), 36, mix(c["base"], c["dark"], 0.3), 30)
    return s


def figure_b(expr, bg):
    """Side B: short, wide, loud. Red, backwards-tilted cap."""
    c = RED
    s = Svg(1024, 1536, bg)
    s.shadow(512, 1418, 300, 36)
    for x in (440, 584):
        s.tube("M%d,1320 L%d,1385" % (x, x), 56, c["dark"])
    s.ell(428, 1406, 66, 28, s.ball(G5))
    s.ell(596, 1406, 66, 28, s.ball(G5))
    arm(s, POSES_B[expr], 58, mix(c["base"], c["dark"], 0.25), 40)
    arm(s, mirror(POSES_B[expr]), 58, mix(c["base"], c["dark"], 0.25), 40)
    s.ell(512, 1080, 282, 272, s.ball(c["base"]))
    s.add('<ellipse cx="512" cy="1250" rx="160" ry="70" fill="#FFF" opacity="0.25"/>')
    s.shine(380, 930, 60, 30)
    s.path("M676,872 Q800,858 840,898 Q770,926 676,908 Z", s.ball(c["dark"]))
    s.path("M318,890 C318,742 706,742 706,890 Q512,850 318,890 Z", s.ball(mix(c["base"], c["dark"], 0.55)))
    s.line("M512,770 L512,878", 6, mix(c["dark"], OUT, 0.3))
    s.add('<circle cx="512" cy="768" r="16" fill="#FFF" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    for x in (360, 664):
        s.add('<ellipse cx="%d" cy="1080" rx="44" ry="22" fill="%s" opacity="0.4"/>' % (x, BLUSH))
    face(s, 512, 990, 184, 56, 64, 130, 150, expr, c["dark"], 34)
    return s


# 3. Backgrounds 1080x1920 ------------------------------------------------

def bg_split():
    s = Svg(1080, 1920)
    s.add('<rect width="540" height="1920" fill="%s"/>' % s.vgrad(mix(BLUE["base"], WHITE, 0.25), BLUE["deep"]))
    s.add('<rect x="540" width="540" height="1920" fill="%s"/>' % s.vgrad(mix(RED["base"], WHITE, 0.25), RED["deep"]))
    for x, c in ((270, BLUE), (810, RED)):
        s.add('<polygon points="%d,0 %d,0 %d,1560 %d,1560" fill="#FFF" opacity="0.10" filter="url(#glow)"/>' % (x - 70, x + 70, x + 240, x - 240))
        s.add('<rect x="%d" y="1500" width="540" height="420" fill="%s"/>' % (x - 270, s.vgrad(c["dark"], c["deep"])))
        s.add('<ellipse cx="%d" cy="1610" rx="220" ry="46" fill="#FFF" opacity="0.22" filter="url(#soft)"/>' % x)
    s.line("M0,1500 L1080,1500", SW)
    s.add('<rect x="525" width="30" height="1920" fill="#FFF" opacity="0.6" filter="url(#soft)"/>')
    s.add('<rect x="533" width="14" height="1920" fill="#FFF" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    return s


def bg_podium():
    s = Svg(1080, 1920)
    s.add('<rect width="1080" height="1520" fill="%s"/>' % s.vgrad(G1, G3))
    for x in range(90, 1080, 180):
        s.add('<rect x="%d" y="0" width="6" height="1520" fill="#FFF" opacity="0.5"/>' % x)
    s.add('<rect y="1520" width="1080" height="400" fill="%s"/>' % s.vgrad(G2, "#C9CDD3"))
    s.line("M0,1520 L1080,1520", SW)
    s.add('<polygon points="470,0 610,0 900,1640 180,1640" fill="#FFF" opacity="0.35" filter="url(#glow)"/>')
    s.shadow(540, 1712, 470, 40, 0.18)
    for x0, x1, top, trim in ((130, 400, 1410, BLUE["base"]), (680, 950, 1480, RED["base"]), (400, 680, 1290, G5)):
        s.path("M%d,%d L%d,%d L%d,1710 L%d,1710 Z" % (x0, top, x1, top, x1, x0), s.vgrad(WHITE, G3))
        s.path("M%d,%d L%d,%d L%d,%d L%d,%d Z" % (x0 + 16, top - 44, x1 - 16, top - 44, x1, top, x0, top), s.vgrad(WHITE, G1))
        s.add('<rect x="%d" y="%d" width="%d" height="26" fill="%s" stroke="%s" stroke-width="%d"/>' % (x0, top, x1 - x0, s.ball(trim), OUT, SW))
    return s


def bg_city():
    rnd = random.Random(7)
    s = Svg(1080, 1920)
    s.add('<rect width="1080" height="1920" fill="%s"/>' % s.vgrad("#7DB6FF", "#EAF4FF"))
    s.add('<circle cx="860" cy="330" r="190" fill="%s" opacity="0.45" filter="url(#glow)"/>' % "#FFE3B0")
    s.add('<circle cx="860" cy="330" r="110" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball("#FFD9A0"), OUT, SW))
    for cx, cy, k in ((220, 360, 1.0), (640, 560, 0.75), (140, 820, 0.6)):
        s.path("M%g,%g a%g,%g 0 0 1 %g,%g a%g,%g 0 0 1 %g,%g a%g,%g 0 0 1 %g,%g Z"
               % (cx - 150 * k, cy, 60 * k, 60 * k, 110 * k, -40 * k, 80 * k, 80 * k, 140 * k, 0, 55 * k, 55 * k, 50 * k, 40 * k),
               s.vgrad(WHITE, G1))
    x = -20
    while x < 1080:
        w = rnd.randint(90, 150)
        h = rnd.randint(280, 560)
        s.add('<rect x="%d" y="%d" width="%d" height="%d" fill="#B9CBE4" opacity="0.8"/>' % (x, 1690 - h - 180, w, h + 180))
        x += w + rnd.randint(-10, 10)
    x = -30
    while x < 1080:
        w = rnd.randint(130, 210)
        h = rnd.randint(220, 480)
        top = 1690 - h
        s.path("M%d,1690 L%d,%d L%d,%d L%d,1690 Z" % (x, x, top, x + w, top, x + w), s.vgrad(rnd.choice((G3, G4, "#C3C8D0")), G4))
        for wy in range(top + 40, 1640, 70):
            for wx in range(x + 24, x + w - 40, 52):
                col = rnd.choice((G1, G1, G1, BLUE["light"], RED["light"]))
                s.add('<rect x="%d" y="%d" width="28" height="38" rx="6" fill="%s"/>' % (wx, wy, col))
        x += w + rnd.randint(20, 50)
    s.add('<rect y="1680" width="1080" height="70" fill="%s" stroke="%s" stroke-width="%d"/>' % (G3, OUT, SW))
    s.add('<rect y="1750" width="1080" height="170" fill="%s"/>' % G5)
    for dx in range(30, 1080, 180):
        s.add('<rect x="%d" y="1830" width="100" height="14" rx="7" fill="#FFF" opacity="0.85"/>' % dx)
    return s


def bg_living():
    s = Svg(1080, 1920)
    s.add('<rect width="1080" height="1500" fill="%s"/>' % s.vgrad(G1, G2))
    s.add('<rect y="1500" width="1080" height="420" fill="%s"/>' % s.vgrad("#DCD7D0", "#C8C2BA"))
    for y in range(1560, 1920, 70):
        s.line("M0,%d L1080,%d" % (y, y), 3, "#B8B1A8")
    s.add('<rect y="1470" width="1080" height="40" fill="%s" stroke="%s" stroke-width="%d"/>' % (WHITE, OUT, SW))
    # window, upper left
    s.add('<rect x="80" y="330" width="330" height="520" rx="18" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.vgrad("#9CC6FF", "#E3F0FF"), OUT, SW))
    s.line("M245,330 L245,850 M80,590 L410,590", SW)
    s.add('<rect x="60" y="850" width="370" height="30" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (WHITE, OUT, SW))
    # abstract framed picture, right wall
    s.add('<rect x="690" y="460" width="300" height="240" rx="12" fill="%s" stroke="%s" stroke-width="%d"/>' % (WHITE, OUT, SW))
    s.add('<circle cx="790" cy="560" r="55" fill="%s"/>' % RED["light"])
    s.add('<path d="M720,670 L840,600 L960,670 Z" fill="%s"/>' % BLUE["light"])
    # sofa on the left, lamp on the right, rug in the middle; centre stays clear
    s.shadow(180, 1580, 300, 30)
    s.path("M-40,1170 Q-40,1120 10,1120 L330,1120 Q380,1120 380,1170 L380,1420 L-40,1420 Z", s.ball(BLUE["base"]))
    s.path("M-40,1330 L420,1330 Q450,1330 450,1370 L450,1540 L-40,1540 Z", s.ball(mix(BLUE["base"], BLUE["dark"], 0.3)))
    s.add('<rect x="-40" y="1300" width="430" height="70" rx="30" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(BLUE["light"]), OUT, SW))
    s.shadow(930, 1590, 110, 20)
    s.line("M930,1580 L930,1050", 14)
    s.ell(930, 1585, 80, 20, s.ball(G5))
    s.path("M850,1060 L880,900 L980,900 L1010,1060 Z", s.ball(RED["base"]))
    s.add('<ellipse cx="930" cy="1180" rx="140" ry="160" fill="%s" opacity="0.25" filter="url(#glow)"/>' % RED["light"])
    s.ell(560, 1730, 380, 100, s.vgrad(G3, G4))
    s.add('<ellipse cx="560" cy="1730" rx="300" ry="70" fill="none" stroke="#FFF" stroke-width="10" opacity="0.6"/>')
    return s


def bg_grid():
    s = Svg(1080, 1920, WHITE)
    for i, x in enumerate(range(0, 1081, 60)):
        s.line("M%d,0 L%d,1920" % (x, x), 3 if i % 5 else 4, "#E3E7EC" if i % 5 else "#D2D8DF")
    for i, y in enumerate(range(0, 1921, 60)):
        s.line("M0,%d L1080,%d" % (y, y), 3 if i % 5 else 4, "#E3E7EC" if i % 5 else "#D2D8DF")
    s.defs["vig"] = ('<radialGradient id="vig" cx="0.5" cy="0.5" r="0.75"><stop offset="0.6" stop-color="#FFF" stop-opacity="0"/>'
                     '<stop offset="1" stop-color="%s" stop-opacity="0.6"/></radialGradient>' % G2)
    s.add('<rect width="1080" height="1920" fill="url(#vig)"/>')
    return s


def bg_solo(c):
    """Full-screen stage for one side (close-up when that side is talked about)."""
    s = Svg(1080, 1920)
    s.add('<rect width="1080" height="1920" fill="%s"/>' % s.vgrad(mix(c["base"], WHITE, 0.25), c["deep"]))
    for i in range(12):
        a = math.radians(i * 30 + 15)
        s.add('<polygon points="540,760 %g,%g %g,%g" fill="#FFF" opacity="0.06"/>'
              % (540 + 2400 * math.cos(a), 760 + 2400 * math.sin(a), 540 + 2400 * math.cos(a + 0.22), 760 + 2400 * math.sin(a + 0.22)))
    s.add('<circle cx="540" cy="760" r="420" fill="#FFF" opacity="0.18" filter="url(#glow)"/>')
    s.add('<rect y="1560" width="1080" height="360" fill="%s"/>' % s.vgrad(c["dark"], c["deep"]))
    s.line("M0,1560 L1080,1560", SW)
    s.add('<ellipse cx="540" cy="1720" rx="420" ry="70" fill="#FFF" opacity="0.2" filter="url(#soft)"/>')
    return s


# 4. Props 1024x1024, transparent, per colour variant --------------------

def prop_money(s, c):
    s.shadow(512, 760, 330, 44)
    for rot, dy in ((-8, 40), (-3, 18), (3, -4)):
        s.add('<g transform="rotate(%d 512 520)">' % rot)
        s.add('<rect x="232" y="%d" width="560" height="290" rx="26" fill="%s" stroke="%s" stroke-width="%d"/>' % (375 + dy, s.ball(mix(c["base"], WHITE, 0.55)), OUT, SW))
        s.add('</g>')
    s.add('<g transform="rotate(3 512 520)">')
    s.add('<rect x="262" y="400" width="500" height="230" rx="18" fill="none" stroke="%s" stroke-width="6"/>' % c["dark"])
    s.add('<circle cx="512" cy="515" r="72" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<circle cx="512" cy="515" r="36" fill="none" stroke="#FFF" stroke-width="10"/>')
    s.add('<rect x="350" y="356" width="70" height="318" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(WHITE), OUT, SW))
    s.add('</g>')


def prop_scale(s, c):
    s.shadow(512, 868, 220, 30)
    s.path("M402,860 Q402,800 452,800 L572,800 Q622,800 622,860 Z", s.ball(G4))
    s.add('<rect x="494" y="330" width="36" height="480" rx="12" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    for px in (262, 762):
        s.line("M%d,372 L%d,610 M%d,372 L%d,610" % (px, px - 112, px, px + 112), 6)
        s.path("M%d,606 Q%d,712 %d,606 Z" % (px - 130, px, px + 130), s.ball(c["base"]))
        s.add('<circle cx="%d" cy="370" r="14" fill="%s" stroke="%s" stroke-width="%d"/>' % (px, G3, OUT, SW))
    s.add('<rect x="232" y="346" width="560" height="34" rx="17" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<circle cx="512" cy="322" r="34" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["dark"]), OUT, SW))


def prop_trophy(s, c):
    s.shadow(512, 840, 200, 28)
    for d in ("M350,355 C220,350 225,540 385,530", "M674,355 C804,350 799,540 639,530"):
        s.tube(d, 34, c["dark"])
    s.path("M322,290 L702,290 Q702,560 512,624 Q322,560 322,290 Z", s.ball(c["base"]))
    s.ell(512, 290, 190, 30, s.ball(c["light"]))
    s.add('<path d="M512,370 L532,420 L586,424 L544,458 L558,510 L512,482 L466,510 L480,458 L438,424 L492,420 Z" fill="#FFF" opacity="0.75"/>')
    s.shine(390, 400, 24, 70, 10)
    s.add('<rect x="478" y="612" width="68" height="100" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["dark"]), OUT, SW))
    s.add('<rect x="372" y="700" width="280" height="120" rx="20" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
    s.add('<rect x="432" y="735" width="160" height="50" rx="10" fill="%s"/>' % G3)


def prop_globe(s, c):
    s.shadow(512, 870, 180, 26)
    s.tube("M512,770 A300,300 0 0 1 512,170", 24, G4)
    s.tube("M512,770 L512,830", 30, G4)
    s.ell(512, 850, 150, 30, s.ball(G5))
    s.add('<circle cx="512" cy="470" r="250" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    cid = s.uid("globe")
    s.defs[cid] = '<clipPath id="%s"><circle cx="512" cy="470" r="246"/></clipPath>' % cid
    s.add('<g clip-path="url(#%s)" fill="%s" stroke="%s" stroke-width="5">' % (cid, mix(c["light"], WHITE, 0.3), mix(c["dark"], OUT, 0.2)))
    s.add('<path d="M330,300 C390,250 470,280 460,340 C450,400 520,420 500,480 C480,540 400,520 380,470 C360,420 290,380 330,300 Z"/>')
    s.add('<path d="M580,250 C650,230 720,280 700,330 C680,370 610,350 590,320 Z"/>')
    s.add('<path d="M560,520 C620,490 700,520 690,600 C680,680 600,700 570,640 C540,590 520,550 560,520 Z"/>')
    s.add('</g>')
    s.shine(420, 360, 70, 34)


def prop_stopwatch(s, c):
    s.shadow(512, 868, 260, 32)
    s.add('<rect x="482" y="170" width="60" height="80" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G4), OUT, SW))
    s.add('<rect x="440" y="140" width="144" height="44" rx="20" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["dark"]), OUT, SW))
    s.add('<rect x="700" y="250" width="50" height="80" rx="12" fill="%s" stroke="%s" stroke-width="%d" transform="rotate(42 725 290)"/>' % (s.ball(G4), OUT, SW))
    s.add('<circle cx="512" cy="540" r="300" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<circle cx="512" cy="540" r="232" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(WHITE), OUT, SW))
    s.add('<path d="M512,540 L512,320 A220,220 0 0 1 702,430 Z" fill="%s" opacity="0.35"/>' % c["light"])
    for i in range(12):
        a = math.radians(i * 30)
        r0 = 180 if i % 3 else 160
        s.line("M%g,%g L%g,%g" % (512 + r0 * math.sin(a), 540 - r0 * math.cos(a), 512 + 208 * math.sin(a), 540 - 208 * math.cos(a)), 10)
    s.line("M512,540 L690,438", 16, c["dark"])
    s.add('<circle cx="512" cy="540" r="22" fill="%s" stroke="%s" stroke-width="%d"/>' % (c["dark"], OUT, SW))
    s.shine(370, 380, 60, 28)


def prop_house(s, c):
    s.shadow(512, 840, 300, 36)
    s.add('<rect x="636" y="290" width="64" height="150" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G4), OUT, SW))
    s.add('<rect x="282" y="460" width="460" height="365" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(WHITE), OUT, SW))
    s.path("M222,500 L512,240 L802,500 Q812,520 790,520 L234,520 Q212,520 222,500 Z", s.ball(c["base"]))
    s.path("M462,825 L462,690 A50,50 0 0 1 562,690 L562,825 Z", s.ball(c["dark"]))
    s.add('<circle cx="540" cy="760" r="8" fill="%s"/>' % c["light"])
    for x in (322, 604):
        s.add('<rect x="%d" y="570" width="98" height="98" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (x, s.vgrad(mix(c["light"], WHITE, 0.4), WHITE), OUT, SW))
        s.line("M%d,570 L%d,668 M%d,619 L%d,619" % (x + 49, x + 49, x, x + 98), 6)


def prop_car(s, c):
    s.shadow(512, 800, 380, 34)
    s.path("M320,520 Q350,372 470,366 L610,366 Q720,372 770,520 Z", s.ball(c["base"]))
    s.path("M368,512 Q392,412 476,404 L536,404 L536,512 Z", s.vgrad(mix(c["light"], WHITE, 0.5), WHITE))
    s.path("M570,404 L606,404 Q690,410 718,512 L570,512 Z", s.vgrad(mix(c["light"], WHITE, 0.5), WHITE))
    s.add('<rect x="170" y="505" width="684" height="200" rx="74" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.line("M553,520 L553,690", 6)
    s.add('<rect x="590" y="560" width="50" height="14" rx="7" fill="%s"/>' % c["dark"])
    s.ell(826, 575, 22, 30, "#FFF3C4")
    s.ell(196, 575, 16, 26, c["dark"])
    s.shine(330, 545, 70, 18, -5)
    for x in (330, 694):
        s.add('<circle cx="%d" cy="712" r="82" fill="%s" stroke="%s" stroke-width="%d"/>' % (x, s.ball("#3A3F47"), OUT, SW))
        s.add('<circle cx="%d" cy="712" r="34" fill="%s" stroke="%s" stroke-width="%d"/>' % (x, s.ball(G3), OUT, SW))


def prop_magnifier(s, c):
    s.shadow(560, 870, 280, 30)
    s.tube("M610,610 L820,820", 74, c["base"])
    s.tube("M610,610 L650,650", 74, G4)
    s.add('<circle cx="450" cy="450" r="215" fill="%s" fill-opacity="0.75"/>' % s.vgrad(mix(c["light"], WHITE, 0.6), WHITE))
    s.add('<circle cx="450" cy="450" r="215" fill="none" stroke="%s" stroke-width="%d"/>' % (OUT, 46 + 2 * SW))
    s.add('<circle cx="450" cy="450" r="215" fill="none" stroke="%s" stroke-width="46"/>' % G4)
    s.add('<circle cx="450" cy="450" r="200" fill="none" stroke="#FFF" stroke-width="6" opacity="0.6"/>')
    s.line("M330,380 A140,140 0 0 1 420,300", 22, "#FFF", 'opacity="0.85"')


def prop_doctor_bag(s, c):
    s.shadow(512, 840, 300, 34)
    s.tube("M400,400 L400,330 Q400,290 440,290 L584,290 Q624,290 624,330 L624,400", 30, G5)
    s.add('<rect x="232" y="390" width="560" height="430" rx="60" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.line("M240,480 Q512,520 784,480", SW)
    s.add('<rect x="482" y="500" width="60" height="220" rx="14" fill="#FFF" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    s.add('<rect x="402" y="580" width="220" height="60" rx="14" fill="#FFF" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    s.add('<rect x="488" y="584" width="48" height="52" fill="#FFF"/>')
    s.shine(320, 450, 50, 22)


def prop_mask(s, c):
    """Smiling mask on a stick: fake friends."""
    s.shadow(560, 880, 220, 28)
    s.tube("M600,640 L760,880", 34, G5)
    s.path("M512,180 C700,180 780,320 780,470 C780,640 660,730 512,730 C364,730 244,640 244,470 C244,320 324,180 512,180 Z", s.ball(c["light"]))
    for x, side in ((420, -1), (604, 1)):
        s.path("M%d,430 Q%d,380 %d,430 Q%d,470 %d,430 Z" % (x - 60, x, x + 60, x, x - 60), OUT)
        s.line("M%d,%d L%d,%d" % (x - 60 * side, 330, x + 50 * side, 370), 14)
    s.path("M380,560 Q512,680 644,560 Q512,620 380,560 Z", OUT)
    s.add('<ellipse cx="360" cy="520" rx="40" ry="22" fill="%s" opacity="0.5"/>' % BLUSH)
    s.add('<ellipse cx="664" cy="520" rx="40" ry="22" fill="%s" opacity="0.5"/>' % BLUSH)
    s.shine(380, 280, 60, 26)


PROPS = {"geldbuendel": prop_money, "waage": prop_scale, "pokal": prop_trophy, "weltkugel": prop_globe,
         "stoppuhr": prop_stopwatch, "haus": prop_house, "auto": prop_car, "lupe": prop_magnifier,
         "arztkoffer": prop_doctor_bag, "maske": prop_mask}


# 5. Comparison elements --------------------------------------------------

def el_vs():
    s = Svg(1024, 1024)
    s.shadow(512, 900, 300, 40)
    cid = s.uid("vs")
    s.defs[cid] = '<clipPath id="%s"><circle cx="512" cy="512" r="370"/></clipPath>' % cid
    s.add('<g clip-path="url(#%s)">' % cid)
    s.add('<rect x="0" y="0" width="1024" height="1024" fill="%s"/>' % s.ball(BLUE["base"]))
    s.add('<polygon points="600,100 470,470 570,500 430,940 1024,940 1024,100" fill="%s"/>' % s.ball(RED["base"]))
    s.line("M600,100 L470,470 L570,500 L430,940", 20, "#FFF")
    s.add('</g>')
    s.add('<circle cx="512" cy="512" r="370" fill="none" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    s.add('<circle cx="512" cy="512" r="340" fill="none" stroke="#FFF" stroke-width="8" opacity="0.5"/>')
    V = "M262,380 L370,650 L478,380"
    S = "M752,400 C690,352 580,360 588,436 C596,510 760,500 760,580 C760,662 640,676 566,624"
    for d in (V, S):
        s.add('<path d="%s" fill="none" stroke="#000" stroke-opacity="0.25" stroke-width="102" stroke-linecap="round" stroke-linejoin="round" transform="translate(10 14)"/>' % d)
    for d in (V, S):
        s.tube(d, 70, WHITE)
    return s


def el_arrow(c, down):
    s = Svg(1024, 1024)
    s.shadow(512, 900, 220, 30)
    tf = ' transform="rotate(180 512 512)"' if down else ""
    s.add('<g%s>' % tf)
    s.path("M512,150 L800,460 L640,460 L640,840 L384,840 L384,460 L224,460 Z", s.ball(c["base"]))
    s.add('<path d="M512,200 L740,440 L700,440 L512,240 Z" fill="#FFF" opacity="0.35"/>')
    s.add('</g>')
    return s


def el_check(c):
    s = Svg(1024, 1024)
    s.shadow(512, 880, 240, 30)
    s.tube("M270,540 L440,710 L760,330", 120, c["base"])
    s.line("M300,520 L440,660", 18, "#FFF", 'opacity="0.45"')
    return s


def el_cross(c):
    s = Svg(1024, 1024)
    s.shadow(512, 880, 240, 30)
    s.tube("M300,300 L724,724", 120, c["base"])
    s.tube("M724,300 L300,724", 120, c["base"])
    s.line("M330,300 L460,430", 18, "#FFF", 'opacity="0.45"')
    return s


def el_chart(bars):
    s = Svg(1024, 1024)
    s.add('<rect x="120" y="140" width="784" height="740" rx="40" fill="#FFF" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    for y in (300, 450, 600):
        s.line("M200,%d L840,%d" % (y, y), 4, G3, 'stroke-dasharray="14 16"')
    s.line("M200,220 L200,760 L840,760", 12)
    n = len(bars)
    step = 600 / n
    w = step * 0.6
    for i, (h, col) in enumerate(bars):
        x = 220 + step * i + (step - w) / 2
        s.add('<rect x="%g" y="%g" width="%g" height="%g" rx="18" fill="%s" fill-opacity="0.18" stroke="%s" stroke-width="%d" stroke-dasharray="26 14"/>'
              % (x, 760 - h, w, h - 10, col, col if col != G4 else G5, SW))
    return s


# 6. Theme costumes: overlays on the 1024x1536 figure canvas -------------

def sparkle(s, x, y, r):
    s.add('<path d="M%g,%g Q%g,%g %g,%g Q%g,%g %g,%g Q%g,%g %g,%g Q%g,%g %g,%g Z" fill="#FFF" stroke="%s" stroke-width="4"/>'
          % (x, y - r, x, y, x + r, y, x, y, x, y + r, x, y, x - r, y, x, y, x, y - r, OUT))


def costume_rich_a():
    s = Svg(1024, 1536)
    s.add('<g transform="rotate(14 600 300)">')
    s.path("M520,330 L530,230 L572,280 L600,210 L628,280 L670,230 L680,330 Z", s.ball(GOLD))
    s.add('<rect x="516" y="320" width="168" height="30" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(GOLD), OUT, SW))
    for x in (556, 600, 644):
        s.add('<circle cx="%d" cy="335" r="9" fill="%s"/>' % (x, BLUE["light"]))
    s.add('</g>')
    s.add('<circle cx="569" cy="600" r="58" fill="#FFF" fill-opacity="0.12" stroke="%s" stroke-width="16"/>' % OUT)
    s.add('<circle cx="569" cy="600" r="58" fill="none" stroke="%s" stroke-width="8"/>' % GOLD)
    s.line("M612,640 Q640,720 620,800", 4, GOLD)
    s.tube("M410,836 Q512,980 614,836", 12, GOLD)
    s.add('<circle cx="512" cy="950" r="42" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(GOLD), OUT, SW))
    s.add('<circle cx="512" cy="950" r="20" fill="none" stroke="#FFF" stroke-width="6" opacity="0.8"/>')
    sparkle(s, 720, 230, 26)
    sparkle(s, 470, 260, 16)
    sparkle(s, 580, 990, 18)
    return s


def patch(s, x, y, w, h, rot, fill):
    s.add('<g transform="rotate(%g %g %g)">' % (rot, x, y))
    s.add('<rect x="%g" y="%g" width="%g" height="%g" rx="8" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - w / 2, y - h / 2, w, h, s.ball(fill), OUT, SW))
    s.add('<rect x="%g" y="%g" width="%g" height="%g" rx="4" fill="none" stroke="%s" stroke-width="4" stroke-dasharray="10 8"/>' % (x - w / 2 + 10, y - h / 2 + 10, w - 20, h - 20, OUT))
    s.add('</g>')


def costume_poor_b():
    s = Svg(1024, 1536)
    patch(s, 600, 830, 70, 52, 12, G3)
    patch(s, 395, 1225, 96, 84, -10, mix(RED["light"], G3, 0.5))
    patch(s, 668, 1185, 70, 62, 8, G4)
    s.add('<g transform="rotate(-28 690 1060)"><rect x="640" y="1043" width="100" height="34" rx="17" fill="#F4D9B8" stroke="%s" stroke-width="6"/>'
          '<rect x="676" y="1047" width="28" height="26" fill="#E8C49A"/></g>' % OUT)
    for x, y, r in ((300, 1060, 26), (720, 1280, 32), (520, 1290, 22)):
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%g" fill="%s" opacity="0.35"/>' % (x, y, r, r * 0.6, G5))
    s.line("M560,1335 L580,1305 L600,1335 L620,1305", 6)
    s.add('<path d="M720,770 Q740,700 770,740" fill="none" stroke="%s" stroke-width="5" opacity="0.6"/>' % G5)
    s.add('<path d="M760,800 Q790,730 815,780" fill="none" stroke="%s" stroke-width="5" opacity="0.6"/>' % G5)
    return s


# ----------------------------------------------------------------------

def build():
    out = {}
    for bg, suffix in ((BG, ""), (None, "_freigestellt")):
        out["1_maskottchen/pip_frontal%s" % suffix] = pip_front(bg)
        out["1_maskottchen/pip_seitlich%s" % suffix] = pip_side(bg)
        for expr, name in (("neutral", "neutral"), ("proud", "stolz"), ("surprised", "ueberrascht"), ("annoyed", "genervt")):
            out["2_figuren/figur_a_blau_%s%s" % (name, suffix)] = figure_a(expr, bg)
            out["2_figuren/figur_b_rot_%s%s" % (name, suffix)] = figure_b(expr, bg)
    out["3_hintergruende/bg1_geteilte_buehne"] = bg_split()
    out["3_hintergruende/bg2_studio_podest"] = bg_podium()
    out["3_hintergruende/bg3_stadt_skyline_tag"] = bg_city()
    out["3_hintergruende/bg4_wohnzimmer"] = bg_living()
    out["3_hintergruende/bg5_raster_weiss"] = bg_grid()
    out["3_hintergruende/bg6_solo_blau"] = bg_solo(BLUE)
    out["3_hintergruende/bg7_solo_rot"] = bg_solo(RED)
    out["6_kostueme/reich_figur_a"] = costume_rich_a()
    out["6_kostueme/arm_figur_b"] = costume_poor_b()
    for name, fn in PROPS.items():
        for cname, c in (("blau", BLUE), ("rot", RED)):
            s = Svg(1024, 1024)
            fn(s, c)
            out["4_requisiten/%s_%s" % (name, cname)] = s
    out["5_elemente/vs"] = el_vs()
    for cname, c in (("blau", BLUE), ("rot", RED)):
        out["5_elemente/pfeil_hoch_%s" % cname] = el_arrow(c, False)
        out["5_elemente/pfeil_runter_%s" % cname] = el_arrow(c, True)
        out["5_elemente/haken_%s" % cname] = el_check(c)
        out["5_elemente/kreuz_%s" % cname] = el_cross(c)
    out["5_elemente/balken_a_vs_b"] = el_chart([(420, BLUE["base"]), (420, RED["base"])])
    out["5_elemente/balken_ranking_5"] = el_chart([(200, G4), (290, G4), (380, G4), (460, G4), (520, G4)])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", help="headless Chromium binary used to render PNGs")
    args = ap.parse_args()
    for name, s in build().items():
        svg_path = os.path.join(HERE, "svg", name + ".svg")
        os.makedirs(os.path.dirname(svg_path), exist_ok=True)
        with open(svg_path, "w") as f:
            f.write(s.svg())
        if args.chrome:
            png_path = os.path.join(HERE, "png", name + ".png")
            os.makedirs(os.path.dirname(png_path), exist_ok=True)
            scale = 1 if name.startswith("3_") else 2  # backgrounds exactly 1080x1920, the rest 2x
            subprocess.run([args.chrome, "--no-sandbox", "--hide-scrollbars", "--default-background-color=00000000",
                            "--force-device-scale-factor=%d" % scale, "--window-size=%d,%d" % (s.w, s.h),
                            "--screenshot=" + png_path, "file://" + svg_path],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
