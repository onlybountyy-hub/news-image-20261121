#!/usr/bin/env python3
"""THE WORLD TODAY — Saturday 21 November 2026.

A one-page newspaper front page that sums up the world's news of
Saturday 21 November 2026, drawn entirely by this program with the
Python standard library alone (no network, no third-party packages).

The program renders a 1024x1024 poster into a pixel buffer with its
own tiny rasteriser and stroke typeface, encodes it as a PNG with
zlib, and writes it to $MAKEFUN_OUTPUT_DIR/entry.png (or
/output/entry.png when the variable is unset).  The drawing is a pure
function of the constants in this file, so every run writes exactly
the same bytes.

Run it:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- canvas

class Canvas:
    """An RGB pixel buffer with the few primitives the page needs."""

    def __init__(self, w, h, colour):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(colour) * (w * h))

    def fill(self, colour):
        self.px[:] = bytes(colour) * (self.w * self.h)

    def blend_px(self, x, y, colour, alpha):
        if 0 <= x < self.w and 0 <= y < self.h and alpha > 0.0:
            i = (y * self.w + x) * 3
            if alpha >= 1.0:
                self.px[i] = colour[0]
                self.px[i + 1] = colour[1]
                self.px[i + 2] = colour[2]
            else:
                ia = 1.0 - alpha
                self.px[i] = int(colour[0] * alpha + self.px[i] * ia + 0.5)
                self.px[i + 1] = int(colour[1] * alpha + self.px[i + 1] * ia + 0.5)
                self.px[i + 2] = int(colour[2] * alpha + self.px[i + 2] * ia + 0.5)

    def rect(self, x, y, w, h, colour):
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.w, int(x + w))
        y1 = min(self.h, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(colour) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def vgrad(self, x, y, w, h, top, bottom):
        """Vertical linear gradient over a rectangle."""
        x0 = max(0, int(x))
        x1 = min(self.w, int(x + w))
        if x1 <= x0:
            return
        steps = max(1, int(h) - 1)
        for j in range(int(h)):
            yy = int(y) + j
            if yy < 0 or yy >= self.h:
                continue
            t = j / steps
            c = (int(top[0] + (bottom[0] - top[0]) * t + 0.5),
                 int(top[1] + (bottom[1] - top[1]) * t + 0.5),
                 int(top[2] + (bottom[2] - top[2]) * t + 0.5))
            row = bytes(c) * (x1 - x0)
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def segment(self, x0, y0, x1, y1, radius, colour, alpha=1.0):
        """A round-capped thick line, anti-aliased by coverage."""
        import math
        r = radius
        lo_x = max(0, int(min(x0, x1) - r - 1))
        hi_x = min(self.w - 1, int(max(x0, x1) + r + 1))
        lo_y = max(0, int(min(y0, y1) - r - 1))
        hi_y = min(self.h - 1, int(max(y0, y1) + r + 1))
        dx = x1 - x0
        dy = y1 - y0
        len2 = dx * dx + dy * dy
        lim = r + 0.75
        lim2 = lim * lim
        for yy in range(lo_y, hi_y + 1):
            for xx in range(lo_x, hi_x + 1):
                if len2 == 0.0:
                    ddx = xx - x0
                    ddy = yy - y0
                else:
                    t = ((xx - x0) * dx + (yy - y0) * dy) / len2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                    ddx = xx - (x0 + t * dx)
                    ddy = yy - (y0 + t * dy)
                d2 = ddx * ddx + ddy * ddy
                if d2 < lim2:
                    cov = r + 0.5 - math.sqrt(d2)
                    if cov > 1.0:
                        cov = 1.0
                    if cov > 0.0:
                        self.blend_px(xx, yy, colour, cov * alpha)

    def disc(self, cx, cy, r, colour, alpha=1.0):
        import math
        lo_x = max(0, int(cx - r - 1))
        hi_x = min(self.w - 1, int(cx + r + 1))
        lo_y = max(0, int(cy - r - 1))
        hi_y = min(self.h - 1, int(cy + r + 1))
        lim = r + 0.75
        lim2 = lim * lim
        for yy in range(lo_y, hi_y + 1):
            for xx in range(lo_x, hi_x + 1):
                ddx = xx - cx
                ddy = yy - cy
                d2 = ddx * ddx + ddy * ddy
                if d2 < lim2:
                    cov = r + 0.5 - math.sqrt(d2)
                    if cov > 1.0:
                        cov = 1.0
                    if cov > 0.0:
                        self.blend_px(xx, yy, colour, cov * alpha)

    def polygon(self, points, colour):
        """Scanline fill; edges are smoothed afterwards by stroking
        the outline with the same colour (see stroke_polygon)."""
        ys = [p[1] for p in points]
        y_lo = max(0, int(min(ys)))
        y_hi = min(self.h - 1, int(max(ys)))
        n = len(points)
        for yy in range(y_lo, y_hi + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                xa, ya = points[i]
                xb, yb = points[(i + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(xs[k], yy, xs[k + 1] - xs[k], 1, colour)

    def stroke_polygon(self, points, colour, radius=1.1):
        n = len(points)
        for i in range(n):
            xa, ya = points[i]
            xb, yb = points[(i + 1) % n]
            self.segment(xa, ya, xb, yb, radius, colour)

# ---------------------------------------------------------------- type
# A small stroke typeface, drawn by hand for this page.  Each glyph is
# a list of polylines on a 12-wide, 16-tall grid: the baseline sits at
# y=12.5, cap height reaches y=2.5, x-height y=5.5 and descenders fall
# to y=15.5.  The first value of each entry is the advance width.

GLYPHS = {
    " ": (4.0, []),
    "A": (8.6, [[(1, 12.5), (4.3, 2.5), (7.6, 12.5)], [(2.55, 9.1), (6.05, 9.1)]]),
    "B": (8.2, [[(1.2, 2.5), (1.2, 12.5)],
                [(1.2, 2.5), (4.6, 2.5), (6, 3.7), (6, 5.3), (4.6, 6.9), (1.2, 6.9)],
                [(1.2, 6.9), (5, 6.9), (6.6, 8.3), (6.6, 10.9), (5, 12.5), (1.2, 12.5)]]),
    "C": (8.4, [[(7.2, 4.2), (5.4, 2.7), (3.4, 2.5), (1.8, 4.4), (1.4, 7.5),
                 (1.8, 10.6), (3.4, 12.5), (5.4, 12.3), (7.2, 10.8)]]),
    "D": (8.6, [[(1.2, 2.5), (1.2, 12.5)],
                [(1.2, 2.5), (4.4, 2.5), (6.6, 5), (7, 7.5), (6.6, 10), (4.4, 12.5), (1.2, 12.5)]]),
    "E": (7.8, [[(6.8, 2.5), (1.2, 2.5), (1.2, 12.5), (6.8, 12.5)], [(1.2, 7.3), (5.4, 7.3)]]),
    "F": (7.6, [[(6.8, 2.5), (1.2, 2.5), (1.2, 12.5)], [(1.2, 7.3), (5.2, 7.3)]]),
    "G": (8.8, [[(7.4, 4.2), (5.6, 2.7), (3.6, 2.5), (1.9, 4.4), (1.5, 7.5),
                 (1.9, 10.6), (3.6, 12.5), (5.8, 12.5), (7.4, 11), (7.4, 8.6), (4.9, 8.6)]]),
    "H": (8.8, [[(1.2, 2.5), (1.2, 12.5)], [(7, 2.5), (7, 12.5)], [(1.2, 7.5), (7, 7.5)]]),
    "I": (5.2, [[(2.6, 2.5), (2.6, 12.5)], [(0.9, 2.5), (4.3, 2.5)], [(0.9, 12.5), (4.3, 12.5)]]),
    "J": (7.2, [[(5.8, 2.5), (5.8, 10.6), (4.6, 12.3), (2.8, 12.5), (1.6, 11.4)],
                [(3.2, 2.5), (5.8, 2.5)]]),
    "K": (8.4, [[(1.2, 2.5), (1.2, 12.5)], [(6.8, 2.5), (1.5, 8.5)], [(2.7, 7.1), (7, 12.5)]]),
    "L": (7.6, [[(1.2, 2.5), (1.2, 12.5), (6.6, 12.5)]]),
    "M": (9.6, [[(1, 12.5), (1, 2.5), (4.4, 8.6), (7.8, 2.5), (7.8, 12.5)]]),
    "N": (8.8, [[(1.2, 12.5), (1.2, 2.5), (7, 12.5), (7, 2.5)]]),
    "O": (9.2, [[(3.6, 2.5), (1.9, 4.2), (1.5, 7.5), (1.9, 10.8), (3.6, 12.5),
                 (5.4, 12.5), (7.1, 10.8), (7.5, 7.5), (7.1, 4.2), (5.4, 2.5), (3.6, 2.5)]]),
    "P": (8.4, [[(1.2, 12.5), (1.2, 2.5), (4.8, 2.5), (6.6, 4.2), (6.6, 6.6), (4.8, 8.4), (1.2, 8.4)]]),
    "Q": (9.2, [[(3.6, 2.5), (1.9, 4.2), (1.5, 7.5), (1.9, 10.8), (3.6, 12.5),
                 (5.4, 12.5), (7.1, 10.8), (7.5, 7.5), (7.1, 4.2), (5.4, 2.5), (3.6, 2.5)],
                [(5.1, 10.3), (7.7, 13.5)]]),
    "R": (8.4, [[(1.2, 12.5), (1.2, 2.5), (4.8, 2.5), (6.6, 4.2), (6.6, 6.6), (4.8, 8.4), (1.2, 8.4)],
                [(4.5, 8.4), (7, 12.5)]]),
    "S": (8.4, [[(7, 4), (5.4, 2.6), (3.4, 2.5), (1.9, 3.8), (2.1, 6.2), (3.4, 7.3),
                 (5.6, 8.2), (6.9, 9.6), (6.7, 11.4), (5.2, 12.5), (3.2, 12.4), (1.6, 11.2)]]),
    "T": (8.4, [[(0.8, 2.5), (7.6, 2.5)], [(4.2, 2.5), (4.2, 12.5)]]),
    "U": (8.8, [[(1.2, 2.5), (1.2, 10.4), (2.6, 12.3), (4.6, 12.5), (6.4, 12.3),
                 (7.4, 10.4), (7.4, 2.5)]]),
    "V": (8.6, [[(0.8, 2.5), (4.2, 12.5), (7.6, 2.5)]]),
    "W": (9.6, [[(0.6, 2.5), (2.4, 12.5), (4.4, 5.6), (6.4, 12.5), (8.2, 2.5)]]),
    "X": (8.4, [[(1, 2.5), (7.2, 12.5)], [(7.2, 2.5), (1, 12.5)]]),
    "Y": (8.6, [[(0.8, 2.5), (4.2, 7.6), (7.6, 2.5)], [(4.2, 7.6), (4.2, 12.5)]]),
    "Z": (8.4, [[(1, 2.5), (7.2, 2.5), (1, 12.5), (7.2, 12.5)]]),
    "0": (8.0, [[(3.2, 2.5), (1.9, 4.4), (1.6, 7.5), (1.9, 10.6), (3.2, 12.5),
                 (4.8, 12.5), (6.1, 10.6), (6.4, 7.5), (6.1, 4.4), (4.8, 2.5), (3.2, 2.5)]]),
    "1": (8.0, [[(2.4, 4.4), (4.6, 2.5), (4.6, 12.5)], [(2.2, 12.5), (6.8, 12.5)]]),
    "2": (8.0, [[(1.6, 4.6), (2.8, 2.7), (4.8, 2.5), (6.2, 4.2), (6, 6.4), (1.4, 12.5), (6.8, 12.5)]]),
    "3": (8.0, [[(1.6, 4.2), (3.2, 2.6), (5, 2.5), (6.3, 4.2), (5.6, 6.6), (3.6, 7.4)],
                [(3.6, 7.4), (5.8, 8.2), (6.4, 10.4), (5.2, 12.4), (3.2, 12.5), (1.6, 11.2)]]),
    "4": (8.0, [[(4.8, 12.5), (4.8, 2.5), (1, 9.4), (7, 9.4)]]),
    "5": (8.0, [[(6.4, 2.5), (1.8, 2.5), (1.6, 7), (3.6, 6.4), (5.4, 6.8), (6.3, 8.8),
                 (6, 11.2), (4.4, 12.5), (2.4, 12.4), (1.2, 11)]]),
    "6": (8.0, [[(6, 3.6), (4.4, 2.5), (2.8, 3.6), (1.8, 6.6), (1.7, 9.8), (2.8, 12.1),
                 (4.4, 12.5), (6, 11.4), (6.3, 9.4), (5.4, 7.6), (3.8, 7.2), (2.2, 8.2)]]),
    "7": (8.0, [[(1.2, 2.5), (6.8, 2.5), (3.8, 12.5)]]),
    "8": (8.0, [[(4, 7.3), (2.4, 6.4), (2, 4.4), (3, 2.7), (5, 2.7), (6, 4.4), (5.6, 6.4), (4, 7.3)],
                [(4, 7.3), (5.8, 8.4), (6.2, 10.6), (5, 12.4), (3, 12.4), (1.8, 10.6), (2.2, 8.4), (4, 7.3)]]),
    "9": (8.0, [[(2, 11.4), (3.6, 12.5), (5.2, 11.4), (6.2, 8.4), (6.3, 5.2), (5.2, 2.9),
                 (3.6, 2.5), (2, 3.6), (1.7, 5.6), (2.6, 7.4), (4.2, 7.8), (6, 6.6)]]),
    "a": (7.6, [[(6.2, 7.6), (4.8, 5.6), (3, 5.5), (1.7, 7.2), (1.6, 9.8),
                 (2.8, 12.3), (4.6, 12.5), (6.2, 10.6)], [(6.2, 5.5), (6.2, 12.5)]]),
    "b": (7.6, [[(1.4, 2.5), (1.4, 12.5)],
                [(1.4, 7.8), (2.8, 5.7), (4.8, 5.5), (6.1, 7.4), (6.2, 9.9),
                 (5, 12.3), (3, 12.5), (1.4, 10.8)]]),
    "c": (7.4, [[(6.1, 7.2), (4.8, 5.6), (3.2, 5.5), (1.8, 7.2), (1.6, 9.9),
                 (2.8, 12.3), (4.6, 12.5), (6.1, 11)]]),
    "d": (7.6, [[(6.2, 7.8), (5, 5.7), (3, 5.5), (1.7, 7.4), (1.6, 9.9),
                 (2.8, 12.3), (4.8, 12.5), (6.2, 10.8)], [(6.2, 2.5), (6.2, 12.5)]]),
    "e": (7.5, [[(1.7, 9.2), (6.2, 9.2), (6.1, 7.4), (4.9, 5.6), (3.1, 5.5),
                 (1.8, 7.3), (1.6, 9.9), (2.8, 12.3), (4.7, 12.5), (6.2, 11.1)]]),
    "f": (6.2, [[(5.8, 3.8), (4.9, 2.6), (3.4, 2.5), (2.6, 3.8), (2.6, 12.5)],
                [(1.2, 6.4), (5, 6.4)]]),
    "g": (7.6, [[(6.2, 7.8), (5, 5.7), (3, 5.5), (1.7, 7.4), (1.6, 9.9),
                 (2.8, 12.3), (4.8, 12.5), (6.2, 10.8)],
                [(6.2, 5.5), (6.2, 13.6), (5.2, 15.2), (3.4, 15.5), (1.9, 14.6)]]),
    "h": (7.6, [[(1.4, 2.5), (1.4, 12.5)],
                [(1.4, 7.6), (2.8, 5.7), (4.8, 5.5), (6, 7.2), (6, 12.5)]]),
    "i": (4.4, [[(2.6, 5.5), (2.6, 12.5)], [(2.6, 3.1), (2.6, 3.9)]]),
    "j": (5.2, [[(3.8, 5.5), (3.8, 13.4), (2.8, 15.2), (1.4, 15.4)], [(3.8, 3.1), (3.8, 3.9)]]),
    "k": (7.4, [[(1.4, 2.5), (1.4, 12.5)], [(5.8, 5.5), (1.6, 9.6)], [(3, 8.6), (6, 12.5)]]),
    "l": (4.4, [[(2.4, 2.5), (2.4, 12.5)]]),
    "m": (11.2, [[(1.2, 5.5), (1.2, 12.5)],
                 [(1.2, 7.6), (2.6, 5.7), (4.4, 5.5), (5.4, 7.2), (5.4, 12.5)],
                 [(5.4, 7.6), (6.8, 5.7), (8.6, 5.5), (9.6, 7.2), (9.6, 12.5)]]),
    "n": (7.4, [[(1.2, 5.5), (1.2, 12.5)],
                [(1.2, 7.6), (2.6, 5.7), (4.6, 5.5), (5.8, 7.2), (5.8, 12.5)]]),
    "o": (7.6, [[(3.4, 5.5), (2, 7.2), (1.6, 9.9), (2.8, 12.3), (4.6, 12.5),
                 (6, 10.8), (6.3, 8.2), (5.4, 5.9), (3.4, 5.5)]]),
    "p": (7.6, [[(1.4, 5.5), (1.4, 15.5)],
                [(1.4, 7.8), (2.8, 5.7), (4.8, 5.5), (6.1, 7.4), (6.2, 9.9),
                 (5, 12.3), (3, 12.5), (1.4, 10.8)]]),
    "q": (7.6, [[(6.2, 7.8), (5, 5.7), (3, 5.5), (1.7, 7.4), (1.6, 9.9),
                 (2.8, 12.3), (4.8, 12.5), (6.2, 10.8)], [(6.2, 5.5), (6.2, 15.5)]]),
    "r": (6.4, [[(1.4, 5.5), (1.4, 12.5)], [(1.4, 7.8), (2.8, 5.8), (4.6, 5.5), (5.6, 6.4)]]),
    "s": (7.2, [[(5.9, 6.8), (4.7, 5.6), (3, 5.5), (1.8, 6.6), (2.2, 8.6), (3.4, 9.4),
                 (5, 10.2), (5.9, 11.2), (5.4, 12.3), (3.6, 12.5), (1.9, 11.6)]]),
    "t": (6.0, [[(3, 3.4), (3, 11.4), (3.9, 12.4), (5.2, 12.4)], [(1.2, 6.2), (5.4, 6.2)]]),
    "u": (7.4, [[(1.4, 5.5), (1.4, 10.4), (2.4, 12.2), (4.2, 12.5), (6, 11), (6, 5.5)],
                [(6, 11), (6, 12.5)]]),
    "v": (7.6, [[(1, 5.5), (3.8, 12.5), (6.6, 5.5)]]),
    "w": (8.4, [[(0.8, 5.5), (2.2, 12.5), (3.9, 7.6), (5.6, 12.5), (7, 5.5)]]),
    "x": (7.2, [[(1.2, 5.5), (6, 12.5)], [(6, 5.5), (1.2, 12.5)]]),
    "y": (7.6, [[(1, 5.5), (3.8, 11.4), (6.6, 5.5)], [(3.8, 11.4), (3.2, 14.6), (1.8, 15.5)]]),
    "z": (7.2, [[(1.2, 5.5), (6, 5.5), (1.2, 12.5), (6.2, 12.5)]]),
    ".": (3.6, [[(1.8, 12.1), (1.8, 12.8)]]),
    ",": (3.6, [[(2.1, 12.1), (1.7, 13.9)]]),
    ";": (3.6, [[(1.8, 7.5), (1.8, 8.2)], [(2.1, 12.1), (1.7, 13.9)]]),
    ":": (3.6, [[(1.8, 7.5), (1.8, 8.2)], [(1.8, 12.1), (1.8, 12.8)]]),
    "'": (3.2, [[(2, 2.8), (2, 4.7)]]),
    "!": (3.6, [[(2, 2.5), (2, 9.6)], [(2, 12.1), (2, 12.8)]]),
    "?": (7.4, [[(1.6, 4.4), (2.8, 2.7), (4.6, 2.5), (5.8, 3.8), (5.4, 6.2),
                 (3.8, 7.6), (3.8, 9.2)], [(3.8, 12.1), (3.8, 12.8)]]),
    "-": (6.0, [[(1, 8.8), (5, 8.8)]]),
    "–": (6.8, [[(0.8, 8.8), (6, 8.8)]]),
    "—": (9.0, [[(0.6, 8.8), (8.4, 8.8)]]),
    "(": (5.6, [[(5, 2.5), (3, 5), (2.4, 7.5), (3, 10), (5, 12.5)]]),
    ")": (5.6, [[(1.6, 2.5), (3.6, 5), (4.2, 7.5), (3.6, 10), (1.6, 12.5)]]),
    "%": (8.4, [[(6.8, 2.5), (1, 12.5)],
                [(2.2, 2.7), (1.2, 3.8), (2.2, 4.9), (3.2, 3.8), (2.2, 2.7)],
                [(5.6, 9.9), (4.6, 11), (5.6, 12.1), (6.6, 11), (5.6, 9.9)]]),
    "$": (7.8, [[(4, 1.4), (4, 13.8)],
                [(6.4, 4.4), (5, 2.8), (3.2, 2.6), (1.9, 4), (2.2, 6.2), (3.4, 7.2),
                 (5.2, 8), (6.2, 9.4), (5.9, 11.4), (4.6, 12.5), (2.8, 12.4), (1.4, 11.2)]]),
    "€": (8.2, [[(7, 4.4), (5.2, 2.7), (3.2, 2.6), (1.8, 5), (1.6, 9.8),
                 (3, 12.3), (5.2, 12.4), (7, 10.8)], [(0.8, 6.4), (5.4, 6.4)], [(0.8, 8.8), (5.4, 8.8)]]),
    "£": (8.0, [[(6.6, 4), (5.4, 2.6), (3.6, 2.5), (2.4, 3.8), (2.4, 8.8),
                 (1.2, 12.5), (6.8, 12.5)], [(1.2, 8), (5.6, 8)]]),
    "+": (8.0, [[(4, 5), (4, 11)], [(1, 8), (7, 8)]]),
    "/": (6.4, [[(1, 12.5), (6, 2.5)]]),
    "&": (8.2, [[(5.8, 12.5), (3, 9.6), (2, 7.6), (2.4, 4.6), (3.8, 2.7), (5.4, 3.2),
                 (5.2, 5.4), (3.4, 7.4), (6.4, 12.5)], [(5.2, 5.4), (6.6, 3.4)]]),
    "•": (4.8, [[(2.4, 8.3), (2.4, 9.2)]]),
    "·": (3.6, [[(1.8, 8.7), (1.8, 9.4)]]),
    '"': (6.0, [[(1.6, 2.8), (1.6, 4.8)], [(4.4, 2.8), (4.4, 4.8)]]),
    "…": (9.0, [[(1.4, 12.1), (1.4, 12.8)], [(4.4, 12.1), (4.4, 12.8)], [(7.4, 12.1), (7.4, 12.8)]]),
    "*": (7.6, [[(4, 4.4), (4, 10.4)], [(1.8, 5.6), (6.2, 9.2)], [(6.2, 5.6), (1.8, 9.2)]]),
    "=": (8.0, [[(1, 6.6), (7, 6.6)], [(1, 9.8), (7, 9.8)]]),
}

_CHAR_MAP = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "−": "–", "‑": "-", "«": '"', "»": '"',
}


def _norm(text):
    return "".join(_CHAR_MAP.get(c, c) for c in text)

import math

_MASK_CACHE = {}


def _glyph_mask(ch, scale, weight):
    """Rasterise one glyph to an alpha mask.  Returns
    (mask, w, h, x_off, y_off) where the mask's pixel (0,0) belongs at
    canvas position (pen_x + x_off, baseline + y_off)."""
    key = (ch, round(scale * 8), round(weight * 8))
    hit = _MASK_CACHE.get(key)
    if hit is not None:
        return hit
    adv, strokes = GLYPHS.get(ch, GLYPHS[" "])
    radius = weight * scale
    x0u, x1u = -2.2, 13.4
    y0u, y1u = -0.6, 16.9
    w = int((x1u - x0u) * scale + 2 * radius + 2)
    h = int((y1u - y0u) * scale + 2 * radius + 2)
    mask = bytearray(w * h)
    # distance-to-segment coverage, per stroke segment
    for stroke in strokes:
        for i in range(len(stroke) - 1):
            ax, ay = stroke[i]
            bx, by = stroke[i + 1]
            ax = (ax - x0u) * scale + radius + 1
            ay = (ay - y0u) * scale + radius + 1
            bx = (bx - x0u) * scale + radius + 1
            by = (by - y0u) * scale + radius + 1
            lo_x = max(0, int(min(ax, bx) - radius - 1))
            hi_x = min(w - 1, int(max(ax, bx) + radius + 1))
            lo_y = max(0, int(min(ay, by) - radius - 1))
            hi_y = min(h - 1, int(max(ay, by) + radius + 1))
            dx = bx - ax
            dy = by - ay
            len2 = dx * dx + dy * dy
            lim = radius + 0.75
            lim2 = lim * lim
            for yy in range(lo_y, hi_y + 1):
                base = yy * w
                for xx in range(lo_x, hi_x + 1):
                    if len2 == 0.0:
                        ddx = xx - ax
                        ddy = yy - ay
                    else:
                        t = ((xx - ax) * dx + (yy - ay) * dy) / len2
                        if t < 0.0:
                            t = 0.0
                        elif t > 1.0:
                            t = 1.0
                        ddx = xx - (ax + t * dx)
                        ddy = yy - (ay + t * dy)
                    d2 = ddx * ddx + ddy * ddy
                    if d2 < lim2:
                        cov = radius + 0.5 - math.sqrt(d2)
                        if cov > 1.0:
                            cov = 1.0
                        if cov > 0.0:
                            v = int(cov * 255 + 0.5)
                            idx = base + xx
                            if v > mask[idx]:
                                mask[idx] = v
    x_off = x0u * scale - radius - 1
    y_off = (y0u - 12.5) * scale - radius - 1
    out = (mask, w, h, x_off, y_off)
    _MASK_CACHE[key] = out
    return out


def text_width(text, size, weight=0.62, tracking=0.0):
    scale = size / 16.0
    total = 0.0
    for ch in _norm(text):
        adv = GLYPHS.get(ch, GLYPHS[" "])[0]
        total += adv * scale + tracking
    if text:
        total -= tracking
    return total


def draw_text(cv, x, baseline, text, size, colour, weight=0.62,
              tracking=0.0, alpha=1.0):
    """Draw one line of text with its baseline at the given y.
    Returns the pen x after the last glyph."""
    scale = size / 16.0
    pen = float(x)
    for ch in _norm(text):
        adv, _strokes = GLYPHS.get(ch, GLYPHS[" "])
        if ch != " ":
            mask, mw, mh, xo, yo = _glyph_mask(ch, scale, weight)
            ox = int(pen + xo + 0.5)
            oy = int(baseline + yo + 0.5)
            for yy in range(mh):
                cy = oy + yy
                if cy < 0 or cy >= cv.h:
                    continue
                mrow = yy * mw
                crow = cy * cv.w
                for xx in range(mw):
                    a = mask[mrow + xx]
                    if a:
                        cx = ox + xx
                        if 0 <= cx < cv.w:
                            cv.blend_px(cx, cy, colour, (a / 255.0) * alpha)
        pen += adv * scale + tracking
    return pen


def draw_text_centered(cv, cx, baseline, text, size, colour, weight=0.62,
                       tracking=0.0, alpha=1.0):
    w = text_width(text, size, weight, tracking)
    return draw_text(cv, cx - w / 2.0, baseline, text, size, colour,
                     weight, tracking, alpha)


def draw_text_right(cv, rx, baseline, text, size, colour, weight=0.62,
                    tracking=0.0, alpha=1.0):
    w = text_width(text, size, weight, tracking)
    return draw_text(cv, rx - w, baseline, text, size, colour,
                     weight, tracking, alpha)


def wrap_text(text, size, weight, max_w, tracking=0.0):
    """Greedy word wrap; returns the list of lines."""
    words = text.split()
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, weight, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_paragraph(cv, x, baseline, text, size, line_h, colour, max_w,
                   weight=0.62, tracking=0.0, alpha=1.0, align="left"):
    """Wrap and draw a paragraph; returns the baseline of its last line."""
    lines = wrap_text(text, size, weight, max_w, tracking)
    y = baseline
    for line in lines:
        if align == "center":
            draw_text_centered(cv, x + max_w / 2.0, y, line, size, colour,
                               weight, tracking, alpha)
        elif align == "right":
            draw_text_right(cv, x + max_w, y, line, size, colour,
                            weight, tracking, alpha)
        else:
            draw_text(cv, x, y, line, size, colour, weight, tracking, alpha)
        y += line_h
    return y - line_h

# ---------------------------------------------------------------- page

PAPER = (247, 243, 233)
PAPER_DIM = (238, 231, 214)
INK = (26, 24, 20)
INK_SOFT = (92, 87, 76)
RULE_SOFT = (178, 170, 152)
RED = (172, 30, 38)
RED_DARK = (128, 22, 30)
GOLD = (198, 148, 44)

MX = 34            # page margin
RX = W - MX        # right edge of the content column
CW = RX - MX       # content width


def outline(cv, x, y, w, h, colour, t):
    cv.rect(x, y, w, t, colour)
    cv.rect(x, y + h - t, w, t, colour)
    cv.rect(x, y, t, h, colour)
    cv.rect(x + w - t, y, t, h, colour)


def _trail(cv, points, r_head, r_tail, colour, glow):
    """A tapering trail along a polyline, with a soft glow pass."""
    # total length for the taper
    segs = []
    total = 0.0
    for i in range(len(points) - 1):
        ax, ay = points[i]
        bx, by = points[i + 1]
        ln = math.hypot(bx - ax, by - ay)
        segs.append((ax, ay, bx, by, ln))
        total += ln
    done = 0.0
    for ax, ay, bx, by, ln in segs:
        steps = max(2, int(ln / 7))
        for s in range(steps):
            t0 = done + ln * s / steps
            t1 = done + ln * (s + 1) / steps
            xa = ax + (bx - ax) * s / steps
            ya = ay + (by - ay) * s / steps
            xb = ax + (bx - ax) * (s + 1) / steps
            yb = ay + (by - ay) * (s + 1) / steps
            r0 = r_head + (r_tail - r_head) * (t0 / total)
            r1 = r_head + (r_tail - r_head) * (t1 / total)
            r = (r0 + r1) / 2.0
            cv.segment(xa, ya, xb, yb, r * 2.7, glow, 0.16)
            cv.segment(xa, ya, xb, yb, r, colour, 0.92)
        done += ln
    hx, hy = points[-1]
    cv.disc(hx, hy, r_tail + 1.6, (255, 240, 210), 0.95)


def _impact(cv, x, y):
    cv.disc(x, y - 2, 17, (255, 140, 50), 0.30)
    cv.disc(x, y - 2, 8, (255, 170, 70), 0.45)
    cv.disc(x, y - 2, 4.2, (255, 226, 170), 0.95)
    for ang in range(8):
        a = ang * 0.785 + 0.35
        x2 = x + math.cos(a) * (11 + (ang % 3) * 3.5)
        y2 = y - 2 + math.sin(a) * (8 + (ang % 3) * 2.5)
        cv.segment(x, y - 2, x2, y2, 1.25, (255, 196, 110), 0.85)
    cv.disc(x - 3, y - 15, 6.5, (96, 96, 102), 0.16)
    cv.disc(x + 5, y - 22, 9.5, (96, 96, 102), 0.13)


def hero_scene(cv, x, y, w, h):
    """Night over the border fields: missile trails coming down."""
    import random
    sky_bot = y + int(h * 0.70)
    cv.vgrad(x, y, w, sky_bot - y, (9, 14, 32), (54, 62, 90))
    cv.vgrad(x, sky_bot, w, y + h - sky_bot, (34, 38, 30), (15, 17, 15))
    rng = random.Random(20261121)
    for _ in range(90):
        sx = x + rng.uniform(6, w - 6)
        sy = y + rng.uniform(6, (sky_bot - y) * 0.82)
        cv.disc(sx, sy, rng.uniform(0.55, 1.45), (235, 240, 255),
                rng.uniform(0.25, 0.9))
    cv.disc(x + w - 62, y + 44, 27, (240, 244, 252), 0.14)
    cv.disc(x + w - 62, y + 44, 17, (233, 237, 245), 0.95)
    cv.disc(x + w - 70, y + 39, 3.2, (203, 209, 220), 0.8)
    cv.disc(x + w - 54, y + 52, 2.4, (203, 209, 220), 0.8)
    hills = [(x, sky_bot), (x + 74, sky_bot - 16), (x + 164, sky_bot - 6),
             (x + 254, sky_bot - 20), (x + 344, sky_bot - 8),
             (x + 434, sky_bot - 18), (x + w, sky_bot - 2), (x + w, sky_bot)]
    cv.polygon(hills, (37, 43, 51))
    cv.stroke_polygon(hills, (37, 43, 51), 1.2)
    for gy in (sky_bot + 12, sky_bot + 24, sky_bot + 35):
        cv.segment(x + 14, gy, x + w - 14, gy, 0.7, (126, 134, 112), 0.20)
    sil = (9, 11, 15)
    cv.rect(x + 34, sky_bot - 22, 34, 22, sil)
    cv.polygon([(x + 30, sky_bot - 22), (x + 51, sky_bot - 36), (x + 72, sky_bot - 22)], sil)
    cv.rect(x + 80, sky_bot - 14, 24, 14, sil)
    cv.polygon([(x + 77, sky_bot - 14), (x + 92, sky_bot - 25), (x + 107, sky_bot - 14)], sil)
    cv.rect(x + 212, sky_bot - 32, 10, 32, sil)
    cv.polygon([(x + 209, sky_bot - 32), (x + 217, sky_bot - 48), (x + 225, sky_bot - 32)], sil)
    cv.disc(x + 128, sky_bot - 16, 13, (13, 19, 15), 0.95)
    cv.rect(x + 126, sky_bot - 8, 4, 9, sil)
    ground = sky_bot + 4
    _trail(cv, [(x + w - 4, y + 8), (x + 394, y + 62), (x + 304, y + 122),
                (x + 238, ground)], 1.1, 3.1, (255, 216, 152), (255, 150, 60))
    _trail(cv, [(x + w - 44, y + 62), (x + 420, y + 106), (x + 372, y + 158),
                (x + 352, ground + 6)], 1.0, 2.9, (255, 216, 152), (255, 150, 60))
    _trail(cv, [(x + w - 2, y + 130), (x + 380, y + 156), (x + 250, y + 176),
                (x + 132, ground - 2)], 0.8, 2.2, (214, 226, 244), (150, 170, 220))
    _impact(cv, x + 238, ground)
    _impact(cv, x + 352, ground + 6)
    _impact(cv, x + 132, ground - 2)


FIGURES = [
    ("2+1", "Russian cruise missiles and a drone down in Poland"),
    ("3", "impact sites found in south-eastern Poland"),
    ("-3.7%", "the S&P 500's Friday fall into correction"),
    ("$7.25bn", "Bayer's settlement of the Roundup lawsuits"),
    ("6.7", "magnitude of the earthquake in central Peru"),
    ("8 yrs", "BepiColombo's journey from launch to Mercury"),
]

STORIES = [
    ("MARKETS", "AI sell-off puts Wall Street in correction",
     "The S&P 500 fell 3.7% and the Nasdaq over 5% as investors fled AI "
     "stocks. Anthropic slid 11% a day after its debut."),
    ("BRUSSELS", "UK and EU sign landmark post-Brexit deals",
     "Food trade, carbon markets and youth mobility: PM Andy "
     "Burnham signs three landmark agreements in Brussels."),
    ("SHENZHEN", "Trump, Xi and Putin end historic first summit",
     "The first trilateral summit closes with a joint statement on "
     "nuclear war, oil and UN reform — and few concrete results."),
    ("IRAN", "Trump: Iran war could run into 2027",
     "'We have time,' Trump says near the war's ninth month. "
     "Tehran says it still wants a diplomatic end to the war."),
    ("ANTALYA", "COP31 in overtime as draft drops fossil fuels",
     "Nearly 200 nations quarrel after a slimmed draft deal deletes "
     "fossil fuels and a $120bn adaptation goal."),
    ("SPACE", "BepiColombo reaches Mercury after 8 years",
     "The European-Japanese probe enters orbit around the innermost "
     "planet — only the second craft ever to do so."),
    ("RIYADH", "Saudi-led coalition downs missiles over Riyadh",
     "Three ballistic missiles were destroyed over the capital; the "
     "coalition then struck the Houthi port of Hodeidah."),
    ("NIGERIA", "Funeral boat capsizes: 4 dead, 24 rescued",
     "An overcrowded boat carrying hundreds to a burial overturned in "
     "Bayelsa. Police say searches are continuing."),
    ("PERU", "Magnitude 6.7 earthquake shakes central Peru",
     "The deep tremor near Carhuamayo was felt strongly in Lima. "
     "Officials report no casualties or damage so far."),
    ("CALIFORNIA", "Jury convicts Palisades Fire arsonist",
     "A Los Angeles jury found Jonathan Rinderknecht guilty of igniting "
     "the fire that tore through Pacific Palisades."),
    ("HEALTH", "Cancer pill hailed as pancreatic breakthrough",
     "In a trial of daraxonrasib, tumours stopped growing in nearly all "
     "patients — 'the biggest breakthrough in decades'."),
    ("BUSINESS", "Bayer's $7.25bn Roundup deal approved",
     "The deal settles over 65,000 lawsuits claiming Roundup causes "
     "cancer, capping Bayer's exposure."),
]


def draw_page():
    cv = Canvas(W, H, PAPER)
    outline(cv, 12, 12, W - 24, H - 24, INK, 2.4)
    outline(cv, 19, 19, W - 38, H - 38, INK, 0.9)

    # top strip
    draw_text(cv, MX, 48, "VOL. I · No. 21", 13.5, INK_SOFT, 0.66, 2.2)
    draw_text_right(cv, RX, 48, "ONE PAGE — THE WHOLE DAY", 13.5, INK_SOFT, 0.66, 2.2)
    cv.rect(MX, 58, CW, 1.2, INK)

    # masthead
    draw_text_centered(cv, W / 2, 128, "THE WORLD TODAY", 102, INK, 1.5, 1.0)
    cv.rect(MX, 142, CW, 3.5, INK)
    cv.rect(MX, 149, CW, 1.1, INK)

    # date band
    cv.rect(MX, 158, CW, 38, INK)
    draw_text(cv, MX + 14, 184, "SATURDAY 21 NOVEMBER 2026", 21, PAPER, 1.0, 1.2)
    draw_text_right(cv, RX - 14, 184, "THE WORLD'S NEWS IN ONE IMAGE", 13.5,
                    PAPER, 0.8, 1.6)

    # ---- hero
    hy = 212
    cv.rect(MX, hy + 2, 10, 10, RED)
    draw_text(cv, MX + 18, hy + 12, "POLAND · NATO", 17, RED, 1.0, 2.4)
    draw_text(cv, MX, hy + 54, "RUSSIAN MISSILES", 52, INK, 1.15)
    pen = draw_text(cv, MX, hy + 116, "FALL ON ", 52, INK, 1.15)
    draw_text(cv, pen, hy + 116, "POLAND", 52, RED_DARK, 1.15)
    deck = ("Two Russian cruise missiles and a jet-powered drone crashed "
            "in south-eastern Poland during Moscow's biggest barrage of "
            "the month on Ukraine. 'It does not look like an accident,' "
            "said Prime Minister Donald Tusk, calling it a deliberate "
            "provocation. NATO's chief flies to Warsaw today.")
    draw_paragraph(cv, MX, hy + 160, deck, 17.5, 23, INK, 436, 0.6)

    panel_x, panel_y, panel_w, panel_h = 486, hy, 504, 282
    hero_scene(cv, panel_x, panel_y, panel_w, panel_h - 42)
    cv.rect(panel_x, panel_y + panel_h - 42, panel_w, 42, (10, 12, 17))
    caption = ("Two Kh-101 cruise missiles and a jet-powered drone came "
               "down near villages in south-eastern Poland. No one in "
               "Poland was hurt.")
    draw_paragraph(cv, panel_x + 12, panel_y + panel_h - 42 + 17, caption,
                   12, 15.5, PAPER, panel_w - 24, 0.58)
    outline(cv, panel_x, panel_y, panel_w, panel_h, INK, 2)

    # ---- figures band
    fy = 508
    cv.rect(MX, fy, CW, 1.2, INK)
    cell_w = CW / 6.0
    for i, (num, label) in enumerate(FIGURES):
        cx = MX + i * cell_w
        if i:
            cv.rect(cx, fy + 10, 0.9, 62, RULE_SOFT)
        draw_text_centered(cv, cx + cell_w / 2, fy + 36, num, 31, RED_DARK, 1.15)
        draw_paragraph(cv, cx + 7, fy + 56, label, 11.8, 14.5, INK, cell_w - 14,
                       0.58, align="center")
    cv.rect(MX, fy + 82, CW, 1.2, INK)

    # ---- story grid: 3 columns x 4 rows
    gy = 606
    draw_text(cv, MX, gy + 14, "AROUND THE WORLD", 14, RED, 1.0, 2.2)
    draw_text_right(cv, RX, gy + 14, "TWELVE STORIES IN BRIEF", 11.5,
                    INK_SOFT, 0.7, 1.8)
    cv.rect(MX, gy + 22, CW, 1.0, RULE_SOFT)
    grid_y = gy + 30
    row_h = 76
    col_gap = 20
    col_w = (CW - 2 * col_gap) / 3.0
    for idx, (tag, head, body) in enumerate(STORIES):
        r, c = divmod(idx, 3)
        x = MX + c * (col_w + col_gap)
        y = grid_y + r * row_h
        if c:
            cv.rect(x - col_gap / 2, y + 4, 0.9, row_h - 10, RULE_SOFT)
        if r:
            cv.rect(x, y - 4, col_w, 0.9, RULE_SOFT)
        draw_text(cv, x, y + 13, tag, 11.5, RED, 1.0, 1.6)
        draw_text(cv, x, y + 34, head, 16, INK, 1.0)
        lines = wrap_text(body, 12.6, 0.58, col_w)[:2]
        by = y + 52
        for line in lines:
            draw_text(cv, x, by, line, 12.6, INK, 0.58)
            by += 15.5

    # ---- ticker + footer
    ty = grid_y + 4 * row_h + 12
    cv.rect(MX, ty, CW, 1.2, INK)
    pen = draw_text(cv, MX, ty + 24, "ALSO IN THE NEWS", 12.8, RED, 1.0, 1.2)
    ticker = ("EU agrees €1bn more for Ukraine's drones and air defences"
              "  •  Iraqi forces enter Jurf al-Sakhar after 12 years"
              "  •  Fiona, Cincinnati's beloved hippo, dies")
    draw_text(cv, pen + 12, ty + 24, ticker, 12.8, INK, 0.58)
    draw_text_centered(
        cv, W / 2, ty + 50,
        "Compiled from reports by Reuters, the Associated Press, BBC News, "
        "The Guardian, ISW, ESA and the USGS · Drawn entirely by a computer "
        "program — no photographs", 11, INK_SOFT, 0.55)
    return cv


# ---------------------------------------------------------------- png

def encode_png(cv):
    raw = bytearray()
    row = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * row:(y + 1) * row]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    cv = draw_page()
    data = encode_png(cv)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    print("wrote %s (%d bytes)" % (path, len(data)))


if __name__ == "__main__":
    main()
