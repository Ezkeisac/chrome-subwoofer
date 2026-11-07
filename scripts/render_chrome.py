#!/usr/bin/env python3
"""The cabinet turning in chrome, as an animated GIF. Stdlib only.

    python3 scripts/render_chrome.py [--out images/chrome-turntable.gif]
    python3 scripts/render_chrome.py --still 0 --out frame.png

GitHub draws an STL in one flat blue and offers no way to change it, and a README cannot
carry a script. So the finish is computed here and shipped as an image: the same geometry
as images/enclosure.stl, a mirror reflecting a bright room, the driver in black rubber.

A mirror has no colour of its own, so every pixel is the room seen along a reflected ray.
No part of that room may be dark: a flat face seen from above shows what is below it, and
a dark floor turns the whole cabinet black. A slight vertical tilt of the normal makes the
reflected horizon waver, as it does on vinyl laid over a sanded panel.

The frames are cold greys, so one 256-entry palette holds them without dithering.
"""
import argparse, math, multiprocessing, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import make_stl                                                     # noqa: E402
from make_banner import write_png                                   # noqa: E402
from sweep_qtc import lzw                                           # noqa: E402

W, H, SS = 360, 480, 2          # output size, and samples per pixel along each axis
FRAMES = 40
DELAY_CS = 9                    # hundredths of a second per frame
START = -0.62                   # radians: opens three-quarter on, driver towards the reader
AXIS_Z = 140.0                  # turns about the cabinet's own centre
EYE = (0.0, 110.0, -1720.0)
FOCAL = 1.98                    # relative to image height


def room():
    """The surround: bright above and below, one thin dark horizon, panels all round."""
    w, h = 1024, 512
    stops = [(0, 255), (.4, 206), (.485, 153), (.5, 67), (.515, 153), (.62, 196), (1, 241)]

    def grad(v):
        for (a, la), (b, lb) in zip(stops, stops[1:]):
            if v <= b:
                return la + (lb - la) * (v - a) / (b - a)
        return stops[-1][1]
    img = [[grad(y / (h - 1.0))] * w for y in range(h)]

    def rect(x0, y0, x1, y1, lum):
        for y in range(int(y0), int(y1)):
            row = img[y]
            for x in range(int(x0), int(x1)):
                row[x % w] = lum
    for i in range(8):
        u = i * 128 + 20
        rect(u, 90, u + 60, 235, 255)
        rect(u + 64, 280, u + 109, 395, 255)
        rect(u + 75, 75, u + 83, 240, 95)
        rect(u + 10, 270, u + 17, 400, 95)
    r = 5
    for _ in range(2):              # two box passes, so the panels have soft edges
        img = [[sum(row[(x + k) % w] for k in range(-r, r + 1)) / (2 * r + 1)
                for x in range(w)] for row in img]
        cols = list(zip(*img))
        cols = [[sum(c[min(h - 1, max(0, y + k))] for k in range(-r, r + 1)) / (2 * r + 1)
                 for y in range(h)] for c in cols]
        img = [list(row) for row in zip(*cols)]
    return img


def load():
    """Triangles in the build frame: y up, baffle at z = 0 facing -z, as make_stl draws it."""
    txt = open(os.path.join(ROOT, 'images', 'enclosure.stl'), encoding='utf-8').read()
    nums = [float(x) for x in re.findall(r'vertex (\S+) (\S+) (\S+)', txt) for x in x]
    pts = [(-nums[i], nums[i + 2], nums[i + 1]) for i in range(0, len(nums), 3)]
    d = make_stl.dims()
    cy = make_stl.margin_centre(d['box external width'], d['box external height'])[1]
    rad = d['flange outer diameter'] / 2.0
    tris, acc = [], {}
    for i in range(0, len(pts), 3):
        a, b, c = pts[i:i + 3]
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        m = math.sqrt(sum(q * q for q in n)) or 1.0
        n = tuple(q / m for q in n)
        cx, cyy, cz = [(a[k] + b[k] + c[k]) / 3.0 for k in range(3)]
        rubber = math.hypot(cx, cyy - cy) <= rad + .5 and cz < 60
        tris.append((a, b, c, n, rubber))
        if rubber:
            for p in (a, b, c):
                s = acc.setdefault(tuple(round(q, 1) for q in p), [0.0, 0.0, 0.0])
                for k in range(3):
                    s[k] += n[k]
    smooth = {}
    for k, s in acc.items():            # rubber is smooth, chrome keeps its corners
        m = math.sqrt(sum(q * q for q in s)) or 1.0
        smooth[k] = tuple(q / m for q in s)
    return tris, smooth


