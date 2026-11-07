#!/usr/bin/env python3
"""Render a draft README as a local HTML preview. Stdlib only.

    python3 scripts/preview_readme.py [--in README.md]

An approximation of GitHub's render, for looking at a draft before it goes anywhere
public. Collapsible sections, the theme-reactive figure and the animated GIF are the
real behaviour. The fenced `stl` block is replaced by a three.js viewer standing in for
GitHub's own, which exists only on github.com.

This lives in the repository rather than in a scratch directory deliberately: the first
copy was written to a temporary directory and was gone by the next session, which is
also how an earlier renderer on another project was lost.

Writes preview-chrome-draft.html at the repository root so images/ resolves. The file
is scaffolding and not part of the build guide.
"""
import argparse, html, io, os, re, sys

import make_stl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CSS = """
:root{--bg:#fff;--fg:#1f2328;--mut:#59636e;--line:#d1d9e0;--code:#f6f8fa}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;
 --line:#3d444d;--code:#151b23}}
body{background:var(--bg);color:var(--fg);margin:0;padding:40px 16px 120px;
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:1012px;margin:0 auto}
.banner{border:1px solid var(--line);border-left:4px solid #d29922;border-radius:6px;
 padding:12px 16px;margin-bottom:32px;color:var(--mut);font-size:14px}
p{margin:0 0 16px}img,svg{max-width:100%}
pre{background:var(--code);border-radius:6px;padding:16px;overflow:auto;font-size:13px;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
code{background:var(--code);border-radius:4px;padding:.2em .4em;font-size:85%;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
pre code{background:none;padding:0;font-size:inherit}
details{border:1px solid var(--line);border-radius:6px;padding:12px 16px;margin:0 0 12px}
summary{cursor:pointer;font-weight:600;margin:-12px -16px;padding:12px 16px}
hr{border:0;border-top:1px solid var(--line);margin:32px 0}
h1{font-size:2em;font-weight:600;line-height:1.25;margin:24px 0 16px;padding-bottom:.3em;
 border-bottom:1px solid var(--line)}
table{border-collapse:collapse;margin:0 0 16px;display:block;overflow:auto}
th,td{border:1px solid var(--line);padding:6px 13px}
a{color:#0969da}@media (prefers-color-scheme:dark){a{color:#4493f8}}
#stlview{border:1px solid var(--line);border-radius:6px;overflow:hidden;
 margin-bottom:24px;position:relative;background:var(--code)}
#c{display:block;width:100%;height:600px}
.hint{position:absolute;left:12px;bottom:10px;font-size:12px;color:#1f2328}
button{font:inherit;font-size:12px;cursor:pointer;background:var(--bg);color:var(--fg);
 border:1px solid var(--line);border-radius:5px;padding:2px 8px}
"""

