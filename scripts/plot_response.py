#!/usr/bin/env python3
"""Render the measured-against-predicted response as an SVG. Stdlib only.

Writes images/response.svg and calculations/measured-vs-predicted.csv from the
measurement and model data, so the figure in the paper and the table behind it
come from one source and cannot drift apart.

    python3 scripts/plot_response.py
    python3 scripts/plot_response.py --dark      images/response-dark.svg

The dark variant exists so a <picture> block can hand the reader the figure drawn on
their own background. A chrome surface returns the room it is in; this is the only
place a web page can do that.
"""
import csv, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'calculations'))
from derive_crossover import COMBINED_HZ, COMBINED_ORDER, butter  # one source for the filter

W, H = 760, 380
L, R, T, B = 56, 18, 20, 52
FMIN, FMAX, DMIN, DMAX = 12.0, 200.0, -62.0, 10.0
MEAS, PRED, INK, MUTED, GRID = '#1B6CA8', '#C4762A', '#1d2125', '#6b7580', '#dfe3e8'
FILT = '#4f5964'
PAPER, PLOT = '#ffffff', '#fafbfc'
DARK = dict(MEAS='#56A8E0', PRED='#E09A4F', FILT='#c3ccd6', INK='#e6e9ed', MUTED='#8b95a1',
            GRID='#2b3138', PAPER='#0d1117', PLOT='#11161d')


def read(path):
    with open(path, newline='') as fh:
        return {float(r['hz']): float(r['db']) for r in csv.DictReader(fh)}


def px(hz):
    return L + (math.log(hz) - math.log(FMIN)) / (math.log(FMAX) - math.log(FMIN)) * (W - L - R)


def py(db):
    return T + (DMAX - db) / (DMAX - DMIN) * (H - T - B)


def filter_db(f):
    """The measured chain, receiver and plate amplifier together: 4th order, -3 dB at 57 Hz."""
    return 20.0 * math.log10(butter(f, COMBINED_HZ, COMBINED_ORDER))


def main():
    global MEAS, PRED, FILT, INK, MUTED, GRID, PAPER, PLOT
    dark = '--dark' in sys.argv
    if dark:
        MEAS, PRED, FILT, INK = DARK['MEAS'], DARK['PRED'], DARK['FILT'], DARK['INK']
        MUTED, GRID, PAPER, PLOT = DARK['MUTED'], DARK['GRID'], DARK['PAPER'], DARK['PLOT']
    meas = read(os.path.join(ROOT, 'data', 'response_sub_isolated.csv'))
    pred = read(os.path.join(ROOT, 'data', 'predicted_sealed.csv'))
    hz = [h for h in sorted(meas) if FMIN <= h <= FMAX]

    def nearest(d, f):
        return d[min(d, key=lambda k: abs(math.log(k) - math.log(f)))]

    # table behind the figure, so both come from the same numbers
    out = os.path.join(ROOT, 'calculations', 'measured-vs-predicted.csv')
    with open(out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['hz', 'measured_db', 'predicted_db', 'difference_db', 'filter_db'])
        for f in hz:
            m, p = meas[f], nearest(pred, f)
            w.writerow(['%.1f' % f, '%.2f' % m, '%.2f' % p, '%+.2f' % (m - p),
                        '%.2f' % (filter_db(f) + 0.0 if filter_db(f) < -0.005 else 0.0)])

    def path(d):
        return 'M ' + ' L '.join('%.1f %.1f' % (px(f), py(d[f] if f in d else nearest(d, f))) for f in hz)

    # sampled finely rather than at the 27 measured tones: this one is a formula
    fine = [FMIN * (FMAX / FMIN) ** (i / 240.0) for i in range(241)]
    fpath = 'M ' + ' L '.join('%.1f %.1f' % (px(f), py(filter_db(f))) for f in fine)

    xt = [(20, '20'), (30, '30'), (50, '50'), (80, '80'), (120, '120'), (200, '200')]
    yt = [(10, '+10'), (0, '0'), (-20, '−20'), (-40, '−40'), (-60, '−60')]
    g = ''.join('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s"/>'
                % (px(v), T, px(v), H - B, GRID) for v, _ in xt)
    g += ''.join('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s"/>'
                 % (L, py(v), W - R, py(v), GRID) for v, _ in yt)
    xl = ''.join('<text x="%.1f" y="%d" text-anchor="middle">%s</text>' % (px(v), H - B + 18, t) for v, t in xt)
    yl = ''.join('<text x="%d" y="%.1f" text-anchor="end">%s</text>' % (L - 9, py(v) + 4, t) for v, t in yt)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     font-family="system-ui,-apple-system,Segoe UI,sans-serif" role="img"
     aria-label="Measured response against prediction and the filter chain, 12 to 200 hertz">
<rect width="{W}" height="{H}" fill="{PAPER}"/>
<rect x="{L}" y="{T}" width="{W-L-R}" height="{H-T-B}" fill="{PLOT}"/>
{g}
<path d="{path(pred)}" fill="none" stroke="{PRED}" stroke-width="2.2" stroke-dasharray="6 4"/>
<path d="{fpath}" fill="none" stroke="{FILT}" stroke-width="2" stroke-linecap="round" stroke-dasharray="0.5 5"/>
<path d="{path(meas)}" fill="none" stroke="{MEAS}" stroke-width="2.6" stroke-linejoin="round"/>
<g font-size="11.5" fill="{MUTED}">{xl}{yl}</g>
<text x="{(L+W-R)//2}" y="{H-14}" text-anchor="middle" font-size="11.5" fill="{MUTED}">frequency (Hz)</text>
<text x="16" y="{(T+H-B)//2}" text-anchor="middle" font-size="11.5" fill="{MUTED}"
      transform="rotate(-90 16 {(T+H-B)//2})">relative level (dB)</text>
<g font-size="12.5" fill="{INK}">
  <line x1="{L+14}" y1="{T+16}" x2="{L+40}" y2="{T+16}" stroke="{MEAS}" stroke-width="2.6"/>
  <text x="{L+47}" y="{T+20}">measured</text>
  <line x1="{L+130}" y1="{T+16}" x2="{L+156}" y2="{T+16}" stroke="{PRED}" stroke-width="2.2" stroke-dasharray="6 4"/>
  <text x="{L+163}" y="{T+20}">predicted</text>
  <line x1="{L+246}" y1="{T+16}" x2="{L+272}" y2="{T+16}" stroke="{FILT}" stroke-width="2" stroke-linecap="round" stroke-dasharray="0.5 5"/>
  <text x="{L+279}" y="{T+20}">filter chain, 4th order, −3 dB at {COMBINED_HZ:.0f} Hz</text>
</g>
</svg>
'''
    sp = os.path.join(ROOT, 'images',
                      'response-dark.svg' if dark else 'response.svg')
    open(sp, 'w').write(svg)
    print('wrote %s' % sp)
    if not dark:
        print('wrote %s  (%d rows)' % (out, len(hz)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
