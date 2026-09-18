#!/usr/bin/env python3
"""Measured acoustic response, and the comparison against prediction. Stdlib only.

Reuses the magnitude extraction from analyse_impedance.py -- same manifest, same
single-bin DFT, different meaning: this one is a microphone recording, not a voltage.

    python3 analyse_response.py measure --wav nearfield.wav --manifest ~/Movies/sweep.json --out nf.csv
    python3 analyse_response.py compare --measured nf.csv --predicted predicted.csv
    python3 analyse_response.py selftest

WHAT THIS CAN AND CANNOT SAY
  can: shape -- F3, slope, the knee, where a resonance sits
  cannot: absolute SPL. The DR-05's mics are uncalibrated, so every curve here is
          relative and normalised to a reference band.

THE USABLE BAND IS NARROW. The SPA300-D low-passes at 80 Hz, so everything above
that is the amplifier rolling off, not the box. The comparison band is roughly
20-70 Hz and the reference band must sit inside it.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from analyse_impedance import magnitudes, read_csv2, search_offset   # noqa: E402

REF_LO, REF_HI = 50.0, 70.0


def to_db(rows, ref_lo=REF_LO, ref_hi=REF_HI):
    """Normalise to the mean level in the reference band, then convert to dB."""
    band = [v for hz, v in rows if ref_lo <= hz <= ref_hi and v > 0]
    if not band:
        raise SystemExit('nothing in the %g-%g Hz reference band -- was the sub playing?'
                         % (ref_lo, ref_hi))
    ref = sum(band) / len(band)
    return [(hz, round(20.0 * math.log10(v / ref), 3) if v > 0 else -120.0)
            for hz, v in rows]


def find_f3(db_rows):
    """Lowest frequency at which the curve passes -3 dB, walking down from the band."""
    rows = sorted(db_rows)
    for (f1, d1), (f2, d2) in zip(rows, rows[1:]):
        if d1 < -3.0 <= d2:
            t = (-3.0 - d1) / (d2 - d1)
            return f1 + t * (f2 - f1)
    return None


def _rebase(rows: dict, lo: float, hi: float) -> dict:
    """Shift a dB curve so its mean over [lo, hi] is 0."""
    band = [v for hz, v in rows.items() if lo <= hz <= hi]
    if not band:
        raise SystemExit('nothing in the %g-%g Hz band to reference against' % (lo, hi))
    off = sum(band) / len(band)
    return {hz: v - off for hz, v in rows.items()}


def compare(meas: dict, pred: dict, lo: float = REF_LO, hi: float = REF_HI):
    """Diff two curves after referencing BOTH to the same band.

    This matters more than it looks. The SPA300-D low-passes at 80 Hz, so the
    usable band is about 20-70 Hz -- which lies entirely inside the box's own
    transition region. There is no flat passband to normalise against, and a
    measured curve referenced to 50-70 Hz is shifted up relative to an anechoic
    prediction referenced to infinity. Comparing them unshifted makes the measured
    F3 read LOWER than it is, and it can land close to the predicted value by pure
    arithmetic coincidence. Rebase both, then only the shape is being compared.
    """
    m, q = _rebase(meas, lo, hi), _rebase(pred, lo, hi)
    out = []
    for hz in sorted(m):
        near = min(q, key=lambda p: abs(math.log(p) - math.log(hz)))
        if abs(math.log(near) - math.log(hz)) < 0.05:
            out.append((hz, m[hz], q[near], m[hz] - q[near]))
    return out


def selftest() -> int:
    fails = []
    # a flat input normalises to 0 dB everywhere
    flat = [(f, 1.0) for f in (20, 30, 40, 50, 60, 70, 80)]
    if any(abs(d) > 1e-6 for _, d in to_db(flat)):
        fails.append('flat input did not normalise to 0 dB')

    # a synthetic Butterworth: referenced to a TRUE passband, F3 lands on Fc
    fc, qtc = 40.0, 0.7071
    rows = []
    for i in range(600):
        f = 10.0 * math.exp(math.log(80.0) * i / 599)
        x = f / fc
        rows.append((f, (x * x) / math.hypot(1 - x * x, x / qtc)))
    got = find_f3(to_db(rows, 400.0, 700.0))
    if got is None or abs(got - 40.0) > 1.0:
        fails.append('F3 against a true passband: got %r, want ~40' % got)

    # ...and referenced to 50-70 Hz instead it reads LOW, because that band is
    # still inside the rolloff. This is the trap compare() exists to avoid.
    band_ref = find_f3(to_db(rows, 50.0, 70.0))
    if band_ref is None or band_ref >= got - 1.0:
        fails.append('band-referenced F3 %r should read well below %r' % (band_ref, got))

    # rebasing both curves to the same band cancels that offset entirely
    pred_d = dict(to_db(rows, 400.0, 700.0))
    meas_d = dict(to_db(rows, 50.0, 70.0))
    worst = max(abs(d) for _, _, _, d in compare(meas_d, pred_d, 50.0, 70.0))
    # 0.01 dB, not zero: to_db rounds to 3 decimals, so a few thousandths of a dB
    # of rounding noise survives. Anything real is orders of magnitude larger.
    if worst > 0.01:
        fails.append('identical shapes did not cancel after rebasing: worst %r' % worst)

    # an empty reference band must fail loudly rather than divide by zero
    try:
        to_db([(10.0, 1.0), (20.0, 1.0)])
        fails.append('accepted a recording with nothing in the reference band')
    except SystemExit:
        pass

    if fails:
        print('RESPONSE SELFTEST FAILED', file=sys.stderr)
        for f in fails:
            print('  - ' + f, file=sys.stderr)
        return 1
    print('analyse_response selftest: OK')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('selftest')
    m = sub.add_parser('measure')
    m.add_argument('--wav', required=True)
    m.add_argument('--manifest', required=True)
    m.add_argument('--out', required=True)
    m.add_argument('--ref-lo', type=float, default=REF_LO)
    m.add_argument('--ref-hi', type=float, default=REF_HI)
    m.add_argument('--offset-s', type=float,
                   help='seconds into the recording where the sweep starts')
    m.add_argument('--auto-offset', action='store_true',
                   help='find the offset by maximising in-band energy (recommended)')
    c = sub.add_parser('compare')
    c.add_argument('--measured', required=True)
    c.add_argument('--predicted', required=True)
    c.add_argument('--band-lo', type=float, default=20.0)
    c.add_argument('--band-hi', type=float, default=70.0)
    a = p.parse_args()

    if a.cmd == 'selftest':
        return selftest()

    if a.cmd == 'measure':
        off = a.offset_s
        if a.auto_offset:
            off = search_offset(a.wav, a.manifest)
            print('  auto-offset: sweep starts at %.2f s' % off, file=sys.stderr)
        db = to_db(magnitudes(a.wav, a.manifest, off), a.ref_lo, a.ref_hi)
        with open(a.out, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['hz', 'db'])
            w.writerows(db)
        got = find_f3(db)
        print('wrote %s -- %d points, normalised to %g-%g Hz'
              % (a.out, len(db), a.ref_lo, a.ref_hi))
        print('  F3 vs the %g-%g Hz band: %s'
              % (a.ref_lo, a.ref_hi, '%.1f Hz' % got if got else 'not reached in this sweep'))
        print('  NOT the anechoic F3 -- that band is inside the rolloff, so this reads')
        print('  low. Use `compare`, which rebases both curves, rather than this number.')
        print('  reminder: relative shape only. Above ~80 Hz you are seeing the')
        print('  SPA300-D low-pass, not the box.')
        return 0

    rows = [r for r in compare(read_csv2(a.measured), read_csv2(a.predicted))
            if a.band_lo <= r[0] <= a.band_hi]
    if not rows:
        raise SystemExit('no overlap in %g-%g Hz' % (a.band_lo, a.band_hi))
    print('   %8s %9s %9s %9s' % ('Hz', 'measured', 'predicted', 'delta'))
    for hz, mv, pv, d in rows:
        flag = '  <-- ' + ('measured low' if d < -3 else 'measured high') if abs(d) > 3 else ''
        print('   %8.1f %8.2f %9.2f %+9.2f%s' % (hz, mv, pv, d, flag))
    errs = [abs(d) for _, _, _, d in rows]
    print()
    print('  mean |error| %.2f dB, worst %.2f dB, over %g-%g Hz'
          % (sum(errs) / len(errs), max(errs), a.band_lo, a.band_hi))
    print('  A large error is not automatically the model being wrong. Room modes,')
    print('  mic response and placement all live in the measured curve too -- say')
    print('  which candidates the data cannot separate.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
