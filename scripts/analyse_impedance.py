#!/usr/bin/env python3
"""Stepped-sine analysis: recordings -> magnitudes -> impedance -> T/S. Stdlib only.

No numpy, no scipy, nothing to install. Each tone's frequency is known exactly, so
the magnitude comes from a single DFT bin evaluated at that frequency -- O(n), the
same cost as an FFT bin, without needing the FFT.

    # 1. one CSV per recording
    python3 analyse_impedance.py magnitude --wav ref.wav  --manifest sweep.json --out ref.csv
    python3 analyse_impedance.py magnitude --wav meas.wav --manifest sweep.json --out meas.csv

    # 2. the divider: Z = R * (Vref/Vmeas - 1)
    python3 analyse_impedance.py impedance --ref ref.csv --meas meas.csv --resistor 100 --out z.csv

    # 3. Fs, Qms, Qes, Qts from the impedance peak
    python3 analyse_impedance.py ts --z z.csv --re 3.8

    # 4. Vas, from a second run with a known mass on the cone
    python3 analyse_impedance.py ts --z z.csv --re 3.8 --z-mass z_mass.csv --added-g 60 --sd-cm2 346.4

    python3 analyse_impedance.py selftest
"""
from __future__ import annotations

import argparse
import array
import csv
import json
import math
import sys
import wave

RHO = 1.18       # kg/m3, air
C_AIR = 345.0    # m/s


# --------------------------------------------------------------------------- #
# signal
# --------------------------------------------------------------------------- #

def read_wav(path: str) -> tuple[list[float], int]:
    """16- or 24-bit PCM WAV to floats in [-1, 1], mixed to mono.

    24-bit matters: field recorders default to it, and Python's wave module hands
    back raw bytes for it rather than an array type.
    """
    with wave.open(path, 'rb') as w:
        width, rate, nch = w.getsampwidth(), w.getframerate(), w.getnchannels()
        frames = w.readframes(w.getnframes())

    if width == 2:
        a = array.array('h')
        a.frombytes(frames)
        vals = [x / 32768.0 for x in a]
    elif width == 3:
        vals = []
        for i in range(0, len(frames) - 2, 3):
            v = frames[i] | (frames[i + 1] << 8) | (frames[i + 2] << 16)
            if v & 0x800000:
                v -= 0x1000000
            vals.append(v / 8388608.0)
    elif width == 4:
        a = array.array('i')
        a.frombytes(frames)
        vals = [x / 2147483648.0 for x in a]
    else:
        raise SystemExit('unsupported sample width: %d-bit' % (width * 8))

    if nch > 1:
        vals = [sum(vals[i:i + nch]) / nch for i in range(0, len(vals) - nch + 1, nch)]
    return vals, rate


def bin_magnitude(samples: list[float], rate: int, freq: float) -> float:
    """Amplitude at exactly `freq`, Hann-windowed.

    The window's coherent gain scales every result by the same factor, and every
    number downstream is a ratio of two of these, so the scaling cancels.
    """
    n = len(samples)
    if n < 4:
        return 0.0
    w = 2.0 * math.pi * freq / rate
    re = im = wsum = 0.0
    for i, x in enumerate(samples):
        win = 0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1))
        wsum += win
        xw = x * win
        re += xw * math.cos(w * i)
        im -= xw * math.sin(w * i)
    # normalise by the window sum, not by n: a Hann window has a coherent gain of
    # 0.5, so dividing by n would report every amplitude at half its true value.
    return 2.0 * math.hypot(re, im) / wsum


LEADER_FALLBACK_HZ = 50.0


