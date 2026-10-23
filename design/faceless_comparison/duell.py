"""Renders a ~75 s 1080x1920 round-based duel video for one theme file (needs Pillow, numpy and ffmpeg).

    python generate.py --chrome ...                       # PNGs first
    python duell.py themen/automatik_vs_manuell.json

Theme keys: "a" = blue side, "b" = red side, each {"name", "figur"? (character name, see charaktere.md), "kostuem"?};
"hook" = opening line;
"runden" = rounds {"titel", "a": side, "b": side, "sieger": "a" | "b" | null} where a side is
{"text", "bilder": [prop/element names], "zahl"?: {"label", "wert", "vor"?, "nach"?}, "messer"?: {"label", "wert" 0-100}};
"frage" = closing question; optional "ende" = {"sieger": pose, "verlierer": pose} for the final scene
(default jubelnd/traurig; a happy loser sways instead of leaning over) or {"pokal_klau": true}: the winner cheers
with the cup, the happy loser walks over, slaps his head, takes the cup and gets a yellow card; optional "kurz" = round indices for the short cut (--kurz). Every scene length is a
multiple of one beat at 120 BPM, and the last second fades back into the first frame so the video loops.
Referee Pip whistles every round, shows the loser a yellow card and calls the final score. A side may set "emotion".

Dialogue: three speakers. Each side's "text" is that bird's own line, shown in a speech bubble in its colour.
The referee says the hook, every round's "ansage" (default "Runde N: TITEL!"), the verdict (or a round's "urteil"), "ende.abpfiff" and the
closing question; with pokal_klau the thief says "ende.spruch". All lines with their start times are written to
demo/<theme>_skript.txt. With "ende": {"abwuergen": true, "spruch", "konter", "pip"} the winner cheers ("spruch"),
then stalls his car on the street while the other bird rolls past ("konter") and Pip comments ("pip").

Voices: if stimmen/<theme>/ holds one mp3 per line (sorted by name, in timeline order), each scene is stretched to
fit its spoken lines (rounded up to the beat), the voices are mixed into the soundtrack and the speaking bird's
beak opens with the loudness of its voice. "ansage_sprechen": false keeps the round titles silent (text only);
"teaser": "<text>" opens the video with 1.5 s of the stalling car before the hook.
"""

import glob
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

from demo_clip import (BLUE, FPS, H, OUT, PNG, RED, SIDES, SOUNDS, SR, W, clamp, ease, ease_out_back, font, img, pill,
                       pop, put, whistle)

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


def engine(kind):
    """Car sounds: 'rev' (revving), 'stall' (sputter and die), 'vorbei' (smooth drive-by)."""
    dur = {"rev": 1.0, "stall": 1.0, "vorbei": 2.5}[kind]
    tt = np.arange(int(SR * dur)) / SR
    rng = np.random.default_rng(5)
    if kind == "vorbei":
        f = 70 + 15 * tt / dur
        env = np.sin(np.pi * tt / dur) ** 2
        return 0.25 * env * (np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.4 + 0.3 * rng.standard_normal(len(tt)) * 0.3)
    f = 60 + (80 * tt / dur if kind == "rev" else 40 * (1 - tt / dur))
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.5 + 0.2 * rng.standard_normal(len(tt))
    if kind == "rev":
        return 0.3 * tone * np.minimum(1, tt / 0.1)
    gate = (np.sin(2 * np.pi * (6 + 4 * tt) * tt) > 0.2 * tt / dur).astype(float) * (1 - tt / dur)
    clunk = np.zeros(len(tt))
    k = np.arange(int(SR * 0.3)) / SR
    clunk[-len(k):] = np.sin(2 * np.pi * 70 * k) * np.exp(-k * 15)
    return 0.3 * tone * gate + 0.6 * clunk


SOUNDS = dict(SOUNDS, ding=ding(), pfiff=short_whistle(), klatsch=slap(),
              rev=engine("rev"), stall=engine("stall"), vorbei=engine("vorbei"))