def basis():
    f = [-e for e in EYE]
    m = math.sqrt(sum(q * q for q in f))
    f = [q / m for q in f]
    r = (f[2], 0.0, -f[0])              # right, level with the floor
    m = math.sqrt(sum(q * q for q in r))
    r = [q / m for q in r]
    u = (r[2] * f[1] - r[1] * f[2], r[0] * f[2] - r[2] * f[0], r[1] * f[0] - r[0] * f[1])
    u = [-q for q in u] if u[1] < 0 else list(u)
    return f, r, u


def render(i):
    """One frame at SS x the output size, boxed down to palette indices."""
    tw, th = W * SS, H * SS
    ang = START + 2 * math.pi * i / FRAMES
    ca, sa = math.cos(ang), math.sin(ang)
    fwd, right, up = BASIS
    foc = FOCAL * th
    ex, ey, ez = EYE
    lum = [[74.0 - 40.0 * y / th] * tw for y in range(th)]    # the backdrop
    zb = [[1e18] * tw for _ in range(th)]
    rw = len(ROOM[0])
    rh = len(ROOM)

    def turn(p):
        x, y, z = p[0], p[1], p[2] - AXIS_Z
        return x * ca + z * sa, y, -x * sa + z * ca

    def proj(p):
        d = (p[0] - ex, p[1] - ey, p[2] - ez)
        z = d[0] * fwd[0] + d[1] * fwd[1] + d[2] * fwd[2]
        x = d[0] * right[0] + d[1] * right[1] + d[2] * right[2]
        y = d[0] * up[0] + d[1] * up[1] + d[2] * up[2]
        return tw / 2.0 + foc * x / z, th / 2.0 - foc * y / z, z

    for a0, b0, c0, n0, rubber in TRIS:
        a, b, c = turn(a0), turn(b0), turn(c0)
        n = (n0[0] * ca + n0[2] * sa, n0[1], -n0[0] * sa + n0[2] * ca)
        if n[0] * (a[0] - ex) + n[1] * (a[1] - ey) + n[2] * (a[2] - ez) >= 0:
            continue                    # faces away
        pa, pb, pc = proj(a), proj(b), proj(c)
        area = (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])
        if abs(area) < 1e-6:
            continue
        x0 = max(0, int(min(pa[0], pb[0], pc[0])))
        x1 = min(tw - 1, int(max(pa[0], pb[0], pc[0])) + 1)
        y0 = max(0, int(min(pa[1], pb[1], pc[1])))
        y1 = min(th - 1, int(max(pa[1], pb[1], pc[1])) + 1)
        plane = n[0] * (a[0] - ex) + n[1] * (a[1] - ey) + n[2] * (a[2] - ez)
        if rubber:
            sn = [SMOOTH[tuple(round(q, 1) for q in p)] for p in (a0, b0, c0)]
            sn = [(q[0] * ca + q[2] * sa, q[1], -q[0] * sa + q[2] * ca) for q in sn]
        for y in range(y0, y1 + 1):
            py = y + .5
            ry = zb[y]
            rl = lum[y]
            for x in range(x0, x1 + 1):
                px = x + .5
                w0 = ((pb[0] - px) * (pc[1] - py) - (pb[1] - py) * (pc[0] - px)) / area
                w1 = ((pc[0] - px) * (pa[1] - py) - (pc[1] - py) * (pa[0] - px)) / area
                w2 = 1.0 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0:
                    continue
                sx, sy = (px - tw / 2.0) / foc, (th / 2.0 - py) / foc
                dx = fwd[0] + sx * right[0] + sy * up[0]
                dy = fwd[1] + sx * right[1] + sy * up[1]
                dz = fwd[2] + sx * right[2] + sy * up[2]
                den = n[0] * dx + n[1] * dy + n[2] * dz
                if den == 0:
                    continue
                t = plane / den
                if t >= ry[x]:
                    continue
                ry[x] = t
                m = math.sqrt(dx * dx + dy * dy + dz * dz)
                dx, dy, dz = dx / m, dy / m, dz / m
                if rubber:
                    nx = w0 * sn[0][0] + w1 * sn[1][0] + w2 * sn[2][0]
                    ny = w0 * sn[0][1] + w1 * sn[1][1] + w2 * sn[2][1]
                    nz = w0 * sn[0][2] + w1 * sn[1][2] + w2 * sn[2][2]
                    m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
                    nx, ny, nz = nx / m, ny / m, nz / m
                else:
                    wx = ex + t * dx * m
                    wy = ey + t * dy * m
                    wz = ez + t * dz * m - 0.0
                    ox = wx * ca - wz * sa      # back to the cabinet's own frame
                    oz = wx * sa + wz * ca + AXIS_Z
                    s = ox + oz
                    tilt = (.020 * math.sin(wy * .052 + 1.4 * math.sin(s * .012))
                            + .011 * math.sin(wy * .131 + s * .021 + 1.)
                            + .005 * math.sin(wy * .29 - s * .037 + 2.))
                    nx, ny, nz = n[0], n[1] + tilt, n[2]
                    m2 = math.sqrt(nx * nx + ny * ny + nz * nz)
                    nx, ny, nz = nx / m2, ny / m2, nz / m2
                dn = dx * nx + dy * ny + dz * nz
                rx, ry_, rz = dx - 2 * dn * nx, dy - 2 * dn * ny, dz - 2 * dn * nz
                v = int((.5 - math.asin(max(-1.0, min(1.0, ry_))) / math.pi) * (rh - 1))
                u = int((math.atan2(rz, rx) / (2 * math.pi) + .5) * (rw - 1))
                seen = ROOM[v][u]
                if rubber:
                    diff = max(0.0, .3 * nx + .62 * ny - .72 * nz)
                    fres = (1.0 + dn) ** 4
                    rl[x] = 11.0 + 30.0 * diff + seen * (.05 + .42 * fres)
                else:
                    rl[x] = seen * .94

    out = bytearray(W * H)
    k = SS * SS
    for y in range(H):
        rows = lum[y * SS:(y + 1) * SS]
        for x in range(W):
            s = 0.0
            for r in rows:
                s += sum(r[x * SS:(x + 1) * SS])
            out[y * W + x] = max(0, min(255, int(s / k)))
    return bytes(out)


