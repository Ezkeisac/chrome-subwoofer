#!/usr/bin/env python3
"""The Q(tc) fader, as an animated GIF. Stdlib only — the LZW encoder is below.

    python3 scripts/sweep_qtc.py [--out images/qtc-sweep.gif]

A README cannot carry a slider: GitHub strips scripts, styles and form controls. So the
fader plays itself. The handle travels a drawn track from Q 0.50 to 1.20 and back while
the response curve rises into its peak, with Butterworth (0.707) and the build's own
damping (0.799) marked on the track as ticks.

One image, and it carries the decision the whole enclosure turns on: a Q slightly above
Butterworth, accepted rather than corrected, because a small room contributes
low-frequency gain of its own.

Everything is drawn into a 4-colour indexed bitmap and compressed here, because the
repository has no dependencies and is not going to acquire any.
"""
import argparse, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import model                                                        # noqa: E402

W, H = 560, 280
L, R, T, B = 48, 14, 16, 64
FMIN, FMAX, DMIN, DMAX = 12.0, 200.0, -30.0, 10.0
FC = 40.27                      # calculations/driver-parameters.csv
Q_LO, Q_HI, Q_BUILD, Q_BUTTER = 0.50, 1.20, 0.799, 0.707
FRAMES, DELAY_CS = 28, 7        # per half-sweep; ping-pong, so 2n-2 frames total

PAL = [(0x0d, 0x11, 0x17),      # 0 paper
       (0x2b, 0x31, 0x38),      # 1 grid and track
       (0x56, 0xa8, 0xe0),      # 2 curve
       (0xe0, 0x9a, 0x4f)]      # 3 handle, ticks, the build's mark


class Bits:
    def __init__(self): self.b = bytearray(); self.cur = 0; self.n = 0
    def write(self, code, size):
        self.cur |= code << self.n; self.n += size
        while self.n >= 8:
            self.b.append(self.cur & 0xFF); self.cur >>= 8; self.n -= 8
    def done(self):
        if self.n: self.b.append(self.cur & 0xFF)
        return bytes(self.b)


def lzw(px, mcs):
    clear, eoi = 1 << mcs, (1 << mcs) + 1
    size = mcs + 1
    table = {bytes([i]): i for i in range(clear)}
    nxt = eoi + 1
    out = Bits(); out.write(clear, size)
    buf = b''
    for p in px:
        nb = buf + bytes([p])
        if nb in table:
            buf = nb; continue
        out.write(table[buf], size)
        table[nb] = nxt
        if nxt == (1 << size) and size < 12:
            size += 1
        nxt += 1
        if nxt == 4096:
            out.write(clear, size)
            table = {bytes([i]): i for i in range(clear)}
            nxt = eoi + 1; size = mcs + 1
        buf = bytes([p])
    if buf: out.write(table[buf], size)
    out.write(eoi, size)
    return out.done()


def blocks(data):
    o = bytearray()
    for i in range(0, len(data), 255):
        c = data[i:i + 255]; o.append(len(c)); o += c
    o.append(0)
    return bytes(o)


def px_(hz):
    return L + (math.log(hz) - math.log(FMIN)) / (math.log(FMAX) - math.log(FMIN)) * (W - L - R)


def py_(db):
    return T + (DMAX - db) / (DMAX - DMIN) * (H - T - B)


def frame(q):
    f = bytearray([0]) * (W * H)
    def put(x, y, c):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < W and 0 <= y < H: f[y * W + x] = c
    def line(x0, y0, x1, y1, c, wd=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / n
            for o in range(wd):
                put(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + o, c)

    for v in (20, 30, 50, 80, 120, 200):
        line(px_(v), T, px_(v), H - B, 1)
    for v in (10, 0, -10, -20, -30):
        line(L, py_(v), W - R, py_(v), 1)

    prev = None
    steps = 240
    for i in range(steps + 1):
        hz = FMIN * (FMAX / FMIN) ** (i / steps)
        p = (px_(hz), py_(model.response_db(hz, FC, q)))
        if prev: line(prev[0], prev[1], p[0], p[1], 2, 2)
        prev = p

    ty, tx0, tx1 = H - 30, L, W - R
    line(tx0, ty, tx1, ty, 1, 3)
    for qq in (Q_BUTTER, Q_BUILD):
        x = tx0 + (qq - Q_LO) / (Q_HI - Q_LO) * (tx1 - tx0)
        line(x, ty - 8, x, ty + 10, 3, 2)
    hx = tx0 + (q - Q_LO) / (Q_HI - Q_LO) * (tx1 - tx0)
    for dy in range(-11, 12):
        line(hx - 4, ty + dy, hx + 4, ty + dy, 3)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join('images', 'qtc-sweep.gif'))
    a = ap.parse_args()

    qs = [Q_LO + (Q_HI - Q_LO) * i / (FRAMES - 1) for i in range(FRAMES)]
    qs += qs[-2:0:-1]

    g = bytearray(b'GIF89a')
    g += bytes([W & 255, W >> 8, H & 255, H >> 8, 0xF1, 0, 0])
    for r, gg, b in PAL: g += bytes([r, gg, b])
    g += b'\x21\xFF\x0bNETSCAPE2.0\x03\x01\x00\x00\x00'
    for q in qs:
        g += bytes([0x21, 0xF9, 4, 0x04, DELAY_CS & 255, DELAY_CS >> 8, 0, 0])
        g += bytes([0x2C, 0, 0, 0, 0, W & 255, W >> 8, H & 255, H >> 8, 0])
        g += bytes([2]) + blocks(lzw(frame(q), 2))
    g += b'\x3B'

    out = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(bytes(g))
    print('%s  %d frames, %.0f KB  (Q %.2f..%.2f, Fc %.2f Hz)'
          % (out, len(qs), len(g) / 1024.0, Q_LO, Q_HI, FC))
    return 0


if __name__ == '__main__':
    sys.exit(main())
