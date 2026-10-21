"""Renders a 9 s 1080x1920 demo comparison clip from the PNG assets (needs Pillow and ffmpeg).

    python generate.py --chrome ...   # PNGs first
    python demo_clip.py
"""

import math
import os
import subprocess

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "png")
W, H, FPS = 1080, 1920, 30
OUT = (43, 47, 54)
BLUE, ORANGE = (47, 123, 255), (255, 138, 31)

_cache = {}


def img(name, height):
    key = (name, height)
    if key not in _cache:
        im = Image.open(os.path.join(PNG, name + ".png")).convert("RGBA")
        _cache[key] = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    return _cache[key]


def ease_out_back(t):
    t = min(max(t, 0.0), 1.0)
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def put(frame, im, cx, bottom, sx=1.0, sy=1.0):
    """Paste with the anchor at bottom centre; sx/sy squash and stretch around that anchor."""
    if sx <= 0 or sy <= 0:
        return
    if sx != 1.0 or sy != 1.0:
        im = im.resize((max(1, round(im.width * sx)), max(1, round(im.height * sy))), Image.BILINEAR)
    frame.alpha_composite(im, (round(cx - im.width / 2), round(bottom - im.height)))


def pop(frame, name, height, cx, cy, t):
    s = ease_out_back(t / 0.35)
    if s > 0.02:
        im = img(name, height)
        put(frame, im, cx, cy + im.height * s / 2, s, s)


def bob(t, phase=0.0):
    return math.sin((t + phase) * 2 * math.pi * 1.2)


def character(frame, name, cx, bottom, t, phase=0.0, height=900, react=None):
    """Idle bounce; `react` is the time an expression switch happened (squash, then stretch)."""
    b = bob(t, phase)
    sy = 1 + 0.015 * b
    if react is not None and 0 <= t - react < 0.3:
        k = math.sin((t - react) / 0.3 * math.pi)
        sy += 0.08 * k
    put(frame, img(name, height), cx, bottom, 2 - sy, sy)


def scene_versus(t):
    f = img("3_hintergruende/bg1_geteilte_buehne", H).copy()
    xa = -400 + (270 + 400) * ease_out_back(t / 0.8)
    xb = W + 400 - (W + 400 - 810) * ease_out_back((t - 0.15) / 0.8)
    a = "figur_a_blau_stolz" if t >= 1.6 else "figur_a_blau_neutral"
    b = "figur_b_orange_ueberrascht" if t >= 1.6 else "figur_b_orange_neutral"
    character(f, "2_figuren/" + a + "_freigestellt", xa, 1700, t, 0.0, react=1.6)
    character(f, "2_figuren/" + b + "_freigestellt", xb, 1700, t, 0.4, react=1.6)
    pop(f, "5_elemente/vs", 480, W / 2, 400, t - 0.6)
    pop(f, "5_elemente/haken_blau", 260, 200, 700, t - 2.0)
    pop(f, "5_elemente/kreuz_orange", 260, 880, 700, t - 2.2)
    return f


def scene_chart(t):
    f = img("3_hintergruende/bg5_raster_weiss", H).copy()
    size = 940
    cx0, cy0 = (W - size) / 2, 260
    f.alpha_composite(img("5_elemente/balken_a_vs_b", size), (round(cx0), cy0))
    k = size / 1024
    d = ImageDraw.Draw(f)
    for i, (target, col) in enumerate(((290, BLUE), (520, ORANGE))):
        h = target * ease((t - 0.3 - 0.25 * i) / 1.2)
        if h > 4:
            x0 = cx0 + (280 + 300 * i) * k
            d.rounded_rectangle([x0, cy0 + (760 - h) * k, x0 + 180 * k, cy0 + 760 * k], radius=round(18 * k), fill=col, outline=OUT, width=round(8 * k))
    pop(f, "5_elemente/pfeil_runter_blau", 220, cx0 + 370 * k, cy0 + 300 * k, t - 1.6)
    pop(f, "5_elemente/pfeil_hoch_orange", 220, cx0 + 670 * k, cy0 + 100 * k, t - 1.8)
    pip_x = -300 + 560 * ease_out_back(t / 0.7)
    character(f, "1_maskottchen/pip_frontal_freigestellt", pip_x, 1860, t, 0.2, height=640)
    pop(f, "4_requisiten/stoppuhr_orange", 300, 830, 1560, t - 0.9)
    return f


def scene_podium(t):
    f = img("3_hintergruende/bg2_studio_podest", H).copy()
    drop = 1250 * (1 - ease_out_back(t / 0.7))
    character(f, "2_figuren/figur_b_orange_stolz_freigestellt", 540, 1270 - drop, t, 0.0, height=640)
    character(f, "2_figuren/figur_a_blau_genervt_freigestellt", 265, 1390, t, 0.5, height=640, react=0.9)
    character(f, "1_maskottchen/pip_frontal_freigestellt", 815, 1460, t, 0.3, height=440)
    pop(f, "4_requisiten/pokal_orange", 360, 540, 620, t - 1.0)
    return f


SCENES = [(scene_versus, 3.0), (scene_chart, 3.0), (scene_podium, 3.0)]


def main():
    os.makedirs(os.path.join(HERE, "demo"), exist_ok=True)
    out = os.path.join(HERE, "demo", "vergleich_demo.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    white = Image.new("RGB", (W, H), (255, 255, 255))
    for si, (scene, dur) in enumerate(SCENES):
        for n in range(round(dur * FPS)):
            t = n / FPS
            frame = scene(t).convert("RGB")
            flash = 0.0
            if si > 0 and t < 0.15:
                flash = 1 - t / 0.15
            if si < len(SCENES) - 1 and t > dur - 0.1:
                flash = (t - (dur - 0.1)) / 0.1
            if flash > 0:
                frame = Image.blend(frame, white, min(flash, 1.0))
            ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
