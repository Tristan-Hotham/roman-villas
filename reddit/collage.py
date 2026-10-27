"""Reddit collage for The Roman Commuter Belt? (2400 x 3000 px). Run from this folder: python3 collage.py
Every number comes from ../data/results.json and the data files."""
import json, os
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle
from pyproj import Transformer
from shapely.geometry import shape

F = "/tmp/claude-0/-home-claude/c232619d-81e0-53f3-9de6-41e973630753/scratchpad/fonts/"
for f in ["FrauncesVar.ttf", "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "SourceSerif4-Regular.ttf", "SourceSerif4-Semibold.ttf", "SourceSerif4-It.ttf"]:
    fm.fontManager.addfont(F + f)
DISP = fm.FontProperties(fname=F + "FrauncesVar.ttf", weight=900)
SER, MONO = "Source Serif 4", "IBM Plex Mono"
BG, FG, MUT, LAND, EDGE = "#F4E6D2", "#2B1B12", "#7A5F4B", "#EADAC2", "#D7C2A3"
RED, OCH, TERRA = "#A8321E", "#B97A1C", "#C9663F"
QC = ["#E3D6BE", "#B9D2C8", "#7FAFA7", "#3F7F7B", "#174A50"]
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
R = json.load(open(os.path.join(ROOT, "data", "results.json")))
M = pd.read_csv(os.path.join(ROOT, "data", "msoa.csv")); V = pd.read_csv(os.path.join(ROOT, "data", "villas.csv"))
T = Transformer.from_crs(4326, 27700, always_xy=True)
pc = lambda v, d=0: f"{v * 100:.{d}f}%"
sp = lambda v, d=1: ("+" if round(v * 100, d) > 0 else "−" if round(v * 100, d) < 0 else "") + f"{abs(v) * 100:.{d}f}%"

fig = plt.figure(figsize=(12, 15), dpi=200, facecolor=BG)
# mosaic border: small square tesserae round the edge
bd = fig.add_axes([0, 0, 1, 1]); bd.set_xlim(0, 120); bd.set_ylim(0, 150); bd.axis("off"); bd.set_zorder(-5)
cols = [RED, OCH, FG, TERRA]
k = 0
for x in np.arange(0.6, 119.5, 1.5):
    for y in (0.6, 148.4):
        bd.add_patch(Rectangle((x, y), 1.0, 1.0, color=cols[k % 4], lw=0)); k += 1
for y in np.arange(2.1, 148.0, 1.5):
    for x in (0.6, 118.4):
        bd.add_patch(Rectangle((x, y), 1.0, 1.0, color=cols[k % 4], lw=0)); k += 1

fig.text(0.05, 0.962, "Did the Romans pick", fontproperties=DISP, fontsize=46, color=FG, va="top")
fig.text(0.05, 0.917, "the commuter belt?", fontproperties=DISP, fontsize=46, color=RED, va="top")
fig.text(0.05, 0.872, f"{R['villas']['total']:,} Roman villas in England and Wales against today's household income\n"
         f"in {R['msoa']['n']:,} neighbourhoods. Villa country looks richer, until you compare like with like.",
         family=SER, fontsize=15, color=FG, va="top", linespacing=1.4)

# hero map
ax = fig.add_axes([0.02, 0.305, 0.6, 0.515]); ax.set_facecolor(BG)
g = json.load(open("/home/claude/hist/how-roman-is-your-road/data/ons/ltla.geojson"))
for f in g["features"]:
    if f["properties"]["areacd"][0] not in "EW":
        continue
    geom = shape(f["geometry"]).simplify(0.004)
    for p in getattr(geom, "geoms", [geom]):
        x, y = T.transform(*np.asarray(p.exterior.coords).T); ax.fill(x, y, color=LAND, ec=EDGE, lw=0.3, zorder=0)
mx, my = T.transform(M.lon.values, M.lat.values)
q = np.searchsorted(R["income_breaks"], M.income.values, side="right")
o = np.argsort(q)
ax.scatter(mx[o], my[o], s=3.2, c=[QC[i] for i in q[o]], lw=0, zorder=2, rasterized=True)
vx, vy = T.transform(V.lon.values, V.lat.values)
ax.scatter(vx, vy, s=20, marker="s", c=RED, ec=BG, lw=0.6, zorder=4)
ax.set_xlim(140000, 660000); ax.set_ylim(5000, 660000); ax.set_aspect("equal"); ax.axis("off")
lx, ly = T.transform(-0.1276, 51.5073)
ax.annotate("London", (lx, ly), xytext=(600000, 255000), family=MONO, fontsize=11, color=FG, bbox=dict(fc=BG, ec="none", pad=1), arrowprops=dict(arrowstyle="-", color=FG, lw=.8))
cx, cy = T.transform(-1.95, 51.8)
ax.annotate("Cotswolds:\nmost villas of any\nlocal authority", (cx, cy), xytext=(160000, 330000), family=MONO, fontsize=10.5, color=FG,
            arrowprops=dict(arrowstyle="-", color=FG, lw=.8))
b = [f"£{round(x / 1000)}k" for x in R["income_breaks"]]
labs = [f"under {b[0]}", f"{b[0]} to {b[1]}", f"{b[1]} to {b[2]}", f"{b[2]} to {b[3]}", f"over {b[3]}"]
hs = [plt.Line2D([], [], ls="", marker="o", ms=8, mfc=QC[i], mec="none", label=l) for i, l in enumerate(labs)]
hs.append(plt.Line2D([], [], ls="", marker="s", ms=8, mfc=RED, mec=BG, label="Roman villa"))
fig.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.045, 0.80), frameon=False, prop={"family": MONO, "size": 11},
           title="Household income, 2022/23", title_fontproperties={"family": MONO, "size": 11}, alignment="left", labelcolor=FG)

