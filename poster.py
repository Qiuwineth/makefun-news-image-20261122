#!/usr/bin/env python3
"""THE WORLD ON SUNDAY - 22 November 2026. One day, one picture.

A dense newspaper front page rendered entirely with the Python standard
library: own rasterizer, own stroke font, own PNG encoder. No Pillow, no
system fonts, no network. Writes entry.png to $MAKEFUN_OUTPUT_DIR when
set, otherwise next to this script. Fully deterministic.
"""

import math
import os
import sys
import zlib

# ---------------------------------------------------------------- canvas
W = 1024
H = 1024
SS = 2                      # supersampling factor
W2 = W * SS
H2 = H * SS
FB = bytearray(W2 * H2 * 3)

PAPER = (246, 239, 221)
INK = (20, 17, 12)
RED = (158, 27, 27)
BLUE = (29, 58, 110)
GOLD = (176, 132, 28)
GREY = (104, 96, 80)
CREAM = (246, 239, 221)
BLACK = (12, 10, 8)


def _set(x, y, c):
    if 0 <= x < W2 and 0 <= y < H2:
        i = (y * W2 + x) * 3
        FB[i] = c[0]
        FB[i + 1] = c[1]
        FB[i + 2] = c[2]


def fill_rect(x, y, w, h, c):
    """Filled rectangle, coordinates in final pixels (floats ok)."""
    x0 = int(round(x * SS))
    y0 = int(round(y * SS))
    x1 = int(round((x + w) * SS))
    y1 = int(round((y + h) * SS))
    if x1 <= 0 or y1 <= 0 or x0 >= W2 or y0 >= H2:
        return
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W2, x1)
    y1 = min(H2, y1)
    row = bytes(c) * (x1 - x0)
    n = len(row)
    for yy in range(y0, y1):
        i = (yy * W2 + x0) * 3
        FB[i:i + n] = row


def hline(x0, x1, y, c):
    fill_rect(x0, y, x1 - x0, 1.0 / SS, c)


_DISKS = {}


def _disk(r):
    if r not in _DISKS:
        pts = []
        rr = r * r
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= rr:
                    pts.append((dx, dy))
        _DISKS[r] = pts
    return _DISKS[r]


def line(x0, y0, x1, y1, c, thick=1.0):
    """Thick line, coordinates in final pixels."""
    ax, ay = x0 * SS, y0 * SS
    bx, by = x1 * SS, y1 * SS
    r = max(0, int(round(thick * SS / 2.0)))
    pts = _disk(r)
    steps = int(max(abs(bx - ax), abs(by - ay))) + 1
    for i in range(steps + 1):
        t = i / steps
        cx = int(round(ax + (bx - ax) * t))
        cy = int(round(ay + (by - ay) * t))
        for dx, dy in pts:
            _set(cx + dx, cy + dy, c)


def polyline(pts, c, thick=1.0, close=False):
    pp = list(pts)
    if close and pp:
        pp.append(pp[0])
    for i in range(len(pp) - 1):
        line(pp[i][0], pp[i][1], pp[i + 1][0], pp[i + 1][1], c, thick)


def poly_fill(pts, c):
    """Scanline polygon fill, coordinates in final pixels."""
    pp = [(x * SS, y * SS) for x, y in pts]
    ys = [p[1] for p in pp]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H2 - 1, int(math.ceil(max(ys))))
    n = len(pp)
    for yy in range(y0, y1 + 1):
        yc = yy + 0.5
        xs = []
        for i in range(n):
            xa, ya = pp[i]
            xb, yb = pp[(i + 1) % n]
            if (ya <= yc < yb) or (yb <= yc < ya):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(math.floor(xs[k]))
            xb = int(math.ceil(xs[k + 1]))
            xa = max(0, xa)
            xb = min(W2, xb)
            if xb > xa:
                row = bytes(c) * (xb - xa)
                i = (yy * W2 + xa) * 3
                FB[i:i + len(row)] = row


def circle_fill(cx, cy, r, c):
    cx2, cy2, r2 = cx * SS, cy * SS, r * SS
    y0 = max(0, int(cy2 - r2 - 1))
    y1 = min(H2 - 1, int(cy2 + r2 + 1))
    for yy in range(y0, y1 + 1):
        d = math.sqrt(max(0.0, r2 * r2 - (yy - cy2) ** 2))
        xa = max(0, int(cx2 - d))
        xb = min(W2, int(cx2 + d))
        if xb > xa:
            row = bytes(c) * (xb - xa)
            i = (yy * W2 + xa) * 3
            FB[i:i + len(row)] = row


def ellipse_fill(cx, cy, rx, ry, c):
    cx2, cy2, rx2, ry2 = cx * SS, cy * SS, rx * SS, ry * SS
    y0 = max(0, int(cy2 - ry2 - 1))
    y1 = min(H2 - 1, int(cy2 + ry2 + 1))
    for yy in range(y0, y1 + 1):
        t = (yy - cy2) / ry2
        d = rx2 * math.sqrt(max(0.0, 1.0 - t * t))
        xa = max(0, int(cx2 - d))
        xb = min(W2, int(cx2 + d))
        if xb > xa:
            row = bytes(c) * (xb - xa)
            i = (yy * W2 + xa) * 3
            FB[i:i + len(row)] = row


def arc(cx, cy, rx, ry, a0, a1, c, thick=1.0, steps=None):
    if steps is None:
        steps = max(8, int(abs(a1 - a0) * max(rx, ry) * SS / 3))
    prev = None
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        p = (cx + rx * math.cos(a), cy + ry * math.sin(a))
        if prev is not None:
            line(prev[0], prev[1], p[0], p[1], c, thick)
        prev = p


def rect_outline(x, y, w, h, c, thick=1.0):
    line(x, y, x + w, y, c, thick)
    line(x + w, y, x + w, y + h, c, thick)
    line(x + w, y + h, x, y + h, c, thick)
    line(x, y + h, x, y, c, thick)


def gradient_v(x, y, w, h, c_top, c_bot):
    rows = int(round(h))
    for i in range(rows):
        t = i / max(1, rows - 1)
        c = tuple(int(round(c_top[k] + (c_bot[k] - c_top[k]) * t))
                  for k in range(3))
        fill_rect(x, y + i, w, 1.0, c)


class LCG:
    """Deterministic pseudo-random source (fixed seed => same picture)."""

    def __init__(self, seed):
        self.s = seed & 0x7FFFFFFF

    def next(self):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return self.s

    def rand(self):
        return self.next() / 2147483648.0

    def range(self, a, b):
        return a + (b - a) * self.rand()


