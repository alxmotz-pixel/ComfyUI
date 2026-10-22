"""Renders a ~75 s 1080x1920 round-based duel video for one theme file (needs Pillow, numpy and ffmpeg).

    python generate.py --chrome ...                       # PNGs first
    python duell.py themen/automatik_vs_manuell.json

Theme keys: "a" = blue side, "b" = red side, each {"name", "kostuem"?}; "hook" = opening line;
"runden" = rounds {"titel", "a": side, "b": side, "sieger": "a" | "b" | null} where a side is
{"text", "bilder": [prop/element names], "zahl"?: {"label", "wert", "vor"?, "nach"?}, "messer"?: {"label", "wert" 0-100}};
"frage" = closing question; optional "ende" = {"sieger": pose, "verlierer": pose} for the final scene
(default jubelnd/traurig; a happy loser sways instead of leaning over) or {"pokal_klau": true}: the cup goes to the
happy loser, the winner walks over, slaps the back of his head, takes the cup and gets a yellow card; optional "kurz" = round indices for the short cut (--kurz). Every scene length is a
multiple of one beat at 120 BPM, and the last second fades back into the first frame so the video loops.
Referee Pip whistles every round, shows the loser a yellow card and calls the final score. A side may set "emotion".
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

from PIL import Image, ImageDraw

from demo_clip import (BLUE, FPS, H, OUT, RED, SIDES, SOUNDS, SR, W, clamp, ease, ease_out_back, font, img, pill,
                       pop, put, textbox, whistle)

YELLOW = (255, 200, 61)
# scene lengths in seconds, all multiples of 0.5 s (one beat at 120 BPM)
TEMPO = {"lang": {"intro": 3.5, "runde": 1.5, "seite": 3.5, "wisch": 0.5, "urteil": 2.0, "finale": 7.0, "loop": 1.0, "frage": 2.5},
         "kurz": {"intro": 2.5, "runde": 1.0, "seite": 2.5, "wisch": 0.5, "urteil": 1.5, "finale": 4.0, "loop": 0.5, "frage": 1.5}}


def ding():
    tt = np.arange(int(SR * 0.5)) / SR
    return 0.3 * (np.sin(2 * np.pi * 1320 * tt) + 0.5 * np.sin(2 * np.pi * 1980 * tt)) * np.exp(-tt * 7)


def short_whistle():
    return whistle()[int(SR * 0.2):int(SR * 0.45)]


def slap():
    n = int(SR * 0.18)
    tt = np.arange(n) / SR
    crack = np.random.default_rng(4).standard_normal(n) * np.exp(-tt * 45)
    thump = np.sin(2 * np.pi * 110 * tt) * np.exp(-tt * 20)
    return 0.7 * crack + 0.5 * thump


SOUNDS = dict(SOUNDS, ding=ding(), pfiff=short_whistle(), klatsch=slap())


def outlined(text, size, fill="white"):
    f = font(size)
    w = round(f.getlength(text)) + 40
    im = Image.new("RGBA", (w, size + 40))
    ImageDraw.Draw(im).text((w / 2, (size + 40) / 2), text, font=f, fill=fill, anchor="mm", stroke_width=8, stroke_fill=OUT)
    return im


def scoreboard(names, sa, sb, scale=1.0):
    w, h = round(920 * scale), round(120 * scale)
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=h // 2, fill=BLUE, outline=OUT, width=8)
    d.rounded_rectangle([w / 2 + 8, 8, w + 8, h + 8], radius=h // 2, fill=RED, outline=OUT, width=8)
    d.rectangle([w / 2 + 8, 12, w / 2 + 60, h + 4], fill=RED)
    d.rounded_rectangle([w / 2 - 70 * scale + 8, 4, w / 2 + 70 * scale + 8, h + 12], radius=24, fill="white", outline=OUT, width=8)
    d.text((w / 2 + 8, h / 2 + 8), "%d:%d" % (sa, sb), font=font(round(64 * scale)), fill=OUT, anchor="mm")
    for name, x in ((names[0], w / 4 - 20 * scale), (names[1], 3 * w / 4 + 20 * scale)):
        f = font(round(46 * scale))
        while f.getlength(name) > w / 2 - 170 * scale:
            f = font(f.size - 2)
        d.text((x + 8, h / 2 + 8), name, font=f, fill="white", anchor="mm")
    return im


def gauge(label, value, color):
    """Half-circle meter on a white panel; value 0-100."""
    w, h = 560, 400
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=48, fill="white", outline=OUT, width=8)
    cx, cy, r = w / 2 + 8, 300, 200
    box = [cx - r, cy - r, cx + r, cy + r]
    d.arc(box, 180, 360, fill=(217, 220, 225), width=46)
    if value > 0:
        d.arc(box, 180, 180 + 180 * value / 100, fill=color, width=46)
    for i in range(11):
        a = math.radians(180 + 18 * i)
        d.line([(cx + (r - 40) * math.cos(a), cy + (r - 40) * math.sin(a)), (cx + (r - 62) * math.cos(a), cy + (r - 62) * math.sin(a))], fill=OUT, width=6)
    a = math.radians(180 + 180 * value / 100)
    d.line([(cx, cy), (cx + (r - 30) * math.cos(a), cy + (r - 30) * math.sin(a))], fill=OUT, width=16)
    d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=OUT)
    d.text((cx, cy + 60), "%s %d%%" % (label, round(value)), font=font(44), fill=OUT, anchor="mm")
    return im


def counter(label, value, pre, post, target):
    step = 100 if target >= 1000 else 10 if target >= 100 else 1
    value = round(value / step) * step
    w, h = 620, 300
    im = Image.new("RGBA", (w + 16, h + 16))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, w + 8, h + 8], radius=48, fill="white", outline=OUT, width=8)
    d.text((w / 2 + 8, 80), label, font=font(42), fill=(74, 80, 90), anchor="mm")
    num = pre + "{:,}".format(round(value)).replace(",", ".") + post
    d.text((w / 2 + 8, 195), num, font=font(110), fill=OUT, anchor="mm")
    return im


class Duel:
    def __init__(self, th, short):
        self.th = th
        self.T = TEMPO["kurz" if short else "lang"]
        self.names = (th["a"]["name"], th["b"]["name"])
        self.rounds = [th["runden"][i] for i in th["kurz"]] if short else th["runden"]
        self.score = [(0, 0)]
        for r in self.rounds:
            sa, sb = self.score[-1]
            self.score.append((sa + (r["sieger"] == "a"), sb + (r["sieger"] == "b")))
        self.boards = {}
        self.hook = textbox(th["hook"], 76, 900)
        self.question = textbox(th["frage"], 64, 880, tail=True)
        self.vs = img("5_elemente/vs", 460)
        self.labels = {k: pill(th[k]["name"], SIDES[k][1]) for k in SIDES}
        self.texts = [{k: textbox(r[k]["text"], 56, 760) for k in SIDES} for r in self.rounds]
        self.titles = [(pill("RUNDE %d" % (i + 1), OUT, 54), outlined(r["titel"], 150)) for i, r in enumerate(self.rounds)]
        self.plus = outlined("+1", 150, (255, 200, 61))
        self.draw = pill("UNENTSCHIEDEN", OUT, 60)
        rnd = random.Random(3)
        self.confetti = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(500, 1100), rnd.choice((BLUE, RED, (255, 255, 255), YELLOW)), rnd.randint(10, 20)) for _ in range(60)]

    def board(self, sa, sb, scale=1.0):
        key = (sa, sb, scale)
        if key not in self.boards:
            self.boards[key] = scoreboard(self.names, sa, sb, scale)
        return self.boards[key]

    # characters ---------------------------------------------------------------

    def character(self, f, side, emotion, cx, bottom, t, height, react=None, angle=0.0, sy=None):
        if sy is None:
            sy = 1 + 0.015 * math.sin((t + (0.4 if side == "b" else 0)) * 2 * math.pi * 1.2)
        if react is not None and 0 <= t - react < 0.3:
            sy += 0.08 * math.sin((t - react) / 0.3 * math.pi)
        im = img("2_figuren/%s_%s_freigestellt" % (SIDES[side][0], emotion), height).copy()
        costume = self.th[side].get("kostuem")
        if costume:
            im.alpha_composite(img("6_kostueme/" + costume, height))
        if angle:
            im = im.rotate(angle, resample=Image.BICUBIC)
        put(f, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)

    def pip(self, f, cx, bottom, t, height, blowing=False, card=None):
        """Referee Pip; `card` = -1/1 holds a yellow card up on that side."""
        sy = 1 + 0.015 * math.sin((t + 0.2) * 2 * math.pi * 1.2) + (0.05 * math.sin(t * 40) if blowing else 0)
        for name in ("1_maskottchen/pip_frontal_freigestellt", "6_kostueme/pip_schiedsrichter" + ("_pfeift" if blowing else "")):
            im = img(name, height)
            put(f, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)
        k = height / 1536
        if blowing:
            x, y = cx + (680 - 512) * k, bottom - height + 1006 * k
            d = ImageDraw.Draw(f)
            for i in range(3):
                r = (60 + 50 * i + 25 * ((t * 6) % 1)) * k * 2
                d.arc([x - r, y - r, x + r, y + r], -45, 45, fill="white", width=max(6, round(14 * k * 2)))
        if card:
            c = Image.new("RGBA", (round(150 * k * 2), round(210 * k * 2)))
            ImageDraw.Draw(c).rounded_rectangle([4, 4, c.width - 4, c.height - 4], radius=12, fill=YELLOW, outline=OUT, width=6)
            c = c.rotate(-15 * card, expand=True, resample=Image.BICUBIC)
            put(f, c, cx + card * 330 * k, bottom - height + 900 * k)

    # scenes ---------------------------------------------------------------------

    def stage(self):
        return img("3_hintergruende/bg1_geteilte_buehne", H).copy()

    def intro(self, t):
        """Everything is on screen in the very first frame (hook at second 0); only the bounce moves in."""
        f = self.stage()
        self.character(f, "a", "neutral", 270, 1700, t, 900, react=0.0)
        self.character(f, "b", "neutral", 810, 1700, t, 900, react=0.1)
        put(f, self.vs, W / 2, 640, 1 + 0.08 * math.sin(clamp(t / 0.3) * math.pi))
        put(f, self.hook, W / 2, 250, 1 + 0.05 * math.sin(clamp(t / 0.3) * math.pi))
        put(f, self.labels["a"], 270, 1800)
        put(f, self.labels["b"], 810, 1800)
        return f

    def round_intro(self, i, t):
        f = img("3_hintergruende/bg2_studio_podest", H).copy()
        put(f, self.board(*self.score[i]), W / 2, 90)
        small, big = self.titles[i]
        pop(f, small, W / 2, 330, t - 0.05)
        pop(f, big, W / 2, 500, t - 0.15)
        self.pip(f, W / 2, 1300, t, 760, blowing=0.1 <= t < 0.5)
        return f

    def side(self, i, k, t):
        r = self.rounds[i][k]
        _, color, cname, _ = SIDES[k]
        f = img("3_hintergruende/bg6_solo_%s" % cname, H).copy()
        left = k == "a"
        cx_char, cx_obj = (290, 720) if left else (790, 360)
        self.character(f, k, r.get("emotion", "neutral"), cx_char, 1840, t, 950, react=0.0)
        pics = r["bilder"]
        size = 520 if len(pics) == 1 else 380
        for j, name in enumerate(pics):
            gx = cx_obj + (j - (len(pics) - 1) / 2) * 300
            pop(f, img(name, size), gx, 860 + 16 * math.sin(t * 3 + j), t - 0.3 - 0.12 * j)
        p = clamp((t - 0.6) / 1.4)
        p = 1 - (1 - p) ** 2
        if "messer" in r:
            m = r["messer"]
            pop(f, gauge(m["label"], m["wert"] * p, color), cx_obj, 1320, t - 0.5)
        if "zahl" in r:
            z = r["zahl"]
            pop(f, counter(z["label"], z["wert"] * p, z.get("vor", ""), z.get("nach", ""), z["wert"]), cx_obj, 1320, t - 0.5)
        put(f, self.board(*self.score[i]), W / 2, 90)
        pop(f, self.texts[i][k], W / 2, 330, t - 0.1)
        return f

    def wipe(self, i, t):
        """Blue side slides away under a red sweep; no caption."""
        fa = self.side(i, "a", self.T["seite"])
        fb = self.side(i, "b", 0.0)
        x = ease(t / self.T["wisch"]) * (W + 700) - 350
        mask = Image.new("L", (W, H))
        ImageDraw.Draw(mask).polygon([(x + 350, 0), (W + 400, 0), (W + 400, H), (x - 350, H)], fill=255)
        f = Image.composite(fb, fa, mask)
        d = ImageDraw.Draw(f)
        d.line([(x + 350, 0), (x - 350, H)], fill="white", width=34)
        d.line([(x + 330, 0), (x - 370, H)], fill=OUT, width=8)
        d.line([(x + 370, 0), (x - 330, H)], fill=OUT, width=8)
        return f

    def verdict(self, i, t):
        f = self.stage()
        win = self.rounds[i]["sieger"]
        after = t >= 0.5
        emo = {k: ("ueberrascht" if win is None else ("stolz" if k == win else "genervt")) if t >= 0.3 else "neutral" for k in SIDES}
        self.character(f, "a", emo["a"], 230, 1760, t, 720, react=0.3)
        self.character(f, "b", emo["b"], 850, 1760, t, 720, react=0.3)
        loser = {"a": 1, "b": -1}.get(win) if t >= 0.3 else None
        self.pip(f, W / 2, 1790, t, 700, card=loser)
        if win:
            pop(f, self.plus, SIDES[win][3], 930, t - 0.4)
        else:
            pop(f, self.draw, W / 2, 900, t - 0.3)
        put(f, self.board(*self.score[i + (1 if after else 0)]), W / 2, 90, 1 + 0.12 * math.sin(clamp((t - 0.5) / 0.3) * math.pi))
        return f

    # visible top of each figure as a fraction of its canvas height (crest tip)
    TOP = {"a": 0.2, "b": 0.46}

    def finale(self, t):
        """Final whistle: the winner jumps for joy with wings up, the loser leans over and is sad."""
        f = self.stage()
        sa, sb = self.score[-1]
        win = "a" if sa > sb else "b" if sb > sa else None
        lose = {"a": "b", "b": "a"}.get(win)
        x = {"a": 250, "b": 830}
        bottom, height = 1730, 760
        if win:
            go = t >= 0.6
            end = self.th.get("ende", {})
            pose_win, pose_lose = end.get("sieger", "jubelnd"), end.get("verlierer", "traurig")
            wild = pose_win == "jubelnd"
            period = 0.5 if wild else 1.0
            hop = abs(math.sin(math.pi * (t - 0.6) / period)) if go else 0.0
            jump = (160 if wild else 70) * hop
            self.character(f, win, pose_win if go else "neutral", x[win], bottom - jump, t, height,
                           react=0.6, sy=1 + 0.06 * hop - 0.06 * (1 - hop) ** 6 if go else None)
            if pose_lose == "traurig":
                lean = ease((t - 0.6) / 0.8)
                self.character(f, lose, pose_lose if go else "neutral", x[lose] + (40 if lose == "b" else -40) * lean,
                               bottom + 20 * lean, t, height, react=0.6, angle=(-18 if lose == "b" else 18) * lean)
            else:
                sway = 7 * math.sin(2 * math.pi * (t - 0.6)) * ease((t - 0.6) / 0.3) if go else 0.0
                self.character(f, lose, pose_lose if go else "neutral", x[lose], bottom, t, height, react=0.6, angle=sway)
            top = bottom - jump - height * (1 - self.TOP[win])
            pop(f, img("4_requisiten/pokal_%s" % SIDES[win][2], 260), x[win], top - 110, t - 0.9)
            if t > 0.9:
                d = ImageDraw.Draw(f)
                k = ease((t - 0.9) / 1.4)
                for a, dist, col, r in self.confetti:
                    if k < 1:
                        cx = x[win] + math.cos(a) * dist * k
                        cy = top + math.sin(a) * dist * k * 0.8 + 700 * k * k
                        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col, outline=OUT, width=3)
        else:
            for k in SIDES:
                self.character(f, k, "ueberrascht", x[k], bottom, t, height)
        self.pip(f, W / 2, 1800, t, 520, blowing=0.2 <= t < 0.9)
        put(f, self.board(sa, sb, 1.0), W / 2, 260, 1 + 0.12 * math.sin(clamp((t - 0.3) / 0.3) * math.pi))
        pop(f, self.question, W / 2, 560, t - self.T["frage"])
        return f

    # pokal_klau beats (s): cup lands on the loser, walk over, slap, walk back, cheer, question
    KLAU = {"pokal": 0.8, "hin": 2.0, "klaps": 3.0, "zurueck": 3.5, "jubel": 4.5, "frage": 5.0, "laenge": 8.0}

    def finale_klau(self, t):
        f = self.stage()
        K = self.KLAU
        sa, sb = self.score[-1]
        win = "a" if sa > sb else "b"
        lose = "b" if win == "a" else "a"
        home, other = {"a": 250, "b": 830}[win], {"a": 250, "b": 830}[lose]
        bottom, height = 1730, 760
        toward = 1 if other > home else -1
        reach = other - toward * 230

        def walk(t0, t1, x0, x1):
            k = clamp((t - t0) / (t1 - t0))
            step = abs(math.sin(math.pi * (t - t0) / 0.25)) if 0 < k < 1 else 0.0
            return x0 + (x1 - x0) * ease(k), 30 * step, (6 * toward if int((t - t0) / 0.25) % 2 else -6 * toward) if 0 < k < 1 else 0.0

        # winner: sad, walks over, slaps, walks back with the cup, then cheers
        if t < K["hin"]:
            wx, wy, wa, pose = home, 0.0, 0.0, "traurig" if t >= 0.6 else "neutral"
        elif t < K["klaps"]:
            (wx, wy, wa), pose = walk(K["hin"], K["klaps"] - 0.1, home, reach), "genervt"
        elif t < K["zurueck"]:
            swing = math.sin(clamp((t - K["klaps"]) / 0.3) * math.pi)
            wx, wy, wa, pose = reach + toward * 40 * swing, 0.0, -toward * 22 * swing, "ueberrascht"
        elif t < K["jubel"]:
            (wx, wy, wa), pose = walk(K["zurueck"], K["jubel"] - 0.1, reach, home), "stolz"
        else:
            hop = abs(math.sin(math.pi * (t - K["jubel"]) / 0.5))
            wx, wy, wa, pose = home, 160 * hop, 0.0, "jubelnd"

        # loser: happy with the cup until the slap, then shocked, then sad
        hit = K["klaps"] + 0.15
        # referee stands further back so the birds walk in front of him
        self.pip(f, W / 2, 1570, t, 440, blowing=(0.2 <= t < 0.9) or (hit + 0.1 <= t < hit + 0.5),
                 card=-toward if hit + 0.5 <= t < K["frage"] + 1.5 else None)
        if t < hit:
            sway = 7 * math.sin(2 * math.pi * (t - 0.6)) * ease((t - 0.6) / 0.3) if t >= 0.6 else 0.0
            self.character(f, lose, "gluecklich" if t >= 0.6 else "neutral", other, bottom, t, height, react=0.6, angle=sway)
        else:
            k = clamp((t - hit) / 0.25)
            jolt = math.sin(k * math.pi)
            pose_l = "ueberrascht" if t < K["jubel"] else "traurig"
            lean = ease((t - K["jubel"]) / 0.8) if t >= K["jubel"] else 0.0
            self.character(f, lose, pose_l, other + toward * 30 * jolt + toward * 40 * lean, bottom + 20 * lean, t, height,
                           react=hit, angle=toward * (-18 * jolt) + (-18 if lose == "b" else 18) * lean, sy=1 - 0.1 * jolt)
            if t < hit + 1.2:
                head_y = bottom - height * (1 - self.TOP[lose]) + 40
                d = ImageDraw.Draw(f)
                for i in range(4):
                    a = 2 * math.pi * (i / 4 + (t - hit) * 1.5)
                    sx, sy = other + 120 * math.cos(a), head_y + 30 * math.sin(a)
                    r = 22
                    pts = [(sx + (r if j % 2 == 0 else r * 0.45) * math.cos(math.pi / 5 * j - math.pi / 2),
                            sy + (r if j % 2 == 0 else r * 0.45) * math.sin(math.pi / 5 * j - math.pi / 2)) for j in range(10)]
                    d.polygon(pts, fill=YELLOW, outline=OUT, width=4)

        self.character(f, win, pose, wx, bottom - wy, t, height, angle=wa, sy=1.0 if wy else None)

        # the cup: above the loser, flies to the winner on the slap, then rides on the winner
        cup = img("4_requisiten/pokal_%s" % SIDES[win][2], 240)
        top_l = bottom - height * (1 - self.TOP[lose]) - 110
        top_w = bottom - wy - height * (1 - self.TOP[win]) - 110
        if t < hit:
            pop(f, cup, other, top_l + 10 * math.sin(t * 4), t - K["pokal"])
        else:
            k = ease(clamp((t - hit) / 0.45))
            cx = other + (wx - other) * k
            cy = top_l + (top_w - top_l) * k - 260 * math.sin(k * math.pi)
            put(f, cup.rotate(-360 * k * toward, resample=Image.BICUBIC), cx, cy)
        if K["pokal"] < t < K["hin"] + 0.5:
            d = ImageDraw.Draw(f)
            k = ease((t - K["pokal"]) / 1.4)
            for a, dist, col, r in self.confetti:
                if k < 1:
                    x = other + math.cos(a) * dist * k
                    y = top_l + math.sin(a) * dist * k * 0.8 + 700 * k * k
                    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=OUT, width=3)
        put(f, self.board(sa, sb, 1.0), W / 2, 260, 1 + 0.12 * math.sin(clamp((t - 0.3) / 0.3) * math.pi))
        pop(f, self.question, W / 2, 560, t - K["frage"])
        return f

    def final_scene(self):
        if self.th.get("ende", {}).get("pokal_klau"):
            K = self.KLAU
            sounds = [(0.2, "whistle"), (K["pokal"], "ding"), (K["hin"], "whoosh"), (K["klaps"] + 0.15, "klatsch"),
                      (K["klaps"] + 0.25, "pfiff"), (K["klaps"] + 0.2, "whoosh"), (K["jubel"], "ding"), (K["frage"], "pop")]
            return self.finale_klau, K["laenge"], sounds
        return self.finale, self.T["finale"], [(0.2, "whistle"), (0.7, "pop"), (1.3, "ding"), (self.T["frage"], "pop")]

    def loop(self, t):
        """Fade the last finale frame back into the first intro frame so the end flows into the start."""
        scene, dur, _ = self.final_scene()
        return Image.blend(scene(dur), self.intro(0.0), ease(t / self.T["loop"]))

    def timeline(self):
        T = self.T
        tl = [(self.intro, T["intro"], [(0.0, "whoosh"), (0.0, "pop")])]
        for i in range(len(self.rounds)):
            tl.append((lambda t, i=i: self.round_intro(i, t), T["runde"], [(0.1, "pfiff"), (0.15, "pop")]))
            side_sounds = [(0.1, "pop"), (0.3, "pop"), (0.5, "pop")]
            tl.append((lambda t, i=i: self.side(i, "a", t), T["seite"], side_sounds))
            tl.append((lambda t, i=i: self.wipe(i, t), T["wisch"], [(0.0, "whoosh")]))
            tl.append((lambda t, i=i: self.side(i, "b", t), T["seite"], side_sounds))
            tl.append((lambda t, i=i: self.verdict(i, t), T["urteil"], [(0.3, "pop"), (0.45, "ding" if self.rounds[i]["sieger"] else "pop")]))
        tl.append(self.final_scene())
        tl.append((self.loop, T["loop"], [(0.0, "whoosh")]))
        return tl


def main():
    theme_path = sys.argv[1]
    short = "--kurz" in sys.argv[2:]
    only_end = "--nur-ende" in sys.argv[2:]
    with open(theme_path, encoding="utf-8") as f:
        duel = Duel(json.load(f), short)
    tl = duel.timeline()
    if only_end:
        tl = tl[-2:]
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

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo"), exist_ok=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", os.path.splitext(os.path.basename(theme_path))[0] + ("_kurz" if short else "") + ("_ende" if only_end else "") + ".mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-i", wav.name, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    frames = 0
    for scene, dur, _ in tl:
        end = round((frames / FPS + dur) * FPS)
        start = frames
        while frames < end:
            ff.stdin.write(scene((frames - start) / FPS).convert("RGB").tobytes())
            frames += 1
    ff.stdin.close()
    ff.wait()
    os.unlink(wav.name)


if __name__ == "__main__":
    main()
