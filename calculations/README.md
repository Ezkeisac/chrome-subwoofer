# Calculations

Every number the build rests on, and where it came from.

| file | what it holds |
|---|---|
| `box-dimensions.csv` | driver and enclosure geometry, mm and inches |
| `volume.csv` | internal, displaced and effective volume |
| `materials-cost.csv` | the bill of materials |
| `derive_box.py` | the dimensioning, run as a script so it can be checked |

```bash
python3 derive_box.py
```

## The dimensioning method in one line

**The cross-section was fixed by requirement R3; only the height was free.**

R3 asks for the same footprint as a Nova 7B so the subwoofer can sit under one and
act as its stand. That fixes external width and length, and therefore internal width
and length once wall thickness is subtracted. The enclosure volume the driver wants
then has exactly one way to be satisfied:

```
height = volume / (internal width x internal length)
```

which is why the box is tall and narrow rather than the cube a free design would give.
Everything else follows from that one constraint.