JS = """
import * as THREE from 'three';
import {STLLoader} from 'three/addons/loaders/STLLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {mergeVertices} from 'three/addons/utils/BufferGeometryUtils.js';
const CY=@@CY@@,R=@@R@@;
const cv=document.getElementById('c');
const r=new THREE.WebGLRenderer({canvas:cv,antialias:true});
r.setPixelRatio(devicePixelRatio);
r.toneMapping=THREE.ACESFilmicToneMapping;r.toneMappingExposure=1.05;
const sc=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(38,1,1,5000);

// A mirror is only what surrounds it. A flat face seen from above reflects what is below
// it and seen from below what is above, so no part of the surround may be dark: bright
// floor and ceiling, one thin dark line for a horizon, and panels all the way round so
// that turning the model always brings something new across its faces.
function room(){
  const c=document.createElement('canvas');c.width=2048;c.height=1024;
  const x=c.getContext('2d');
  const g=x.createLinearGradient(0,0,0,1024);
  g.addColorStop(0,'#ffffff');g.addColorStop(.4,'#c6ced8');g.addColorStop(.485,'#8f99a6');
  g.addColorStop(.5,'#3c434c');g.addColorStop(.515,'#8f99a6');g.addColorStop(.62,'#bcc4ce');
  g.addColorStop(1,'#eef1f5');
  x.fillStyle=g;x.fillRect(0,0,2048,1024);
  x.filter='blur(10px)';
  for(let i=0;i<8;i++){
    const u=i*256+40;
    x.fillStyle='#ffffff';x.fillRect(u,180,120,290);x.fillRect(u+128,560,90,230);
    x.fillStyle='#5a636e';x.fillRect(u+150,150,16,330);x.fillRect(u+20,540,14,260);
  }
  x.filter='none';
  const t=new THREE.CanvasTexture(c);
  t.mapping=THREE.EquirectangularReflectionMapping;t.colorSpace=THREE.SRGBColorSpace;
  return t;
}
const roomTex=room();
const pm=new THREE.PMREMGenerator(r);
sc.environment=pm.fromEquirectangular(roomTex).texture;
sc.background=roomTex;sc.backgroundBlurriness=.7;   // it reflects the room you can see

// Vinyl over a sanded panel is not optically flat. A slight vertical tilt of the normal
// makes the reflected horizon waver, as it does on the real cabinet. Kept small: this is
// the surface's departure from flat, not a pattern laid on it.
const chrome=new THREE.MeshStandardMaterial({color:0xf2f4f7,metalness:1,roughness:.045,
  side:THREE.DoubleSide});
chrome.onBeforeCompile=sh=>{
  sh.vertexShader=sh.vertexShader
    .replace('#include <common>','#include <common>\\nvarying vec3 vP;varying vec3 vUp;')
    .replace('#include <begin_vertex>','#include <begin_vertex>\\nvP=position;vUp=normalMatrix*vec3(0.,1.,0.);');
  sh.fragmentShader=sh.fragmentShader
    .replace('#include <common>','#include <common>\\nvarying vec3 vP;varying vec3 vUp;')
    .replace('#include <normal_fragment_maps>',`#include <normal_fragment_maps>
      float w=vP.x+vP.z;
      normal=normalize(normal+normalize(vUp)*(
        .020*sin(vP.y*.052+1.4*sin(w*.012))
       +.011*sin(vP.y*.131+w*.021+1.)
       +.005*sin(vP.y*.29-w*.037+2.)));`);
};
const rubber=new THREE.MeshStandardMaterial({color:0x0a0a0b,metalness:0,roughness:.5,
  side:THREE.DoubleSide});

// Parsed from the page, not fetched: browsers refuse fetch() on a file:// page, and this
// is the block the README actually carries rather than the finer images/enclosure.stl.
const p=new STLLoader().parse(document.getElementById('stl').textContent)
  .getAttribute('position').array;
const cab=[],drv=[];
for(let i=0;i<p.length;i+=9){
  const x=(p[i]+p[i+3]+p[i+6])/3,y=(p[i+1]+p[i+4]+p[i+7])/3,z=(p[i+2]+p[i+5]+p[i+8])/3;
  (Math.hypot(x,y-CY)<=R+.5&&z<60?drv:cab).push(...p.subarray(i,i+9));
}
const geo=a=>{const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.Float32BufferAttribute(a,3));return g;};
const gc=geo(cab);gc.computeVertexNormals();
const gd=mergeVertices(geo(drv),.02);gd.computeVertexNormals();  // rubber is smooth, chrome is faceted
const obj=new THREE.Group();
obj.add(new THREE.Mesh(gc,chrome),new THREE.Mesh(gd,rubber));
obj.position.z=-140;sc.add(obj);
cam.position.set(620,70,-1320);cam.lookAt(0,0,0);
document.getElementById('wire').onclick=()=>{chrome.wireframe=!chrome.wireframe;rubber.wireframe=chrome.wireframe;};
const ctl=new OrbitControls(cam,cv);ctl.enableDamping=true;
function size(){const w=cv.clientWidth,h=cv.clientHeight;r.setSize(w,h,false);
 cam.aspect=w/h;cam.updateProjectionMatrix();}
addEventListener('resize',size);size();
(function loop(){requestAnimationFrame(loop);ctl.update();r.render(sc,cam);})();
"""


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', t)
    t = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',
               r'<img src="\2" alt="\1">', t)        # images first
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', t)
    for tag in ('sub', 'sup'):
        t = t.replace('&lt;%s&gt;' % tag, '<%s>' % tag)
        t = t.replace('&lt;/%s&gt;' % tag, '</%s>' % tag)
    return t


def stamped():
    """The aperture's centre and radius, from make_stl, so the split cannot drift."""
    d = make_stl.dims()
    cy = make_stl.margin_centre(d['box external width'], d['box external height'])[1]
    return (JS.replace('@@CY@@', repr(cy))
              .replace('@@R@@', repr(d['flange outer diameter'] / 2.0)))


def cells(ln):
    return ln.strip().strip('|').split('|')


def row(ln, tag, aligns):
    return '<tr>%s</tr>' % ''.join(
        '<%s style="text-align:%s">%s</%s>' % (tag, a, inline(c.strip()), tag)
        for c, a in zip(cells(ln), aligns))


