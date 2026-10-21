"""Renders a 10 s 1080x1920 comparison clip for one theme file (needs Pillow and ffmpeg).

    python generate.py --chrome ...                 # PNGs first
    python demo_clip.py themen/arm_vs_reich.json

Theme: "a" = blue side, "b" = red side, "plus" = 3 points where B is better,
"minus" = 3 points where B is worse, "frage" = closing question.
"""

import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "png")
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
W, H, FPS = 1080, 1920, 30
OUT = (43, 47, 54)
BLUE, RED = (47, 123, 255), (238, 51, 64)

_cache = {}


def img(name, height):
    key = (name, height)
    if key not in _cache:
        im = Image.open(os.path.join(PNG, name + ".png")).convert("RGBA")
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


def ease_out_back(t):
    t = min(max(t, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


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


def character(frame, name, cx, bottom, t, phase=0.0, height=620, react=None):
    """Idle bounce anchored at the feet; `react` = time of an expression change (stretch)."""
    sy = 1 + 0.015 * math.sin((t + phase) * 2 * math.pi * 1.2)
    if react is not None and 0 <= t - react < 0.3:
        sy += 0.08 * math.sin((t - react) / 0.3 * math.pi)
    im = img(name + "_freigestellt", height)
    put(frame, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)


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
    w, h = 900, 150
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=36, fill="white", outline=OUT, width=8)
    d.rounded_rectangle([8, 8, 40, h + 8], radius=16, fill=color)
    d.line([(40, 12), (40, h + 4)], fill=OUT, width=6)
    ic = img(icon, 130)
    im.alpha_composite(ic, (60, round((h + 16 - ic.height) / 2)))
    d.text((210, h / 2 + 8), text, font=fit(text, w - 230, 60), fill=OUT, anchor="lm")
    return im


class Clip:
    def __init__(self, theme):
        self.th = theme
        self.label_a = pill(theme["a"], BLUE)
        self.label_b = pill(theme["b"], RED)
        self.vs = img("5_elemente/vs", 420)
        self.head_plus = pill("3× BESSER: " + theme["b"], RED, 58)
        self.head_minus = pill("3× SCHLECHTER: " + theme["b"], RED, 58)
        self.plus = [card(p, "5_elemente/haken_rot", RED) for p in theme["plus"]]
        self.minus = [card(p, "5_elemente/kreuz_rot", RED) for p in theme["minus"]]
        q = theme["frage"]
        self.question = pill(q, OUT, 66) if font(66).getlength(q) < 900 else pill(q, OUT, 48)

    def stage(self):
        return img("3_hintergruende/bg1_geteilte_buehne", H).copy()

    def intro(self, t):
        f = self.stage()
        xa = -400 + 670 * ease_out_back(t / 0.7)
        xb = W + 400 - 670 * ease_out_back((t - 0.15) / 0.7)
        character(f, "2_figuren/figur_a_blau_neutral", xa, 1700, t, 0.0, 900)
        character(f, "2_figuren/figur_b_rot_neutral", xb, 1700, t, 0.4, 900)
        pop(f, self.vs, W / 2, 470, t - 0.5)
        pop(f, self.label_a, 270, 1800, t - 0.8)
        pop(f, self.label_b, 810, 1800, t - 0.95)
        return f

    def points(self, t, head, cards, b_wins):
        f = self.stage()
        pop(f, head, W / 2, 230, t)
        for i, c in enumerate(cards):
            pop(f, c, W / 2, 470 + 200 * i, t - 0.45 - 0.9 * i)
        a = "figur_a_blau_" + ("genervt" if b_wins else "stolz")
        b = "figur_b_rot_" + ("stolz" if b_wins else "genervt")
        character(f, "2_figuren/" + a, 270, 1720, t, 0.0, react=0.1)
        character(f, "2_figuren/" + b, 810, 1720, t, 0.4, react=0.1)
        put(f, self.label_a, 270, 1810, 0.8)
        put(f, self.label_b, 810, 1810, 0.8)
        return f

    def outro(self, t):
        f = self.stage()
        character(f, "2_figuren/figur_a_blau_ueberrascht", 200, 1720, t, 0.0, 560)
        character(f, "2_figuren/figur_b_rot_ueberrascht", 880, 1720, t, 0.4, 560)
        character(f, "1_maskottchen/pip_frontal", W / 2, 1760, t, 0.2, 760)
        pop(f, self.question, W / 2, 520, t - 0.1)
        return f

    def scenes(self):
        return [(self.intro, 2.0),
                (lambda t: self.points(t, self.head_plus, self.plus, True), 3.5),
                (lambda t: self.points(t, self.head_minus, self.minus, False), 3.5),
                (self.outro, 1.0)]


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
            if si > 0 and t < 0.15:
                flash = 1 - t / 0.15
            if si < len(scenes) - 1 and t > dur - 0.1:
                flash = (t - (dur - 0.1)) / 0.1
            if flash > 0:
                frame = Image.blend(frame, white, min(flash, 1.0))
            ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