# right column numbers
tx = fig.add_axes([0.63, 0.32, 0.34, 0.48]); tx.axis("off")
notes = [(sp(R["raw"]["median_gap_pct"], 0), f"higher median household income where\na villa lies within 2 km ({R['msoa']['villa_2km']:,} areas)."),
         (sp(R["model"]["urban"]["premium"]), "the same 'villa premium' after allowing\nfor region, distance to London, Roman\nroads and towns, terrain and urbanness."),
         (pc(R["placebo"]["raw_share_ge_real"]), f"of {R['placebo']['runs']} runs with every villa moved 5 to\n15 km at random show as big a premium.\nThe exact spot does not matter."),
         ("75 to 100 km", "from London: where villas are densest\n"
          f"({R['bands'][3]['villas_per_1000km2']:.1f} per 1,000 km²). Income just keeps\nfalling with distance.")]
for (big, small), y in zip(notes, [1.0, 0.75, 0.48, 0.21]):
    tx.text(0, y, big, fontproperties=DISP, fontsize=30, color=RED, va="top", transform=tx.transAxes)
    tx.text(0, y - 0.075, small, family=SER, fontsize=12.5, color=FG, va="top", transform=tx.transAxes, linespacing=1.3)

# bottom row: ladder, bands, placebo
fig.text(0.05, 0.278, "THE VILLA PREMIUM AS CONTROLS ARE ADDED", family=MONO, fontsize=11, color=MUT)
a1 = fig.add_axes([0.22, 0.13, 0.26, 0.135]); a1.set_facecolor(BG)
Ms = R["models"]; yy = np.arange(len(Ms))[::-1]
for yi, r in zip(yy, Ms):
    a1.plot([r["lo"] * 100, r["hi"] * 100], [yi, yi], color=RED, lw=3, alpha=.4, solid_capstyle="round")
    a1.plot(r["premium"] * 100, yi, "o", ms=9, mfc=RED if r["key"] == "raw" else BG, mec=RED, mew=2)
    a1.text(r["hi"] * 100 + .5, yi, sp(r["premium"]), va="center", family=MONO, fontsize=10, color=FG)
a1.axvline(0, color=FG, lw=1); a1.set_yticks(yy)
a1.set_yticklabels(["no controls", "within region", "+ London distance", "+ roads, towns, terrain", "+ urbanness", "+ local authority"], family=MONO, fontsize=10, color=FG)
a1.set_xlim(-3, 16); a1.set_xticks([0, 5, 10]); a1.set_xticklabels(["0%", "+5%", "+10%"], family=MONO, fontsize=10, color=FG)
for s in ["top", "right", "left"]:
    a1.spines[s].set_visible(False)
a1.spines["bottom"].set_color(MUT); a1.tick_params(axis="y", length=0); a1.tick_params(axis="x", colors=FG)

fig.text(0.54, 0.278, "VILLAS AND INCOME BY DISTANCE FROM LONDON", family=MONO, fontsize=11, color=MUT)
a2 = fig.add_axes([0.54, 0.13, 0.40, 0.135]); a2.set_facecolor(BG)
B = R["bands"]; xs = np.arange(len(B))
a2.bar(xs - 0.2, [bb["villas_per_1000km2"] for bb in B], 0.38, color=RED, label="villas per 1,000 km²")
a3 = a2.twinx()
a3.bar(xs + 0.2, [bb["median_income"] / 1000 for bb in B], 0.38, color=QC[3], label="median income (£k)")
a2.set_xticks(xs); a2.set_xticklabels([f"{bb['lo']}+" for bb in B], family=MONO, fontsize=10, color=FG)
a2.set_ylim(0, 13); a3.set_ylim(0, 85)
a2.tick_params(axis="y", colors=RED, labelsize=10); a3.tick_params(axis="y", colors=QC[3], labelsize=10)
for a in (a2, a3):
    for s in ["top"]:
        a.spines[s].set_visible(False)
    a.spines["bottom"].set_color(MUT); a.spines["left"].set_color(RED); a.spines["right"].set_color(QC[3])
    for t in a.get_yticklabels():
        t.set_family(MONO)
a2.text(0.0, -0.27, "km from Charing Cross", transform=a2.transAxes, family=MONO, fontsize=10, color=MUT)
a2.text(3.0, 11.6, "villas per 1,000 km²", family=MONO, fontsize=10, color=RED, ha="center")
a3.text(6.1, 62, "median income\n(£ thousand)", family=MONO, fontsize=10, color=QC[3], ha="center")

fig.text(0.05, 0.022,
         "Data: Wikipedia lists of Roman villas in England and Wales (CC BY-SA 4.0), Wikidata (CC0), OpenStreetMap contributors (ODbL),\n"
         "Pleiades (CC BY 3.0), Itiner-e Roman roads; ONS income estimates for small areas FYE2023, Census 2021 and Open Geography\n"
         "(OGL v3, contains OS data © Crown copyright and database right 2026). Villas: known, recorded sites only, a south-leaning sample.\n"
         "Analysis and chart: Tristan Hotham, with Python and matplotlib. Correlation, not causation.",
         family=MONO, fontsize=9, color=MUT, linespacing=1.45)
fig.savefig(os.path.join(HERE, "roman_commuter_belt.png"), facecolor=BG, dpi=200)
print("ok")