# ------------------------------------------------------------------ font
# Glyphs live on a grid: x in [0..4] typical, cap height y 0..7 with the
# baseline at y=7. Lowercase x-height is y 2.6..7, ascenders reach y 0.6,
# descenders reach y 9.4. Each entry: (advance_units, "stroke; stroke")
# where a stroke is a space separated list of "x,y" points.
FONT_RAW = {
    " ": (2.8, ""),
    "A": (5.2, "0,7 2,0 4,7; 0.8,4.5 3.2,4.5"),
    "B": (5.2, "0,0 0,7; 0,0 2.6,0 3.4,0.8 3.4,2.4 2.6,3.2 0,3.2; "
               "0,3.2 2.8,3.2 3.6,4 3.6,6 2.8,7 0,7"),
    "C": (5.0, "3.8,1.2 2.8,0.2 1.2,0.2 0.2,1.2 0.2,5.8 1.2,6.8 2.8,6.8 "
               "3.8,5.8"),
    "D": (5.2, "0,0 0,7; 0,0 2.4,0 3.8,1.6 3.8,5.4 2.4,7 0,7"),
    "E": (4.8, "4,0 0,0 0,7 4,7; 0,3.5 3.2,3.5"),
    "F": (4.8, "4,0 0,0 0,7; 0,3.5 3.2,3.5"),
    "G": (5.2, "3.8,1.2 2.8,0.2 1.2,0.2 0.2,1.2 0.2,5.8 1.2,6.8 2.8,6.8 "
               "3.9,5.6 3.9,3.8 2.6,3.8"),
    "H": (5.2, "0,0 0,7; 4,0 4,7; 0,3.5 4,3.5"),
    "I": (3.4, "0.6,0 3,0; 1.8,0 1.8,7; 0.6,7 3,7"),
    "J": (4.6, "0.4,0 3.6,0; 2.6,0 2.6,5.6 1.8,6.8 0.5,6.8 0.1,5.8"),
    "K": (5.2, "0,0 0,7; 3.9,0 0.3,3.6; 0.9,2.8 4,7"),
    "L": (4.8, "0,0 0,7 4,7"),
    "M": (6.0, "0,7 0,0 2.2,3 4.4,0 4.4,7"),
    "N": (5.4, "0,7 0,0 4.2,7 4.2,0"),
    "O": (5.4, "1.3,0.2 2.9,0.2 3.9,1.4 3.9,5.6 2.9,6.8 1.3,6.8 0.3,5.6 "
               "0.3,1.4 1.3,0.2"),
    "P": (5.0, "0,7 0,0 2.8,0 3.8,1 3.8,2.8 2.8,3.8 0,3.8"),
    "Q": (5.4, "1.3,0.2 2.9,0.2 3.9,1.4 3.9,5.6 2.9,6.8 1.3,6.8 0.3,5.6 "
               "0.3,1.4 1.3,0.2; 2.6,5.2 4.3,7.4"),
    "R": (5.2, "0,7 0,0 2.8,0 3.8,1 3.8,2.8 2.8,3.8 0,3.8; 2.3,3.8 4,7"),
    "S": (4.8, "3.8,1.2 2.8,0.2 1.2,0.3 0.3,1.2 0.5,2.6 3.3,3.9 3.7,5.4 "
               "2.8,6.7 1.2,6.8 0.2,5.8"),
    "T": (5.0, "0,0 4.2,0; 2.1,0 2.1,7"),
    "U": (5.2, "0,0 0,5.4 1,6.8 3.2,6.8 4.2,5.4 4.2,0"),
    "V": (5.2, "0,0 2.1,7 4.2,0"),
    "W": (6.6, "0,0 0.9,7 2.2,3 3.4,7 4.6,0"),
    "X": (5.0, "0,0 4,7; 4,0 0,7"),
    "Y": (5.2, "0,0 2.1,3.2 4.2,0; 2.1,3.2 2.1,7"),
    "Z": (5.0, "0,0 4.2,0 0,7 4.2,7"),
    "a": (4.6, "3.4,3.4 2.6,2.7 1.2,2.7 0.4,3.4 0.4,6.2 1.2,6.9 2.6,6.9 "
               "3.4,6.2; 3.4,2.8 3.4,7"),
    "b": (4.6, "0.4,0.6 0.4,7; 0.4,3.6 1.2,2.8 2.8,2.8 3.6,3.6 3.6,6.1 "
               "2.8,6.9 1.2,6.9 0.4,6.1"),
    "c": (4.4, "3.4,3.6 2.6,2.8 1.3,2.8 0.4,3.6 0.4,6.1 1.3,6.9 2.6,6.9 "
               "3.4,6.1"),
    "d": (4.6, "3.6,0.6 3.6,7; 3.6,3.6 2.8,2.8 1.2,2.8 0.4,3.6 0.4,6.1 "
               "1.2,6.9 2.8,6.9 3.6,6.1"),
    "e": (4.6, "0.4,4.6 3.6,4.6 3.6,3.8 2.8,2.8 1.3,2.8 0.4,3.7 0.4,6.1 "
               "1.3,6.9 2.7,6.9 3.5,6.2"),
    "f": (3.8, "3.2,1 2.4,0.6 1.4,0.8 1.2,2 1.2,7; 0.2,3 2.6,3"),
    "g": (4.6, "3.4,3.4 2.6,2.7 1.2,2.7 0.4,3.4 0.4,6.2 1.2,6.9 2.6,6.9 "
               "3.4,6.2; 3.4,2.8 3.4,8 2.8,9.2 1.2,9.3 0.4,8.6"),
    "h": (4.8, "0.4,0.6 0.4,7; 0.4,4 1.2,3 2.7,3 3.5,4 3.5,7"),
    "i": (2.6, "1.1,2.8 1.1,7; 1.1,0.9 1.1,1.3"),
    "j": (2.8, "1.7,2.8 1.7,8.2 0.9,9.3 0,9.1; 1.7,0.9 1.7,1.3"),
    "k": (4.6, "0.4,0.6 0.4,7; 3.4,2.8 0.6,5; 1.4,4.2 3.6,7"),
    "l": (2.6, "1.1,0.6 1.1,7"),
    "m": (7.0, "0.3,2.8 0.3,7; 0.3,4 1,3 2.2,3 3,4 3,7; 3,4 3.8,3 5,3 "
               "5.8,4 5.8,7"),
    "n": (4.8, "0.4,2.8 0.4,7; 0.4,4 1.2,3 2.8,3 3.6,4 3.6,7"),
    "o": (4.6, "1.3,2.8 2.7,2.8 3.6,3.7 3.6,6.1 2.7,6.9 1.3,6.9 0.4,6.1 "
               "0.4,3.7 1.3,2.8"),
    "p": (4.6, "0.4,2.8 0.4,9.4; 0.4,3.6 1.2,2.8 2.8,2.8 3.6,3.6 3.6,6.1 "
               "2.8,6.9 1.2,6.9 0.4,6.1"),
    "q": (4.6, "3.6,2.8 3.6,9.4; 3.6,3.6 2.8,2.8 1.2,2.8 0.4,3.6 0.4,6.1 "
               "1.2,6.9 2.8,6.9 3.6,6.1"),
    "r": (3.8, "0.4,2.8 0.4,7; 0.4,4.2 1.2,3 2.6,2.9 3.4,3.4"),
    "s": (4.2, "3.4,3.4 2.6,2.8 1.2,2.9 0.5,3.6 0.8,4.6 3,5.4 3.5,6.2 "
               "2.7,6.9 1.2,6.9 0.4,6.3"),
    "t": (3.8, "1.9,1 1.9,6.2 2.6,6.9 3.4,6.8; 0.4,3 3.4,3"),
    "u": (4.8, "0.4,2.8 0.4,6.1 1.2,6.9 2.7,6.9 3.5,6.1; 3.5,2.8 3.5,7"),
    "v": (4.6, "0.3,2.8 2,7 3.7,2.8"),
    "w": (6.6, "0.2,2.8 0.9,7 2,4.1 3.1,7 4.2,4.1 5.3,7 6,2.8"),
    "x": (4.6, "0.4,2.8 3.6,7; 3.6,2.8 0.4,7"),
    "y": (4.6, "0.3,2.8 2,5.4; 3.7,2.8 2,5.4 1.5,8.6 0.6,9.3"),
    "z": (4.4, "0.4,2.8 3.6,2.8 0.4,7 3.6,7"),
    "0": (4.8, "1.3,0.3 2.7,0.3 3.6,1.4 3.6,5.6 2.7,6.7 1.3,6.7 0.4,5.6 "
               "0.4,1.4 1.3,0.3"),
    "1": (4.2, "1.2,1.6 2.4,0.4 2.4,7; 1,7 3.4,7"),
    "2": (4.8, "0.4,1.4 1.2,0.3 2.8,0.3 3.6,1.4 3.4,3 0.4,7 3.8,7"),
    "3": (4.8, "0.4,1.2 1.4,0.3 2.8,0.4 3.4,1.6 2.8,3 1.6,3.3; 1.6,3.3 "
               "2.9,3.6 3.6,4.8 3,6.4 1.4,6.8 0.3,5.8"),
    "4": (5.0, "2.9,7 2.9,0 0.2,5 4.1,5"),
    "5": (4.8, "3.7,0 0.6,0 0.5,3.2 1.4,2.7 2.9,2.8 3.7,4 3.6,5.8 2.7,6.8 "
               "1.2,6.7 0.3,5.7"),
    "6": (4.8, "3.4,1.2 2.4,0.3 1.2,0.6 0.4,2 0.4,5.6 1.2,6.7 2.8,6.7 "
               "3.6,5.7 3.6,4 2.8,3.1 1.2,3.1 0.4,4"),
    "7": (4.8, "0.3,0 3.8,0 1.6,7"),
    "8": (4.8, "1.4,0.3 2.6,0.3 3.3,1 2.9,2.4 1.1,2.4 0.7,1 1.4,0.3; "
               "1.1,2.4 2.9,2.4 3.7,3.6 3.6,5.8 2.7,6.8 1.3,6.8 0.4,5.8 "
               "0.3,3.6 1.1,2.4"),
    "9": (4.8, "0.6,5.8 1.6,6.7 2.8,6.4 3.6,5 3.6,1.4 2.8,0.3 1.2,0.3 "
               "0.4,1 0.4,3 1.2,3.9 2.8,3.9 3.6,3"),
    ".": (2.4, "1,6.5 1.2,6.9"),
    ",": (2.4, "1.1,6.3 0.8,7.6"),
    ":": (2.4, "1,2.4 1.2,2.8; 1,6.1 1.2,6.5"),
    ";": (2.4, "1,2.4 1.2,2.8; 1.1,6.1 0.8,7.4"),
    "'": (2.2, "1.2,0.5 1,1.8"),
    '"': (3.2, "0.7,0.5 0.5,1.8; 2.1,0.5 1.9,1.8"),
    "-": (3.6, "0.6,4 3,4"),
    "—": (5.6, "0.2,4 5.2,4"),
    "!": (2.4, "1.1,0.4 1.1,5.2; 1,6.5 1.2,6.9"),
    "?": (4.6, "0.5,1.4 1.3,0.3 2.7,0.3 3.5,1.3 3.2,2.6 2,3.4 2,4.6; "
               "1.9,6.5 2.1,6.9"),
    "(": (3.4, "2.8,0.4 1.7,1.6 1.3,3.5 1.7,5.4 2.8,6.6"),
    ")": (3.4, "0.6,0.4 1.7,1.6 2.1,3.5 1.7,5.4 0.6,6.6"),
    "/": (4.2, "0.6,7 3.4,0"),
    "%": (5.4, "0.8,7 3.6,0; 0.3,1.1 0.8,0.4 1.4,0.6 1.5,1.3 1,1.9 "
               "0.4,1.7 0.3,1.1; 3,5.9 3.5,5.2 4.1,5.4 4.2,6.1 3.7,6.7 "
               "3.1,6.5 3,5.9"),
    "$": (4.8, "3.8,1.2 2.8,0.2 1.2,0.3 0.3,1.2 0.5,2.6 3.3,3.9 3.7,5.4 "
               "2.8,6.7 1.2,6.8 0.2,5.8; 2,-0.4 2,7.4"),
    "&": (5.2, "3.6,7 1,2.6 1.6,0.6 2.8,0.5 2.6,2.2 0.6,4.4 0.8,6.4 "
               "2.2,6.9 3.4,5.6"),
    "+": (4.6, "2.1,1.8 2.1,5.6; 0.5,3.7 3.7,3.7"),
    "=": (4.6, "0.5,2.7 3.7,2.7; 0.5,4.6 3.7,4.6"),
    "·": (2.2, "1,3.8 1.2,4.2"),
    "°": (3.4, "1.1,0.9 1.6,0.2 2.3,0.4 2.4,1.1 1.9,1.7 1.3,1.6 1.1,0.9"),
    "…": (5.4, "0.5,6.5 0.7,6.9; 2.4,6.5 2.6,6.9; 4.3,6.5 4.5,6.9"),
    "*": (4.0, "1.9,1.6 1.9,5.4; 0.5,2.4 3.3,4.6; 3.3,2.4 0.5,4.6"),
}

