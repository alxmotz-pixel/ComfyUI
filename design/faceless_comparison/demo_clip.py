"""Renders a ~72 s 1080x1920 comparison video for one theme file (needs Pillow, numpy and ffmpeg).

    python generate.py --chrome ...                 # PNGs first
    python demo_clip.py themen/adidas_vs_nike.json

Theme keys: "a" = blue side, "b" = red side, each {"name", "kostuem"?, "plus": [3 points], "minus": [3 points]}
with points {"text", "info"?, "bilder": [prop/element names], "emotion"?}; "hook" = opening line,
"frage" = closing question that referee Pip throws in after his whistle. No voice, only generated sound effects.
"""

import json
import math
import os
import random
import subprocess
import sys
import tempfile
import wave

import numpy as np

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = os.path.join(HERE, "png")
FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
W, H, FPS, SR = 1080, 1920, 30, 44100
OUT = (43, 47, 54)
BLUE, RED = (47, 123, 255), (238, 51, 64)
SIDES = {"a": ("figur_a_blau", BLUE, "blau", 270), "b": ("figur_b_rot", RED, "rot", 810)}
POINT = 4.5

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
    while size > 16 and font(size).getlength(text) > max_w:
        size -= 2
    return font(size)


def wrap(text, f, max_w):
    lines = [""]
    for word in text.split():
        trial = (lines[-1] + " " + word).strip()
        if f.getlength(trial) > max_w and lines[-1]:
            lines.append(word)
        else:
            lines[-1] = trial
    return lines


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


def zoom(frame, z, cx, cy):
    """Crop towards (cx, cy) by factor z (1 = no zoom) and scale back to full frame."""
    if z <= 1.0:
        return frame
    bw, bh = W / z, H / z
    x0 = min(max(cx - bw / 2, 0), W - bw)
    y0 = min(max(cy - bh / 2, 0), H - bh)
    return frame.crop((round(x0), round(y0), round(x0 + bw), round(y0 + bh))).resize((W, H), Image.BILINEAR)


# graphics ------------------------------------------------------------------

def pill(text, color, size=64, pad=34):
    f = font(size)
    w = round(f.getlength(text)) + 2 * pad
    h = size + 2 * pad - 10
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=h // 2, fill=color, outline=OUT, width=8)
    d.text((w / 2 + 8, h / 2 + 8), text, font=f, fill="white", anchor="mm")
    return im


def textbox(text, size, max_w, tail=False, fill="white", color=OUT):
    f = font(size)
    lines = wrap(text, f, max_w)
    lh = round(size * 1.25)
    w = round(max(f.getlength(line) for line in lines)) + 80
    h = lh * len(lines) + 60
    im = Image.new("RGBA", (w + 16, h + (56 if tail else 16)))
    d = ImageDraw.Draw(im)
    if tail:
        d.polygon([(w / 2 - 30, h + 4), (w / 2 + 30, h + 4), (w / 2, h + 50)], fill=fill, outline=OUT, width=8)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=44, fill=fill, outline=OUT, width=8)
    if tail:
        d.polygon([(w / 2 - 22, h), (w / 2 + 22, h), (w / 2, h + 36)], fill=fill)
    for i, line in enumerate(lines):
        d.text((w / 2 + 8, 38 + lh * i + lh / 2), line, font=f, fill=color, anchor="mm")
    return im


def card(text, icon, color, w=940, h=170, size=68, icon_h=140):
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=h // 4, fill="white", outline=OUT, width=8)
    d.rounded_rectangle([8, 8, 40, h + 8], radius=16, fill=color)
    d.line([(40, 12), (40, h + 4)], fill=OUT, width=6)
    ic = img(icon, icon_h)
    im.alpha_composite(ic, (52, round((h + 16 - ic.height) / 2)))
    x = 60 + icon_h
    d.text((x, h / 2 + 8), text, font=fit(text, w - x - 20, size), fill=OUT, anchor="lm")
    return im


# sound -----------------------------------------------------------------------

def whistle():
    """Referee whistle: a short and a long trilled blast."""
    out = []
    rng = np.random.default_rng(1)
    for dur, gap in ((0.14, 0.06), (0.45, 0.0)):
        tt = np.arange(int(SR * dur)) / SR
        trill = np.sin(2 * np.pi * 34 * tt)
        phase = 2 * np.pi * np.cumsum(2950 + 220 * trill) / SR
        env = np.minimum(1, tt / 0.015) * np.minimum(1, (dur - tt) / 0.06)
        tone = (np.sin(phase) + 0.25 * np.sin(2 * phase)) * (0.75 + 0.25 * trill) + 0.04 * rng.standard_normal(len(tt))
        out += [0.5 * env * tone, np.zeros(int(SR * gap))]
    return np.concatenate(out)


def pop_sound():
    tt = np.arange(int(SR * 0.09)) / SR
    phase = 2 * np.pi * np.cumsum(900 * np.exp(-tt * 25) + 260) / SR
    return 0.35 * np.sin(phase) * np.exp(-tt * 40)


