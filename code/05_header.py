"""Step 5. Render header.png (1200x630 social card) with Playwright Chromium.

Reads the data embedded in index.html. Fonts: set FONT_DIR to a folder holding FrauncesVar.ttf,
SourceSerif4-Regular.ttf, IBMPlexMono-Regular.ttf and IBMPlexMono-Medium.ttf (from github.com/google/fonts);
otherwise system serif fonts are used.

Usage:
    FONT_DIR=/path/to/fonts python3 code/05_header.py
"""
import json
import math
import os
import re

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json")))
S = json.loads(re.search(r"const D = (\{.*?\});\nconst R", open(os.path.join(ROOT, "index.html"), encoding="utf-8").read(), re.S).group(1))
FD = os.environ.get("FONT_DIR", "")
br = R["income_breaks"]
QC = ["#E9E1CF", "#C3D6CC", "#8DB8AF", "#4E8B86", "#1F5358"]


def proj(lat, lon):
    k = math.cos(math.radians(52.6))
    return (lon + 5.8) * k * 108, (55.9 - lat) * 108


dots = []
for a in S["msoa"]:
    x, y = proj(a[0], a[1]); q = sum(a[2] >= b for b in br)
    dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.1" fill="{QC[q]}"/>')
vil = []
for a in S["villas"]:
    x, y = proj(a[0], a[1])
    vil.append(f'<rect x="{x - 3.2:.1f}" y="{y - 3.2:.1f}" width="6.4" height="6.4" transform="rotate(45 {x:.1f} {y:.1f})" fill="#A8321E" stroke="#F6EEDF" stroke-width="1"/>')
ff = ""
if FD:
    ff = "".join(f"@font-face{{font-family:'{n}';src:url('file://{FD}/{f}');font-weight:{w};}}" for n, f, w in [
        ("Fraunces", "FrauncesVar.ttf", "100 900"), ("Source Serif 4", "SourceSerif4-Regular.ttf", "400"),
        ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "400"), ("IBM Plex Mono", "IBMPlexMono-Medium.ttf", "500")])
dek = (f"{R['villas']['total']:,} Roman villas against today's household incomes. "
       f"A {R['raw']['median_gap_pct'] * 100:.0f}% gap that geography explains away.")
html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{ff}
body{{margin:0;width:1200px;height:630px;background:#F6EEDF;color:#2B1B12;overflow:hidden;position:relative;font-family:'Source Serif 4',Georgia,serif}}
.b{{position:absolute;left:0;right:0;height:12px;background:linear-gradient(90deg,#A8321E 0 25%,#F6EEDF 25% 33.3%,#B97A1C 33.3% 58.3%,#F6EEDF 58.3% 66.6%,#2B1B12 66.6% 91.6%,#F6EEDF 91.6%) 0 0/36px 12px repeat-x}}
.k{{position:absolute;left:72px;top:62px;font:500 17px/1 'IBM Plex Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#76604F;display:flex;gap:14px;align-items:center}}
.k b{{background:#A8321E;color:#fff;padding:8px 10px;font-weight:500}}
h1{{position:absolute;left:68px;top:108px;margin:0;font:900 100px/.9 Fraunces,Georgia,serif;letter-spacing:-.02em;font-variation-settings:"SOFT" 50;width:640px}}
h1 em{{font-style:normal;color:#A8321E}}
p{{position:absolute;left:72px;top:418px;width:560px;margin:0;font-size:27px;line-height:1.36;color:#3D2A1E}}
.f{{position:absolute;left:72px;bottom:44px;font:400 15px/1 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:#8C7764}}
svg{{position:absolute;right:28px;top:22px}}
</style></head><body><div class="b" style="top:0"></div><div class="b" style="bottom:0"></div>
<div class="k"><b>Data study</b><span>History × data</span></div>
<h1>The Roman <em>commuter belt</em>?</h1>
<p>{dek}</p>
<div class="f">Dr Tristan Hotham · Independent researcher</div>
<svg width="520" height="600" viewBox="0 0 520 650">{''.join(dots)}{''.join(vil)}</svg>
</body></html>"""
tmp = os.path.join(ROOT, "_header.html")
open(tmp, "w", encoding="utf-8").write(html)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto("file://" + tmp); pg.wait_for_timeout(600)
    pg.screenshot(path=os.path.join(ROOT, "header.png")); b.close()
os.remove(tmp)
print("header.png written")
