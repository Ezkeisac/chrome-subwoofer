#!/usr/bin/env python3
"""What the plate amplifier's dial must be set to, given everything else.

Requirement R6 asks for a 60 Hz handover, chosen by measuring where the Nova 7B
mains run out. But there are TWO low-pass filters between the source and the
driver, not one, and their slopes add:

    receiver SUBWOOFER OUT  ->  SPA300-D dial  ->  driver

The Yamaha RX-V361 manual states its SUBWOOFER OUT carries bass below 90 Hz --
a fixed filter the user cannot change. Measurement of the finished system
(section 5) gives the COMBINED result as 4th order, -3 dB at 57 Hz.

Given a fixed 90 Hz stage, this solves for what the dial itself must be doing.

    python3 derive_crossover.py
"""
import math
import sys

RECEIVER_HZ = 90.0      # per the RX-V361 manual
COMBINED_HZ = 57.0      # measured, section 5
COMBINED_ORDER = 4      # measured: two independent slope pairs gave 24.4 / 24.6 dB per octave


def butter(f, fc, order):
    """Butterworth magnitude, linear."""
    return 1.0 / math.sqrt(1.0 + (f / fc) ** (2 * order))


def solve_second_stage(f_target, fc_a, order_each=2):
    """Find fc_b such that two cascaded filters are -3 dB at f_target."""
    lo, hi = 10.0, 500.0
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        mag = butter(f_target, fc_a, order_each) * butter(f_target, mid, order_each)
        if mag < 1 / math.sqrt(2):
            lo = mid            # too much attenuation, push the corner up
        else:
            hi = mid
    return math.sqrt(lo * hi)


def main():
    print('=' * 70)
    print('TWO FILTERS, NOT ONE')
    print('  receiver SUBWOOFER OUT      %.0f Hz, fixed  (RX-V361 manual)' % RECEIVER_HZ)
    print('  SPA300-D dial               unknown -- solving for it')
    print('  measured combined           %.0f Hz, order %d  (section 5)'
          % (COMBINED_HZ, COMBINED_ORDER))

    fc_b = solve_second_stage(COMBINED_HZ, RECEIVER_HZ)
    print('\n  -> dial is at approximately  %.0f Hz' % fc_b)
    print('  -> requirement R6 asked for  60 Hz')
    print('  -> difference               %.0f Hz' % abs(fc_b - 60.0))

    print('\n  check: cascading %.0f Hz and %.0f Hz, both 2nd order' % (RECEIVER_HZ, fc_b))
    for f in (40, 50, 57, 60, 70, 90, 120):
        m = butter(f, RECEIVER_HZ, 2) * butter(f, fc_b, 2)
        print('    %5.0f Hz  %+6.2f dB' % (f, 20 * math.log10(m)))

    print('\nWHAT THIS IS AND IS NOT')
    print('  It is a derivation, not a measurement. It holds only if the receiver')
    print('  stage really is 2nd order at 90 Hz -- the manual gives the frequency')
    print('  but not the slope, and I could not confirm the slope from the PDF.')
    print('  Measuring the receiver output alone would settle it and has not been done.')
    print()
    print('  What IS measured is the combined result: 4th order, -3 dB at 57 Hz.')
    print('  That much stands on its own regardless of how the two stages divide.')
    print('=' * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