def whoosh():
    n = int(SR * 0.35)
    noise = np.random.default_rng(2).standard_normal(n)
    smooth = np.convolve(noise, np.ones(24) / 24, mode="same")
    return 0.6 * smooth * np.sin(np.linspace(0, np.pi, n)) ** 2


SOUNDS = {"pop": pop_sound(), "whoosh": whoosh(), "whistle": whistle()}


# video ----------------------------------------------------------------------

class Clip:
    def __init__(self, th):
        self.th = th
        self.label = {k: pill(th[k]["name"], SIDES[k][1]) for k in SIDES}
        self.vs = img("5_elemente/vs", 420)
        self.hook = textbox(th["hook"], 66, 900)
        self.question = textbox(th["frage"], 64, 880, tail=True)
        self.points = {}
        self.recap = {}
        for k in SIDES:
            _, color, cname, _ = SIDES[k]
            other = RED if color == BLUE else BLUE
            name = th[k]["name"]
            for positive, key, word, icon, hcol in ((True, "plus", "BESSER", "haken_" + cname, color), (False, "minus", "SCHLECHTER", "kreuz_rot", other)):
                for i, p in enumerate(th[k][key]):
                    self.points.setdefault(k, []).append({
                        "head": pill("%s · %s %d/3" % (name, word, i + 1), hcol, 50),
                        "card": card(p["text"], icon, RED if not positive else color),
                        "info": p.get("info") and textbox(p["info"], 46, 560),
                        "bilder": p["bilder"], "emotion": p.get("emotion", "stolz" if positive else "genervt"),
                        "positive": positive})
                    self.recap.setdefault(k, []).append(card(p["text"], icon, RED if not positive else color, 500, 92, 34, 64))
            self.label[k + "_next"] = pill("JETZT: " + name, color, 70)
        rnd = random.Random(3)
        self.confetti = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(500, 1100), rnd.choice(("c", (255, 255, 255), (255, 200, 61))), rnd.randint(10, 20)) for _ in range(40)]

    def character(self, frame, side, emotion, cx, bottom, t, height, react=None):
        """Idle bounce anchored at the feet; `react` = time of an expression change (stretch)."""
        sy = 1 + 0.015 * math.sin((t + (0.4 if side == "b" else 0)) * 2 * math.pi * 1.2)
        if react is not None and 0 <= t - react < 0.3:
            sy += 0.08 * math.sin((t - react) / 0.3 * math.pi)
        costume = self.th[side].get("kostuem")
        for name in ("2_figuren/%s_%s_freigestellt" % (SIDES[side][0], emotion), costume and "6_kostueme/" + costume):
            if name:
                im = img(name, height)
                put(frame, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)

    def pip(self, frame, cx, bottom, t, height, blowing):
        sy = 1 + 0.015 * math.sin((t + 0.2) * 2 * math.pi * 1.2) + (0.05 * math.sin(t * 40) if blowing else 0)
        for name in ("1_maskottchen/pip_frontal_freigestellt", "6_kostueme/pip_schiedsrichter" + ("_pfeift" if blowing else "")):
            im = img(name, height)
            put(frame, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)

    def stage(self):
        return img("3_hintergruende/bg1_geteilte_buehne", H).copy()

    def whip(self, f, t, start, side):
        """Fast zoom onto one half of the split stage."""
        z = ease((t - start) / 0.35)
        return zoom(f, 1 + z, SIDES[side][3], 1250) if z > 0 else f

    def intro(self, t):
        f = self.stage()
        xa = -400 + 670 * ease_out_back(t / 0.7)
        xb = W + 400 - 670 * ease_out_back((t - 0.15) / 0.7)
        self.character(f, "a", "neutral", xa, 1700, t, 900)
        self.character(f, "b", "neutral", xb, 1700, t, 900)
        pop(f, self.hook, W / 2, 190, t - 1.3)
        pop(f, self.vs, W / 2, 560, t - 0.6)
        pop(f, self.label["a"], 270, 1800, t - 0.9)
        pop(f, self.label["b"], 810, 1800, t - 1.05)
        return self.whip(f, t, 3.6, "a")

    def switch(self, t):
        f = self.stage()
        self.character(f, "a", "genervt", 270, 1700, t, 900, react=0.2)
        self.character(f, "b", "stolz", 810, 1700, t, 900, react=0.2)
        put(f, self.label["a"], 270, 1800)
        put(f, self.label["b"], 810, 1800)
        pop(f, self.label["b_next"], W / 2, 560, t - 0.3)
        return self.whip(f, t, 2.1, "b")

    def point(self, t, side, p):
        f = img("3_hintergruende/bg6_solo_%s" % SIDES[side][2], H).copy()
        positive = p["positive"]
        if not positive:
            f.alpha_composite(Image.new("RGBA", (W, H), (20, 22, 30, 70)))
        self.character(f, side, p["emotion"], 300, 1830, t, 1050, react=0.0)
        pics = p["bilder"]
        size = 600 if len(pics) == 1 else 420
        shake = 14 * math.sin(t * 60) * (1 - clamp((t - 0.45) / 0.4)) if not positive and t > 0.45 else 0
        for i, name in enumerate(pics):
            gx = 720 + (i - (len(pics) - 1) / 2) * 330 + shake
            gy = 840 + 18 * math.sin(t * 3 + i)
            pop(f, img(name, size), gx, gy, t - 0.45 - 0.15 * i)
        if positive and t > 0.45:
            d = ImageDraw.Draw(f)
            k = ease((t - 0.45) / 0.8)
            for a, dist, col, r in self.confetti:
                if k < 1:
                    x = 720 + math.cos(a) * dist * k
                    y = 840 + math.sin(a) * dist * k * 0.8 + 400 * k * k
                    d.ellipse([x - r, y - r, x + r, y + r], fill=SIDES[side][1] if col == "c" else col, outline=OUT, width=3)
        if p["info"]:
            pop(f, p["info"], 720, 1280, t - 1.3)
        pop(f, p["head"], W / 2, 110, t)
        pop(f, p["card"], W / 2, 300, t - 0.1)
        return zoom(f, 1 + 0.04 * t / POINT, W / 2, 900)

    def recap_scene(self, t):
        f = self.stage()
        self.character(f, "a", "neutral", 270, 1780, t, 620)
        self.character(f, "b", "neutral", 810, 1780, t, 620)
        for k in SIDES:
            cx = SIDES[k][3]
            start = 0.3 if k == "a" else 2.0
            pop(f, self.label[k], cx, 140, t - start + 0.2)
            for i, c in enumerate(self.recap[k]):
                pop(f, c, cx, 290 + 115 * i, t - start - 0.22 * i)
        return f

    WHISTLE = (0.3, 1.0)

    def outro(self, t):
        f = self.stage()
        w0, w1 = self.WHISTLE
        blowing = w0 <= t < w1
        react = w0 + 0.05
        self.character(f, "a", "ueberrascht" if t >= react else "neutral", 200, 1760, t, 620, react=react)
        self.character(f, "b", "ueberrascht" if t >= react else "neutral", 880, 1760, t, 620, react=react)
        height = 820
        self.pip(f, W / 2, 1800, t, height, blowing)
        if blowing:
            k = height / 1536
            x, y = W / 2 + (680 - 512) * k, 1800 - height + 1006 * k
            d = ImageDraw.Draw(f)
            for i in range(3):
                r = 60 + 50 * i + 25 * ((t * 6) % 1)
                d.arc([x - r, y - r, x + r, y + r], -45, 45, fill="white", width=14)
        pop(f, self.question, W / 2, 620, t - 1.2)
        return f

    def timeline(self):
        """(scene, duration, [(offset, sound)])"""
        pops = [(0.0, "pop"), (0.45, "pop"), (1.3, "pop")]
        tl = [(self.intro, 4.0, [(0.0, "whoosh"), (0.6, "pop"), (0.9, "pop"), (1.3, "pop"), (3.6, "whoosh")])]
        tl += [(lambda t, p=p: self.point(t, "a", p), POINT, pops) for p in self.points["a"]]
        tl.append((self.switch, 2.5, [(0.3, "pop"), (2.1, "whoosh")]))
        tl += [(lambda t, p=p: self.point(t, "b", p), POINT, pops) for p in self.points["b"]]
        tl.append((self.recap_scene, 6.5, [(0.3 + 0.22 * i, "pop") for i in range(6)] + [(2.0 + 0.22 * i, "pop") for i in range(6)]))
        tl.append((self.outro, 4.5, [(self.WHISTLE[0], "whistle"), (1.2, "pop")]))
        return tl


