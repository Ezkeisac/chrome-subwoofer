#!/usr/bin/env python3
"""Derive the enclosure from its one free variable, and check it against the build.

The design has a constraint most do not: requirement R3 fixes the footprint to a
Nova 7B's, so the subwoofer can stand under one. Cross-section is therefore given,
not chosen, and height is the only dimension left to solve.

    python3 derive_box.py
"""
import csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MM3_PER_L = 1_000_000.0


def read(name, key='item'):
    with open(os.path.join(HERE, name), newline='') as fh:
        return {r[key]: r for r in csv.DictReader(fh)}


def main():
    dims = read('box-dimensions.csv')
    vols = read('volume.csv')
    mm = lambda k: float(dims[k]['mm'])
    lt = lambda k: float(vols[k]['litres'])

    ext_w, ext_l, wall = mm('box external width'), mm('box external length'), mm('box wall thickness')
    int_w, int_l, int_h = mm('box internal width'), mm('box internal length'), mm('box internal height')

    print('=' * 70)
    print('FIXED BY R3 -- footprint must match a Nova 7B so the sub works as its base')
    print('  external cross-section      %.0f x %.0f mm' % (ext_w, ext_l))
    print('  wall                        %.0f mm (3/4 in MDF)' % wall)

    d_w, d_l = ext_w - 2 * wall, ext_l - 2 * wall
    print('\nINTERNAL CROSS-SECTION -- follows, nothing to choose')
    print('  %.0f - 2(%.0f) = %.0f mm    (build says %.0f)  %s'
          % (ext_w, wall, d_w, int_w, 'ok' if abs(d_w - int_w) < 0.5 else 'MISMATCH'))
    print('  %.0f - 2(%.0f) = %.0f mm    (build says %.0f)  %s'
          % (ext_l, wall, d_l, int_l, 'ok' if abs(d_l - int_l) < 0.5 else 'MISMATCH'))
    area = d_w * d_l
    print('  area                        %.0f mm2 = %.5f m2' % (area, area / 1e6))

    target = lt('box internal volume')
    print('\nHEIGHT -- the only free variable, solved from the volume')
    print('  required internal volume    %.2f L' % target)
    h = target * MM3_PER_L / area
    print('  height = volume / area      %.2f mm   (build says %.0f)  %s'
          % (h, int_h, 'ok' if abs(h - int_h) < 1.0 else 'MISMATCH'))
    print('  external height             %.0f mm' % (int_h + 2 * wall))

    print('\nEFFECTIVE VOLUME -- what the driver actually sees')
    disp = lt('driver displacement')
    eff = target - disp
    print('  internal                    %.2f L' % target)
    print('  driver displacement         %.2f L  (magnet %.2f + basket %.2f)'
          % (disp, lt('magnet volume'), lt('basket volume')))
    print('  effective                   %.2f L   (build says %.2f)  %s'
          % (eff, lt('box effective volume'),
             'ok' if abs(eff - lt('box effective volume')) < 0.05 else 'MISMATCH'))

    print('\nWHY THE BOX IS THE SHAPE IT IS')
    print('  A free design for %.1f L would be a cube about %.0f mm on a side.'
          % (target, (target * MM3_PER_L) ** (1 / 3.0)))
    print('  R3 forbids that. Holding the footprint and solving for height gives a')
    print('  column %.1f times taller than it is wide -- a consequence of the'
          % (int_h / int_w))
    print('  requirement, not a stylistic choice.')

    cost = 0.0
    with open(os.path.join(HERE, 'materials-cost.csv'), newline='') as fh:
        for r in csv.DictReader(fh):
            cost += float(r['ext_price_usd'])
    print('\nCOST  $%.2f' % cost)
    print('=' * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
