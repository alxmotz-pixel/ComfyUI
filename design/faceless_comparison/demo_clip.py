"""Renders a 10 s 1080x1920 comparison clip for one theme file (needs Pillow and ffmpeg).

    python generate.py --chrome ...                 # PNGs first
    python demo_clip.py themen/arm_vs_reich.json

Theme keys: "a" = blue side, "b" = red side, "fokus" = side the points are about ("a"/"b"),
"kostuem_a"/"kostuem_b" = optional overlays from png/6_kostueme,
"plus"/"minus" = 3 points each {"text", "bilder": [prop/element names], "emotion"?}, "frage" = closing question.
"""

import json
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "png")
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
W, H, FPS = 1080, 1920, 30
OUT = (43, 47, 54)
BLUE, RED = (47, 123, 255), (238, 51, 64)
SIDES = {"a": ("figur_a_blau", BLUE, "blau", 270), "b": ("figur_b_rot", RED, "rot", 810)}

_cache = {}


def img(name, height):
    key = (name, height)
    if key not in _cache:
        path = os.path.join(PNG, name + ".png")
        if not os.path.exists(path):
            path = next(os.path.join(PNG, d, name + ".png") for d in ("4_requisiten", "5_elemente")
                        if os.path.exists(os.path.join(PNG, d, name + ".png")))
        im = Image.open(path).convert("RGBA")
        _cache[key] = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    return _cache[key]


def font(size):
    if size not in _cache:
        _cache[size] = ImageFont.truetype(FONT, size)
    return _cache[size]


def fit(text, max_w, size):
    while size > 30 and font(size).getlength(text) > max_w:
        size -= 2
    return font(size)


def clamp(t):
    return min(max(t, 0.0), 1.0)


def ease(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_out_back(t):
    t = clamp(t)
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


def put(frame, im, cx, cy, s=1.0, sy=None):
    """Paste centred on (cx, cy); s/sy scale around the centre."""
    sy = s if sy is None else sy
    if s <= 0.02 or sy <= 0.02:
        return
    if s != 1.0 or sy != 1.0:
        im = im.resize((round(im.width * s), round(im.height * sy)), Image.BILINEAR)
    frame.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2)))


def pop(frame, im, cx, cy, t):
    put(frame, im, cx, cy, ease_out_back(t / 0.35))


def pill(text, color, size=64, pad=34):
    f = font(size)
    w = round(f.getlength(text)) + 2 * pad
    h = size + 2 * pad - 10
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=h // 2, fill=color, outline=OUT, width=8)
    d.text((w / 2 + 8, h / 2 + 8), text, font=f, fill="white", anchor="mm")
    return im


def card(text, icon, color):
    w, h = 940, 170
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=40, fill="white", outline=OUT, width=8)
    d.rounded_rectangle([8, 8, 40, h + 8], radius=16, fill=color)
    d.line([(40, 12), (40, h + 4)], fill=OUT, width=6)
    ic = img(icon, 140)
    im.alpha_composite(ic, (60, round((h + 16 - ic.height) / 2)))
    d.text((220, h / 2 + 8), text, font=fit(text, w - 240, 68), fill=OUT, anchor="lm")
    return im