def find_leader(samples: list[float], rate: int, leader_hz: float = LEADER_FALLBACK_HZ,
                block_ms: float = 50.0) -> int:
    """First sample of the leader, found by energy AT THE LEADER FREQUENCY.

    Broadband RMS was the wrong test and it failed on the first real recording.
    Measuring a subwoofer acoustically, the chain low-passes at 80 Hz, so a 1 kHz
    leader is simply not reproduced -- the detector then locked onto the first loud
    thing, which was the sub entering its own passband eighteen seconds later, and
    every window landed on the wrong tone.

    Looking only at the leader's own frequency ignores whatever else is loud.
    """
    bs = max(1, int(rate * block_ms / 1000.0))
    mags = []
    for i in range(0, len(samples) - bs, bs):
        mags.append((bin_magnitude(samples[i:i + bs], rate, leader_hz), i))
    if not mags:
        raise SystemExit('recording too short')
    peak = max(m for m, _ in mags)
    if peak < 1e-5:
        raise SystemExit('no energy at %g Hz anywhere -- wrong leader frequency for this '
                         'chain, or nothing was captured. Pass --offset-s instead.' % leader_hz)
    for m, i in mags:
        if m > peak * 0.5:
            return i
    return 0


def magnitudes(wav_path: str, manifest_path: str,
               offset_s: float | None = None) -> list[tuple[float, float]]:
    samples, rate = read_wav(wav_path)
    man = json.load(open(manifest_path))
    if rate != man['rate']:
        print('  recording is %d Hz, sequence was %d Hz' % (rate, man['rate']), file=sys.stderr)
    if offset_s is not None:
        offset = int(offset_s * rate)
        print('  offset given: %.3f s (leader detection skipped)' % offset_s, file=sys.stderr)
    else:
        offset = find_leader(samples, rate, man.get('leader_hz', LEADER_FALLBACK_HZ))
        print('  leader found at %.3f s' % (offset / rate), file=sys.stderr)

    # The manifest indexes samples at the rate the sweep was GENERATED at. A
    # recording made at another rate needs every position scaled, or each window
    # lands on the wrong tone -- silently, and the further in, the worse.
    scale = rate / man['rate']
    if abs(scale - 1.0) > 1e-9:
        print('  rescaling manifest positions by %.6f (%d -> %d Hz)'
              % (scale, man['rate'], rate), file=sys.stderr)

    out = []
    for t in man['tones']:
        a = offset + int(round(t['measure_start'] * scale))
        b = a + int(round(t['measure_samples'] * scale))
        if b > len(samples):
            print('  TRUNCATED at %.1f Hz -- recording ended early, %d of %d tones usable'
                  % (t['hz'], len(out), len(man['tones'])), file=sys.stderr)
            break
        out.append((t['hz'], bin_magnitude(samples[a:b], rate, t['hz'])))
    return out


# --------------------------------------------------------------------------- #
# impedance and T/S
# --------------------------------------------------------------------------- #

def read_csv2(path: str) -> dict[float, float]:
    with open(path) as fh:
        return {float(r['hz']): float(r[[k for k in r if k != 'hz'][0]])
                for r in csv.DictReader(fh)}


def impedance(ref: dict, meas: dict, resistor: float) -> list[tuple[float, float]]:
    """Voltage divider, one channel, two passes.

    Pass 1 is the source straight into the recorder. Pass 2 is the voltage across
    the sense resistor with the driver in circuit. Everything common to both -- the
    headphone amp's response, the recorder's input response -- divides out.
    """
    out = []
    for hz in sorted(ref):
        if hz not in meas:
            continue
        vm = meas[hz]
        if vm <= 1e-9:
            continue
        out.append((hz, resistor * (ref[hz] / vm - 1.0)))
    return out


def derive_ts(z: list[tuple[float, float]], re: float) -> dict:
    """Fs, Qms, Qes, Qts from the impedance peak. Classic -3 dB-point method."""
    fs, zmax = max(z, key=lambda p: p[1])
    r0 = zmax / re
    if r0 <= 1.0:
        raise SystemExit('peak impedance %.2f is not above Re %.2f -- check Re and the jig' % (zmax, re))
    ztarget = re * math.sqrt(r0)

    def cross(seq):
        for (f1, z1), (f2, z2) in zip(seq, seq[1:]):
            if (z1 - ztarget) * (z2 - ztarget) < 0:      # sign change brackets it
                t = (ztarget - z1) / (z2 - z1)
                return f1 + t * (f2 - f1)
        return None

    below = [p for p in z if p[0] <= fs]
    above = [p for p in z if p[0] >= fs]
    f1, f2 = cross(below), cross(list(reversed(above)))
    if not f1 or not f2:
        raise SystemExit('could not bracket both -3 dB points -- widen the sweep or add points')

    qms = fs * math.sqrt(r0) / (f2 - f1)
    qes = qms / (r0 - 1.0)
    return {'fs_hz': round(fs, 2), 'z_max_ohm': round(zmax, 2), 're_ohm': re,
            'f1_hz': round(f1, 2), 'f2_hz': round(f2, 2),
            'qms': round(qms, 3), 'qes': round(qes, 3),
            'qts': round(qms * qes / (qms + qes), 3)}


