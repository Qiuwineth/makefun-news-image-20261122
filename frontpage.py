#!/usr/bin/env python3
"""THE WORLD ON SUNDAY - one image that sums up Sunday 22 November 2026.

A one-page newspaper poster drawn entirely with the Python standard
library: a hand-rolled raster canvas, a stroke font defined as polylines
in code, and a PNG encoder built on zlib and struct. No Pillow, no
system fonts, no external files. Running the script writes entry.png
next to itself, byte for byte identical on every run.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024


# ---------------------------------------------------------------- canvas

class Canvas:
    """A minimal RGB raster canvas over a bytearray."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def fill_all(self, color):
        row = bytes(color) * self.w
        for y in range(self.h):
            i = y * self.w * 3
            self.px[i:i + self.w * 3] = row

    def gradient(self, top, bottom):
        for y in range(self.h):
            t = y / (self.h - 1)
            col = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
            i = y * self.w * 3
            self.px[i:i + self.w * 3] = bytes(col) * self.w

    def set(self, x, y, color):
        x = int(x)
        y = int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def rect(self, x0, y0, x1, y1, color):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        seg = bytes(color) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + len(seg)] = seg

    def circle(self, cx, cy, rad, color):
        r = int(rad + 0.5)
        rr = rad * rad
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= rr:
                    self.set(cx + dx, cy + dy, color)

    def line(self, x0, y0, x1, y1, color, wdt):
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        rad = wdt / 2.0
        for i in range(steps + 1):
            t = i / steps
            self.circle(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, rad, color)

    def polyline(self, pts, color, wdt):
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], color, wdt)

    def ellipse_fill(self, cx, cy, rx, ry, color):
        y0 = int(cy - ry)
        y1 = int(cy + ry)
        for y in range(y0, y1 + 1):
            t = (y - cy) / ry if ry else 0.0
            if abs(t) > 1.0:
                continue
            dx = rx * math.sqrt(1.0 - t * t)
            self.rect(cx - dx, y, cx + dx + 1, y + 1, color)

    def ellipse_outline(self, cx, cy, rx, ry, color, wdt):
        n = max(32, int(rx * 2))
        prev = None
        for i in range(n + 1):
            a = 2.0 * math.pi * i / n
            p = (cx + rx * math.cos(a), cy + ry * math.sin(a))
            if prev is not None:
                self.line(prev[0], prev[1], p[0], p[1], color, wdt)
            prev = p


# ------------------------------------------------------------ PNG writer

def save_png(cv, path):
    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(data)


# ------------------------------------------------------------- the font
# Every glyph is a list of strokes; each stroke is a polyline of points
# in a 4-wide, 6-tall box (x grows right, y grows down, baseline y=6).
# A single-point stroke is drawn as a dot.

