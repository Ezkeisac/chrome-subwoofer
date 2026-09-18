#!/usr/bin/env python3
"""Predicted sealed-box response from T/S. Stdlib only.

A sealed box is a second-order high-pass. With s = j(f/Fc):

    H(s) = s^2 / (s^2 + s/Qtc + 1)

Everything the prediction claims -- F3, the slope, the character -- falls out of
Fc and Qtc alone. Those come from enclosure_math.py, never from here.

    python3 model.py --fc 40.27 --qtc 0.799 --out predicted.csv
    python3 model.py selftest
"""
from __future__ import annotations

import argparse
import csv
import math
import sys


def response_db(f: float, fc: float, qtc: float) -> float:
    """Anechoic sealed-box magnitude at f, in dB relative to the passband."""
    x = f / fc
    num = x * x
    den = math.hypot(1.0 - x * x, x / qtc)
    return 20.0 * math.log10(num / den) if den > 0 else -120.0


def f3(fc: float, qtc: float) -> float:
    """Where the response is 3 dB down. Bisection, so no algebra to get wrong."""
    lo, hi = fc / 20.0, fc * 20.0
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if response_db(mid, fc, qtc) < -3.0:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def curve(fc: float, qtc: float, fmin: float, fmax: float, points: int):
    r = math.log(fmax / fmin) / (points - 1)
    return [(round(fmin * math.exp(r * i), 3),
             round(response_db(fmin * math.exp(r * i), fc, qtc), 3))
            for i in range(points)]


def selftest() -> int:
    fails = []

    def chk(label, got, want, tol):
        if abs(got - want) > tol:
            fails.append('%s: got %r want %r' % (label, got, want))

    # Butterworth: Qtc = 0.707 puts F3 exactly at Fc. The definition of the alignment.
    chk('Butterworth F3 == Fc', f3(40.0, 0.7071), 40.0, 0.05)
    chk('at Fc, Qtc=0.707 is -3 dB', response_db(40.0, 40.0, 0.7071), -3.0, 0.02)

    # Second-order: 12 dB per octave far below Fc
    a, b = response_db(5.0, 40.0, 0.8), response_db(10.0, 40.0, 0.8)
    chk('12 dB/octave asymptote', b - a, 12.0, 0.3)

    # far above Fc the response is flat
    chk('passband is flat', response_db(4000.0, 40.0, 0.8), 0.0, 0.01)

    # higher Qtc peaks above the passband and extends lower
    chk('Qtc 1.2 peaks', max(response_db(f, 40.0, 1.2) for f in range(20, 120)) > 0.5, True, 0)
    if not f3(40.0, 1.2) < f3(40.0, 0.7071):
        fails.append('higher Qtc should reach lower')

    # the build: Fc 40.27, Qtc 0.799 -> F3 ~36.2, matching enclosure_math.py
    chk('CB-001 F3', f3(40.27, 0.799), 36.16, 0.4)

    if fails:
        print('MODEL SELFTEST FAILED', file=sys.stderr)
        for f in fails:
            print('  - ' + f, file=sys.stderr)
        return 1
    print('model selftest: OK')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd')
    sub.add_parser('selftest')
    p.add_argument('--fc', type=float)
    p.add_argument('--qtc', type=float)
    p.add_argument('--fmin', type=float, default=5.0)
    p.add_argument('--fmax', type=float, default=500.0)
    p.add_argument('--points', type=int, default=200)
    p.add_argument('--out')
    a = p.parse_args()

    if a.cmd == 'selftest':
        return selftest()
    if a.fc is None or a.qtc is None:
        raise SystemExit('need --fc and --qtc (from enclosure_math.py), or selftest')

    rows = curve(a.fc, a.qtc, a.fmin, a.fmax, a.points)
    if a.out:
        with open(a.out, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['hz', 'db'])
            w.writerows(rows)
        print('wrote %s -- %d points' % (a.out, len(rows)))
    print('  Fc  %.2f Hz   Qtc %.3f' % (a.fc, a.qtc))
    print('  F3  %.2f Hz' % f3(a.fc, a.qtc))
    peak = max(rows, key=lambda r: r[1])
    print('  peak %+.2f dB at %.1f Hz' % (peak[1], peak[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
