#!/usr/bin/env python3
"""Emit the enclosure as ASCII STL, from the dimensions CSV. Stdlib only.

    python3 scripts/make_stl.py [--segments 36] [--out images/enclosure.stl]

GitHub renders a fenced `stl` block, and an .stl file in a repository, as an
interactive viewer with wireframe, surface-angle and solid modes. So the cabinet can be
shown rather than photographed, and turned rather than described.

Geometry comes from calculations/box-dimensions.csv and nowhere else, so the model and
the paper cannot disagree. The baffle carries the rebate: a 257 mm shoulder 6 mm deep
for the driver flange, stepping to the 233 mm through-hole.
"""
import argparse, csv, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def dims():
    p = os.path.join(ROOT, 'calculations', 'box-dimensions.csv')
    with open(p, newline='', encoding='utf-8') as fh:
        return {r['item']: float(r['mm']) for r in csv.DictReader(fh)}


def tri(a, b, c, out):
    ux, uy, uz = (b[i] - a[i] for i in range(3))
    vx, vy, vz = (c[i] - a[i] for i in range(3))
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    m = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    out.append('  facet normal %.6f %.6f %.6f\n    outer loop' % (nx / m, ny / m, nz / m))
    for v in (a, b, c):
        out.append('      vertex %.3f %.3f %.3f' % v)
    out.append('    endloop\n  endfacet')


def quad(a, b, c, d, out):
    tri(a, b, c, out); tri(a, c, d, out)


def rect_perimeter(w, h, n):
    """n points anticlockwise around a w x h rectangle centred on the origin."""
    per = 2.0 * (w + h)
    pts = []
    for i in range(n):
        t = per * i / n
        if t < w:            pts.append((-w / 2 + t, -h / 2))
        elif t < w + h:      pts.append((w / 2, -h / 2 + (t - w)))
        elif t < 2 * w + h:  pts.append((w / 2 - (t - w - h), h / 2))
        else:                pts.append((-w / 2, h / 2 - (t - 2 * w - h)))
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--segments', type=int, default=36)
    ap.add_argument('--out', default=os.path.join('images', 'enclosure.stl'))
    a = ap.parse_args()
    d = dims()

    W = d['box external width']          # 318, fixed by R3
    Hh = d['box external height']        # 661
    D = d['box external length']         # 280, fixed by R3
    wall = d['box wall thickness']       # 19
    r_out = d['flange outer diameter'] / 2.0     # 128.5, the rebate
    r_in = d['basket hole diameter'] / 2.0       # 116.5, the through-hole
    rebate = d['flange thickness']               # 6

    n = a.segments
    o = ['solid enclosure']
    # The baffle is the front face at z = 0; the body runs to z = D, so the front's
    # outward normal is -z and its quads wind accordingly.
    peri = rect_perimeter(W, Hh, n)
    # Circle points are placed at the ANGLE of each perimeter point, not at uniform
    # angles. Pairing them by index instead twists every strip across the face: the
    # first rectangle corner would be joined to a circle point on the opposite side.
    ang = [math.atan2(y, x) for x, y in peri]
    circ = lambda r: [(r * math.cos(t), r * math.sin(t)) for t in ang]
    co, ci = circ(r_out), circ(r_in)

    # front face: rectangle minus the rebate circle
    for i in range(n):
        j = (i + 1) % n
        quad((peri[i][0], peri[i][1], 0.0), (co[i][0], co[i][1], 0.0),
             (co[j][0], co[j][1], 0.0), (peri[j][0], peri[j][1], 0.0), o)
    # rebate wall, then its shoulder, then the through-hole wall
    for i in range(n):
        j = (i + 1) % n
        quad((co[i][0], co[i][1], 0.0), (co[j][0], co[j][1], 0.0),
             (co[j][0], co[j][1], rebate), (co[i][0], co[i][1], rebate), o)
        quad((co[i][0], co[i][1], rebate), (co[j][0], co[j][1], rebate),
             (ci[j][0], ci[j][1], rebate), (ci[i][0], ci[i][1], rebate), o)
        quad((ci[i][0], ci[i][1], rebate), (ci[j][0], ci[j][1], rebate),
             (ci[j][0], ci[j][1], wall), (ci[i][0], ci[i][1], wall), o)
    # inner face of the baffle, rectangle minus the through-hole
    for i in range(n):
        j = (i + 1) % n
        quad((ci[i][0], ci[i][1], wall), (ci[j][0], ci[j][1], wall),
             (peri[j][0], peri[j][1], wall), (peri[i][0], peri[i][1], wall), o)
    _ = None

    # the box: four sides, a back, and the open front already built above
    x0, x1, y0, y1, z0, z1 = -W / 2, W / 2, -Hh / 2, Hh / 2, 0.0, D
    quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), o)   # back
    quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), o)   # left
    quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), o)   # right
    quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), o)   # bottom
    quad((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), o)   # top
    o.append('endsolid enclosure')

    out = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write('\n'.join(o) + '\n')
    tris = sum(1 for ln in o if ln.startswith('  facet'))
    kb = os.path.getsize(out) / 1024.0
    print('%s  %d triangles, %.0f KB  (%.0f x %.0f x %.0f mm external)'
          % (out, tris, kb, W, Hh, D))
    return 0


if __name__ == '__main__':
    sys.exit(main())
