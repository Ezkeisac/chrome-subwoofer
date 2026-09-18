#!/usr/bin/env python3
"""Generate the stepped-sine measurement sequence. Stdlib only.

Stepped, not swept, because the Mac and the DR-05 share no clock. Each tone is a
separate measurement at a known frequency, so drift between the two devices is
irrelevant -- there is nothing to align.

The file carries a 1 kHz leader so the analyser can find its own start in the
recording, and a trailer so a truncated take is obvious rather than silently short.

    python3 tone_sequence.py --test                 2 s tone, checks the wiring
    python3 tone_sequence.py --out sweep.wav        the full sequence
    python3 tone_sequence.py --out s.wav --fmin 5 --fmax 500 --points 40
"""
from __future__ import annotations

import argparse
import array
import math
import struct
import sys
import wave

RATE = 48000
LEADER_HZ = 1000.0
LEADER_S = 0.5
TRAILER_S = 0.25
GAP_S = 0.3


def dbfs_to_amp(db: float) -> float:
    return 10 ** (db / 20.0)


def tone(freq: float, seconds: float, amp: float, fade_s: float = 0.02) -> array.array:
    """A sine with short raised-cosine fades, so each step does not click.

    A click is broadband: it puts energy at every frequency including the one
    being measured, and it is the classic way a stepped-sine rig quietly lies.
    """
    n = int(RATE * seconds)
    fade = max(1, int(RATE * fade_s))
    out = array.array('h', bytes(2 * n))
    w = 2.0 * math.pi * freq / RATE
    for i in range(n):
        env = 1.0
        if i < fade:
            env = 0.5 - 0.5 * math.cos(math.pi * i / fade)
        elif i > n - fade:
            env = 0.5 - 0.5 * math.cos(math.pi * (n - i) / fade)
        out[i] = int(max(-32767, min(32767, 32767 * amp * env * math.sin(w * i))))
    return out


def silence(seconds: float) -> array.array:
    return array.array('h', bytes(2 * int(RATE * seconds)))


def log_points(fmin: float, fmax: float, n: int) -> list[float]:
    if n < 2:
        return [fmin]
    r = math.log(fmax / fmin) / (n - 1)
    return [round(fmin * math.exp(r * i), 3) for i in range(n)]


def write_wav(path: str, samples: array.array) -> None:
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


MIN_MEASURE_CYCLES = 8
MIN_SETTLE_CYCLES = 4


def durations(freq: float, settle: float, measure: float) -> tuple[float, float]:
    """Low tones need to run longer.

    At 5 Hz a 0.5 s window holds 2.5 cycles, which is not enough for a clean
    magnitude, and Fs sits down in exactly that region. Scale by cycles instead,
    with the flat values as a floor.
    """
    return (max(settle, MIN_SETTLE_CYCLES / freq),
            max(measure, MIN_MEASURE_CYCLES / freq))


def build(freqs, settle, measure, amp):
    """Returns (samples, manifest). The manifest records where every tone landed,
    so the analyser reads it rather than recomputing the layout and risking a
    silent disagreement about which window belongs to which frequency."""
    out = array.array('h')
    out.extend(tone(LEADER_HZ, LEADER_S, amp))
    out.extend(silence(GAP_S))
    manifest = []
    for f in freqs:
        st, ms = durations(f, settle, measure)
        start = len(out)
        out.extend(tone(f, st + ms, amp))
        manifest.append({
            'hz': f,
            'tone_start': start,
            'settle_samples': int(RATE * st),
            'measure_start': start + int(RATE * st),
            'measure_samples': int(RATE * ms),
        })
    out.extend(silence(GAP_S))
    out.extend(tone(LEADER_HZ, TRAILER_S, amp))
    return out, manifest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default='sweep.wav')
    p.add_argument('--fmin', type=float, default=5.0)
    p.add_argument('--fmax', type=float, default=500.0)
    p.add_argument('--points', type=int, default=45)
    p.add_argument('--settle', type=float, default=0.30, help='discarded, lets the driver reach steady state')
    p.add_argument('--measure', type=float, default=0.50, help='analysed')
    p.add_argument('--level-dbfs', type=float, default=-20.0)
    p.add_argument('--test', action='store_true', help='2 s of 1 kHz, for checking the wiring')
    a = p.parse_args()

    amp = dbfs_to_amp(a.level_dbfs)

    if a.test:
        write_wav(a.out, tone(LEADER_HZ, 2.0, amp))
        print('wrote %s -- 2.0 s of %g Hz at %g dBFS' % (a.out, LEADER_HZ, a.level_dbfs))
        print()
        print('  play it, and watch the DR-05 input meters.')
        print('  meters moving  -> the path works, set the record level and go on')
        print('  meters flat    -> check the cable, and that the DR-05 is on EXT IN')
        print('  meters pinned  -> lower the Mac volume before connecting the driver')
        return 0

    freqs = log_points(a.fmin, a.fmax, a.points)
    seq, manifest = build(freqs, a.settle, a.measure, amp)
    write_wav(a.out, seq)

    import json, os
    mpath = os.path.splitext(a.out)[0] + '.json'
    with open(mpath, 'w') as fh:
        json.dump({'rate': RATE, 'leader_hz': LEADER_HZ, 'leader_s': LEADER_S,
                   'gap_s': GAP_S, 'level_dbfs': a.level_dbfs,
                   'tones': manifest}, fh, indent=1)

    total = len(seq) / RATE
    slowest = max(m['measure_samples'] for m in manifest) / RATE
    print('wrote %s  and  %s' % (a.out, os.path.basename(mpath)))
    print('  %d tones, %.1f Hz to %.1f Hz, log spaced' % (len(freqs), freqs[0], freqs[-1]))
    print('  windows scale with frequency: %.2f s at the bottom, %.2f s flat above'
          % (slowest, a.measure))
    print('  total %.1f s at %g dBFS' % (total, a.level_dbfs))
    print()
    print('  KEEP THE .json -- the analyser reads it. Do not regenerate the wav')
    print('  without it, and do not edit or trim the recording.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
