#!/usr/bin/env python3
"""Render a draft README as a local HTML preview. Stdlib only.

    python3 scripts/preview_readme.py [--in README-chrome-draft.md]

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
a{color:#0969da}@media (prefers-color-scheme:dark){a{color:#4493f8}}
#stlview{border:1px solid var(--line);border-radius:6px;overflow:hidden;
 margin-bottom:24px;position:relative;background:var(--code)}
#c{display:block;width:100%;height:460px}
.hint{position:absolute;left:12px;bottom:10px;font-size:12px;color:var(--mut)}
button{font:inherit;font-size:12px;cursor:pointer;background:var(--bg);color:var(--fg);
 border:1px solid var(--line);border-radius:5px;padding:2px 8px}
"""

JS = """
import * as THREE from 'three';
import {STLLoader} from 'three/addons/loaders/STLLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const cv=document.getElementById('c');
const dark=matchMedia('(prefers-color-scheme:dark)').matches;
const r=new THREE.WebGLRenderer({canvas:cv,antialias:true});
r.setPixelRatio(devicePixelRatio);
const sc=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(38,1,1,5000);
sc.add(new THREE.HemisphereLight(0xffffff,0x334155,2.1));
const d1=new THREE.DirectionalLight(0xffffff,1.5);d1.position.set(600,900,800);sc.add(d1);
const mat=new THREE.MeshStandardMaterial({color:dark?0x9fb3c8:0xb9c4cf,
 metalness:.72,roughness:.3,side:THREE.DoubleSide});
new STLLoader().load('images/enclosure.stl',g=>{
  g.computeVertexNormals();g.center();
  const m=new THREE.Mesh(g,mat);sc.add(m);
  const b=new THREE.Box3().setFromObject(m),s=b.getSize(new THREE.Vector3()).length();
  cam.position.set(s*.42,s*.18,s*.78);cam.lookAt(0,0,0);
  document.getElementById('wire').onclick=()=>{mat.wireframe=!mat.wireframe;};
},undefined,e=>{
  document.querySelector('.hint').textContent =
    'model failed to load \\u2014 three.js comes from a CDN, so this needs network';
});
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


def convert(src):
    """Markdown subset -> HTML. The one rule worth stating: a line is HTML if it starts
    with '<' AFTER indentation. Testing the raw line escapes the indented <source> and
    <img> inside a <picture> block, which silently deletes the figure and prints its
    markup as prose."""
    m = re.search(r'```stl\n.*?\n```', src, re.S)
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
                       '<button id="wire">wireframe</button></div></div>'); i += 1
        elif bare.startswith('<!--'):
            while i < len(lines) and '-->' not in lines[i]:
                i += 1
            i += 1                      # the comment is dropped, contents and all
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
    ap.add_argument('--in', dest='inp', default='README-chrome-draft.md')
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
            "GitHub's render. The model uses three.js in place of GitHub's own STL "
            'viewer; the collapsible sections, the theme-reactive figure and the '
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
            '</script>\n</body></html>\n') % (CSS, body, JS)
    io.open(a.out, 'w', encoding='utf-8').write(page)
    print('%s  %.0f KB  (from %s)' % (a.out, os.path.getsize(a.out) / 1024.0, a.inp))
    return 0


if __name__ == '__main__':
    sys.exit(main())
