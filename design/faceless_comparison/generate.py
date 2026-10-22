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
    if expr == "happy":
        s.line("M%g,%g Q%g,%g %g,%g" % (cx - rx, cy + ry * 0.2, cx, cy - ry * 0.9, cx + rx, cy + ry * 0.2), 14)
        return
    if expr == "sad":
        look = (0, 1)
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
    elif expr == "sad":
        inner, outer = (x1, x0) if side < 0 else (x0, x1)
        d = "M%g,%g L%g,%g" % (outer, cy + 10, inner, cy - 22)
    elif expr == "happy":
        d = "M%g,%g Q%g,%g %g,%g" % (x0, cy - 16, cx, cy - 44, x1, cy - 16)
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


# 1. Narrator mascot "Pip" --------------------------------------------------

PIP_BODY = "#ECEEF2"
PIP_LIMB = "#D5D9E0"
EGG = "M512,560 C720,560 800,860 800,1040 C800,1240 680,1360 512,1360 C344,1360 224,1240 224,1040 C224,860 304,560 512,560 Z"


FEATHER = "M0,0 C-22,-55 -17,-105 0,-135 C17,-105 22,-55 0,0 Z"
BEAK_UP = "M456,955 Q512,925 568,955 Q545,985 512,1002 Q479,985 456,955 Z"
BEAK_LO = "M480,975 L544,975 Q538,1012 512,1036 Q486,1012 480,975 Z"
PIP_WING = "M262,950 C150,980 100,1090 112,1235 Q140,1210 158,1248 Q178,1216 200,1242 Q222,1212 240,1236 Q246,1180 266,1150 Z"


def feathers(s, x, y, angles, scale=1.0, fill=G5):
    for a in angles:
        s.add('<path d="%s" fill="%s" stroke="%s" stroke-width="%d" stroke-linejoin="round" vector-effect="non-scaling-stroke" transform="translate(%g %g) rotate(%g) scale(%g)"/>'
              % (FEATHER, s.ball(fill), OUT, SW, x, y, a, scale))


def bird_foot(s, x, y, toes):
    s.tube("M%g,%g L%g,%g" % (x, y - 30, x, y), 18, GOLD)
    for dx, dy in toes:
        s.tube("M%g,%g L%g,%g" % (x, y, x + dx, y + dy), 16, GOLD)


def draw_pip_front(s):
    s.shadow(512, 1415, 270, 34)
    for x in (450, 574):
        bird_foot(s, x, 1385, ((-44, 22), (0, 30), (44, 22)))
    feathers(s, 512, 590, (-28, 0, 28))
    s.path(PIP_WING, s.ball(PIP_LIMB))
    s.add('<g transform="translate(1024 0) scale(-1 1)">')
    s.path(PIP_WING, s.ball(PIP_LIMB))
    s.add('</g>')
    s.path(EGG, s.ball(PIP_BODY))
    s.add('<ellipse cx="512" cy="1235" rx="150" ry="95" fill="#FFF" opacity="0.6"/>')
    s.shine(380, 700, 60, 30)
    for x in (340, 684):
        s.add('<ellipse cx="%d" cy="985" rx="42" ry="22" fill="%s" opacity="0.4"/>' % (x, BLUSH))
    for side in (-1, 1):
        ex = 512 + side * 102
        eye(s, ex, 845, 64, 78, "neutral", PIP_LIMB, side)
        brow(s, ex, 845 - 78 - 50, 64 * 1.4, "neutral", side)
    for x in (410, 614):  # oversized round glasses = signature feature
        s.add('<circle cx="%d" cy="845" r="96" fill="#FFF" fill-opacity="0.15" stroke="%s" stroke-width="16"/>' % (x, OUT))
        s.line("M%d,790 Q%d,768 %d,772" % (x - 56, x - 40, x - 18), 9, "#FFF", 'opacity="0.8"')
    s.line("M506,835 Q512,820 518,835", 16)
    s.path(BEAK_LO, s.ball(mix(GOLD, RED["dark"], 0.35)))
    s.path(BEAK_UP, s.ball(GOLD))
    bow_tie(s)


def pip_front(bg):
    s = Svg(1024, 1536, bg)
    draw_pip_front(s)
    return s