def convert(src):
    """Markdown subset -> HTML. The one rule worth stating: a line is HTML if it starts
    with '<' AFTER indentation. Testing the raw line escapes the indented <source> and
    <img> inside a <picture> block, which silently deletes the figure and prints its
    markup as prose."""
    m = re.search(r'```stl\n(.*?)\n```', src, re.S)
    stl = m.group(1) if m else ''
    if m:
        src = src[:m.start()] + '@@STL@@' + src[m.end():]
    out, i, lines = [], 0, src.split('\n')
    while i < len(lines):
        ln, bare = lines[i], lines[i].lstrip()
        if bare.startswith('```'):
            lang = bare[3:].strip(); i += 1; buf = []
            while i < len(lines) and not lines[i].lstrip().startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            out.append('<pre class="%s"><code>%s</code></pre>'
                       % (lang, html.escape('\n'.join(buf))))
        elif bare.startswith('$$'):
            t = bare
            if t.endswith('$$') and len(t) > 4:
                buf = [t]; i += 1
            else:
                buf = [ln]; i += 1
                while i < len(lines) and not lines[i].lstrip().startswith('$$'):
                    buf.append(lines[i]); i += 1
                if i < len(lines):
                    buf.append(lines[i]); i += 1
            out.append('<div class="math">%s</div>' % html.escape('\n'.join(buf)))
        elif bare == '@@STL@@':
            out.append('<div id="stlview"><canvas id="c"></canvas><div class="hint">'
                       'drag to turn · scroll to zoom · '
                       '<button id="wire">wireframe</button></div></div>'
                       '<script type="text/plain" id="stl">%s</script>' % stl); i += 1
        elif (bare.startswith('|') and i + 1 < len(lines)
              and re.fullmatch(r'\|(\s*:?-+:?\s*\|)+', lines[i + 1].strip())):
            aligns = ['right' if c.strip().endswith(':') else 'left'
                      for c in cells(lines[i + 1])]
            out.append('<table>' + row(ln, 'th', aligns))
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                out.append(row(lines[i], 'td', aligns)); i += 1
            out.append('</table>')
        elif bare.startswith('<!--'):
            while i < len(lines) and '-->' not in lines[i]:
                i += 1
            i += 1                      # the comment is dropped, contents and all
        elif re.match(r'#{1,3} ', bare):
            lvl = len(bare) - len(bare.lstrip('#'))
            out.append('<h%d>%s</h%d>' % (lvl, inline(bare[lvl + 1:]), lvl)); i += 1
        elif bare == '---':
            out.append('<hr>'); i += 1
        elif bare.startswith('<'):
            out.append(ln); i += 1
        elif not bare:
            i += 1
        else:
            buf = []
            while (i < len(lines) and lines[i].strip()
                   and not lines[i].lstrip().startswith(('<', '```', '$$'))
                   and lines[i].strip() != '---'):
                buf.append(lines[i].strip()); i += 1
            out.append('<p>%s</p>' % inline(' '.join(buf)))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='README.md')
    ap.add_argument('--out', default='preview-chrome-draft.html')
    a = ap.parse_args()
    os.chdir(ROOT)
    body = convert(io.open(a.inp, encoding='utf-8').read())
    page = ('<!doctype html><html><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<title>README draft — chrome-subwoofer</title>\n'
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/'
            'KaTeX/0.16.9/katex.min.css">\n<style>%s</style></head><body><main>\n'
            '<div class="banner"><strong>Local preview.</strong> An approximation of '
            "GitHub's render. The chrome finish exists only here: GitHub's STL viewer draws "
            'the same geometry in one flat colour, with wireframe and surface-angle '
            'modes. The collapsible sections, the theme-reactive figure and the '
            'animated GIF are the real behaviour. Scaffolding — delete when done.'
            '</div>\n%s\n</main>\n'
            '<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/'
            'npm/three@0.160.0/build/three.module.js","three/addons/":"https://'
            'cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script>\n'
            '<script type="module">%s</script>\n'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/'
            'katex.min.js"></script>\n'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/'
            'auto-render.min.js" onload="renderMathInElement(document.body,'
            "{delimiters:[{left:'$$',right:'$$',display:true}]})\">"
            '</script>\n</body></html>\n') % (CSS, body, stamped())
    io.open(a.out, 'w', encoding='utf-8').write(page)
    print('%s  %.0f KB  (from %s)' % (a.out, os.path.getsize(a.out) / 1024.0, a.inp))
    return 0


if __name__ == '__main__':
    sys.exit(main())
