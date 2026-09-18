# data

| file | what it is |
|---|---|
| `response_sub_isolated.csv` | **DR0000_0123, 2026-09-16. Mains disconnected.** 24-bit WAV, peak -2.8 dBFS, no clipping. The first take that measures the enclosure |
| `response_system_nearfield.csv` | DR0000_0121, sub + both mains. Kept as the contrast that proves isolation |
| `response_panel_position.csv` | DR0000_0122, M9 panel position. 24-bit WAV, peak -3.1 dBFS, no clipping |
| `predicted_sealed.csv` | `model.py --fc 40.27 --qtc 0.799`, from NOMINAL T/S |
| `response_nearfield.csv` | superseded. DR0000_0117, 320 kbps MP3 |

## Isolation confirmed by DR0000_0123

With the mains disconnected the sub falls to **-42 to -59 dB above 128 Hz**, against
-11 to -18 dB for the same positions with the mains live. A 24 to 43 dB difference,
rising with frequency exactly as two-way mains taking over would.

That is a clean control, and it settles two things:

**The M9 panel result was the mains, not the panel.** The +5 to +11 dB seen at
104-195 Hz in the panel take does not survive isolation -- the sub alone produces
essentially nothing up there.

**It also answers the bracing question.** At 175 Hz the isolated sub is 59 dB down.
Whatever the panels are doing at their computed 260-590 Hz fundamental, nothing is
exciting them, because nothing above ~100 Hz reaches the driver. Consistent with
`panel_modes.py`, and arrived at from the opposite direction.

## The SPA300-D low-pass, measured

The 80 Hz figure was a rough estimate from the spec sheet. It is a **knob**, and the
data says where it is actually set.

Dividing the measurement by the sealed-box model leaves a residual that should be the
amplifier's filter and nothing else. Fitting Butterworth magnitudes to it over
45-110 Hz:

| order | corner | mean error |
|---|---|---|
| 2 | 41.2 Hz | 2.93 dB |
| 3 | 53.0 Hz | 1.65 dB |
| **4** | **57.0 Hz** | **1.19 dB** |
| 5 | 60.5 Hz | 1.73 dB |

Two independent slope measurements agree: **24.4 and 24.6 dB/octave**, which is 4th
order. So the knob sits near **57 Hz with a 24 dB/octave slope** -- not 80 Hz.

**The box model plus that filter accounts for the measurement to 1.19 dB mean over
45-110 Hz.** That is the strongest agreement anything here has produced, and it was
obtained by letting the data set the crossover rather than assuming it.

Two points fit poorly and are worth naming rather than smoothing: **55.5 Hz** sits
+2.9 dB above the fit and **93.7 Hz** +2.9 dB. The room's second-order length mode
computes to 53.6 Hz, which is near the first -- a candidate, not a conclusion.

## Still unexplained: +3 dB near Fc

Over 32-56 Hz, clear of the amplifier filter, the measurement runs about 3 dB above
the box model. Candidates, none eliminated by this data:

- actual Qtc higher than the nominal 0.799, i.e. the published T/S is wrong for this unit
- boundary reinforcement -- AST-002 shows the box against a wall
- the DR-05's own microphone response

The shape is mildly informative: it is a **bump centred near Fc**, not a monotonic rise
toward low frequency, and boundary gain more usually does the latter. That leans toward
Qtc. It does not settle it, and room modes also make bumps.

## The superseded takes



**The microphone hears the whole system: the sub and both Nova 7B mains.** Confirmed
in AST-002, which shows a Nova 7B standing directly on top of the subwoofer. There is
no microphone position near the sub that is not also within centimetres of a main
speaker.

Three consequences, and none of them are small:

1. **The 50-70 Hz reference band is the worst possible place to normalise.** It sits
   right at the 80 Hz crossover where sub and mains overlap most, so the reference
   itself is contaminated and every dB value inherits it.

2. **The M9 panel result is confounded and cannot be read.** Moving the mic from the
   cone to the panel also moved it relative to the speaker sitting on the box. The
   +5 to +11 dB seen at 104-195 Hz has at least three candidate explanations --
   panel radiation, changed distance to the main speaker, different room reflections
   at the two positions -- and **this data cannot separate them.**

3. **Placement is uncontrolled.** AST-002 shows the sub against a wall in an alcove.
   Boundary reinforcement is a live candidate for the region where measurement ran
   above prediction, alongside the nominal T/S being wrong for this unit.

## What would fix it

Mute or disconnect the mains and repeat. That is the whole remedy, and until it is
done nothing here supports a claim about the enclosure.

## Limits that apply regardless

- Uncalibrated microphone: **shape only, never absolute SPL**
- Above ~80 Hz the curve is the SPA300-D low-pass plus the mains
- Below ~20 Hz output approaches the room noise floor