GLYPHS = {}
for _ch, (_adv, _spec) in FONT_RAW.items():
    _strokes = []
    if _spec:
        for _s in _spec.split(";"):
            _pts = []
            for _p in _s.split():
                _a, _b = _p.split(",")
                _pts.append((float(_a), float(_b)))
            _strokes.append(_pts)
    GLYPHS[_ch] = (_adv, _strokes)

_NORMALIZE = {"’": "'", "‘": "'", "“": '"', "”": '"',
              "–": "-", "―": "—", "…": "…"}


def _glyph(ch):
    ch = _NORMALIZE.get(ch, ch)
    return GLYPHS.get(ch, GLYPHS[" "])


def text_width(text, size, tracking=0.0):
    unit = size / 7.0
    w = 0.0
    for ch in text:
        w += _glyph(ch)[0] * unit + tracking
    return w - (tracking if text else 0.0)


def draw_text(x, y, text, size, color, weight=1.0, align="l",
              tracking=0.0, angle=0.0):
    """Draw text; (x, y) is the top-left of the cap-height box.

    align: 'l', 'c' or 'r' relative to x. angle rotates around (x, y).
    Returns the drawn width in final pixels.
    """
    unit = size / 7.0
    total = text_width(text, size, tracking)
    if align == "c":
        x -= total / 2.0
    elif align == "r":
        x -= total
    thick = max(0.75, size * 0.115 * weight)
    ca = math.cos(angle)
    sa = math.sin(angle)
    ox, oy = x, y
    cx = x
    for ch in text:
        adv, strokes = _glyph(ch)
        for stroke in strokes:
            pts = []
            for gx, gy in stroke:
                px = cx + gx * unit
                py = oy + gy * unit
                if angle:
                    dx, dy = px - ox, py - oy
                    px = ox + dx * ca - dy * sa
                    py = oy + dx * sa + dy * ca
                pts.append((px, py))
            if len(pts) == 1:
                p = pts[0]
                line(p[0], p[1], p[0] + 0.01, p[1] + 0.01, color, thick)
            else:
                polyline(pts, color, thick)
        cx += adv * unit + tracking
    return total