class Clip:
    def __init__(self, th):
        self.th = th
        self.focus = th["fokus"]
        self.costume = {k: th.get("kostuem_" + k) for k in SIDES}
        self.label = {k: pill(th[k], SIDES[k][1]) for k in SIDES}
        self.vs = img("5_elemente/vs", 420)
        fig, color, cname, _ = SIDES[self.focus]
        name = th[self.focus]
        self.plus = [(pill("%s · BESSER %d/3" % (name, i + 1), color, 50), card(p["text"], "haken_" + cname, color), p) for i, p in enumerate(th["plus"])]
        self.minus = [(pill("%s · SCHLECHTER %d/3" % (name, i + 1), RED if color == BLUE else BLUE, 50), card(p["text"], "kreuz_rot", RED), p) for i, p in enumerate(th["minus"])]
        q = th["frage"]
        self.question = pill(q, OUT, 66) if font(66).getlength(q) < 900 else pill(q, OUT, 48)
        rnd = random.Random(3)
        self.confetti = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(500, 1100), rnd.choice((color, (255, 255, 255), (255, 200, 61))), rnd.randint(10, 20)) for _ in range(40)]

    def character(self, frame, side, emotion, cx, bottom, t, height, react=None):
        """Idle bounce anchored at the feet; `react` = time of an expression change (stretch)."""
        sy = 1 + 0.015 * math.sin((t + (0.4 if side == "b" else 0)) * 2 * math.pi * 1.2)
        if react is not None and 0 <= t - react < 0.3:
            sy += 0.08 * math.sin((t - react) / 0.3 * math.pi)
        for name in ("2_figuren/%s_%s_freigestellt" % (SIDES[side][0], emotion), self.costume[side] and "6_kostueme/" + self.costume[side]):
            if name:
                im = img(name, height)
                put(frame, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)

    def pip(self, frame, cx, bottom, t, height):
        sy = 1 + 0.015 * math.sin((t + 0.2) * 2 * math.pi * 1.2)
        im = img("1_maskottchen/pip_frontal_freigestellt", height)
        put(frame, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)

    def split(self, t, emotion="neutral"):
        f = img("3_hintergruende/bg1_geteilte_buehne", H).copy()
        xa = -400 + 670 * ease_out_back(t / 0.7)
        xb = W + 400 - 670 * ease_out_back((t - 0.15) / 0.7)
        self.character(f, "a", emotion, xa, 1700, t, 900)
        self.character(f, "b", emotion, xb, 1700, t, 900)
        return f

    def intro(self, t):
        f = self.split(t)
        pop(f, self.vs, W / 2, 470, t - 0.45)
        pop(f, self.label["a"], 270, 1800, t - 0.7)
        pop(f, self.label["b"], 810, 1800, t - 0.85)
        # whip zoom onto the focus side
        z = ease((t - 1.45) / 0.35)
        if z > 0:
            bw, bh = W - 540 * z, H - 960 * z
            x0 = (SIDES[self.focus][3] - 270) * z
            y0 = 760 * z
            f = f.crop((round(x0), round(y0), round(x0 + bw), round(y0 + bh))).resize((W, H), Image.BILINEAR)
        return f

    def point(self, t, item, positive):
        head, crd, p = item
        side = self.focus
        f = img("3_hintergruende/bg6_solo_%s" % SIDES[side][2], H).copy()
        if not positive:
            f.alpha_composite(Image.new("RGBA", (W, H), (20, 22, 30, 70)))
        emotion = p.get("emotion", "stolz" if positive else "genervt")
        self.character(f, side, emotion, 300, 1830, t, 1050, react=0.0)
        pics = p["bilder"]
        size = 660 if len(pics) == 1 else 440
        shake = 14 * math.sin(t * 60) * (1 - clamp((t - 0.35) / 0.4)) if not positive else 0
        for i, name in enumerate(pics):
            gx = 720 + (i - (len(pics) - 1) / 2) * 330 + shake
            gy = 900 + 18 * math.sin(t * 5 + i)
            pop(f, img(name, size), gx, gy, t - 0.15 - 0.12 * i)
        if positive and t > 0.2:
            d = ImageDraw.Draw(f)
            k = ease((t - 0.2) / 0.7)
            for a, dist, col, r in self.confetti:
                x = 730 + math.cos(a) * dist * k
                y = 900 + math.sin(a) * dist * k * 0.8 + 400 * k * k
                if k < 1:
                    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=OUT, width=3)
        pop(f, head, W / 2, 110, t)
        pop(f, crd, W / 2, 300, t - 0.05)
        return f

    def points(self, items, positive):
        dur = 1.2

        def scene(t):
            i = min(int(t / dur), 2)
            return self.point(t - i * dur, items[i], positive)
        return scene

    def outro(self, t):
        f = img("3_hintergruende/bg1_geteilte_buehne", H).copy()
        self.character(f, "a", "ueberrascht", 210, 1720, t, 620)
        self.character(f, "b", "ueberrascht", 870, 1720, t, 620)
        self.pip(f, W / 2, 1760, t, 760)
        pop(f, self.question, W / 2, 520, t - 0.1)
        return f

    def scenes(self):
        return [(self.intro, 1.8), (self.points(self.plus, True), 3.6), (self.points(self.minus, False), 3.6), (self.outro, 1.0)]


def main():
    theme_path = sys.argv[1]
    with open(theme_path, encoding="utf-8") as f:
        clip = Clip(json.load(f))
    os.makedirs(os.path.join(HERE, "demo"), exist_ok=True)
    out = os.path.join(HERE, "demo", os.path.splitext(os.path.basename(theme_path))[0] + ".mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    white = Image.new("RGB", (W, H), (255, 255, 255))
    scenes = clip.scenes()
    for si, (scene, dur) in enumerate(scenes):
        for n in range(round(dur * FPS)):
            t = n / FPS
            frame = scene(t).convert("RGB")
            flash = 0.0
            if si > 0 and t < 0.12:
                flash = 1 - t / 0.12
            if si < len(scenes) - 1 and t > dur - 0.08:
                flash = (t - (dur - 0.08)) / 0.08
            if flash > 0:
                frame = Image.blend(frame, white, min(flash, 1.0))
            ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
