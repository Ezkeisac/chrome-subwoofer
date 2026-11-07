# Measurement method — implementation detail

The reasoning behind stepped tones rather than a sweep is in `PAPER.md`, §4.2. This file
records what that choice costs and how the programs are built to pay it. Every constant
quoted here is the one in the code; change it there, not here.

| | |
|---|---|
| Generator | [`tone_sequence.py`](tone_sequence.py) |
| Magnitude extraction, alignment | [`analyse_impedance.py`](analyse_impedance.py) |
| Response and comparison | [`analyse_response.py`](analyse_response.py) |

Standard library only. Each carries a `selftest`.

---

## 1. Tone duration scales with frequency

A window fixed in seconds holds progressively fewer cycles as frequency falls, and the
region of interest is the lowest. At 5 Hz a 0.5 s window contains two and a half cycles,
from which no clean magnitude can be taken — and free-air resonance sits down in exactly
that region.

Duration is therefore the longer of a floor in seconds and a floor in cycles:

```
settle  = max(settle_s,  MIN_SETTLE_CYCLES  / f)      MIN_SETTLE_CYCLES  = 4
measure = max(measure_s, MIN_MEASURE_CYCLES / f)      MIN_MEASURE_CYCLES = 8
```

Above the frequency where the two floors cross, the fixed one wins and windows are
constant; below it the cycle count wins and windows lengthen as frequency falls. The settle period is discarded,
not analysed: it exists so the driver and the room are in steady state before the measured
window opens.

Frequencies are spaced logarithmically (`log_points`), because an equal-interval sweep
spends most of its points where nothing is happening.

## 2. Each step is faded in and out

Tones carry a 20 ms raised-cosine fade at each end. A hard edge is broadband — it deposits
energy at every frequency including the one being measured, which is the classic way a
stepped-sine rig lies quietly. Steps are separated by 0.3 s of silence.

## 3. The generator writes the layout; the analyser reads it

`tone_sequence.py` emits a `.json` manifest beside the `.wav`, recording the sample rate,
the leader, and for every tone its frequency, `measure_start` and `measure_samples`. The
analyser reads that file rather than recomputing the layout.

This is the point of the design. Two programs deriving the same layout independently is an
invitation to disagree silently — the kind of disagreement that yields a plausible curve
rather than an obvious failure. **Keep the manifest with the recording.** Regenerating the
wav without it leaves a recording nothing can interpret.

The manifest indexes samples at the rate the sequence was *generated* at. A recording made
at a different rate has every position rescaled by the ratio, and the rescaling is
announced; without it each window lands on the wrong tone, progressively worse the further
into the take. A recording that ends early is reported as truncated at the frequency where
it ran out, with a count of usable tones, rather than silently returning a short curve.

## 4. Magnitude is read at one frequency, not transformed

`bin_magnitude` evaluates a single DFT bin at the known frequency, Hann-windowed —
a product against cosine and sine, summed. There is no FFT and no need of one: the
frequency is known in advance, so only one bin is ever wanted. This is what keeps the
analysis inside the standard library.

Normalisation is by the window sum rather than by sample count. A Hann window has a
coherent gain of 0.5, so dividing by *n* would report every amplitude at half its value.
The scaling is identical for every tone in any case, and every figure downstream is a
ratio of two of them, so it cancels.

## 5. Alignment, and why the marker is not trusted

The sequence carries a 1 kHz leader for the analyser to find its start, and a trailer so a
truncated take is obvious.

**Leader detection has failed twice on real recordings.** Once because the leader lies
outside the chain's passband — measuring a subwoofer acoustically, nothing above 80 Hz is
reproduced, so a 1 kHz leader is simply absent, and a broadband detector locked instead
onto the first loud event, the subwoofer entering its own passband eighteen seconds later.
Every window then landed on the wrong tone. Once because a lossy codec smeared the marker
past recognition.

Two fixes, in order of preference:

1. `find_leader` tests energy **at the leader's own frequency** rather than broadband RMS,
   in 50 ms blocks, so whatever else is loud is ignored.
2. `search_offset` dispenses with the leader altogether, scanning candidate offsets in
   20 ms steps and maximising in-band energy over 20–80 Hz. At the correct offset every
   window holds its whole tone; misaligned windows straddle boundaries and lose level. The
   peak runs typically two orders of magnitude above the worst offset, so it is not a
   judgement call.

An offset may also be supplied by hand, which skips detection entirely.

## 6. What comes out, and in what units

Curves are **relative**. The DR-05 is uncalibrated, so each is normalised to its mean level
over a reference band of 50–70 Hz and expressed in dB about that. *F*<sub>3</sub> is found
by interpolating where the curve crosses −3 dB.

The reference band must sit inside the usable band, which is narrow: the plate amplifier
low-passes at 80 Hz, so everything above that is the amplifier rolling off rather than the
enclosure. Useful comparison runs roughly 20–70 Hz.

Spectral shape is available — a knee, a slope, where a resonance sits. Absolute sound
pressure is not, and no claim in this repository depends on it.