def load_voice(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768


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


SPEAKERS = {"pip": ("SCHIEDSRICHTER", OUT), "a": ("BLAU", BLUE), "b": ("ROT", RED)}


def speech(text, speaker, tail=0.5, size=56, max_w=820):
    """Speech bubble with the speaker's colour as outline; `tail` = tail position across the bubble (0..1)."""
    f = font(size)
    lines = [""]
    for word in text.split():
        trial = (lines[-1] + " " + word).strip()
        if f.getlength(trial) > max_w and lines[-1]:
            lines.append(word)
        else:
            lines[-1] = trial
    lh = round(size * 1.25)
    w = round(max(f.getlength(line) for line in lines)) + 80
    h = lh * len(lines) + 56
    color = SPEAKERS[speaker][1]
    im = Image.new("RGBA", (w + 20, h + 60))
    d = ImageDraw.Draw(im)
    tx = 10 + max(50, min(w - 50, w * tail))
    d.polygon([(tx - 30, h + 4), (tx + 30, h + 4), (tx + 10 * (1 if tail > 0.5 else -1), h + 54)], fill="white", outline=color, width=10)
    d.rounded_rectangle([10, 10, w + 10, h + 10], radius=44, fill="white", outline=color, width=10)
    d.polygon([(tx - 20, h), (tx + 20, h), (tx + 6 * (1 if tail > 0.5 else -1), h + 36)], fill="white")
    for i, line in enumerate(lines):
        d.text((w / 2 + 10, 38 + lh * i + lh / 2), line, font=f, fill=OUT, anchor="mm")
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
        self.talk = {}
        self.hook = speech(th["hook"], "pip", 0.5, 72, 900)
        self.teaser_pill = pill(th["teaser"], OUT, 60) if th.get("teaser") else None
        self.question = speech(th["frage"], "pip", 0.5, 62, 880)
        end = th.get("ende", {})
        self.ansagen = [r.get("ansage", "Runde %d: %s!" % (i + 1, r["titel"].capitalize())) for i, r in enumerate(self.rounds)]
        self.urteile = [r.get("urteil") or ("Punkt für %s!" % th[r["sieger"]].get("figur", th[r["sieger"]]["name"].capitalize()) if r["sieger"] else "Unentschieden!")
                        for r in self.rounds]
        self.urteil_bubbles = [speech(u, "pip", 0.5, 52) for u in self.urteile]
        sa, sb = self.score[-1]
        winner = "a" if sa > sb else "b" if sb > sa else None
        self.abpfiff = end.get("abpfiff", "Abpfiff! %s gewinnt %d zu %d!" % (th[winner]["name"].capitalize(), max(sa, sb), min(sa, sb)) if winner else "Abpfiff! Unentschieden!")
        self.abpfiff_bubble = speech(self.abpfiff, "pip", 0.5, 52)
        self.thief = "b" if winner == "a" else "a"
        self.spruch = end.get("spruch")
        self.spruch_bubble = self.spruch and speech(self.spruch, self.thief, 0.75 if self.thief == "b" else 0.25, 60, 600)
        if end.get("abwuergen"):
            other = "b" if winner == "a" else "a"
            self.spruch_bubble = speech(end["spruch"], winner, 0.5, 56, 700)
            self.konter_bubble = speech(end["konter"], other, 0.5, 56, 600)
            self.pip_bubble = "pip" in end and speech(end["pip"], "pip", 0.2, 56, 560)
        self.vs = img("5_elemente/vs", 460)
        self.labels = {k: pill(th[k]["name"], SIDES[k][1]) for k in SIDES}
        self.texts = [{k: speech(r[k]["text"], k, 0.25 if k == "a" else 0.75, 56, 800) for k in SIDES} for r in self.rounds]
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

    def sprite(self, side, emotion):
        """Bird sprite; while that bird is speaking and its beak is up, the open-beak frame."""
        name = "2_figuren/%s_%s" % (SIDES[side][0], emotion)
        if self.talk.get(side) and os.path.exists(os.path.join(PNG, name + "_sprechen_freigestellt.png")):
            return name + "_sprechen_freigestellt"
        return name + "_freigestellt"

    def character(self, f, side, emotion, cx, bottom, t, height, react=None, angle=0.0, sy=None):
        if sy is None:
            sy = 1 + 0.015 * math.sin((t + (0.4 if side == "b" else 0)) * 2 * math.pi * 1.2)
        if react is not None and 0 <= t - react < 0.3:
            sy += 0.08 * math.sin((t - react) / 0.3 * math.pi)
        im = img(self.sprite(side, emotion), height).copy()
        costume = self.th[side].get("kostuem")
        if costume:
            im.alpha_composite(img("6_kostueme/" + costume, height))
        if angle:
            im = im.rotate(angle, resample=Image.BICUBIC)
        put(f, im, cx, bottom - im.height * sy / 2, 2 - sy, sy)

    def pip(self, f, cx, bottom, t, height, blowing=False, card=None):
        """Referee Pip; `card` = -1/1 holds a yellow card up on that side."""
        sy = 1 + 0.015 * math.sin((t + 0.2) * 2 * math.pi * 1.2) + (0.05 * math.sin(t * 40) if blowing else 0)
        base = "1_maskottchen/pip_frontal_freigestellt" if self.talk.get("pip") else "1_maskottchen/pip_frontal_zu_freigestellt"
        for name in (base, "6_kostueme/pip_schiedsrichter" + ("_pfeift" if blowing else "")):
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

    TEASER = 1.5

    def teaser(self, t):
        """Flash-forward of the stalling car so the viewer wants to see how it ends."""
        f = img("3_hintergruende/bg3_stadt_skyline_tag", H).copy()
        sa, sb = self.score[-1]
        win = "a" if sa > sb else "b"
        im = img("4_requisiten/auto_%s" % SIDES[win][2], 640)
        shake = 10 * math.sin(t * 70)
        bird = img(self.sprite(win, "ueberrascht"), 380)
        roof = 1624 + shake - 320 + 229
        put(f, bird, 710, roof - 170 - 380 * self.TOP[win] + 190)
        put(f, im, 700, 1624 + shake)
        d = ImageDraw.Draw(f)
        for i in range(6):
            k = (t * 1.5 + i / 6) % 1
            r = 30 + 60 * k
            g = round(150 + 80 * k)
            d.ellipse([360 - 80 * k - r, 1700 - 200 * k - r, 360 - 80 * k + r, 1700 - 200 * k + r], fill=(g, g, g))
        put(f, self.teaser_pill, W / 2, 560, 1 + 0.06 * math.sin(clamp(t / 0.3) * math.pi))
        return f

    def intro(self, t):
        """Hook at second 0: an optional teaser of the ending, then both birds, VS and the hook line."""
        if self.teaser_pill is not None:
            if t < self.TEASER:
                return self.teaser(t)
            t -= self.TEASER
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
        pop(f, self.urteil_bubbles[i], W / 2, 1180, t - 0.3)
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
        if 0.3 <= t < self.T["frage"]:
            pop(f, self.abpfiff_bubble, W / 2, 1150, t - 0.3)
        pop(f, self.question, W / 2, 560, t - self.T["frage"])
        return f

    # pokal_klau beats (s): winner cheers with the cup, loser walks over, slap, walks back, cheers, question
    KLAU = {"hin": 2.0, "klaps": 3.0, "zurueck": 3.5, "jubel": 4.5, "frage": 5.0, "laenge": 8.0}

    def finale_klau(self, t):
        """The winner cheers with the cup; the happy loser walks over, slaps the back of his head,
        takes the cup back to his side and cheers for real. Pip whistles the foul and shows him a yellow card."""
        f = self.stage()
        K = self.KLAU
        sa, sb = self.score[-1]
        holder = "a" if sa > sb else "b"
        thief = "b" if holder == "a" else "a"
        xs = {"a": 250, "b": 830}
        home, target = xs[thief], xs[holder]
        bottom, height = 1730, 760
        toward = 1 if target > home else -1
        reach = target - toward * 230
        hit = K["klaps"] + 0.15

        def walk(t0, t1, x0, x1):
            k = clamp((t - t0) / (t1 - t0))
            moving = 0 < k < 1
            step = abs(math.sin(math.pi * (t - t0) / 0.25)) if moving else 0.0
            tilt = (6 if int((t - t0) / 0.25) % 2 else -6) * toward if moving else 0.0
            return x0 + (x1 - x0) * ease(k), 30 * step, tilt

        self.pip(f, W / 2, 1570, t, 440, blowing=(0.2 <= t < 0.9) or (hit + 0.1 <= t < hit + 0.5),
                 card=-toward if hit + 0.5 <= t < K["frage"] + 1.5 else None)

        # holder: cheers and hops with the cup until the slap, then shocked, then sad and leaning over
        if t < hit:
            hop = abs(math.sin(math.pi * (t - 0.6) / 0.5)) if t >= 0.6 else 0.0
            hx, hy = target, 160 * hop
            self.character(f, holder, "jubelnd" if t >= 0.6 else "neutral", hx, bottom - hy, t, height,
                           react=0.6, sy=1 + 0.06 * hop - 0.06 * (1 - hop) ** 6 if t >= 0.6 else None)
        else:
            jolt = math.sin(clamp((t - hit) / 0.25) * math.pi)
            lean = ease((t - K["jubel"]) / 0.8) if t >= K["jubel"] else 0.0
            hx, hy = target + toward * 30 * jolt + toward * 40 * lean, 0.0
            self.character(f, holder, "ueberrascht" if t < K["jubel"] else "traurig", hx, bottom + 20 * lean, t, height,
                           react=hit, angle=-toward * 18 * jolt - toward * 18 * lean, sy=1 - 0.1 * jolt)
            if t < hit + 1.2:
                head_y = bottom - height * (1 - self.TOP[holder]) + 40
                d = ImageDraw.Draw(f)
                for i in range(4):
                    a = 2 * math.pi * (i / 4 + (t - hit) * 1.5)
                    sx, sy = target + 120 * math.cos(a), head_y + 30 * math.sin(a)
                    pts = [(sx + (22 if j % 2 == 0 else 10) * math.cos(math.pi / 5 * j - math.pi / 2),
                            sy + (22 if j % 2 == 0 else 10) * math.sin(math.pi / 5 * j - math.pi / 2)) for j in range(10)]
                    d.polygon(pts, fill=YELLOW, outline=OUT, width=4)

        # thief: happy, walks over, slaps, walks back with the cup, then cheers
        if t < K["hin"]:
            sway = 7 * math.sin(2 * math.pi * (t - 0.6)) * ease((t - 0.6) / 0.3) if t >= 0.6 else 0.0
            tx, ty, ta, pose = home, 0.0, sway, "gluecklich" if t >= 0.6 else "neutral"
        elif t < K["klaps"]:
            (tx, ty, ta), pose = walk(K["hin"], K["klaps"] - 0.1, home, reach), "stolz"
        elif t < K["zurueck"]:
            swing = math.sin(clamp((t - K["klaps"]) / 0.3) * math.pi)
            tx, ty, ta, pose = reach + toward * 40 * swing, 0.0, -toward * 22 * swing, "ueberrascht"
        elif t < K["jubel"]:
            (tx, ty, ta), pose = walk(K["zurueck"], K["jubel"] - 0.1, reach, home), "stolz"
        else:
            hop = abs(math.sin(math.pi * (t - K["jubel"]) / 0.5))
            tx, ty, ta, pose = home, 160 * hop, 0.0, "jubelnd"
        self.character(f, thief, pose, tx, bottom - ty, t, height, react=0.6 if t < K["hin"] else None,
                       angle=ta, sy=1.0 if ty else None)

        # the cup: rides on the holder, flies to the thief on the slap, then rides on the thief
        cup = img("4_requisiten/pokal_%s" % SIDES[holder][2], 240)
        top_h = bottom - hy - height * (1 - self.TOP[holder]) - 110
        top_t = bottom - ty - height * (1 - self.TOP[thief]) - 110
        if t < hit:
            pop(f, cup, hx, top_h, t - 0.7)
        else:
            k = ease(clamp((t - hit) / 0.45))
            put(f, cup.rotate(360 * k * toward, resample=Image.BICUBIC), target + (tx - target) * k,
                top_h + (top_t - top_h) * k - 260 * math.sin(k * math.pi))
        for t0, cx, cy in ((0.7, hx, top_h), (K["jubel"], tx, top_t)):
            if t0 < t < t0 + 1.4:
                d = ImageDraw.Draw(f)
                k = ease((t - t0) / 1.4)
                for a, dist, col, r in self.confetti:
                    x = cx + math.cos(a) * dist * k
                    y = cy + math.sin(a) * dist * k * 0.8 + 700 * k * k
                    d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=OUT, width=3)
        put(f, self.board(sa, sb, 1.0), W / 2, 260, 1 + 0.12 * math.sin(clamp((t - 0.3) / 0.3) * math.pi))
        if 0.3 <= t < K["hin"]:
            pop(f, self.abpfiff_bubble, W / 2, 1020, t - 0.3)
        if self.spruch_bubble and hit + 0.5 <= t < K["frage"]:
            pop(f, self.spruch_bubble, min(max(tx, 360), W - 360), 900 - ty, t - hit - 0.5)
        pop(f, self.question, W / 2, 560, t - K["frage"])
        return f

    def finale_abwuergen(self, t, S):
        """Winner cheers with the cup, then on the street his car stalls while the other bird rolls past."""
        sa, sb = self.score[-1]
        win = "a" if sa > sb else "b"
        other = "b" if win == "a" else "a"
        if t < S["strasse"]:
            f = self.stage()
            go = t >= 0.6
            hop = abs(math.sin(math.pi * (t - 0.6) / 0.5)) if go else 0.0
            xs = {"a": 250, "b": 830}
            self.character(f, win, "jubelnd" if go else "neutral", xs[win], 1730 - 160 * hop, t, 760, react=0.6,
                           sy=1 + 0.06 * hop - 0.06 * (1 - hop) ** 6 if go else None)
            self.character(f, other, "genervt" if go else "neutral", xs[other], 1730, t, 760, react=0.6)
            top = 1730 - 160 * hop - 760 * (1 - self.TOP[win])
            pop(f, img("4_requisiten/pokal_%s" % SIDES[win][2], 240), xs[win], top - 110, t - 0.7)
            self.pip(f, W / 2, 1800, t, 480, blowing=0.2 <= t < 0.9)
            put(f, self.board(sa, sb, 1.0), W / 2, 260, 1 + 0.12 * math.sin(clamp((t - 0.3) / 0.3) * math.pi))
            if 0.3 <= t < S["spruch"]:
                pop(f, self.abpfiff_bubble, W / 2, 1000, t - 0.3)
            if S["spruch"] <= t:
                pop(f, self.spruch_bubble, min(max(xs[win], 380), W - 380), 900, t - S["spruch"])
            return f
        # street scene
        f = img("3_hintergruende/bg3_stadt_skyline_tag", H).copy()
        ts = t - S["strasse"]
        put(f, self.board(sa, sb, 1.0), W / 2, 260)

        def car(side, cx, shake, emotion):
            im = img("4_requisiten/auto_%s" % SIDES[side][2], 640)
            cy = 1624 + shake
            roof = cy - 320 + 229
            bird_h = 380 if side == "b" else 340
            bird = img(self.sprite(side, emotion), bird_h)
            vis_top = roof - (170 if side == "b" else 230)
            put(f, bird, cx + 10, vis_top - bird_h * self.TOP[side] + bird_h / 2)
            put(f, im, cx, cy)
            return roof

        stalled = ts >= S["aus"] - S["strasse"]
        rumble = S["rev"] - S["strasse"] <= ts < S["aus"] - S["strasse"]
        shake = 10 * math.sin(ts * 70) if rumble else 0.0
        car(win, 700, shake, "genervt" if stalled else "jubelnd")
        if S["stall"] - S["strasse"] <= ts < S["aus"] - S["strasse"] + 0.6:
            d = ImageDraw.Draw(f)
            for i in range(6):
                k = ((ts - (S["stall"] - S["strasse"])) * 1.5 + i / 6) % 1
                r = 30 + 60 * k
                gray = round(150 + 80 * k)
                d.ellipse([360 - 80 * k - r, 1700 - 200 * k - r, 360 - 80 * k + r, 1700 - 200 * k + r], fill=(gray, gray, gray))
        tc = ts - (S["konter_auto"] - S["strasse"])
        if tc > 0:
            bx = -400 + (W + 800) * clamp(tc / 2.5)
            roof_b = car(other, bx, 0.0, "stolz")
            if S["konter"] <= t < S["pip_satz"] and self.konter_bubble:
                pop(f, self.konter_bubble, min(max(bx, 380), W - 380), roof_b - 260, t - S["konter"])
        if t >= S["pip_satz"]:
            self.pip(f, 170, 1980, t, 460)
            if self.pip_bubble and t < S["frage"]:
                pop(f, self.pip_bubble, 380, 1260, t - S["pip_satz"])
        if t >= S["frage"]:
            pop(f, self.question, W / 2, 620, t - S["frage"])
        return f

    def abwuergen_schedule(self, voice):
        """Start times inside the final scene, spaced by the spoken lines (or fixed reading times without voices)."""
        has_pip = "pip" in self.th["ende"]
        d = list(voice) if voice else [2.0] * (5 if has_pip else 4)
        if not has_pip:
            d.insert(3, -0.3)
        S = {"spruch": 0.3 + d[0] + 0.2}
        S["strasse"] = S["spruch"] + d[1] + 0.3
        S["rev"] = S["strasse"] + 0.3
        S["stall"] = S["rev"] + 1.0
        S["aus"] = S["stall"] + 1.0
        S["konter_auto"] = S["aus"] + 0.5
        S["konter"] = S["konter_auto"] + 0.6
        S["pip_satz"] = max(S["konter_auto"] + 2.5, S["konter"] + d[2] + 0.3)
        S["frage"] = S["pip_satz"] + d[3] + 0.3
        S["ende"] = math.ceil((S["frage"] + d[4] + 0.8) * 2) / 2
        return S

    def final_scene(self, voice=None):
        """(scene, duration, sounds, lines) for the last scene; `voice` = durations of its spoken lines."""
        end = self.th.get("ende", {})
        if end.get("abwuergen"):
            S = self.abwuergen_schedule(voice)
            sounds = [(0.2, "whistle"), (0.7, "ding"), (S["strasse"], "whoosh"), (S["rev"], "rev"), (S["stall"], "stall"),
                      (S["konter_auto"], "vorbei"), (S["frage"], "pop")]
            sa, sb = self.score[-1]
            win = "a" if sa > sb else "b"
            lines = [(0.3, "pip", self.abpfiff), (S["spruch"], win, end["spruch"]),
                     (S["konter"], "b" if win == "a" else "a", end["konter"])]
            if "pip" in end:
                lines.append((S["pip_satz"], "pip", end["pip"]))
            lines.append((S["frage"], "pip", self.th["frage"]))
            return (lambda t: self.finale_abwuergen(t, S)), S["ende"], sounds, lines
        if end.get("pokal_klau"):
            K = self.KLAU
            hit = K["klaps"] + 0.15
            sounds = [(0.2, "whistle"), (0.7, "ding"), (K["hin"], "whoosh"), (hit, "klatsch"),
                      (K["klaps"] + 0.25, "pfiff"), (K["klaps"] + 0.2, "whoosh"), (K["jubel"], "ding"), (K["frage"], "pop")]
            lines = [(0.3, "pip", self.abpfiff)] + ([(hit + 0.5, self.thief, self.spruch)] if self.spruch else []) + [(K["frage"], "pip", self.th["frage"])]
            return self.finale_klau, K["laenge"], sounds, lines
        return (self.finale, self.T["finale"], [(0.2, "whistle"), (0.7, "pop"), (1.3, "ding"), (self.T["frage"], "pop")],
                [(0.3, "pip", self.abpfiff), (self.T["frage"], "pip", self.th["frage"])])

    def loop(self, t):
        """Fade the last finale frame back into the first intro frame so the end flows into the start."""
        scene, dur, _, _ = self.last
        return Image.blend(scene(dur), self.intro(0.0), ease(t / self.T["loop"]))

    def timeline(self, voices=None):
        """(scene, duration, [(offset, sound)], [(offset, speaker, line)]); `voices` = one sample array per line."""
        T = self.T
        intro_len = T["intro"] + (self.TEASER if self.teaser_pill is not None else 0)
        tl = [(self.intro, intro_len, [(0.0, "rev"), (self.TEASER if self.teaser_pill is not None else 0.0, "whoosh")],
               [(0.0, "pip", self.th["hook"])])]
        for i, r in enumerate(self.rounds):
            spoken = [(0.5, "pip", self.ansagen[i])] if self.th.get("ansage_sprechen", True) else []
            tl.append((lambda t, i=i: self.round_intro(i, t), T["runde"] if spoken else 1.0, [(0.1, "pfiff"), (0.15, "pop")], spoken))
            side_sounds = [(0.1, "pop"), (0.3, "pop"), (0.5, "pop")]
            tl.append((lambda t, i=i: self.side(i, "a", t), T["seite"], side_sounds, [(0.1, "a", r["a"]["text"])]))
            tl.append((lambda t, i=i: self.wipe(i, t), T["wisch"], [(0.0, "whoosh")], []))
            tl.append((lambda t, i=i: self.side(i, "b", t), T["seite"], side_sounds, [(0.1, "b", r["b"]["text"])]))
            tl.append((lambda t, i=i: self.verdict(i, t), T["urteil"], [(0.3, "pop"), (0.45, "ding" if r["sieger"] else "pop")],
                       [(0.3, "pip", self.urteile[i])]))
        n_before = sum(len(x[3]) for x in tl)
        final_voice = [len(v) / SR for v in voices[n_before:]] if voices else None
        self.last = self.final_scene(final_voice)
        tl.append(self.last)
        if voices:
            # stretch every scene so its spoken lines fit, rounded up to the beat
            i = 0
            for k, (scene, dur, sounds, lines) in enumerate(tl):
                need = max([off + len(voices[i + j]) / SR + 0.3 for j, (off, _, _) in enumerate(lines)] + [dur])
                tl[k] = (scene, math.ceil(need * 2) / 2, sounds, lines)
                i += len(lines)
            self.last = tl[-1]
        tl.append((self.loop, T["loop"], [(0.0, "whoosh")], []))
        return tl