GLYPHS = {
    "A": [[(0, 6), (2, 0), (4, 6)], [(0.8, 4.2), (3.2, 4.2)]],
    "B": [[(0, 0), (0, 6)],
          [(0, 0), (2.5, 0), (3.6, 0.9), (3.6, 2.1), (2.5, 3), (0, 3)],
          [(0, 3), (2.7, 3), (3.8, 3.9), (3.8, 5.1), (2.7, 6), (0, 6)]],
    "C": [[(3.9, 1.1), (2.9, 0.2), (1.1, 0.2), (0.2, 1.3), (0.2, 4.7),
           (1.1, 5.8), (2.9, 5.8), (3.9, 4.9)]],
    "D": [[(0, 0), (0, 6)],
          [(0, 0), (2.3, 0), (3.8, 1.5), (3.8, 4.5), (2.3, 6), (0, 6)]],
    "E": [[(3.8, 0), (0, 0), (0, 6), (3.8, 6)], [(0, 3), (2.9, 3)]],
    "F": [[(3.8, 0), (0, 0), (0, 6)], [(0, 3), (2.8, 3)]],
    "G": [[(3.9, 1.1), (2.9, 0.2), (1.1, 0.2), (0.2, 1.3), (0.2, 4.7),
           (1.1, 5.8), (2.9, 5.8), (3.9, 4.9), (3.9, 3.6), (2.5, 3.6)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(2, 0), (2, 6)], [(0.7, 0), (3.3, 0)], [(0.7, 6), (3.3, 6)]],
    "J": [[(3.7, 0), (3.7, 4.7), (2.9, 5.8), (1.1, 5.8), (0.3, 5.0)]],
    "K": [[(0, 0), (0, 6)], [(3.8, 0), (0.3, 3.3)], [(1.4, 2.3), (3.9, 6)]],
    "L": [[(0, 0), (0, 6), (3.8, 6)]],
    "M": [[(0, 6), (0, 0), (2, 2.8), (4, 0), (4, 6)]],
    "N": [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    "O": [[(1.1, 0.2), (2.9, 0.2), (3.8, 1.3), (3.8, 4.7), (2.9, 5.8),
           (1.1, 5.8), (0.2, 4.7), (0.2, 1.3), (1.1, 0.2)]],
    "P": [[(0, 6), (0, 0), (2.7, 0), (3.8, 0.9), (3.8, 2.3), (2.7, 3.1),
           (0, 3.1)]],
    "Q": [[(1.1, 0.2), (2.9, 0.2), (3.8, 1.3), (3.8, 4.7), (2.9, 5.8),
           (1.1, 5.8), (0.2, 4.7), (0.2, 1.3), (1.1, 0.2)],
          [(2.3, 4.0), (4.0, 6.0)]],
    "R": [[(0, 6), (0, 0), (2.7, 0), (3.8, 0.9), (3.8, 2.3), (2.7, 3.1),
           (0, 3.1)],
          [(1.7, 3.1), (3.9, 6)]],
    "S": [[(3.8, 0.9), (2.9, 0.2), (1.1, 0.2), (0.3, 0.9), (0.3, 2.1),
           (1.0, 2.8), (3.0, 3.3), (3.8, 4.0), (3.8, 5.0), (2.9, 5.8),
           (1.1, 5.8), (0.2, 5.1)]],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    "U": [[(0, 0), (0, 4.7), (1.0, 5.8), (3.0, 5.8), (4, 4.7), (4, 0)]],
    "V": [[(0, 0), (2, 6), (4, 0)]],
    "W": [[(0, 0), (0.7, 6), (2, 2.6), (3.3, 6), (4, 0)]],
    "X": [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    "Y": [[(0, 0), (2, 2.9), (4, 0)], [(2, 2.9), (2, 6)]],
    "Z": [[(0, 0), (4, 0), (0, 6), (4, 6)]],
    "0": [[(1.1, 0.2), (2.9, 0.2), (3.7, 1.3), (3.7, 4.7), (2.9, 5.8),
           (1.1, 5.8), (0.3, 4.7), (0.3, 1.3), (1.1, 0.2)]],
    "1": [[(1.1, 1.1), (2.4, 0), (2.4, 6)], [(0.9, 6), (3.5, 6)]],
    "2": [[(0.3, 1.0), (1.1, 0.2), (2.9, 0.2), (3.7, 1.0), (3.7, 2.1),
           (0.3, 6), (3.9, 6)]],
    "3": [[(0.3, 0.6), (1.2, 0.2), (2.8, 0.2), (3.7, 1.0), (3.7, 2.0),
           (2.7, 2.8), (1.5, 2.8)],
          [(2.7, 2.8), (3.7, 3.7), (3.7, 4.9), (2.8, 5.8), (1.1, 5.8),
           (0.2, 5.2)]],
    "4": [[(2.9, 6), (2.9, 0), (0.2, 4.3), (4.0, 4.3)]],
    "5": [[(3.7, 0), (0.4, 0), (0.3, 2.5), (2.5, 2.2), (3.7, 3.1),
           (3.7, 4.9), (2.8, 5.8), (1.0, 5.8), (0.2, 5.1)]],
    "6": [[(3.6, 0.9), (2.7, 0.2), (1.2, 0.3), (0.3, 1.5), (0.3, 4.7),
           (1.1, 5.8), (2.9, 5.8), (3.7, 4.8), (3.7, 3.3), (2.8, 2.5),
           (1.1, 2.5), (0.3, 3.3)]],
    "7": [[(0.2, 0), (3.8, 0), (1.7, 6)]],
    "8": [[(1.2, 0.3), (2.8, 0.3), (3.5, 1.0), (3.5, 2.0), (2.8, 2.7),
           (1.2, 2.7), (0.5, 2.0), (0.5, 1.0), (1.2, 0.3)],
          [(1.1, 2.7), (2.9, 2.7), (3.7, 3.7), (3.7, 5.0), (2.9, 5.8),
           (1.1, 5.8), (0.3, 5.0), (0.3, 3.7), (1.1, 2.7)]],
    "9": [[(0.4, 5.1), (1.3, 5.8), (2.8, 5.7), (3.7, 4.5), (3.7, 1.3),
           (2.9, 0.2), (1.1, 0.2), (0.3, 1.2), (0.3, 2.7), (1.2, 3.5),
           (2.8, 3.5), (3.7, 2.7)]],
    ".": [[(2, 5.5)]],
    ",": [[(2.1, 5.2)], [(2.3, 5.5), (1.8, 6.5)]],
    ":": [[(2, 1.2)], [(2, 5.0)]],
    ";": [[(2, 1.2)], [(2.1, 5.0)], [(2.3, 5.3), (1.8, 6.5)]],
    "-": [[(0.7, 3), (3.3, 3)]],
    "·": [[(2, 3)]],
    "'": [[(2.1, 0), (1.8, 1.5)]],
    '"': [[(1.2, 0), (0.9, 1.5)], [(3.1, 0), (2.8, 1.5)]],
    "!": [[(2, 0), (2, 3.9)], [(2, 5.5)]],
    "?": [[(0.4, 1.0), (1.2, 0.2), (2.8, 0.2), (3.6, 1.0), (3.6, 2.0),
           (2, 3.3), (2, 4.3)],
          [(2, 5.5)]],
    "$": [[(3.8, 0.9), (2.9, 0.2), (1.1, 0.2), (0.3, 0.9), (0.3, 2.1),
           (1.0, 2.8), (3.0, 3.3), (3.8, 4.0), (3.8, 5.0), (2.9, 5.8),
           (1.1, 5.8), (0.2, 5.1)],
          [(2, -0.3), (2, 6.3)]],
    "%": [[(1.85, 1.2), (1.6, 1.8), (1, 2.05), (0.4, 1.8), (0.15, 1.2),
           (0.4, 0.6), (1, 0.35), (1.6, 0.6), (1.85, 1.2)],
          [(3.7, 0), (0.3, 6)],
          [(3.85, 4.8), (3.6, 5.4), (3, 5.65), (2.4, 5.4), (2.15, 4.8),
           (2.4, 4.2), (3, 3.95), (3.6, 4.2), (3.85, 4.8)]],
    "/": [[(3.5, 0), (0.5, 6)]],
    "(": [[(3.1, 0.2), (1.7, 1.4), (1.7, 4.6), (3.1, 5.8)]],
    ")": [[(0.9, 0.2), (2.3, 1.4), (2.3, 4.6), (0.9, 5.8)]],
    "+": [[(2, 1.5), (2, 4.5)], [(0.7, 3), (3.3, 3)]],
    "—": [[(0.2, 3), (4.3, 3)]],
    "–": [[(0.5, 3), (3.8, 3)]],
}


# ---------------------------------------------------------- text engine

def text_width(text, size, track=0.0):
    if not text:
        return 0.0
    unit = size / 6.0
    return len(text) * 5.0 * unit + (len(text) - 1) * track


def draw_text(cv, text, x, y, size, color, weight=None, track=0.0,
              align="left"):
    """Draw text with its cap top at y. Returns the drawn width."""
    text = text.upper()
    unit = size / 6.0
    wdt = weight if weight is not None else max(1.5, size * 0.095)
    tw = text_width(text, size, track)
    if align == "center":
        x -= tw / 2.0
    elif align == "right":
        x -= tw
    cx = x
    for ch in text:
        if ch != " ":
            glyph = GLYPHS.get(ch)
            if glyph:
                for stroke in glyph:
                    pts = [(cx + px * unit, y + py * unit) for px, py in stroke]
                    if len(pts) == 1:
                        cv.circle(pts[0][0], pts[0][1], wdt * 0.95, color)
                    else:
                        cv.polyline(pts, color, wdt)
        cx += 5.0 * unit + track
    return tw


def wrap(text, size, maxw, track=0.0):
    lines = []
    cur = ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if not cur or text_width(trial, size, track) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# -------------------------------------------------------------- palette

NAVY_TOP = (9, 14, 31)
NAVY_BOT = (16, 24, 46)
PANEL = (16, 25, 49)
PANEL_LEAD = (20, 31, 59)
BORDER = (58, 72, 105)
GOLD = (216, 178, 84)
GOLD_DIM = (150, 124, 66)
RED = (206, 44, 52)
RED_DEEP = (168, 30, 40)
CREAM = (238, 232, 216)
BODY = (198, 207, 226)
MUTED = (138, 150, 176)
WHITE = (246, 246, 246)


# ------------------------------------------------------------------ art

def flag_usa(cv, x, y, w, h):
    sh = h / 7.0
    for i in range(7):
        col = (178, 34, 52) if i % 2 == 0 else (240, 240, 240)
        cv.rect(x, y + i * sh, x + w, y + (i + 1) * sh + 1, col)
    cw = w * 0.46
    cv.rect(x, y, x + cw, y + sh * 4, (38, 48, 118))
    for r in range(3):
        for c in range(4):
            cv.circle(x + 4 + c * (cw - 6) / 3.0, y + 4 + r * (sh * 4 - 8) / 2.0,
                      1.3, (240, 240, 240))


def flag_china(cv, x, y, w, h):
    cv.rect(x, y, x + w, y + h, (198, 38, 44))
    cv.circle(x + w * 0.20, y + h * 0.26, 3.4, GOLD)
    for dx, dy in ((0.34, 0.10), (0.38, 0.26), (0.38, 0.44), (0.33, 0.58)):
        cv.circle(x + w * dx, y + h * dy, 1.5, GOLD)


def flag_russia(cv, x, y, w, h):
    th = h / 3.0
    cv.rect(x, y, x + w, y + th + 1, (238, 238, 238))
    cv.rect(x, y + th, x + w, y + 2 * th + 1, (40, 80, 170))
    cv.rect(x, y + 2 * th, x + w, y + h, (198, 38, 44))


def draw_lead_art(cv):
    """Three flags over a globe, in the lead box's right-hand zone."""
    gx, gy, gr = 838, 352, 72
    # poles first, so the globe overlaps their feet
    for px in (750, 838, 926):
        cv.line(px, 214, px, 306, GOLD_DIM, 2.4)
        cv.circle(px, 211, 3.0, GOLD)
    # globe
    cv.circle(gx, gy, gr, (23, 56, 100))
    land = (52, 128, 92)
    cv.ellipse_fill(gx - 30, gy - 28, 26, 15, land)
    cv.ellipse_fill(gx + 26, gy - 12, 20, 22, land)
    cv.ellipse_fill(gx - 8, gy + 26, 30, 14, land)
    cv.ellipse_fill(gx + 34, gy + 34, 13, 9, land)
    cv.ellipse_outline(gx, gy, gr * 0.45, gr, (90, 140, 190), 1.4)
    cv.ellipse_outline(gx, gy, gr * 0.8, gr, (90, 140, 190), 1.4)
    cv.ellipse_outline(gx, gy - gr * 0.45, gr * 0.89, gr * 0.2,
                       (90, 140, 190), 1.4)
    cv.ellipse_outline(gx, gy + gr * 0.45, gr * 0.89, gr * 0.2,
                       (90, 140, 190), 1.4)
    cv.ellipse_outline(gx, gy, gr, gr, GOLD, 2.2)
    # flags
    flag_usa(cv, 748, 214, 56, 38)
    flag_china(cv, 836, 214, 56, 38)
    flag_russia(cv, 924, 214, 56, 38)
    draw_text(cv, "SHENZHEN · 19 NOV", gx, 438, 11.5, MUTED, align="center")


# --------------------------------------------------------------- layout

def box_frame(cv, x, y, w, h, accent):
    cv.rect(x, y, x + w, y + h, PANEL)
    cv.rect(x, y, x + w, y + 4, accent)
    cv.polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)],
                BORDER, 1.4)


