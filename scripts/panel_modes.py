#!/usr/bin/env python3
"""Fundamental bending resonance of the enclosure panels. Stdlib only.

Rectangular plate, fundamental (1,1) mode:

    f11 = (pi/2) * sqrt(E*t^2 / (12*rho*(1-nu^2))) * (1/a^2 + 1/b^2)

Simply supported is the LOW bound; fully clamped is roughly 1.8x higher. A panel
glued and screwed into a box sits between the two, so the answer is a band, not a
number -- and MDF's Young's modulus varies enough between batches that pretending
otherwise would be false precision.

    python3 panel_modes.py
"""
import math

T = 0.019
E_LO, E_HI = 2.8e9, 4.0e9
RHO_LO, RHO_HI = 700.0, 780.0
NU = 0.27
CLAMPED = 1.8

PANELS = [
    ('front / back', 0.280, 0.623, 'largest. Front is cut for the 10in driver'),
    ('lateral (sides)', 0.242, 0.623, 'second largest, uncut'),
    ('top / bottom', 0.280, 0.242, 'smallest, stiffest'),
]


def f11(a, b, e, rho):
    return (math.pi / 2.0) * math.sqrt(e * T * T / (12.0 * rho * (1 - NU ** 2))) \
        * (1.0 / a ** 2 + 1.0 / b ** 2)


print('19 mm MDF, E %.1f-%.1f GPa, rho %.0f-%.0f kg/m3\n' % (E_LO / 1e9, E_HI / 1e9, RHO_LO, RHO_HI))
print('  %-16s %-13s %8s   %s' % ('panel', 'size (mm)', 'f11 (Hz)', 'note'))
for name, a, b, note in PANELS:
    lo = f11(a, b, E_LO, RHO_HI)
    hi = f11(a, b, E_HI, RHO_LO) * CLAMPED
    print('  %-16s %4.0f x %-6.0f %4.0f-%-4.0f   %s' % (name, a * 1000, b * 1000, lo, hi, note))

print('\n  simply-supported lower bound to fully-clamped upper bound.')
print('  The SPA300-D low-passes at 80 Hz. A panel is driven at the SIGNAL')
print('  frequency, not at its own resonance, so a mode well above the')
print('  amplifier passband is never meaningfully excited.')