def wrap_text(text, size, max_w, tracking=0.0):
    words = text.split()
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_width(trial, size, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_size(text, size, max_w, tracking=0.0, minimum=6.0):
    """Shrink size until the single line fits max_w."""
    while size > minimum and text_width(text, size, tracking) > max_w:
        size -= 0.5
    return size


def draw_para(x, y, text, size, max_w, color, lh=None, weight=1.0,
              tracking=0.0, max_lines=None):
    """Wrapped paragraph; returns y just below the last line."""
    if lh is None:
        lh = size * 1.42
    lines = wrap_text(text, size, max_w, tracking)
    if max_lines:
        lines = lines[:max_lines]
    for ln in lines:
        draw_text(x, y, ln, size, color, weight, tracking=tracking)
        y += lh
    return y


# ------------------------------------------------------------- PNG write
_ABS = bytes((b if b < 128 else 256 - b) for b in range(256))


def _filter_cost(data):
    return sum(data.translate(_ABS))


def write_png(path):
    """Downsample the supersampled framebuffer (with a whisper of paper
    grain) and encode a PNG with per-row filter choice."""
    out = bytearray(W * H * 3)
    lcg = LCG(20261122)
    fb = FB
    w2 = W2
    for yy in range(H):
        r0 = (2 * yy) * w2 * 3
        r1 = (2 * yy + 1) * w2 * 3
        orow = yy * W * 3
        for xx in range(W):
            i0 = r0 + xx * 6
            i1 = r1 + xx * 6
            g = (lcg.next() % 3) - 1
            o = orow + xx * 3
            for k in range(3):
                v = (fb[i0 + k] + fb[i0 + 3 + k] + fb[i1 + k] +
                     fb[i1 + 3 + k]) // 4 + g
                out[o + k] = 0 if v < 0 else (255 if v > 255 else v)
    raw = bytearray()
    prev = bytes(W * 3)
    for yy in range(H):
        row = bytes(out[yy * W * 3:(yy + 1) * W * 3])
        sub = bytes((row[i] - (row[i - 3] if i >= 3 else 0)) & 0xFF
                    for i in range(len(row)))
        up = bytes((row[i] - prev[i]) & 0xFF for i in range(len(row)))
        cands = ((0, row), (1, sub), (2, up))
        best_t, best = 0, row
        best_c = None
        for t, d in cands:
            cst = _filter_cost(d[::7])
            if best_c is None or cst < best_c:
                best_c, best_t, best = cst, t, d
        raw.append(best_t)
        raw.extend(best)
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = zlib.crc32(tag)
        c = zlib.crc32(data, c) & 0xFFFFFFFF
        return (len(data).to_bytes(4, "big") + tag + data +
                c.to_bytes(4, "big"))

    ihdr = (W.to_bytes(4, "big") + H.to_bytes(4, "big") +
            bytes([8, 2, 0, 0, 0]))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------- illustrations
def halftone(x, y, w, h, spacing, r, c, seed=7, jitter=0.0):
    lcg = LCG(seed)
    row = 0
    yy = y + spacing / 2.0
    while yy < y + h:
        xx = x + spacing / 2.0 + (spacing / 2.0 if row % 2 else 0.0)
        while xx < x + w:
            jx = jitter * (lcg.rand() - 0.5)
            jy = jitter * (lcg.rand() - 0.5)
            circle_fill(xx + jx, yy + jy, r, c)
            xx += spacing
        yy += spacing
        row += 1


def flag_us(x, y, w, h):
    bands = 7
    for i in range(bands):
        c = (178, 34, 52) if i % 2 == 0 else (240, 240, 235)
        fill_rect(x, y + h * i / bands, w, h / bands + 0.6, c)
    cw, chh = w * 0.42, h * 4 / bands
    fill_rect(x, y, cw, chh, (30, 40, 110))
    for r in range(4):
        for cc in range(5):
            circle_fill(x + 4 + cc * (cw - 7) / 4.0,
                        y + 3.5 + r * (chh - 6) / 3.0, 0.9, (240, 240, 235))


def flag_cn(x, y, w, h):
    fill_rect(x, y, w, h, (222, 41, 57))
    gold = (255, 222, 0)
    circle_fill(x + w * 0.16, y + h * 0.22, 3.0, gold)
    for dx, dy in ((0.30, 0.10), (0.33, 0.24), (0.31, 0.38), (0.26, 0.48)):
        circle_fill(x + w * dx, y + h * dy, 1.4, gold)


def flag_ru(x, y, w, h):
    fill_rect(x, y, w, h / 3 + 0.6, (240, 240, 240))
    fill_rect(x, y + h / 3, w, h / 3 + 0.6, (0, 57, 166))
    fill_rect(x, y + 2 * h / 3, w, h / 3 + 0.6, (213, 0, 50))


def scene_summit(x, y, w, h):
    """The Shenzhen signing room: flags, a long table, three leaders."""
    gradient_v(x, y, w, h, (38, 34, 30), (74, 62, 48))
    rect_outline(x, y, w, h, INK, 1.4)
    # summit wordmark on the wall, clear of the flags
    draw_text(x + w / 2, y + 5, "SHENZHEN · DECLARATION OF PEACE",
              10.5, (232, 220, 190), 1.1, "c", tracking=1.2)
    wm = text_width("SHENZHEN · DECLARATION OF PEACE", 10.5, 1.2)
    line(x + w / 2 - wm / 2 - 26, y + 12, x + w / 2 - wm / 2 - 6, y + 12,
         GOLD, 1.2)
    line(x + w / 2 + wm / 2 + 6, y + 12, x + w / 2 + wm / 2 + 26, y + 12,
         GOLD, 1.2)
    # flags on poles
    centers = [x + w * 0.20, x + w * 0.50, x + w * 0.80]
    fw, fh = 58, 34
    for i, cx in enumerate(centers):
        line(cx - fw / 2 - 5, y + 20, cx - fw / 2 - 5, y + h - 26,
             (16, 14, 12), 2.0)
        fx, fy = cx - fw / 2, y + 24
        if i == 0:
            flag_us(fx, fy, fw, fh)
        elif i == 1:
            flag_cn(fx, fy, fw, fh)
        else:
            flag_ru(fx, fy, fw, fh)
        rect_outline(fx, fy, fw, fh, (10, 9, 8), 0.8)
    # leaders seated at the table
    table_y = y + h - 30
    ties = [(178, 34, 52), (200, 30, 40), (40, 60, 140)]
    skins = [(224, 178, 130), (232, 190, 140), (220, 172, 124)]
    names = ["TRUMP", "XI", "PUTIN"]
    for i, cx in enumerate(centers):
        ellipse_fill(cx, table_y - 6, 17, 15, (13, 15, 22))
        circle_fill(cx, table_y - 22, 8.6, skins[i])
        poly_fill([(cx - 3, table_y - 13), (cx + 3, table_y - 13),
                   (cx, table_y - 4)], (238, 236, 228))
        poly_fill([(cx - 1.6, table_y - 12), (cx + 1.6, table_y - 12),
                   (cx + 1.2, table_y - 5), (cx - 1.2, table_y - 5)],
                  ties[i])
        # microphone
        line(cx + 13, table_y - 2, cx + 6, table_y - 17, (8, 8, 8), 1.1)
        ellipse_fill(cx + 5.4, table_y - 18.5, 2.6, 1.7, (8, 8, 8))
        # name plate
        fill_rect(cx - 17, table_y + 7, 34, 10, (238, 232, 214))
        draw_text(cx, table_y + 8.6, names[i], 7.5, (20, 17, 12), 1.2, "c")
    # the long table
    poly_fill([(x + 26, table_y), (x + w - 26, table_y),
               (x + w - 4, y + h - 4), (x + 4, y + h - 4)], (30, 21, 14))
    line(x + 26, table_y, x + w - 26, table_y, GOLD, 1.2)
    # press cameras in the near corners
    for sx in (x + 12, x + w - 34):
        fill_rect(sx, y + h - 24, 22, 15, (10, 9, 9))
        circle_fill(sx + 11, y + h - 16.5, 4.6, (34, 34, 38))
        fill_rect(sx + 6, y + h - 29, 10, 5, (10, 9, 9))


def fingerprint(cx, cy, r_max):
    """A whorl of broken concentric arcs, drawn like an inked print."""
    col = (205, 228, 238)
    lcg = LCG(4451)
    r = 4.0
    k = 0
    while r < r_max:
        drift = 1.6 * math.sin(k * 0.7)
        start = lcg.rand() * 6.28
        span = 3.6 + lcg.rand() * 2.4
        arc(cx + drift, cy + drift * 0.4, r, r * 0.92, start,
            start + span, col, 1.15)
        if lcg.rand() < 0.7:
            s2 = start + span + 0.5 + lcg.rand() * 0.5
            arc(cx + drift, cy + drift * 0.4, r, r * 0.92, s2,
                s2 + 0.7 + lcg.rand() * 0.9, col, 1.15)
        r += 3.1
        k += 1
    circle_fill(cx, cy, 1.8, col)


def scene_fire(x, y, w, h):
    """A factory ablaze at night."""
    gradient_v(x, y, w, h, (16, 12, 10), (44, 26, 14))
    rect_outline(x, y, w, h, INK, 1.2)
    base = y + h - 6
    # smoke
    for sx, sy, sr in ((0.30, 0.16, 13), (0.44, 0.10, 17), (0.60, 0.15, 14),
                       (0.72, 0.08, 11)):
        ellipse_fill(x + w * sx, y + h * sy + 6, sr, sr * 0.55,
                     (70, 62, 58))
    # chimney
    fill_rect(x + w * 0.80, base - 44, 12, 44, (10, 9, 9))
    # sawtooth factory block
    bx0, bx1 = x + w * 0.06, x + w * 0.94
    roof_y = base - 30
    fill_rect(bx0, roof_y, bx1 - bx0, base - roof_y, (11, 10, 9))
    teeth = 6
    for i in range(teeth):
        tx = bx0 + (bx1 - bx0) * i / teeth
        poly_fill([(tx, roof_y), (tx + (bx1 - bx0) / teeth, roof_y),
                   (tx + 4, roof_y - 9)], (11, 10, 9))
    # lit windows
    lcg = LCG(918)
    for r in range(2):
        for cc in range(14):
            if lcg.rand() < 0.62:
                fill_rect(bx0 + 8 + cc * (bx1 - bx0 - 16) / 13.0,
                          roof_y + 7 + r * 11, 5.5, 7, (244, 178, 74))
    # flames along the roof line
    flames = [(0.16, 26), (0.30, 38), (0.47, 30), (0.62, 42), (0.83, 28)]
    for fx, fh_ in flames:
        cx = x + w * fx
        for scale, col in ((1.0, (199, 44, 26)), (0.68, (233, 116, 30)),
                           (0.4, (246, 208, 63))):
            hh = fh_ * scale
            ww = 13 * scale
            poly_fill([(cx - ww, roof_y + 2), (cx - ww * 0.3, roof_y - hh * 0.45),
                       (cx, roof_y - hh), (cx + ww * 0.35, roof_y - hh * 0.5),
                       (cx + ww, roof_y + 2)], col)
    # sparks
    lcg2 = LCG(517)
    for _ in range(46):
        circle_fill(x + lcg2.rand() * w, y + 4 + lcg2.rand() * h * 0.5,
                    0.8, (250, 190, 90))
    # glow at the base and the stat chip
    fill_rect(x + 3, base - 2, w - 6, 2.5, (233, 116, 30))
    chip = "3 DEAD · 36 MISSING"
    cw = text_width(chip, 10, 0.8) + 14
    fill_rect(x + 8, y + h - 22, cw, 15, (8, 7, 6))
    draw_text(x + 15, y + h - 19.8, chip, 10, (250, 224, 170), 1.2,
              tracking=0.8)


def scene_boat(x, y, w, h):
    """A capsized boat on night water."""
    gradient_v(x, y, w, h, (10, 30, 52), (16, 52, 84))
    rect_outline(x, y, w, h, INK, 1.2)
    circle_fill(x + w * 0.86, y + 15, 8, (226, 232, 220))
    circle_fill(x + w * 0.86 - 3, y + 13, 6.6, (16, 44, 72))
    # far shore
    poly_fill([(x, y + 16), (x + w * 0.34, y + 10), (x + w * 0.52, y + 17),
               (x, y + 20)], (8, 20, 34))
    # wave lines
    for k in range(5):
        wy = y + h * (0.52 + 0.10 * k)
        pts = []
        for i in range(49):
            xx = x + 4 + (w - 8) * i / 48.0
            pts.append((xx, wy + 2.6 * math.sin(i * 0.55 + k * 1.7)))
        polyline(pts, (110, 165, 205), 1.0)
    # capsized hull, rolled toward the viewer
    cx, cy = x + w * 0.44, y + h * 0.52
    hull = [(-52, -6), (52, -10), (34, 10), (-30, 12)]
    ang = math.radians(168)
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(cx + px * ca - py * sa, cy + px * sa + py * ca) for px, py in hull]
    poly_fill(pts, (52, 34, 20))
    polyline(pts, (16, 10, 6), 1.4, close=True)
    line(cx - 6, cy - 4, cx - 30, cy + 26, (30, 20, 12), 2.2)   # mast in water
    line(cx + 20, cy - 10, cx + 34, cy - 30, (30, 20, 12), 2.0)  # spar up
    # heads and shoulders in the water
    for hx, tone in ((0.20, (198, 150, 104)), (0.63, (168, 118, 78)),
                     (0.72, (205, 158, 110)), (0.30, (178, 128, 88))):
        hx2 = x + w * hx
        hy2 = y + h * 0.60
        circle_fill(hx2, hy2, 4.4, tone)
        arc(hx2, hy2 + 7.5, 7.5, 4.2, 3.35, 6.07, tone, 2.4)
    # floating planks
    for px_, py_, a in ((0.55, 0.78, 0.2), (0.13, 0.82, -0.15)):
        cx2, cy2 = x + w * px_, y + h * py_
        ca2, sa2 = math.cos(a), math.sin(a)
        pp = [(cx2 + dx * ca2 - dy * sa2, cy2 + dx * sa2 + dy * ca2)
              for dx, dy in ((-16, -2), (16, -2), (16, 2), (-16, 2))]
        poly_fill(pp, (96, 66, 38))
    chip = "AT LEAST 24 DEAD"
    cw = text_width(chip, 10, 0.8) + 14
    fill_rect(x + 8, y + h - 22, cw, 15, (6, 12, 20))
    draw_text(x + 15, y + h - 19.8, chip, 10, (214, 232, 246), 1.2,
              tracking=0.8)


