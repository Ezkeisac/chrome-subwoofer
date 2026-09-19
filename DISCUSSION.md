# Discussion

Companion to [`README.md`](README.md). Section numbering follows the paper.

## 6.1 Verification against requirements

**R1 — output to approximately 35 Hz.** Predicted *F*<sub>3</sub> is 36.2 Hz, and the
measured spectral shape is consistent with this value. **Supported but not confirmed**, an
uncalibrated instrument providing no absolute reference.

**R2 — integration with the mains.** The acoustic transition occurs near 80 Hz with
neither a deficiency nor an excess evident across the overlap. **Satisfied** within the
resolution of the method.

**R3 — footprint.** Satisfied by construction (Figure 3).

**R4 — chrome finish.** Satisfied (Figure 3).

**R6 — 60 Hz crossover.** Measurement gives the combined filter chain as fourth-order,
−3 dB at **57 Hz**. Deconvolving the receiver's fixed 90 Hz SUB WOOFER stage [1] places the plate
amplifier's own setting at approximately **62 Hz**, within 2 Hz of the requirement.
**Satisfied.** Derivation: [`calculations/derive_crossover.py`](calculations/derive_crossover.py).

> This deconvolution assumes the receiver stage to be second-order at 90 Hz. The manual
> specifies the frequency but not the slope, which was not independently confirmed. **The
> combined result — fourth-order at 57 Hz — is measured directly and is independent of
> how the two stages divide.**

## 6.2 Enclosure resonance and the necessity of bracing

Two independent arguments.

**Analytically:** treating the largest panel (280 × 623 mm, 19 mm MDF) as a rectangular
plate bounds its fundamental bending mode between 260 and 590 Hz, across simply-supported
to fully-clamped edge conditions and a realistic range of MDF elastic modulus
([`panel_modes.py`](scripts/panel_modes.py)). **Empirically:** the isolated subwoofer
measures **59 dB below reference at 175 Hz**.

A panel radiates at its resonance only when excited there. Since no significant energy
above roughly 100 Hz reaches the driver, the panel resonance — wherever it falls within
the computed bounds — is never excited, and bracing would have served no function.

**A superseded result.** With the microphone at the side panel, an excess of 5–11 dB was
initially observed between 104 and 195 Hz, consistent in form with panel radiation. It did
not survive isolation of the source: a main loudspeaker stands on the subwoofer, so moving
the microphone from cone to panel also moved it relative to that loudspeaker. With the
mains disconnected the difference between conditions above 128 Hz is 24–43 dB, increasing
with frequency — the behaviour of two-way loudspeakers assuming the band.

The error was caught only because the measurement had been recorded as confounded before
the isolated take existed. **A result consistent with an anticipated conclusion warrants
greater scrutiny, not less.**

## 6.3 Unresolved residual

Between 32 and 56 Hz, clear of the filter chain, measurement exceeds prediction by about
3 dB. Three hypotheses: the published parameters do not describe this specimen (§2.3);
boundary reinforcement, the cabinet being against a wall; or non-flat microphone response.

**None is eliminated by the present data.** The residual is a maximum centred near
*F*<sub>c</sub> rather than a monotonic rise toward low frequency, the latter being more
characteristic of boundary loading — weakly favouring the first without establishing it.
Resolution requires measured driver parameters, or repetition with the cabinet away from
the boundary.

## 6.4 Recommendations for repetition

- **Measure driver parameters prior to construction.** Every unresolved residual reported
  here admits "the published parameters may be inaccurate" among its hypotheses.
- **Document construction contemporaneously.** Portions of §3 are reconstructed.
- **Employ a calibrated microphone.** This converts every relative measurement reported
  here into an absolute one, at a cost small relative to the build.
- **Account for both filter stages at the design stage.** The receiver's fixed 90 Hz
  stage was not anticipated, and the plate amplifier was adjusted as though it were the
  only filter in the path.

---