def main():
    theme_path = sys.argv[1]
    short = "--kurz" in sys.argv[2:]
    only_end = "--nur-ende" in sys.argv[2:]
    with open(theme_path, encoding="utf-8") as f:
        duel = Duel(json.load(f), short)
    name = os.path.splitext(os.path.basename(theme_path))[0]
    voice_files = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stimmen", name, "*.mp3")))
    voices = [load_voice(p) for p in voice_files] if voice_files and not short else None
    tl = duel.timeline(voices)
    n_lines = sum(len(x[3]) for x in tl)
    if voices and len(voices) != n_lines:
        sys.exit("stimmen/%s has %d files, the script has %d lines" % (name, len(voices), n_lines))
    if only_end:
        tl = tl[-2:]
    audio = np.zeros(int(SR * (sum(d for _, d, _, _ in tl) + 1)))
    script = []
    t0 = 0.0
    li = 0
    for _, dur, sounds, lines in tl:
        for off, kind in sounds:
            s = int(SR * (t0 + off))
            audio[s:s + len(SOUNDS[kind])] += SOUNDS[kind] * (0.5 if voices else 1.0)
        for off, _, _ in lines:
            if voices:
                s = int(SR * (t0 + off))
                audio[s:s + len(voices[li])] += voices[li]
            li += 1
        script += ["%02d:%04.1f  %-15s %s" % ((t0 + off) // 60, (t0 + off) % 60, SPEAKERS[who][0] + ":", line) for off, who, line in lines]
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
    with open(out[:-4] + "_skript.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(script) + "\n")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-i", wav.name, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    # who is talking in each video frame: the beak is open while that voice is loud
    talking = {}
    if voices:
        t0, li = 0.0, 0
        for _, dur, _, lines in tl:
            for off, who, _ in lines:
                v = voices[li]
                start = t0 + off
                for n in range(int(len(v) / SR * FPS)):
                    chunk = v[int(n * SR / FPS):int((n + 1) * SR / FPS)]
                    if chunk.size and np.sqrt(np.mean(chunk ** 2)) > 0.04:
                        talking.setdefault(round(start * FPS) + n, set()).add(who)
                li += 1
            t0 += dur
    frames = 0
    for scene, dur, _, _ in tl:
        end = round((frames / FPS + dur) * FPS)
        start = frames
        while frames < end:
            duel.talk = {k: True for k in talking.get(frames, ())}
            ff.stdin.write(scene((frames - start) / FPS).convert("RGB").tobytes())
            frames += 1
    ff.stdin.close()
    ff.wait()
    os.unlink(wav.name)


if __name__ == "__main__":
    main()