def main():
    theme_path = sys.argv[1]
    with open(theme_path, encoding="utf-8") as f:
        clip = Clip(json.load(f))
    tl = clip.timeline()
    audio = np.zeros(int(SR * (sum(d for _, d, _ in tl) + 1)))
    t0 = 0.0
    for _, dur, sounds in tl:
        for off, kind in sounds:
            s = int(SR * (t0 + off))
            audio[s:s + len(SOUNDS[kind])] += SOUNDS[kind]
        t0 += dur
    wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    wav.close()

    os.makedirs(os.path.join(HERE, "demo"), exist_ok=True)
    out = os.path.join(HERE, "demo", os.path.splitext(os.path.basename(theme_path))[0] + ".mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-i", wav.name, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    white = Image.new("RGB", (W, H), (255, 255, 255))
    for si, (scene, dur, _) in enumerate(tl):
        for n in range(round(dur * FPS)):
            t = n / FPS
            frame = scene(t).convert("RGB")
            flash = 0.0
            if si > 0 and t < 0.12:
                flash = 1 - t / 0.12
            if si < len(tl) - 1 and t > dur - 0.08:
                flash = (t - (dur - 0.08)) / 0.08
            if flash > 0:
                frame = Image.blend(frame, white, min(flash, 1.0))
            ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    ff.wait()
    os.unlink(wav.name)


if __name__ == "__main__":
    main()