def pip_side(bg):
    s = Svg(1024, 1536, bg)
    s.shadow(530, 1415, 270, 34)
    bird_foot(s, 480, 1380, ((40, 20), (52, 34), (-30, 26)))
    feathers(s, 250, 1215, (-62, -80, -98), 1.15)
    feathers(s, 505, 590, (-48, -24, 0))
    s.path(EGG, s.ball(PIP_BODY))
    s.add('<ellipse cx="610" cy="1235" rx="110" ry="92" fill="#FFF" opacity="0.6"/>')
    s.shine(400, 700, 60, 30)
    bird_foot(s, 590, 1385, ((44, 20), (56, 34), (-30, 26)))
    s.add('<ellipse cx="705" cy="985" rx="32" ry="20" fill="%s" opacity="0.4"/>' % BLUSH)
    eye(s, 668, 845, 46, 78, "neutral", PIP_LIMB, 1, look=(1, 0))
    brow(s, 668, 845 - 78 - 50, 60, "neutral", 1)
    s.line("M612,822 L452,800 Q432,800 432,826", 14)
    s.add('<ellipse cx="672" cy="845" rx="64" ry="96" fill="#FFF" fill-opacity="0.15" stroke="%s" stroke-width="16"/>' % OUT)
    s.line("M640,790 Q650,768 664,770", 9, "#FFF", 'opacity="0.8"')
    s.path("M770,978 Q822,986 852,988 Q812,1012 772,1012 Z", s.ball(mix(GOLD, RED["dark"], 0.35)))
    s.path("M762,925 Q842,930 884,968 Q832,988 770,986 Z", s.ball(GOLD))
    s.path("M705,1110 L640,1070 Q622,1110 640,1150 Z", s.ball(RED["base"]))
    s.path("M705,1110 L752,1086 Q760,1110 752,1134 Z", s.ball(BLUE["base"]))
    s.add('<ellipse cx="708" cy="1110" rx="18" ry="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    s.path("M470,1000 C590,975 668,1080 640,1240 Q616,1212 598,1248 Q578,1214 556,1242 Q534,1214 516,1236 Q486,1130 470,1000 Z", s.ball(PIP_LIMB))
    s.line("M520,1060 Q580,1110 590,1190 M500,1100 Q540,1150 548,1200", 5, G4)
    return s


# 2. Comparison figures ----------------------------------------------------

BIRD_WING = "M0,0 C-62,24 -84,150 -62,270 Q-42,248 -30,280 Q-14,250 2,272 Q18,240 28,258 C34,160 32,60 0,0 Z"
# wing angle per pose (degrees clockwise, 0 = hanging straight down) and whether it is drawn in front of the body
WING_POSE = {"neutral": (16, False), "proud": (40, False), "surprised": (150, False), "annoyed": (-72, True),
             "happy": (135, False), "sad": (4, False)}


def wing(s, x, y, angle, color, side, sx=1.0, sy=1.0):
    s.add('<g transform="translate(%g %g) scale(%g 1) rotate(%g) scale(%g %g)">' % (x, y, side, angle, sx, sy))
    s.add('<path d="%s" fill="%s" stroke="%s" stroke-width="%d" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>' % (BIRD_WING, s.ball(color), OUT, SW))
    s.add('<path d="M-30,120 Q-36,190 -28,240 M-4,130 Q-6,200 4,240" fill="none" stroke="%s" stroke-width="5" opacity="0.6" vector-effect="non-scaling-stroke"/>' % mix(color, WHITE, 0.35))
    s.add('</g>')


def bird_face(s, c, cx, cy, gap, rx, ry, expr, brow_dy):
    for side in (-1, 1):
        ex = cx + side * gap / 2
        eye(s, ex, cy, rx, ry, expr, c["dark"], side)
        brow(s, ex, cy - ry - brow_dy, rx * 1.4, expr, side)
    if expr == "sad":
        x, y = cx - gap / 2 + rx * 0.5, cy + ry + 14
        s.add('<path d="M%g,%g Q%g,%g %g,%g A%g,%g 0 1 1 %g,%g Q%g,%g %g,%g Z" fill="%s" stroke="%s" stroke-width="5"/>'
              % (x, y - 30, x + 4, y - 12, x + 16, y + 4, 18, 18, x - 16, y + 4, x - 4, y - 12, x, y - 30, BLUE["light"], OUT))


def figure_a(expr, bg):
    """Side A: tall, slim bird with a sideways beak and a proud crest. Blue."""
    c = BLUE
    s = Svg(1024, 1536, bg)
    s.shadow(512, 1420, 190, 26)
    for x in (472, 552):
        s.tube("M%d,1180 L%d,1385" % (x, x), 16, GOLD)
        bird_foot(s, x, 1390, ((-36, 18), (0, 26), (36, 18)))
    feathers(s, 512, 440, (-20, 5, 30), 1.1, c["deep"])
    angle, front = WING_POSE[expr]
    shoulders = ((362, 790, 1), (662, 790, -1))
    if not front:
        for x, y, side in shoulders:
            wing(s, x, y, angle, c["dark"], side)
    s.path("M512,430 C640,430 680,620 680,860 C680,1100 620,1220 512,1220 C404,1220 344,1100 344,860 C344,620 384,430 512,430 Z", s.ball(c["base"]))
    s.add('<ellipse cx="512" cy="980" rx="110" ry="190" fill="#FFF" opacity="0.35"/>')
    s.shine(430, 540, 40, 20)
    for x in (432, 592):
        s.add('<ellipse cx="%d" cy="700" rx="28" ry="14" fill="%s" opacity="0.35"/>' % (x, BLUSH))
    bird_face(s, c, 512, 620, 124, 44, 54, expr, 26)
    tilt = {"proud": -10, "annoyed": 8, "sad": 20}.get(expr, 0)
    s.add('<g transform="rotate(%d 490 720)">' % tilt)
    if expr in ("surprised", "happy"):
        s.path("M488,735 L600,768 L488,782 Z", s.ball(mix(GOLD, RED["dark"], 0.35)))
        s.path("M488,690 L626,708 L488,728 Z", s.ball(GOLD))
    else:
        s.path("M488,690 L626,722 L488,752 Z", s.ball(GOLD))
        s.line("M490,722 L560,722", 5, mix(GOLD, OUT, 0.4))
    s.add('</g>')
    if front:
        for x, y, side in shoulders:
            wing(s, x, y, angle, c["dark"], side)
    return s


def figure_b(expr, bg):
    """Side B: short, round bird, loud and direct. Red."""
    c = RED
    s = Svg(1024, 1536, bg)
    s.shadow(512, 1420, 290, 32)
    for x in (450, 574):
        bird_foot(s, x, 1395, ((-40, 20), (0, 28), (40, 20)))
    feathers(s, 512, 830, (-30, 0, 30), 0.95, c["deep"])
    angle, front = WING_POSE[expr]
    shoulders = ((248, 1040, 1), (776, 1040, -1))
    if not front:
        for x, y, side in shoulders:
            wing(s, x, y, angle, c["dark"], side, 1.25, 0.85)
    s.ell(512, 1100, 290, 280, s.ball(c["base"]))
    s.add('<ellipse cx="512" cy="1215" rx="180" ry="125" fill="#FFF" opacity="0.35"/>')
    s.shine(380, 920, 60, 28)
    for x in (360, 664):
        s.add('<ellipse cx="%d" cy="1100" rx="40" ry="20" fill="%s" opacity="0.4"/>' % (x, BLUSH))
    bird_face(s, c, 512, 1015, 190, 58, 66, expr, 30)
    if expr in ("surprised", "happy"):
        s.path("M478,1120 L546,1120 Q540,1170 512,1190 Q484,1170 478,1120 Z", s.ball(mix(GOLD, RED["dark"], 0.35)))
        s.path("M466,1098 Q512,1076 558,1098 Q540,1122 512,1130 Q484,1122 466,1098 Z", s.ball(GOLD))
    else:
        tilt = {"proud": -8, "annoyed": 6, "sad": 0}.get(expr, 0)
        s.add('<g transform="rotate(%d 512 1120)">' % tilt)
        s.path("M466,1098 Q512,1076 558,1098 L512,1166 Z", s.ball(GOLD))
        s.add('</g>')
    if front:
        for x, y, side in ((300, 1190, 1), (724, 1190, -1)):
            wing(s, x, y, angle, c["dark"], side, 1.1, 0.85)
    return s


def figure_side(tall, bg):
    """Side view (facing right) of the blue (tall) or red (round) bird."""
    c = BLUE if tall else RED
    s = Svg(1024, 1536, bg)
    if tall:
        s.shadow(530, 1420, 190, 26)
        s.tube("M500,1180 L500,1385", 16, GOLD)
        bird_foot(s, 500, 1390, ((40, 20), (52, 30), (-30, 22)))
        feathers(s, 380, 1150, (-70, -95, -120), 1.0, c["deep"])
        feathers(s, 500, 440, (-40, -15, 10), 1.1, c["deep"])
        s.path("M512,430 C640,430 680,620 680,860 C680,1100 620,1220 512,1220 C404,1220 344,1100 344,860 C344,620 384,430 512,430 Z", s.ball(c["base"]))
        s.add('<ellipse cx="590" cy="980" rx="70" ry="180" fill="#FFF" opacity="0.35"/>')
        s.tube("M560,1180 L560,1385", 16, GOLD)
        bird_foot(s, 560, 1390, ((40, 20), (52, 30), (-30, 22)))
        eye(s, 590, 620, 38, 54, "proud", c["dark"], 1, look=(1, 0))
        brow(s, 590, 620 - 54 - 26, 54, "proud", 1)
        s.path("M650,690 L780,720 L650,752 Z", s.ball(GOLD))
        wing(s, 500, 790, 8, c["dark"], 1)
    else:
        s.shadow(520, 1420, 290, 32)
        bird_foot(s, 470, 1395, ((44, 20), (56, 30), (-30, 22)))
        feathers(s, 240, 1120, (-70, -95, -120), 0.95, c["deep"])
        feathers(s, 500, 830, (-40, -15, 10), 0.95, c["deep"])
        s.ell(512, 1100, 290, 280, s.ball(c["base"]))
        s.add('<ellipse cx="610" cy="1215" rx="130" ry="115" fill="#FFF" opacity="0.35"/>')
        bird_foot(s, 570, 1398, ((44, 20), (56, 30), (-30, 22)))
        eye(s, 660, 1010, 48, 66, "neutral", c["dark"], 1, look=(1, 0))
        brow(s, 660, 1010 - 66 - 30, 66, "neutral", 1)
        s.path("M778,1080 L872,1112 L778,1146 Z", s.ball(GOLD))
        wing(s, 480, 1050, 12, c["dark"], 1, 1.25, 0.85)
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


def prop_sneaker(s, c):
    s.shadow(520, 790, 360, 34)
    s.path("M170,700 Q170,640 230,640 L820,640 Q880,640 880,700 Q880,740 830,740 L220,740 Q170,740 170,700 Z", s.ball(WHITE))
    s.line("M190,712 L860,712", 6, c["base"])
    s.path("M220,640 C210,520 300,440 390,430 L520,420 Q610,420 650,500 L800,555 Q870,580 870,640 Z", s.ball(c["base"]))
    s.path("M700,520 L800,555 Q870,580 870,640 L720,640 Q700,580 700,520 Z", s.ball(WHITE))
    s.ell(410, 450, 90, 26, OUT, False)
    for i in range(4):
        x = 470 + i * 48
        s.line("M%d,%d L%d,%d" % (x, 450 + i * 22, x + 40, 470 + i * 22), 12, "#FFF")
    s.path("M220,640 C215,560 240,500 280,470 L300,640 Z", s.ball(c["dark"]))
    s.shine(330, 520, 50, 22)


def prop_basketball(s, c):
    s.shadow(512, 860, 260, 30)
    s.add('<circle cx="512" cy="500" r="300" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.line("M512,200 L512,800 M212,500 L812,500", SW)
    s.line("M300,288 Q420,500 300,712 M724,288 Q604,500 724,712", SW)
    s.shine(400, 360, 70, 32)


def prop_wallet(s, c):
    s.shadow(512, 800, 300, 32)
    s.add('<rect x="300" y="300" width="260" height="140" rx="12" fill="%s" stroke="%s" stroke-width="%d" transform="rotate(-10 430 370)"/>' % (s.ball(mix(c["light"], WHITE, 0.5)), OUT, SW))
    s.add('<rect x="232" y="380" width="560" height="380" rx="60" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.path("M232,470 Q232,380 322,380 L702,380 Q792,380 792,470 L792,560 L232,560 Z", s.ball(c["dark"]))
    s.add('<circle cx="700" cy="560" r="34" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    s.add('<rect x="262" y="590" width="400" height="140" rx="30" fill="none" stroke="#FFF" stroke-width="6" stroke-dasharray="16 12" opacity="0.6"/>')
    s.shine(330, 420, 50, 18)


def prop_gear_stick(s, c):
    s.shadow(512, 840, 280, 30)
    s.add('<rect x="262" y="640" width="500" height="180" rx="40" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
    s.line("M352,680 L352,780 M512,680 L512,780 M672,680 L672,780 M352,730 L672,730", 16, "#1E2126")
    s.path("M452,700 L572,700 L552,600 L472,600 Z", s.ball(G4))
    s.tube("M512,610 L512,380", 30, G3)
    s.add('<circle cx="512" cy="320" r="96" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.line("M472,300 L552,300 M512,260 L512,340", 8, "#FFF", 'opacity="0.7"')
    s.shine(470, 270, 34, 16)


def prop_selector(s, c):
    s.shadow(512, 880, 260, 30)
    s.add('<rect x="302" y="280" width="420" height="580" rx="60" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
    for i, ch in enumerate("PRND"):
        s.add('<text x="410" y="%d" font-family="Inter, sans-serif" font-weight="800" font-size="84" fill="%s" text-anchor="middle">%s</text>'
              % (410 + i * 125, "#FFF" if ch == "D" else G4, ch))
    s.line("M590,380 L590,780", 22, "#1E2126")
    s.add('<rect x="520" y="700" width="160" height="110" rx="34" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<rect x="572" y="676" width="56" height="30" rx="12" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    s.shine(560, 725, 30, 12)


def prop_pedals(s, c, n):
    s.shadow(512, 860, 320, 30)
    s.path("M212,840 L812,840 L752,560 L272,560 Z", s.ball(G4))
    pads = ((340, 150, 180), (512, 150, 180), (684, 110, 230)) if n == 3 else ((430, 220, 180), (650, 120, 240))
    for x, w, h in pads:
        s.tube("M%d,250 Q%d,420 %d,%d" % (x, x - 20, x, 640 - h / 2), 26, G5)
        s.add('<rect x="%g" y="%g" width="%d" height="%d" rx="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - w / 2, 640 - h / 2, w, h, s.ball(c["base"]), OUT, SW))
        for k in range(3):
            y = 640 - h / 2 + 40 + k * (h - 80) / 2
            s.line("M%g,%g L%g,%g" % (x - w / 2 + 24, y, x + w / 2 - 24, y), 8, c["dark"])


def prop_fuel_pump(s, c):
    s.shadow(512, 850, 260, 30)
    s.tube("M642,520 C760,520 780,640 760,760 L740,800", 26, G5)
    s.add('<rect x="700" y="770" width="80" height="60" rx="14" fill="%s" stroke="%s" stroke-width="%d" transform="rotate(20 740 800)"/>' % (s.ball(G3), OUT, SW))
    s.add('<rect x="342" y="240" width="300" height="580" rx="44" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<rect x="382" y="300" width="220" height="150" rx="20" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(WHITE), OUT, SW))
    s.line("M412,350 L572,350 M412,400 L520,400", 14, G4)
    s.add('<rect x="640" y="470" width="50" height="90" rx="12" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    s.add('<rect x="312" y="800" width="360" height="50" rx="16" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
    s.shine(400, 520, 30, 60, 0)


def prop_wrench(s, c):
    s.shadow(512, 860, 280, 30)
    mid = s.uid("wrench")
    s.defs[mid] = ('<mask id="%s"><rect width="1024" height="1024" fill="#FFF"/>'
                   '<rect x="640" y="250" width="90" height="140" fill="#000" transform="rotate(45 685 320)"/>'
                   '<circle cx="330" cy="700" r="34" fill="#000"/></mask>' % mid)
    s.add('<g mask="url(#%s)">' % mid)
    s.tube("M360,670 L660,370", 74, c["base"])
    s.add('<circle cx="690" cy="340" r="110" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<circle cx="330" cy="700" r="80" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('</g>')
    s.add('<rect x="640" y="250" width="90" height="140" fill="none" stroke="%s" stroke-width="%d" transform="rotate(45 685 320)" mask="url(#%s)"/>' % (OUT, SW, mid))
    s.add('<circle cx="330" cy="700" r="34" fill="none" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
    s.line("M420,580 L600,400", 10, "#FFF", 'opacity="0.45"')


def prop_charger(s, c):
    s.shadow(560, 870, 260, 30)
    s.tube("M512,560 C512,720 640,700 700,860", 40, G5)
    for x in (450, 574):
        s.add('<rect x="%d" y="220" width="36" height="90" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - 18, s.ball(G3), OUT, SW))
    s.add('<rect x="392" y="290" width="240" height="290" rx="60" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
    s.add('<path d="M530,330 L460,450 L512,450 L488,540 L566,410 L514,410 Z" fill="#FFF" stroke="%s" stroke-width="5" stroke-linejoin="round"/>' % OUT)
    s.shine(440, 340, 26, 14)


def prop_bed(s, c):
    s.shadow(512, 830, 360, 30)
    s.add('<rect x="172" y="420" width="60" height="400" rx="20" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
    s.add('<rect x="792" y="560" width="60" height="260" rx="20" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
    s.add('<rect x="212" y="600" width="610" height="130" rx="30" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(WHITE), OUT, SW))
    s.path("M380,560 Q560,500 800,560 L812,690 Q560,660 372,690 Z", s.ball(c["base"]))
    s.add('<rect x="240" y="540" width="150" height="80" rx="34" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(WHITE), OUT, SW))
    s.add('<path d="M640,250 A120,120 0 1 0 760,410 A95,95 0 1 1 640,250 Z" fill="%s" stroke="%s" stroke-width="%d" stroke-linejoin="round"/>' % (s.ball(GOLD), OUT, SW))
    sparkle(s, 560, 300, 22)
    sparkle(s, 800, 230, 16)


def prop_heart(s, c):
    s.shadow(512, 850, 230, 30)
    s.path("M512,820 C300,680 200,560 200,430 C200,320 290,250 380,250 C440,250 490,285 512,330 C534,285 584,250 644,250 C734,250 824,320 824,430 C824,560 724,680 512,820 Z", s.ball(c["base"]))
    s.shine(340, 360, 50, 26, -30)
    sparkle(s, 800, 270, 24)


def prop_plane(s, c):
    s.shadow(512, 860, 300, 26)
    s.add('<g transform="rotate(-18 512 512)">')
    s.path("M470,500 L260,330 L320,320 L560,470 Z", s.ball(c["dark"]))
    s.path("M470,560 L300,720 L360,730 L560,590 Z", s.ball(c["dark"]))
    s.path("M200,530 Q200,470 280,470 L760,470 Q880,470 900,530 Q880,590 760,590 L280,590 Q200,590 200,530 Z", s.ball(WHITE))
    s.path("M200,530 L170,420 L230,420 L290,490 Z", s.ball(c["base"]))
    for x in range(400, 760, 70):
        s.add('<circle cx="%d" cy="515" r="14" fill="%s" stroke="%s" stroke-width="5"/>' % (x, c["light"], OUT))
    s.line("M260,560 L840,560", 10, c["base"])
    s.add('</g>')


PROPS = {"geldbuendel": prop_money, "waage": prop_scale, "pokal": prop_trophy, "weltkugel": prop_globe,
         "stoppuhr": prop_stopwatch, "haus": prop_house, "auto": prop_car, "lupe": prop_magnifier,
         "arztkoffer": prop_doctor_bag, "maske": prop_mask,
         "sneaker": prop_sneaker, "basketball": prop_basketball,
         "geldboerse": prop_wallet, "schaltknueppel": prop_gear_stick, "waehlhebel": prop_selector,
         "pedale_2": lambda s, c: prop_pedals(s, c, 2), "pedale_3": lambda s, c: prop_pedals(s, c, 3),
         "zapfsaeule": prop_fuel_pump, "werkzeug": prop_wrench, "ladestecker": prop_charger,
         "bett": prop_bed, "herz": prop_heart, "flugzeug": prop_plane}


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
    """Rich: tilted crown next to the crest, monocle, gold chain."""
    s = Svg(1024, 1536)
    s.add('<g transform="rotate(16 610 420)">')
    s.path("M545,440 L553,350 L588,392 L612,330 L636,392 L671,350 L679,440 Z", s.ball(GOLD))
    s.add('<rect x="541" y="430" width="142" height="28" rx="10" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(GOLD), OUT, SW))
    for x in (576, 612, 648):
        s.add('<circle cx="%d" cy="444" r="8" fill="%s"/>' % (x, BLUE["light"]))
    s.add('</g>')
    s.add('<circle cx="574" cy="620" r="62" fill="#FFF" fill-opacity="0.12" stroke="%s" stroke-width="16"/>' % OUT)
    s.add('<circle cx="574" cy="620" r="62" fill="none" stroke="%s" stroke-width="8"/>' % GOLD)
    s.line("M630,650 Q664,720 650,800", 4, GOLD)
    s.tube("M400,800 Q512,920 624,800", 12, GOLD)
    s.add('<circle cx="512" cy="895" r="40" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(GOLD), OUT, SW))
    s.add('<circle cx="512" cy="895" r="18" fill="none" stroke="#FFF" stroke-width="6" opacity="0.8"/>')
    sparkle(s, 720, 330, 26)
    sparkle(s, 410, 400, 16)
    sparkle(s, 575, 940, 18)
    return s


def patch(s, x, y, w, h, rot, fill):
    s.add('<g transform="rotate(%g %g %g)">' % (rot, x, y))
    s.add('<rect x="%g" y="%g" width="%g" height="%g" rx="8" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - w / 2, y - h / 2, w, h, s.ball(fill), OUT, SW))
    s.add('<rect x="%g" y="%g" width="%g" height="%g" rx="4" fill="none" stroke="%s" stroke-width="4" stroke-dasharray="10 8"/>' % (x - w / 2 + 10, y - h / 2 + 10, w - 20, h - 20, OUT))
    s.add('</g>')


def costume_poor_b():
    """Poor: patches, band-aid, dirt, a bent crest feather and flies."""
    s = Svg(1024, 1536)
    patch(s, 380, 1270, 96, 84, -10, mix(RED["light"], G3, 0.5))
    patch(s, 676, 1170, 70, 62, 8, G4)
    s.add('<g transform="rotate(-28 690 1090)"><rect x="640" y="1073" width="100" height="34" rx="17" fill="#F4D9B8" stroke="%s" stroke-width="6"/>'
          '<rect x="676" y="1077" width="28" height="26" fill="#E8C49A"/></g>' % OUT)
    for x, y, r in ((300, 1140, 26), (720, 1300, 32), (560, 1330, 22)):
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%g" fill="%s" opacity="0.35"/>' % (x, y, r, r * 0.6, G5))
    s.add('<path d="M700,760 Q720,690 750,730" fill="none" stroke="%s" stroke-width="5" opacity="0.6"/>' % G5)
    s.add('<path d="M740,790 Q770,720 795,770" fill="none" stroke="%s" stroke-width="5" opacity="0.6"/>' % G5)
    for x, y in ((760, 720), (800, 760)):
        s.add('<circle cx="%d" cy="%d" r="7" fill="%s"/>' % (x, y, OUT))
    return s


# Brand-inspired emblems (deliberately not the real marks)
WING = "M-1,0.3 C-0.6,-0.6 0.4,-0.7 1,-0.5 C0.7,-0.3 0.6,-0.2 0.7,-0.1 C0.4,-0.05 0.3,0.05 0.4,0.15 C0.1,0.2 0,0.3 0.05,0.4 C-0.4,0.45 -0.8,0.45 -1,0.3 Z"
PEAK = "M-1,0.5 L-0.15,-0.6 Q0,-0.75 0.15,-0.6 L1,0.5 Q1.05,0.6 0.9,0.6 L-0.9,0.6 Q-1.05,0.6 -1,0.5 Z"


def emblem(s, d, x, y, size, fill=WHITE, accent=None):
    s.add('<path d="%s" fill="%s" stroke="%s" stroke-width="%d" stroke-linejoin="round" vector-effect="non-scaling-stroke" transform="translate(%g %g) scale(%g)"/>'
          % (d, fill, OUT, SW * 0.75, x, y, size))
    if accent:
        s.add('<path d="M-0.42,-0.1 L-0.2,0.05 L0,-0.12 L0.2,0.05 L0.42,-0.1" fill="none" stroke="%s" stroke-width="%d" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke" transform="translate(%g %g) scale(%g)"/>'
              % (accent, SW * 0.75, x, y, size))


def sneakers(s, c, shoes):
    for x, y, rx, ry in shoes:
        s.ell(x, y + 8, rx + 10, ry + 6, s.ball(c["base"]))
        s.ell(x, y - 2, rx + 4, ry + 2, s.ball(WHITE))
        s.line("M%g,%g L%g,%g M%g,%g L%g,%g" % (x - 14, y - 14, x + 4, y - 8, x - 4, y - 20, x + 14, y - 14), 5)


def costume_sport_a():
    s = Svg(1024, 1536)
    s.path("M374,466 Q512,446 650,466 L654,508 Q512,488 370,508 Z", s.ball(WHITE))
    s.add('<path d="M372,487 Q512,467 652,487" fill="none" stroke="%s" stroke-width="10"/>' % BLUE["base"])
    emblem(s, PEAK, 512, 900, 58, WHITE, BLUE["base"])
    sneakers(s, BLUE, ((462, 1396, 46, 22), (562, 1396, 46, 22)))
    return s


def costume_sport_b():
    s = Svg(1024, 1536)
    s.tube("M320,1150 Q512,1280 704,1150", 6, G1)
    s.add('<rect x="482" y="1220" width="60" height="40" rx="14" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
    s.add('<circle cx="530" cy="1240" r="8" fill="%s"/>' % OUT)
    emblem(s, WING, 512, 1300, 60)
    sneakers(s, RED, ((440, 1400, 56, 24), (584, 1400, 56, 24)))
    return s


def costume_driver_a():
    """Automatik: relaxed, sunglasses pushed up on the head."""
    s = Svg(1024, 1536)
    s.add('<g transform="rotate(-6 512 480)">')
    for x in (455, 569):
        s.add('<rect x="%d" y="452" width="100" height="58" rx="26" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - 50, s.ball("#3A3F47"), OUT, SW))
        s.line("M%d,468 L%d,468" % (x - 30, x - 6), 6, "#FFF", 'opacity="0.6"')
    s.line("M505,478 Q512,466 519,478", 10)
    s.add('</g>')
    return s


def costume_racer_b():
    """Manuell: chequered flag stuck in next to the crest."""
    s = Svg(1024, 1536)
    s.line("M600,860 L600,720", 8, G5)
    for i in range(3):
        for j in range(4):
            s.add('<rect x="%d" y="%d" width="22" height="20" fill="%s"/>' % (600 + j * 22, 720 + i * 20, OUT if (i + j) % 2 else "#FFF"))
    s.add('<rect x="600" y="720" width="88" height="60" fill="none" stroke="%s" stroke-width="5"/>' % OUT)
    return s


def bow_tie(s):
    s.path("M512,1110 L432,1068 Q410,1110 432,1152 Z", s.ball(BLUE["base"]))
    s.path("M512,1110 L592,1068 Q614,1110 592,1152 Z", s.ball(RED["base"]))
    s.add('<circle cx="512" cy="1110" r="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))


def costume_referee(blowing):
    s = Svg(1024, 1536)
    draw_referee(s, blowing)
    return s


def draw_referee(s, blowing):
    """Referee shirt for Pip front view; `blowing` puts the whistle in his beak."""
    cid = s.uid("egg")
    s.defs[cid] = '<clipPath id="%s"><path d="%s"/></clipPath>' % (cid, EGG)
    s.add('<g clip-path="url(#%s)"><path d="M200,1150 Q512,1105 824,1150 L824,1400 L200,1400 Z" fill="%s"/>' % (cid, s.ball(WHITE)))
    sid = s.uid("shirt")
    s.defs[sid] = '<clipPath id="%s"><path d="M200,1150 Q512,1105 824,1150 L824,1400 L200,1400 Z"/></clipPath>' % sid
    s.add('<g clip-path="url(#%s)">' % sid)
    for x in range(228, 824, 64):
        s.add('<rect x="%d" y="1100" width="30" height="300" fill="%s"/>' % (x, OUT))
    s.add('</g>')
    s.add('<path d="M200,1150 Q512,1105 824,1150" fill="none" stroke="%s" stroke-width="%d"/></g>' % (OUT, SW))
    s.add('<path d="%s" fill="none" stroke="%s" stroke-width="%d"/>' % (EGG, OUT, SW))
    s.line("M455,1128 L512,1175 L569,1128", 14)
    bow_tie(s)
    if blowing:
        s.add('<ellipse cx="512" cy="1012" rx="52" ry="30" fill="%s"/>' % PIP_BODY)
        for x in (372, 652):
            s.add('<ellipse cx="%d" cy="990" rx="56" ry="40" fill="%s" opacity="0.55"/>' % (x, BLUSH))
        s.tube("M600,1030 Q640,1120 600,1180", 5, BLUE["base"])
        s.add('<rect x="520" y="980" width="130" height="52" rx="18" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
        s.add('<circle cx="652" cy="1006" r="30" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
        s.add('<circle cx="652" cy="1006" r="10" fill="%s"/>' % OUT)
        s.path(BEAK_UP, s.ball(GOLD))
    else:
        s.tube("M440,1140 Q470,1240 540,1250", 5, BLUE["base"])
        s.add('<rect x="530" y="1228" width="100" height="44" rx="16" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))
        s.add('<circle cx="632" cy="1250" r="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G3), OUT, SW))


def channel_avatar():
    """Profile picture for the channel: referee Pip on the split blue/red badge, no text."""
    s = Svg(1024, 1024)
    cid = s.uid("avatar")
    s.defs[cid] = '<clipPath id="%s"><circle cx="512" cy="512" r="500"/></clipPath>' % cid
    s.add('<g clip-path="url(#%s)">' % cid)
    s.add('<rect width="512" height="1024" fill="%s"/>' % s.ball(BLUE["base"]))
    s.add('<rect x="512" width="512" height="1024" fill="%s"/>' % s.ball(RED["base"]))
    s.add('<rect x="504" width="16" height="1024" fill="#FFF"/>')
    s.add('<g transform="translate(-128 -580) scale(1.25)">')
    draw_pip_front(s)
    draw_referee(s, False)
    s.add('</g></g>')
    s.add('<circle cx="512" cy="512" r="500" fill="none" stroke="%s" stroke-width="%d"/>' % (OUT, SW * 2))
    return s

# 8. Alternative character styles: blue (tall) and red (round) side by side, 2048x1536 ------------

def flat_eye(s, x, y, r):
    s.add('<circle cx="%g" cy="%g" r="%g" fill="%s"/><circle cx="%g" cy="%g" r="%g" fill="#FFF"/>' % (x, y, r, OUT, x - r * 0.3, y - r * 0.35, r * 0.3))


def style_flat(s, c, tall):
    """Flat: no gradients, geometric shapes."""
    if tall:
        s.shadow(512, 1420, 170, 24)
        s.line("M470,1200 L470,1390 M554,1200 L554,1390", 30, c["deep"])
        s.add('<rect x="402" y="700" width="220" height="520" rx="110" fill="%s" stroke="%s" stroke-width="%d"/>' % (c["base"], OUT, SW))
        s.line("M410,820 L320,1020 M614,820 L704,1020", 26, c["dark"])
        s.add('<circle cx="512" cy="520" r="170" fill="%s" stroke="%s" stroke-width="%d"/>' % (c["base"], OUT, SW))
        s.path("M380,430 Q512,300 650,420 L640,380 Q512,280 384,390 Z", c["deep"])
        flat_eye(s, 460, 520, 22)
        flat_eye(s, 564, 520, 22)
        s.line("M470,600 Q512,630 554,600", 10)
    else:
        s.shadow(512, 1420, 280, 30)
        s.line("M440,1330 L440,1395 M584,1330 L584,1395", 40, c["deep"])
        s.line("M250,1080 L170,1200 M774,1080 L854,1200", 34, c["dark"])
        s.add('<circle cx="512" cy="1080" r="280" fill="%s" stroke="%s" stroke-width="%d"/>' % (c["base"], OUT, SW))
        s.add('<circle cx="512" cy="1080" r="200" fill="%s"/>' % mix(c["base"], WHITE, 0.15))
        flat_eye(s, 440, 1020, 30)
        flat_eye(s, 584, 1020, 30)
        s.path("M440,1120 Q512,1200 584,1120 Z", OUT)
    for x in ((470, 554) if tall else (420, 604)):
        s.ell(x, 1402 if tall else 1405, 50, 22, G5)


def style_bird(s, c, tall):
    """Birds, matching the Vergleichvogel referee."""
    if tall:
        s.shadow(512, 1420, 180, 26)
        for x in (472, 552):
            s.tube("M%d,1180 L%d,1385" % (x, x), 16, GOLD)
            bird_foot(s, x, 1390, ((-36, 18), (0, 26), (36, 18)))
        feathers(s, 512, 440, (-20, 5, 30), 1.1, c["deep"])
        s.path("M512,430 C640,430 680,620 680,860 C680,1100 620,1220 512,1220 C404,1220 344,1100 344,860 C344,620 384,430 512,430 Z", s.ball(c["base"]))
        s.path("M352,800 C300,880 300,1000 330,1080 Q350,1040 380,1060 Z", s.ball(c["dark"]))
        s.path("M672,800 C724,880 724,1000 694,1080 Q674,1040 644,1060 Z", s.ball(c["dark"]))
        s.add('<ellipse cx="512" cy="980" rx="110" ry="190" fill="#FFF" opacity="0.35"/>')
        for side in (-1, 1):
            eye(s, 512 + side * 62, 620, 44, 54, "proud", c["dark"], side)
        s.path("M490,690 L620,720 L490,750 Z", s.ball(GOLD))
    else:
        s.shadow(512, 1420, 280, 30)
        for x in (450, 574):
            bird_foot(s, x, 1395, ((-40, 20), (0, 28), (40, 20)))
        feathers(s, 512, 820, (-30, 0, 30), 0.9, c["deep"])
        s.path("M240,1080 C160,1120 150,1240 210,1290 Q230,1240 270,1250 Z", s.ball(c["dark"]))
        s.path("M784,1080 C864,1120 874,1240 814,1290 Q794,1240 754,1250 Z", s.ball(c["dark"]))
        s.ell(512, 1100, 290, 280, s.ball(c["base"]))
        s.add('<ellipse cx="512" cy="1210" rx="180" ry="130" fill="#FFF" opacity="0.35"/>')
        for side in (-1, 1):
            eye(s, 512 + side * 95, 1020, 58, 66, "neutral", c["dark"], side)
        s.path("M470,1100 Q512,1080 554,1100 L512,1160 Z", s.ball(GOLD))


def style_blob(s, c, tall):
    """Glossy jelly blobs without limbs."""
    if tall:
        s.shadow(512, 1400, 220, 30)
        s.path("M512,380 C600,520 700,800 700,1120 C700,1320 620,1390 512,1390 C404,1390 324,1320 324,1120 C324,800 424,520 512,380 Z", s.ball(c["base"]))
        s.shine(440, 800, 40, 120, 15, 0.5)
        s.add('<circle cx="600" cy="1180" r="22" fill="#FFF" opacity="0.5"/>')
        for side in (-1, 1):
            eye(s, 512 + side * 70, 980, 50, 62, "neutral", c["dark"], side)
        mouth(s, 512, 1100, 90, "happy")
    else:
        s.shadow(512, 1410, 330, 34)
        s.path("M200,1390 C150,1390 160,1250 220,1200 C260,1000 380,860 512,860 C644,860 764,1000 804,1200 C864,1250 874,1390 824,1390 Z", s.ball(c["base"]))
        s.shine(380, 980, 70, 30, -20, 0.5)
        for side in (-1, 1):
            eye(s, 512 + side * 100, 1100, 62, 70, "surprised", c["dark"], side)
        mouth(s, 512, 1230, 140, "surprised")


def style_robot(s, c, tall):
    """Robots with screen faces."""
    if tall:
        s.shadow(512, 1420, 200, 26)
        s.line("M512,300 L512,220", 10)
        s.add('<circle cx="512" cy="205" r="24" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(GOLD), OUT, SW))
        for x in (460, 564):
            s.add('<rect x="%d" y="1180" width="44" height="190" rx="12" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - 22, s.ball(G4), OUT, SW))
            s.add('<rect x="%d" y="1360" width="90" height="46" rx="14" fill="%s" stroke="%s" stroke-width="%d"/>' % (x - 45, s.ball(G5), OUT, SW))
        for x, d in ((352, "M352,800 Q290,920 300,1060"), (672, "M672,800 Q734,920 724,1060")):
            s.tube(d, 30, G4)
            s.add('<circle cx="%d" cy="1070" r="34" fill="%s" stroke="%s" stroke-width="%d"/>' % (300 if x < 512 else 724, s.ball(c["dark"]), OUT, SW))
        s.add('<rect x="352" y="700" width="320" height="500" rx="50" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
        s.add('<circle cx="512" cy="900" r="50" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["light"]), OUT, SW))
        s.add('<rect x="372" y="300" width="280" height="360" rx="60" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(c["base"]), OUT, SW))
        s.add('<rect x="402" y="360" width="220" height="200" rx="40" fill="#1E2430" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
        for x in (465, 559):
            s.add('<rect x="%d" y="420" width="34" height="56" rx="17" fill="%s"/>' % (x - 17, c["light"]))
        s.line("M480,520 Q512,536 544,520", 8, c["light"])
        s.add('<rect x="482" y="650" width="60" height="60" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G4), OUT, SW))
    else:
        s.shadow(512, 1420, 280, 30)
        s.add('<circle cx="512" cy="1340" r="70" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(G5), OUT, SW))
        s.add('<circle cx="512" cy="1340" r="26" fill="%s"/>' % G3)
        for d, x in (("M250,1080 Q170,1120 170,1220", 170), ("M774,1080 Q854,1120 854,1220", 854)):
            s.tube(d, 34, G4)
            s.path("M%d,1220 l-30,40 M%d,1220 l30,40" % (x, x), "none")
            s.line("M%d,1215 L%d,1265 M%d,1215 L%d,1265" % (x, x - 34, x, x + 34), 16, G5)
        s.path("M232,1100 C232,860 792,860 792,1100 L792,1180 Q792,1290 680,1290 L344,1290 Q232,1290 232,1180 Z", s.ball(c["base"]))
        s.add('<rect x="322" y="960" width="380" height="190" rx="60" fill="#1E2430" stroke="%s" stroke-width="%d"/>' % (OUT, SW))
        for x in (430, 594):
            s.add('<circle cx="%d" cy="1040" r="34" fill="%s"/>' % (x, c["light"]))
        s.path("M470,1100 Q512,1130 554,1100 Z", c["light"], False)
        s.line("M512,870 L512,800", 10)
        s.add('<circle cx="512" cy="790" r="22" fill="%s" stroke="%s" stroke-width="%d"/>' % (s.ball(GOLD), OUT, SW))


def pie_eye(s, x, y, rx, ry):
    s.ell(x, y, rx, ry, OUT, False)
    s.add('<path d="M%g,%g l%g,%g l%g,%g Z" fill="#FFF"/>' % (x + rx * 0.1, y - ry * 0.55, rx * 0.5, ry * 0.1, -rx * 0.35, ry * 0.4))


def style_retro(s, c, tall):
    """1930s rubber-hose cartoon: pie eyes, white gloves, big shoes."""
    def glove(x, y, r):
        s.add('<circle cx="%g" cy="%g" r="%g" fill="#FFF" stroke="%s" stroke-width="%d"/>' % (x, y, r, OUT, SW))
        s.line("M%g,%g L%g,%g" % (x - r * 0.5, y - r * 0.2, x + r * 0.2, y - r * 0.2), 5)

    if tall:
        s.shadow(512, 1420, 200, 26)
        s.tube("M470,1180 C430,1260 500,1300 460,1385", 22, OUT)
        s.tube("M554,1180 C600,1260 530,1300 570,1385", 22, OUT)
        for x in (440, 590):
            s.ell(x, 1395, 70, 30, s.ball(G5))
        s.tube("M392,820 C250,880 380,1000 250,1080", 22, OUT)
        s.tube("M632,820 C780,760 650,640 790,580", 22, OUT)
        glove(250, 1090, 40)
        glove(795, 570, 40)
        s.path("M512,340 C650,340 650,520 640,700 L660,1150 Q660,1220 590,1220 L434,1220 Q364,1220 364,1150 L384,700 C374,520 374,340 512,340 Z", c["base"])
        s.path("M410,500 Q512,560 614,500 Q620,640 512,660 Q404,640 410,500 Z", "#FFE9D6")
        pie_eye(s, 470, 520, 26, 46)
        pie_eye(s, 554, 520, 26, 46)
        s.path("M450,600 Q512,660 574,600 Q512,630 450,600 Z", OUT)
        s.add('<circle cx="512" cy="580" r="16" fill="%s"/>' % OUT)
    else:
        s.shadow(512, 1420, 280, 30)
        s.tube("M440,1300 C400,1340 460,1360 430,1390", 24, OUT)
        s.tube("M584,1300 C624,1340 564,1360 594,1390", 24, OUT)
        for x in (410, 614):
            s.ell(x, 1400, 80, 32, s.ball(G5))
        s.tube("M250,1060 C150,1000 230,900 150,850", 24, OUT)
        s.tube("M774,1060 C880,1100 800,1200 880,1250", 24, OUT)
        glove(150, 840, 44)
        glove(885, 1260, 44)
        s.ell(512, 1080, 280, 260, c["base"])
        s.path("M330,1000 Q512,920 694,1000 Q700,1200 512,1220 Q324,1200 330,1000 Z", "#FFE9D6")
        pie_eye(s, 450, 1030, 32, 56)
        pie_eye(s, 574, 1030, 32, 56)
        s.path("M420,1130 Q512,1230 604,1130 Q512,1170 420,1130 Z", OUT)
        s.add('<ellipse cx="512" cy="1105" rx="26" ry="20" fill="%s"/>' % OUT)


STYLES = {"1_flach": style_flat, "2_voegel": style_bird, "3_gummi": style_blob, "4_roboter": style_robot, "5_retro": style_retro}


def style_pair(fn):
    s = Svg(2048, 1536, BG)
    fn(s, BLUE, True)
    s.add('<g transform="translate(1024 0)">')
    fn(s, RED, False)
    s.add('</g>')
    return s


# ----------------------------------------------------------------------

def build():
    out = {}
    for bg, suffix in ((BG, ""), (None, "_freigestellt")):
        out["1_maskottchen/pip_frontal%s" % suffix] = pip_front(bg)
        out["1_maskottchen/pip_seitlich%s" % suffix] = pip_side(bg)
        for expr, name in (("neutral", "neutral"), ("proud", "stolz"), ("surprised", "ueberrascht"), ("annoyed", "genervt"),
                           ("happy", "jubelnd"), ("sad", "traurig")):
            out["2_figuren/figur_a_blau_%s%s" % (name, suffix)] = figure_a(expr, bg)
            out["2_figuren/figur_b_rot_%s%s" % (name, suffix)] = figure_b(expr, bg)
        out["2_figuren/figur_a_blau_seitlich%s" % suffix] = figure_side(True, bg)
        out["2_figuren/figur_b_rot_seitlich%s" % suffix] = figure_side(False, bg)
    out["3_hintergruende/bg1_geteilte_buehne"] = bg_split()
    out["3_hintergruende/bg2_studio_podest"] = bg_podium()
    out["3_hintergruende/bg3_stadt_skyline_tag"] = bg_city()
    out["3_hintergruende/bg4_wohnzimmer"] = bg_living()
    out["3_hintergruende/bg5_raster_weiss"] = bg_grid()
    out["3_hintergruende/bg6_solo_blau"] = bg_solo(BLUE)
    out["3_hintergruende/bg6_solo_rot"] = bg_solo(RED)
    out["6_kostueme/reich_figur_a"] = costume_rich_a()
    out["6_kostueme/arm_figur_b"] = costume_poor_b()
    out["6_kostueme/sport_figur_a"] = costume_sport_a()
    out["6_kostueme/sport_figur_b"] = costume_sport_b()
    out["6_kostueme/pip_schiedsrichter"] = costume_referee(False)
    out["6_kostueme/pip_schiedsrichter_pfeift"] = costume_referee(True)
    out["7_kanal/vergleichvogel_profilbild"] = channel_avatar()
    out["6_kostueme/automatik_figur_a"] = costume_driver_a()
    out["6_kostueme/manuell_figur_b"] = costume_racer_b()
    for name, fn in STYLES.items():
        out["8_stile/" + name] = style_pair(fn)
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
