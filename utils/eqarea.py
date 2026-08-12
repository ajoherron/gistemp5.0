"""Equal-area grid geometry for GISTEMP (Sergej's 8000-cell grid).

Ported from gistemp4.0/steps/eqarea.py. Pure geometry — no pipeline deps.
"""

import itertools
import math

band_altitude = [1, 0.9, 0.7, 0.4, 0]
band_boxes    = [4, 8, 12, 16]


def lerp(x, y, p):
    p = float(p)
    return y * p + (1 - p) * x


def northern40():
    for band in range(len(band_boxes)):
        n = band_boxes[band]
        for i in range(n):
            lats = 180 / math.pi * math.asin(band_altitude[band + 1])
            latn = 180 / math.pi * math.asin(band_altitude[band])
            lonw = -180 + 360 * float(i) / n
            lone = -180 + 360 * float(i + 1) / n
            yield (lats, latn, lonw, lone)


def southern40():
    n = list(northern40())
    i = 0
    band = []
    for w in band_boxes:
        band.append(n[i:i + w])
        i += w
    band.reverse()
    s = []
    for x in band:
        s.extend(x)
    for x in s:
        yield (-x[1], -x[0], x[2], x[3])


def grid():
    return itertools.chain(northern40(), southern40())


def gridsub():
    def subgen(box):
        alts = math.sin(box[0] * math.pi / 180)
        altn = math.sin(box[1] * math.pi / 180)
        for y in range(10):
            s = 180 * math.asin(lerp(alts, altn, y * 0.1)) / math.pi
            n = 180 * math.asin(lerp(alts, altn, (y + 1) * 0.1)) / math.pi
            for x in range(10):
                w = lerp(box[2], box[3], x * 0.1)
                e = lerp(box[2], box[3], (x + 1) * 0.1)
                yield (s, n, w, e)

    for box in grid():
        yield (box, subgen(box))


def grid8k():
    for box in gridsub():
        for subbox in box[1]:
            yield subbox


def centre(box):
    sinc = 0.5 * (math.sin(box[0] * math.pi / 180) + math.sin(box[1] * math.pi / 180))
    return math.asin(sinc) * 180 / math.pi, 0.5 * (box[2] + box[3])