def derive_vas(fs: float, fs_mass: float, added_g: float, sd_cm2: float) -> dict:
    """Added-mass method. Mass shifts Fs down by a known amount; that gives Mms."""
    ratio = (fs / fs_mass) ** 2
    if ratio <= 1.0:
        raise SystemExit('Fs did not fall with mass added (%.2f -> %.2f) -- check the runs'
                         % (fs, fs_mass))
    mms = (added_g / 1000.0) / (ratio - 1.0)
    cms = 1.0 / (((2 * math.pi * fs) ** 2) * mms)
    sd = sd_cm2 / 10000.0
    vas = RHO * (C_AIR ** 2) * (sd ** 2) * cms
    return {'fs_free_hz': round(fs, 2), 'fs_massed_hz': round(fs_mass, 2),
            'added_g': added_g, 'mms_g': round(mms * 1000, 2),
            'cms_mm_per_n': round(cms * 1000, 4), 'vas_l': round(vas * 1000, 2)}


# --------------------------------------------------------------------------- #

def selftest() -> int:
    fails = []

    def chk(label, got, want, tol=1e-6):
        if abs(got - want) > tol:
            fails.append('%s: got %r want %r' % (label, got, want))

    rate = 48000
    for f in (25.0, 137.0, 440.0):
        n = int(rate * 0.5)
        sig = [0.37 * math.sin(2 * math.pi * f * i / rate) for i in range(n)]
        chk('bin at %g Hz' % f, bin_magnitude(sig, rate, f), 0.37, 0.01)

    # a tone at another frequency must NOT read as signal here
    n = int(rate * 0.5)
    sig = [0.5 * math.sin(2 * math.pi * 200 * i / rate) for i in range(n)]
    if bin_magnitude(sig, rate, 50.0) > 0.02:
        fails.append('leakage: 200 Hz tone read %.4f at 50 Hz' % bin_magnitude(sig, rate, 50.0))

    # divider: a 4 ohm load with a 100 ohm sense resistor
    ref = {100.0: 1.0}
    meas = {100.0: 100.0 / 104.0}
    chk('impedance 4 ohm', impedance(ref, meas, 100.0)[0][1], 4.0, 0.001)

    # Synthetic resonance -> Fs and Qms recovered.
    # The impedance of a driver near resonance is a COMPLEX sum,
    #     Z(f) = Re + Res / (1 + j*Qms*(f/fs - fs/f))
    # so the magnitude is the modulus of that, not the sum of two magnitudes.
    # Getting this wrong makes the test curve narrower than a real one and the
    # recovered Qms comes out low.
    re_ = 3.8
    fs_true, qms_true, res_ = 25.2, 4.0, 64.6
    z = []
    for i in range(2000):
        f = 5.0 * math.exp(math.log(100.0) * i / 1999)
        x = f / fs_true - fs_true / f
        d = 1.0 + (qms_true * x) ** 2
        z.append((f, math.hypot(re_ + res_ / d, res_ * qms_true * x / d)))
    ts = derive_ts(z, re_)
    chk('Fs recovered', ts['fs_hz'], fs_true, 0.2)
    chk('Qms recovered', ts['qms'], qms_true, 0.15)
    chk('Zmax recovered', ts['z_max_ohm'], re_ + res_, 0.2)
    if not (0 < ts['qts'] < ts['qms']):
        fails.append('Qts %r out of range' % ts['qts'])

    # added mass: doubling Mms drops Fs by sqrt(2)
    v = derive_vas(25.2, 25.2 / math.sqrt(2), 110.7, 346.4)
    chk('Mms from added mass', v['mms_g'], 110.7, 0.5)

    for bad, why in ((lambda: derive_ts([(10, 3.0), (20, 3.5)], 3.8), 'peak below Re'),
                     (lambda: derive_vas(25.0, 26.0, 60, 346.4), 'Fs rose with mass')):
        try:
            bad()
            fails.append('accepted bad input: %s' % why)
        except SystemExit:
            pass

    if fails:
        print('ANALYSER SELFTEST FAILED', file=sys.stderr)
        for f in fails:
            print('  - ' + f, file=sys.stderr)
        return 1
    print('analyse_impedance selftest: OK')
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('selftest')
    m = sub.add_parser('magnitude')
    m.add_argument('--wav', required=True)
    m.add_argument('--manifest', required=True)
    m.add_argument('--out', required=True)
    z = sub.add_parser('impedance')
    z.add_argument('--ref', required=True)
    z.add_argument('--meas', required=True)
    z.add_argument('--resistor', type=float, default=100.0)
    z.add_argument('--out', required=True)
    t = sub.add_parser('ts')
    t.add_argument('--z', required=True)
    t.add_argument('--re', type=float, required=True, help='DC resistance, measured with a multimeter')
    t.add_argument('--z-mass')
    t.add_argument('--added-g', type=float)
    t.add_argument('--sd-cm2', type=float)
    a = p.parse_args()

    if a.cmd == 'selftest':
        return selftest()

    if a.cmd == 'magnitude':
        rows = magnitudes(a.wav, a.manifest)
        with open(a.out, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['hz', 'amplitude'])
            w.writerows([[hz, '%.8f' % v] for hz, v in rows])
        print('wrote %s -- %d tones' % (a.out, len(rows)))
        return 0

    if a.cmd == 'impedance':
        rows = impedance(read_csv2(a.ref), read_csv2(a.meas), a.resistor)
        with open(a.out, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['hz', 'z_ohm'])
            w.writerows([[hz, '%.4f' % v] for hz, v in rows])
        pk = max(rows, key=lambda r: r[1])
        print('wrote %s -- %d points, peak %.2f ohm at %.2f Hz' % (a.out, len(rows), pk[1], pk[0]))
        return 0

    zc = sorted(read_csv2(a.z).items())
    res = derive_ts(zc, a.re)
    if a.z_mass:
        if a.added_g is None or a.sd_cm2 is None:
            raise SystemExit('--z-mass needs --added-g and --sd-cm2')
        fsm = derive_ts(sorted(read_csv2(a.z_mass).items()), a.re)['fs_hz']
        res.update(derive_vas(res['fs_hz'], fsm, a.added_g, a.sd_cm2))
    print(json.dumps(res, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())


def search_offset(wav_path: str, manifest_path: str,
                  lo_hz: float = 20.0, hi_hz: float = 80.0,
                  start_s: float = -1.0, end_s: float = 8.0,
                  step_s: float = 0.02) -> float:
    """Find where the sweep begins by maximising in-band energy.

    Leader detection has now failed twice on real recordings -- once because the
    leader frequency was outside the chain's passband, once because a lossy codec
    smeared it. Alignment by total energy needs no leader at all: at the right
    offset each window holds its whole tone, and misaligned windows straddle
    boundaries and lose level. The peak is sharp, typically two orders of
    magnitude above the worst offset, so it is not a judgement call.
    """
    samples, rate = read_wav(wav_path)
    man = json.load(open(manifest_path))
    scale = rate / man['rate']
    tones = [t for t in man['tones'] if lo_hz <= t['hz'] <= hi_hz]
    if not tones:
        raise SystemExit('no tones in %g-%g Hz to align on' % (lo_hz, hi_hz))

    best = (None, -1.0)
    off = start_s
    while off <= end_s:
        o = int(off * rate)
        tot, ok = 0.0, True
        for t in tones:
            a = o + int(round(t['measure_start'] * scale))
            b = a + int(round(t['measure_samples'] * scale))
            if a < 0 or b > len(samples):
                ok = False
                break
            tot += bin_magnitude(samples[a:b], rate, t['hz'])
        if ok and tot > best[1]:
            best = (off, tot)
        off += step_s
    if best[0] is None:
        raise SystemExit('no offset fits the whole sweep -- the recording is too short')
    return best[0]