def blocks(data):
    out = bytearray()
    for i in range(0, len(data), 255):
        part = data[i:i + 255]
        out += bytes([len(part)]) + part
    return bytes(out) + b'\x00'


def tint(l):
    return int(l * .955), int(l * .975), l      # cold, as the concept's chrome runs


def encode(i):
    return lzw(render(i), 8)


def init():
    global ROOM, TRIS, SMOOTH, BASIS
    ROOM = room()
    TRIS, SMOOTH = load()
    BASIS = basis()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'images', 'chrome-turntable.gif'))
    ap.add_argument('--still', type=int, help='write this one frame as a PNG instead')
    a = ap.parse_args()
    init()
    if a.still is not None:
        px = render(a.still)
        rgb = bytearray()
        for l in px:
            rgb += bytes(tint(l))
        write_png(a.out, W, H, rgb)
        print('wrote %s' % a.out)
        return 0
    with multiprocessing.get_context('fork').Pool() as pool:
        frames = pool.map(encode, range(FRAMES))
    g = bytearray(b'GIF89a' + struct.pack('<HHBBB', W, H, 0xF7, 0, 0))
    for l in range(256):
        g += bytes(tint(l))
    g += b'\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00'         # loop for ever
    for data in frames:
        g += b'\x21\xF9\x04\x00' + struct.pack('<H', DELAY_CS) + b'\x00\x00'
        g += b'\x2C' + struct.pack('<HHHHB', 0, 0, W, H, 0)
        g += b'\x08' + blocks(data)
    g += b'\x3B'
    open(a.out, 'wb').write(g)
    print('%s  %d frames, %.0f KB  (%d x %d)' % (a.out, FRAMES, len(g) / 1024.0, W, H))
    return 0


if __name__ == '__main__':
    sys.exit(main())