def story_box(cv, x, y, w, h, accent, kicker, stat, headline, body):
    box_frame(cv, x, y, w, h, accent)
    tx = x + 16
    tw = w - 32
    draw_text(cv, kicker, tx, y + 13, 13.5, accent, track=1.0)
    draw_text(cv, stat, tx + tw, y + 13, 12.5, GOLD, align="right")
    head_lines = wrap(headline, 19, tw)
    hy = y + 36
    for ln in head_lines:
        draw_text(cv, ln, tx, hy, 19, CREAM)
        hy += 24
    body_lines = wrap(body, 13.5, tw)
    by = hy + 6
    for ln in body_lines:
        draw_text(cv, ln, tx, by, 13.5, BODY)
        by += 17.5


def build():
    cv = Canvas(W, H)
    cv.gradient(NAVY_TOP, NAVY_BOT)

    # double frame
    cv.polyline([(16, 16), (1008, 16), (1008, 1008), (16, 1008), (16, 16)],
                GOLD, 3)
    cv.polyline([(25, 25), (999, 25), (999, 999), (25, 999), (25, 25)],
                GOLD_DIM, 1.2)

    # masthead
    draw_text(cv, "LATE EDITION · THE WHOLE DAY ON ONE PAGE", 512, 36,
              13.5, GOLD, track=2.0, align="center")
    draw_text(cv, "THE WORLD ON SUNDAY", 512, 61, 55, CREAM, align="center")
    cv.line(60, 128, 964, 128, GOLD, 2.2)

    # red date band
    cv.rect(36, 140, 988, 184, RED_DEEP)
    cv.rect(36, 140, 988, 145, RED)
    draw_text(cv, "SUNDAY 22 NOVEMBER 2026 · ONE DAY · ONE PICTURE", 512,
              152, 23, WHITE, align="center")

    # lead story
    lx, ly, lw, lh = 36, 196, 952, 308
    cv.rect(lx, ly, lx + lw, ly + lh, PANEL_LEAD)
    cv.polyline([(lx, ly), (lx + lw, ly), (lx + lw, ly + lh), (lx, ly + lh),
                 (lx, ly)], GOLD, 2.2)
    draw_lead_art(cv)
    tx = lx + 24
    tw = 616
    draw_text(cv, "DIPLOMACY · THE SUMMIT AFTERMATH", tx, ly + 16, 15,
              GOLD, track=1.5)
    hy = ly + 44
    for ln in ("TRUMP, XI AND PUTIN SIGN", "A DECLARATION OF PEACE",
               "AS WAR ROARS OVER UKRAINE"):
        draw_text(cv, ln, tx, hy, 30, CREAM)
        hy += 37
    body = ("TRUMP, XI AND PUTIN MET FOR 90 MINUTES IN SHENZHEN AND "
            "ISSUED A JOINT DECLARATION OF PEACE. TRUMP HAILED IT AS "
            "ONE OF THE MOST MOMENTOUS SUMMITS IN MANY YEARS; ZELENSKY "
            "CALLED IT 'VERY UNSUCCESSFUL FOR RUSSIA'.")
    by = hy + 10
    for ln in wrap(body, 16, tw):
        draw_text(cv, ln, tx, by, 16, BODY)
        by += 21
    draw_text(cv, "90 MINUTES · MOSCOW'S BIGGEST ATTACKS OF THE YEAR",
              tx, ly + lh - 30, 14.5, GOLD)

    # six story boxes, two columns by three rows
    boxes = [
        ((110, 180, 255), "CRIME · UNITED STATES", "NCIC BREACHED",
         "FBI CRIMINAL DATABASE HACKED",
         "FBI PROBES AN APPARENT HACK OF ITS NCIC DATABASE OF "
         "FINGERPRINTS AND WANTED PERSONS. TRUMP CONFIRMED IT."),
        ((255, 150, 80), "DISASTER · INDONESIA", "36 MISSING",
         "DEADLY FIRE AT CANDY FACTORY",
         "FIRE SWEPT A CONFECTIONERY FACTORY IN INDONESIA, KILLING "
         "THREE AND LEAVING DOZENS UNACCOUNTED FOR."),
        ((120, 220, 150), "DISASTER · NIGERIA", "24 DEAD",
         "FUNERAL BOAT CAPSIZES",
         "A BOAT CARRYING MOURNERS TO A FUNERAL CAPSIZED IN SOUTHERN "
         "NIGERIA, KILLING AT LEAST 24 PEOPLE ON BOARD."),
        ((230, 130, 220), "SPORT · LAS VEGAS", "34 LEAD CHANGES",
         "VERSTAPPEN WINS VEGAS THRILLER",
         "MAX VERSTAPPEN WON AN EXTRAORDINARY LAS VEGAS GRAND PRIX, "
         "A RACE OF 34 LEAD CHANGES AND A FERRARI COLLISION."),
        ((100, 220, 210), "POLITICS · SOUTH KOREA", "EXAMS IN CHAOS",
         "EDUCATION MINISTER RESIGNS",
         "CHOI KYO-JIN QUIT OVER AN EXAM CHEATING SCANDAL; "
         "LAST-MINUTE ANTI-AI-CHEATING RULES SPREAD CHAOS."),
        ((240, 200, 90), "DIPLOMACY · NEW DELHI", "TALKS WITH MODI",
         "NEPAL PM LANDS IN NEW DELHI",
         "BALENDRA SHAH BEGAN A TWO-DAY STATE VISIT TO INDIA, HIS "
         "FIRST TRIP ABROAD AS PM, FOR TALKS WITH MODI."),
    ]
    xs = (36, 522)
    ys = (520, 671, 822)
    for i, (accent, kicker, stat, headline, body) in enumerate(boxes):
        story_box(cv, xs[i % 2], ys[i // 2], 466, 142, accent, kicker,
                  stat, headline, body)

    # footer
    draw_text(cv, "SOURCES: BBC · XINHUA · PEOPLE'S DAILY · AL JAZEERA · "
                  "CNBC · RADIO NEPAL · IANS", 512, 976, 13, MUTED,
              align="center")
    return cv


def main():
    cv = build()
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or here
    save_png(cv, os.path.join(out_dir, "entry.png"))


if __name__ == "__main__":
    main()