def checker(x, y, s, cols, rows):
    for r in range(rows):
        for cc in range(cols):
            c = (18, 17, 15) if (r + cc) % 2 == 0 else (238, 234, 222)
            fill_rect(x + cc * s, y + r * s, s, s, c)
    rect_outline(x, y, cols * s, rows * s, INK, 0.9)


def icon_doc(x, y):
    fill_rect(x, y, 15, 19, (250, 247, 238))
    rect_outline(x, y, 15, 19, INK, 1.0)
    for i in range(4):
        line(x + 3, y + 5 + i * 3.4, x + 12, y + 5 + i * 3.4, GREY, 0.9)


def icon_mtn(x, y):
    poly_fill([(x, y + 15), (x + 8, y + 2), (x + 16, y + 15)], (52, 74, 96))
    poly_fill([(x + 11, y + 15), (x + 18, y + 5), (x + 24, y + 15)],
              (70, 96, 124))
    poly_fill([(x + 5.8, y + 6.6), (x + 8, y + 2), (x + 10.2, y + 6.6),
               (x + 8.6, y + 5.6), (x + 8, y + 7.4), (x + 7.4, y + 5.6)],
              (245, 246, 244))


def barcode(x, y, h, seed=31):
    lcg = LCG(seed)
    xx = x
    while xx < x + 84:
        bw = 1 + lcg.next() % 3
        if lcg.rand() < 0.72:
            fill_rect(xx, y, bw, h, CREAM)
        xx += bw + 1 + lcg.next() % 2
    return xx


