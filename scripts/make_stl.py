#!/usr/bin/env python3
"""Emit the enclosure as ASCII STL, from the dimensions CSV. Stdlib only.

    python3 scripts/make_stl.py [--segments 36] [--out images/enclosure.stl]

GitHub renders a fenced `stl` block, and an .stl file in a repository, as an
interactive viewer with wireframe, surface-angle and solid modes. So the cabinet can be
shown rather than photographed, and turned rather than described.

The cabinet comes from calculations/box-dimensions.csv and nowhere else, so the model
and the paper cannot disagree. The baffle carries the rebate: a 257 mm shoulder 6 mm deep
for the driver flange, stepping to the 233 mm through-hole.

Two things are NOT in the CSV, because the build never recorded them, and are read from
the photographs instead. Where the aperture sits: centred across the baffle and low, with
the same margin under the flange as beside it. And the driver's profile: the flange and
through-hole are measured, the roll sits on the published Sd (346.4 cm2 is a 105 mm
piston), and the cone depth and dust cap are drawn to look right, not measured.

The plate amplifier on the back is not modelled: no photograph shows it.
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
    out.append('  facet normal %.4f %.4f %.4f\n    outer loop' % (nx / m, ny / m, nz / m))
    for v in (a, b, c):
        out.append('      vertex %.2f %.2f %.2f' % v)
    out.append('    endloop\n  endfacet')


def quad(a, b, c, d, out):
    tri(a, b, c, out); tri(a, c, d, out)


def margin_centre(W, Hh):
    """The aperture's centre: on the centreline, as far from the floor as from the sides."""
    return 0.0, -Hh / 2 + W / 2


def driver_profile(r_out):
    """(radius, depth) from the flange inward. Negative depth stands proud of the baffle."""
    p = [(r_out, 0.0), (116.0, 0.0)]                       # flange, flush in its rebate
    for a in (36, 72, 108, 144, 180):                      # half-roll surround
        t = math.radians(a)
        p.append((106.0 + 10.0 * math.cos(t), -9.0 * math.sin(t)))
    p += [(70.0, 24.0), (32.0, 52.0)]                      # the cone
    p += [(22.0, 46.0), (11.0, 42.0), (0.0, 41.0)]         # dust cap, a shallow dome
    return p


def hit(cx, cy, t, W, Hh):
    """Where a ray from the aperture centre at angle t meets the baffle's edge."""
    dx, dy = math.cos(t), math.sin(t)
    s = []
    if dx > 1e-9:  s.append((W / 2 - cx) / dx)
    if dx < -1e-9: s.append((-W / 2 - cx) / dx)
    if dy > 1e-9:  s.append((Hh / 2 - cy) / dy)
    if dy < -1e-9: s.append((-Hh / 2 - cy) / dy)
    k = min(s)
    return cx + k * dx, cy + k * dy


def annulus(r, z, n, W, Hh, cx, cy, front, o):
    """The baffle face: rectangle minus a circle. The circle is uniform, so the driver's
    rings meet it point for point, and each corner is added where its angle falls. Without
    the corners the face stops short of the box and leaves a hole at each one."""
    tw = 2 * math.pi
    corners = [(x, y) for x in (-W / 2, W / 2) for y in (-Hh / 2, Hh / 2)]
    ca = sorted((math.atan2(y - cy, x - cx) % tw, x, y) for x, y in corners)
    for i in range(n):
        t0, t1 = tw * i / n, tw * (i + 1) / n
        c0 = (cx + r * math.cos(t0), cy + r * math.sin(t0), z)
        c1 = (cx + r * math.cos(t1), cy + r * math.sin(t1), z)
        seq = [hit(cx, cy, t0, W, Hh)]
        seq += [(x, y) for a, x, y in ca if t0 < a < t1]
        seq.append(hit(cx, cy, t1, W, Hh))
        seq = [(x, y, z) for x, y in seq]
        for a, b in zip(seq, seq[1:]):
            tri(c0, b, a, o) if front else tri(c0, a, b, o)
        tri(c0, c1, seq[-1], o) if front else tri(c0, seq[-1], c1, o)


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
    cx, cy = margin_centre(W, Hh)

    n = a.segments
    o = ['solid enclosure']
    # The baffle is the front face at z = 0; the body runs to z = D, so the front's
    # outward normal is -z.
    ring = lambda r, i, z: (cx + r * math.cos(2 * math.pi * i / n),
                            cy + r * math.sin(2 * math.pi * i / n), z)
    annulus(r_out, 0.0, n, W, Hh, cx, cy, True, o)
    # rebate wall, then its shoulder, then the through-hole wall
    for i in range(n):
        j = i + 1
        quad(ring(r_out, i, 0.0), ring(r_out, j, 0.0),
             ring(r_out, j, rebate), ring(r_out, i, rebate), o)
        quad(ring(r_out, i, rebate), ring(r_out, j, rebate),
             ring(r_in, j, rebate), ring(r_in, i, rebate), o)
        quad(ring(r_in, i, rebate), ring(r_in, j, rebate),
             ring(r_in, j, wall), ring(r_in, i, wall), o)
    annulus(r_in, wall, n, W, Hh, cx, cy, False, o)        # inner face of the baffle

    # the box: four sides and a back; the front is the annulus above
    x0, x1, y0, y1, z0, z1 = -W / 2, W / 2, -Hh / 2, Hh / 2, 0.0, D
    quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), o)   # back
    quad((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), o)   # left
    quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), o)   # right
    quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), o)   # bottom
    quad((x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0), o)   # top

    # the driver, turned about the aperture's axis
    prof = driver_profile(r_out)
    for (r0, z0_), (r1, z1_) in zip(prof, prof[1:]):
        for i in range(n):
            j = i + 1
            if r1 == 0.0:
                tri(ring(r0, i, z0_), ring(0.0, i, z1_), ring(r0, j, z0_), o)
            else:
                quad(ring(r0, i, z0_), ring(r1, i, z1_),
                     ring(r1, j, z1_), ring(r0, j, z0_), o)
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