def sparkline(x, y, w, h):
    vals = [0.42, 0.5, 0.44, 0.58, 0.52, 0.66, 0.6, 0.74, 0.68, 0.8,
            0.76, 0.88]
    pts = [(x + w * i / (len(vals) - 1), y + h - v * h)
           for i, v in enumerate(vals)]
    line(x, y + h - 0.5, x + w, y + h - 0.5, (90, 90, 86), 0.8)
    polyline(pts, (96, 214, 120), 1.5)
    circle_fill(pts[-1][0], pts[-1][1], 2.4, (96, 214, 120))


# ---------------------------------------------------------------- layout
def rule(x0, x1, y, c=INK, t=1.2):
    line(x0, y, x1, y, c, t)


def double_rule(x0, x1, y):
    line(x0, y, x1, y, INK, 2.2)
    line(x0, y + 3.4, x1, y + 3.4, INK, 0.9)


def diamond(cx, cy, r, c):
    poly_fill([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], c)


def compose():
    fill_rect(0, 0, W, H, PAPER)
    MX0, MX1 = 28, 996          # content margins
    # page frame
    rect_outline(12, 12, W - 24, H - 24, INK, 2.0)
    rect_outline(18.5, 18.5, W - 37, H - 37, INK, 0.8)

    # ---- top strip
    draw_text(MX0, 27, "LATE CITY EDITION", 10.5, INK, 1.2, tracking=1.4)
    draw_text(512, 27, "ONE DAY · ONE PICTURE", 10.5, INK, 1.2, "c",
              tracking=2.2)
    draw_text(MX1, 27, "VOL. I · No. 22", 10.5, INK, 1.2, "r",
              tracking=1.4)
    double_rule(MX0, MX1, 46)

    # ---- masthead
    for bx, t1, t2 in ((MX0, "EST.", "MMXXVI"), (MX1 - 118, "PRICE",
                                                  "ONE PICTURE")):
        rect_outline(bx, 62, 118, 50, INK, 1.1)
        draw_text(bx + 59, 72, t1, 11, INK, 1.3, "c", tracking=1.6)
        draw_text(bx + 59, 90, t2, 11, RED if t1 == "PRICE" else INK, 1.3,
                  "c", tracking=1.2)
    msize = fit_size("THE WORLD ON SUNDAY", 57, 700, tracking=1.0)
    draw_text(512, 58, "THE WORLD ON SUNDAY", msize, INK, 1.55, "c",
              tracking=1.0)
    line(MX0, 122, MX1, 122, RED, 3.0)
    line(MX0, 127.5, MX1, 127.5, INK, 0.9)

    # ---- dateline
    draw_text(MX0, 136, "SUNDAY, 22 NOVEMBER 2026", 12.5, INK, 1.35,
              tracking=1.0)
    draw_text(512, 136, "SHENZHEN · WASHINGTON · LAGOS · LAS VEGAS · "
                        "SEOUL · KATHMANDU", 11.5, INK, 1.1, "c",
              tracking=0.8)
    draw_text(MX1, 136, "FAIR · 24°C", 12.5, INK, 1.35, "r",
              tracking=1.0)
    rule(MX0, MX1, 158)

    # ================= LEAD (left) =================
    LX, LW = MX0, 608
    draw_text(LX, 170, "DIPLOMACY · SHENZHEN · AFTERMATH OF THE "
                       "TRILATERAL SUMMIT", 11.5, RED, 1.3, tracking=1.1)
    head = ["A DECLARATION OF PEACE,",
            "SIGNED IN SHENZHEN —",
            "BUT THE WAR GOES ON"]
    hs = 37.0
    for ln in head:
        hs = min(hs, fit_size(ln, hs, LW, tracking=0.4))
    hy = 188
    for ln in head:
        draw_text(LX, hy, ln, hs, INK, 1.5, tracking=0.4)
        hy += hs * 1.22
    draw_text(LX, 322, "BY THE WORLD DESK · REPORTING FROM SHENZHEN, "
                       "KYIV AND WASHINGTON", 9.5, GREY, 1.1, tracking=0.9)
    rule(LX, LX + LW, 338)
    scene_summit(LX, 346, LW, 104)
    draw_text(LX, 456, "SHENZHEN, THURSDAY: TRUMP, XI AND PUTIN AFTER "
                       "NINETY MINUTES BEHIND CLOSED DOORS.", 9.5, GREY,
              1.05, tracking=0.3)
    lead_copy = ("Ninety minutes behind closed doors in Shenzhen produced "
                 "the year's most startling document: a joint declaration "
                 "by Presidents Trump, Xi and Putin that nuclear war "
                 "\"cannot be won and must never be fought\", with promises "
                 "of more petroleum supply, United Nations reform and "
                 "limits on the International Criminal Court. Mr Trump "
                 "hailed it as \"one of the most momentous summits in many "
                 "years\". Kyiv was colder: President Zelensky called it "
                 "\"very unsuccessful for Russia\", even as Russian forces "
                 "launched their biggest attacks of the year on Ukraine.")
    colw = (LW - 16) / 2.0
    words = lead_copy.split()
    half = len(words) // 2
    # split at a word boundary near the middle, by measured width balance
    best, bestd = half, 1e18
    for i in range(len(words) // 3, 2 * len(words) // 3):
        a = len(wrap_text(" ".join(words[:i]), 10.8, colw))
        b = len(wrap_text(" ".join(words[i:]), 10.8, colw))
        if abs(a - b) < bestd:
            bestd, best = abs(a - b), i
    draw_para(LX, 476, " ".join(words[:best]), 10.8, colw, INK, lh=16.2)
    draw_para(LX + colw + 16, 476, " ".join(words[best:]), 10.8, colw, INK,
              lh=16.2)
    line(LX + colw + 8, 478, LX + colw + 8, 592, GREY, 0.7)

    # ================= FBI (right box) =================
    FX, FW = 652, 344
    rect_outline(FX, 168, FW, 432, INK, 1.6)
    rect_outline(FX + 4, 172, FW - 8, 424, INK, 0.7)
    fx = FX + 16
    fw_in = FW - 32
    draw_text(fx, 184, "CYBER CRIME · WASHINGTON", 11, RED, 1.3,
              tracking=1.1)
    fhs = fit_size("DATABASE HACKED", 26, fw_in, tracking=0.3)
    draw_text(fx, 202, "FBI CRIMINAL", fhs, INK, 1.5, tracking=0.3)
    draw_text(fx, 202 + fhs * 1.24, "DATABASE HACKED", fhs, INK, 1.5,
              tracking=0.3)
    rule(fx, fx + fw_in, 272)
    fbi_copy = ("The FBI is investigating an apparent hack of the NCIC, "
                "the national criminal database that holds fingerprints "
                "and files on wanted and missing persons. President Trump "
                "confirmed the breach on Saturday. Agents offered no "
                "detail on who broke in, what was taken, or how long the "
                "intruders were inside. The database is queried millions "
                "of times a day by police across America; any tampering "
                "with its records could follow innocent people for years.")
    draw_para(fx, 282, fbi_copy, 10.5, fw_in, INK, lh=15.2)
    # fingerprint panel
    py = 470
    fill_rect(fx, py, fw_in, 88, (16, 26, 44))
    fingerprint(fx + 46, py + 44, 40)
    draw_text(fx + 96, py + 12, "WHAT IS THE NCIC?", 11, (232, 220, 190),
              1.3, tracking=0.8)
    draw_para(fx + 96, py + 30,
              "The National Crime Information Center: the file America’s "
              "police check first, opened in 1967.", 9.3, fw_in - 108,
              (206, 216, 226), lh=13.2)
    # stat strip
    fill_rect(fx, 566, fw_in, 24, INK)
    draw_text(fx + fw_in / 2, 572.5, "FILES: FINGERPRINTS · WANTED · "
                                     "MISSING", 10.5, CREAM, 1.25, "c",
              tracking=0.8)

    double_rule(MX0, MX1, 612)

    # ================= ROW B: fire + boat =================
    BY = 624
    BW2 = 476
    for bx, scene in ((MX0, "fire"), (520, "boat")):
        if scene == "fire":
            scene_fire(bx, BY, BW2, 72)
            draw_text(bx, BY + 82, "DISASTER · INDONESIA", 9.5, RED, 1.3,
                      tracking=1.1)
            draw_text(bx, BY + 96, "FACTORY FIRE: THREE DEAD,", 20, INK,
                      1.45, tracking=0.2)
            draw_text(bx, BY + 122, "36 MISSING IN INDONESIA", 20, INK,
                      1.45, tracking=0.2)
            copy = ("Three people were killed and 36 are missing after "
                    "fire tore through a confectionery factory in "
                    "Indonesia on Saturday. Rescue teams searched the "
                    "blackened plant through the night as families waited "
                    "at the gates with photographs of the missing. The "
                    "cause is not yet known.")
        else:
            scene_boat(bx, BY, BW2, 72)
            draw_text(bx, BY + 82, "DISASTER · SOUTHERN NIGERIA", 9.5, RED,
                      1.3, tracking=1.1)
            draw_text(bx, BY + 96, "FUNERAL BOAT CAPSIZES;", 20, INK, 1.45,
                      tracking=0.2)
            draw_text(bx, BY + 122, "AT LEAST 24 DROWNED", 20, INK, 1.45,
                      tracking=0.2)
            copy = ("At least 24 people died when a boat carrying mourners "
                    "to a funeral capsized in southern Nigeria. The vessel "
                    "was crowded with families travelling to bury a relative "
                    "when it overturned. Rescuers pulled survivors from the "
                    "water; the search went on after dark.")
        draw_para(bx, BY + 152, copy, 10, BW2, INK, lh=14.2, max_lines=4)

    double_rule(MX0, MX1, 836)

    # ================= ROW C: three columns =================
    CY = 844
    cols = [
        (MX0, "f1", "FORMULA ONE · LAS VEGAS", "VERSTAPPEN TAKES",
         "LAS VEGAS THRILLER",
         "Max Verstappen won an extraordinary Las Vegas Grand Prix: 34 "
         "lead changes under the Strip lights, settled by a Ferrari "
         "collision."),
        (357, "doc", "POLITICS · SEOUL", "MINISTER QUITS IN",
         "EXAM CHEATING ROW",
         "Education minister Choi Kyo-jin resigned over an exam cheating "
         "scandal after last-minute anti-AI measures caused chaos."),
        (686, "mtn", "ASIA · KATHMANDU", "NEPAL PM LANDS",
         "IN INDIA FOR TALKS",
         "Prime Minister Balendra Shah arrived in India for a two-day "
         "state visit and talks with Narendra Modi on trade and borders."),
    ]
    for cx, icon, kicker, h1, h2, copy in cols:
        if icon == "f1":
            checker(cx, CY + 1, 6.5, 4, 3)
            kx = cx + 34
        elif icon == "doc":
            icon_doc(cx, CY)
            kx = cx + 23
        else:
            icon_mtn(cx, CY)
            kx = cx + 31
        draw_text(kx, CY + 4, kicker, 9, RED, 1.3, tracking=0.9)
        chs = fit_size(h2, 16.5, 300, tracking=0.2)
        draw_text(cx, CY + 24, h1, chs, INK, 1.45, tracking=0.2)
        draw_text(cx, CY + 24 + chs * 1.24, h2, chs, INK, 1.45,
                  tracking=0.2)
        draw_para(cx, CY + 24 + chs * 2.42, copy, 9.3, 302, INK, lh=12.4,
                  max_lines=3)
    line(347, CY + 2, 347, CY + 86, GREY, 0.7)
    line(676, CY + 2, 676, CY + 86, GREY, 0.7)

    # ================= IN BRIEF ticker =================
    TY = 950
    lbl = "IN BRIEF"
    lw_ = text_width(lbl, 10.5, 1.0) + 16
    fill_rect(MX0, TY - 3, lw_, 19, RED)
    draw_text(MX0 + 8, TY + 1.5, lbl, 10.5, CREAM, 1.3, tracking=1.0)
    briefs = ("COP31: NEW DRAFT DEAL SEEKS TO AVERT COLLAPSE OF THE TALKS   "
              "·   ICJ VERDICT ON MYANMAR WELCOMED BY ROHINGYA")
    bs = fit_size(briefs, 10.5, MX1 - MX0 - lw_ - 14, tracking=0.4)
    draw_text(MX0 + lw_ + 12, TY + 1.5, briefs, bs, INK, 1.15,
              tracking=0.4)

    # ================= footer =================
    FY = 972
    fill_rect(MX0, FY, MX1 - MX0, 34, BLACK)
    draw_text(MX0 + 12, FY + 6, "MARKETS", 10.5, GOLD, 1.35, tracking=1.2)
    draw_text(MX0 + 12, FY + 19.5, "OIL UP ON SUMMIT PLEDGE · GOLD STEADY",
              9, CREAM, 1.05, tracking=0.5)
    sparkline(430, FY + 8, 120, 18)
    draw_text(566, FY + 12, "STOCKS MIXED · BITCOIN QUIET", 9.5, CREAM,
              1.1, tracking=0.6)
    draw_text(880, FY + 12, "22 11 26", 9.5, CREAM, 1.1, "r",
              tracking=1.0)
    barcode(890, FY + 6, 22)


def main():
    compose()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not out_dir:
        out_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(out_dir, "entry.png")
    n = write_png(path)
    print("wrote %s (%d bytes)" % (path, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
