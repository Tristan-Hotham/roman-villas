"""Step 3. Do Roman villas sit where today's richest neighbourhoods are?

Reads data/villas.csv and data/msoa.csv and writes data/results.json (every number quoted anywhere),
data/local_authorities.csv (villa density and income by local authority) and a temporary
_site_data.json for the page.

Main measures
  - "villa MSOA": an MSOA whose population-weighted centroid has a villa within 2 km.
  - Outcome: ONS mean total annual household income, FYE2023, on a log scale.
  - Villa premium: exp(b) minus 1 for the villa dummy in OLS models with standard errors clustered by
    local authority, adding controls step by step: region; distance to London; Roman roads, Roman towns,
    elevation, relief and coast; urbanness; and finally local authority fixed effects.
  - Placebo: the same full model with every villa moved 5 to 15 km in a random direction (kept on land),
    200 times, to see how unusual the real premium is.

Usage:
    python3 code/03_analyse.py
"""
import json
import os

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from pyproj import Transformer
from scipy import stats
from scipy.spatial import cKDTree
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LTLA = "/home/claude/hist/how-roman-is-your-road/data/ons/ltla.geojson"
T = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
TI = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
rng = np.random.default_rng(20261027)

V = pd.read_csv(os.path.join(ROOT, "data", "villas.csv"))
M = pd.read_csv(os.path.join(ROOT, "data", "msoa.csv"))
VM = json.load(open(os.path.join(ROOT, "data", "villa_sources_summary.json")))
M["ly"] = np.log(M.income)
M["ly_ahc"] = np.log(M.income_ahc)
M["l_lon"] = np.log(M.d_london_km)
M["l_lon2"] = M.l_lon ** 2
M["l_road"] = np.log1p(M.d_road_km)
M["l_town"] = np.log1p(M.d_town_km)
M["l_coast"] = np.log1p(M.d_coast_km)
M["elev100"] = M.elev_m / 100
M["relief10"] = M.relief_m / 10
M["l_bua"] = np.log1p(M.bua_pop)

STEPS = [
    ("raw", "No controls", ""),
    ("region", "Within region", " + C(rgn_nm)"),
    ("london", "+ distance to London", " + C(rgn_nm) + l_lon + l_lon2"),
    ("geo", "+ roads, towns, terrain, coast", " + C(rgn_nm) + l_lon + l_lon2 + l_road + l_town + l_coast + elev100 + relief10"),
    ("urban", "+ urbanness", " + C(rgn_nm) + l_lon + l_lon2 + l_road + l_town + l_coast + elev100 + relief10 + l_bua + in_bua"),
    ("lad", "+ local authority effects", " + C(la_cd) + l_lon + l_lon2 + l_road + l_town + l_coast + elev100 + relief10 + l_bua + in_bua"),
]


def fit(df, var, rhs, y="ly"):
    r = smf.ols(f"{y} ~ {var}{rhs}", data=df).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(df.la_cd)[0]})
    b, se = r.params[var], r.bse[var]
    return dict(b=float(b), se=float(se), p=float(r.pvalues[var]), premium=float(np.exp(b) - 1),
                lo=float(np.exp(b - 1.96 * se) - 1), hi=float(np.exp(b + 1.96 * se) - 1), r2=float(r.rsquared), n=int(r.nobs))


R = {}
R["villas"] = dict(total=int(len(V)), england=int((V.country == "England").sum()), wales=int((V.country == "Wales").sum()),
                   raw_records=VM["raw_records"], records_kept=VM["records_kept"],
                   pleiades_villas_world=VM["raw_records"]["pleiades"],
                   by_nsources={str(k): int(v) for k, v in VM["villas_by_nsources"].items()},
                   multi_source=int((V.n_sources > 1).sum()), only_one=VM["only_one_source"],
                   in_wikipedia=int(V.in_wikipedia.sum()), in_wikidata=int(V.in_wikidata.sum()),
                   in_osm=int(V.in_osm.sum()), in_pleiades=int(V.in_pleiades.sum()),
                   wikipedia_rows=VM["raw_records"]["wikipedia"], wikipedia_without_grid=VM["wikipedia_without_grid"])
lon_xy = np.array(T.transform(-0.1276, 51.5073))
vxy = np.c_[T.transform(V.lon.values, V.lat.values)]
V["d_london_km"] = np.hypot(*(vxy - lon_xy).T) / 1000
R["villas"]["median_d_london_km"] = float(V.d_london_km.median())
R["villas"]["share_within_100km_london"] = float((V.d_london_km <= 100).mean())
R["msoa"] = dict(n=int(len(M)), villa_2km=int(M.villa_2km.sum()), villa_5km=int(M.villa_5km.sum()),
                 share_villa_2km=float(M.villa_2km.mean()), share_villa_5km=float(M.villa_5km.mean()),
                 pop_share_within_100km_london=float(M[M.d_london_km <= 100]["pop"].sum() / M["pop"].sum()),
                 n_towns=int(len(pd.read_csv(os.path.join(ROOT, "data", "roman_towns.csv")))),
                 median_income=float(M.income.median()), mean_income=float(M.income.mean()))

# raw comparison
g = M.groupby("villa_2km").income
R["raw"] = dict(median_with=float(g.median()[1]), median_without=float(g.median()[0]),
                mean_with=float(g.mean()[1]), mean_without=float(g.mean()[0]),
                median_gap=float(g.median()[1] - g.median()[0]),
                median_gap_pct=float(g.median()[1] / g.median()[0] - 1),
                mw_p=float(stats.mannwhitneyu(M.income[M.villa_2km == 1], M.income[M.villa_2km == 0]).pvalue))
dec = pd.qcut(M.income, 10, labels=False)
R["raw"]["share_top_decile_with_villa"] = float(M.villa_2km[dec == 9].mean())
R["raw"]["share_bottom_decile_with_villa"] = float(M.villa_2km[dec == 0].mean())
R["raw"]["villa_msoas_in_top_quintile"] = float((pd.qcut(M.income, 5, labels=False)[M.villa_2km == 1] == 4).mean())
R["raw"]["villa_msoas_in_bottom_quintile"] = float((pd.qcut(M.income, 5, labels=False)[M.villa_2km == 1] == 0).mean())
R["income_breaks"] = [float(x) for x in M.income.quantile([0.2, 0.4, 0.6, 0.8])]
R["income_min"], R["income_max"] = float(M.income.min()), float(M.income.max())
R["deciles"] = [dict(decile=int(d + 1), share=float(M.villa_2km[dec == d].mean()),
                     income_lo=float(M.income[dec == d].min()), income_hi=float(M.income[dec == d].max())) for d in range(10)]

# by region
reg = []
for rn, d in M.groupby("rgn_nm"):
    w = d[d.villa_2km == 1]
    reg.append(dict(region=rn, msoas=int(len(d)), villa_msoas=int(len(w)), villas=int(0),
                    median_with=float(w.income.median()) if len(w) else None, median_without=float(d[d.villa_2km == 0].income.median()),
                    gap_pct=float(w.income.median() / d[d.villa_2km == 0].income.median() - 1) if len(w) >= 10 else None))
# villas by region (via nearest MSOA's region)
nearest = cKDTree(np.c_[T.transform(M.lon.values, M.lat.values)]).query(vxy)[1]
vreg = M.rgn_nm.values[nearest]
for r_ in reg:
    r_["villas"] = int((vreg == r_["region"]).sum())
reg.sort(key=lambda r_: -r_["villas"])
R["regions"] = reg
rg = {r_["region"]: r_ for r_ in reg}
R["reg_sw"] = rg["South West"]["gap_pct"]
R["reg_se_abs"] = -rg["South East"]["gap_pct"]
se = M[M.rgn_nm == "South East"]
R["se_dlon_villa"] = float(se[se.villa_2km == 1].d_london_km.median())
R["se_dlon_novilla"] = float(se[se.villa_2km == 0].d_london_km.median())
R["se_bua_villa_rural"] = float(1 - se[se.villa_2km == 1].in_bua.mean())
R["se_bua_novilla_rural"] = float(1 - se[se.villa_2km == 0].in_bua.mean())
swv = V[np.isin(vreg, ["South West"])]
R["sw_villas_devon_cornwall"] = int(swv.lad_nm.isin(["Cornwall", "Isles of Scilly", "Plymouth", "Torbay", "East Devon", "Mid Devon",
                                                     "North Devon", "South Hams", "Teignbridge", "Torridge", "West Devon", "Exeter"]).sum())
R["sw_villas"] = int(len(swv))
R["villas"]["share_south_east_east_south_west_london"] = float(np.isin(vreg, ["South East", "East", "South West", "London"]).mean())

# models
R["models"] = []
for key, label, rhs in STEPS:
    r = fit(M, "villa_2km", rhs)
    r.update(key=key, label=label)
    R["models"].append(r)
R["model"] = {r_["key"]: r_ for r_ in R["models"]}

# sensitivity
sens = []
for key, label, var, y, df in [
    ("v5", "Villa within 5 km instead of 2 km", "villa_5km", "ly", M),
    ("wp", "Wikipedia-listed villas only", "villa_2km_wp", "ly", M),
    ("ahc", "Income after housing costs", "villa_2km", "ly_ahc", M),
    ("noLondon", "Leaving out London", "villa_2km", "ly", M[M.rgn_nm != "London"]),
    ("south", "South East, East and South West only", "villa_2km", "ly", M[M.rgn_nm.isin(["South East", "East", "South West"])]),
]:
    a = fit(df, var, "", y)
    b = fit(df, var, STEPS[4][2] if df.rgn_nm.nunique() > 1 else STEPS[4][2].replace(" + C(rgn_nm)", ""), y)
    sens.append(dict(key=key, label=label, raw=a["premium"], full=b["premium"], full_lo=b["lo"], full_hi=b["hi"], full_p=b["p"], n=b["n"]))
R["sensitivity"] = sens
R["sens"] = {s["key"]: s for s in sens}
R["sens_min"] = min(s["full"] for s in sens)
R["sens_max"] = max(s["full"] for s in sens)

# forts as a contrast: Roman sites of a different kind, mostly in the north and west
R["forts"] = dict(msoas=int(M.fort_2km.sum()), raw=fit(M, "fort_2km", "")["premium"], full=fit(M, "fort_2km", STEPS[4][2])["premium"],
                  full_p=fit(M, "fort_2km", STEPS[4][2])["p"])

# what drives the raw gap: income against distance to London, villa density by distance band
bands = [0, 25, 50, 75, 100, 150, 200, 300, 500]
M["band"] = pd.cut(M.d_london_km, bands, right=False)
V["band"] = pd.cut(V.d_london_km, bands, right=False)
Tm = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
g = json.load(open(LTLA))
feats = [f for f in g["features"] if f["properties"]["areacd"][0] in "EW"]
import shapely  # noqa: E402
polys_bng = [shapely.make_valid(shapely.transform(shape(f["geometry"]), lambda c: np.c_[Tm.transform(c[:, 0], c[:, 1])]))
             for f in feats]
land = unary_union(polys_bng)
shapely.prepare(land)
# land area in each band, by sampling a 2 km grid
minx, miny, maxx, maxy = land.bounds
gx, gy = np.meshgrid(np.arange(minx, maxx, 2000), np.arange(miny, maxy, 2000))
gx, gy = gx.ravel(), gy.ravel()
on = contains_xy(land, gx, gy)
gd = np.hypot(gx[on] - lon_xy[0], gy[on] - lon_xy[1]) / 1000
gb = pd.cut(gd, bands, right=False)
area = pd.Series(4.0, index=range(len(gd))).groupby(gb, observed=False).sum()
bt = []
for b_ in M.band.cat.categories:
    mm = M[M.band == b_]
    bt.append(dict(band=f"{int(b_.left)} to {int(b_.right)} km", lo=int(b_.left), hi=int(b_.right),
                   villas=int((V.band == b_).sum()), area_km2=float(area[b_]),
                   villas_per_1000km2=float((V.band == b_).sum() / area[b_] * 1000),
                   median_income=float(mm.income.median()), msoas=int(len(mm)),
                   villa_share=float(mm.villa_2km.mean())))
R["bands"] = bt
R["land_area_km2"] = float(on.sum() * 4.0)
R["villas_per_1000km2_all"] = float(len(V) / (on.sum() * 4.0) * 1000)

# local authorities: villa density against income
lad = []
area_lad = {f["properties"]["areacd"]: p.area / 1e6 for f, p in zip(feats, polys_bng)}
name_lad = {f["properties"]["areacd"]: f["properties"]["areanm"] for f in feats}
cent = {f["properties"]["areacd"]: p.representative_point() for f, p in zip(feats, polys_bng)}
vc = V.groupby("lad_cd").size()
for cd, d in M.groupby("lad25_cd"):
    inc_w = float(np.average(d.income, weights=d["pop"]))
    c = cent[cd]
    lad.append(dict(lad_cd=cd, lad_nm=name_lad[cd], region=d.rgn_nm.mode().iloc[0], msoas=int(len(d)), pop=int(d["pop"].sum()),
                    area_km2=round(area_lad[cd], 1), villas=int(vc.get(cd, 0)),
                    villas_per_100km2=round(vc.get(cd, 0) / area_lad[cd] * 100, 3), income=round(inc_w),
                    d_london_km=round(float(np.hypot(c.x - lon_xy[0], c.y - lon_xy[1]) / 1000), 1)))
L = pd.DataFrame(lad)
L["income_rank"] = L.income.rank(ascending=False, method="min").astype(int)
L["density_rank"] = L.villas_per_100km2.rank(ascending=False, method="min").astype(int)
L.sort_values("villas_per_100km2", ascending=False).to_csv(os.path.join(ROOT, "data", "local_authorities.csv"), index=False)
rho, p = stats.spearmanr(L.villas_per_100km2, L.income)
# partial rank correlation after removing log distance to London from both ranks
rx = stats.rankdata(L.villas_per_100km2); ry = stats.rankdata(L.income); rz = np.log(L.d_london_km)
res = lambda a: a - np.polyval(np.polyfit(rz, a, 1), rz)  # noqa: E731
prho, pp = stats.pearsonr(res(rx), res(ry))
# and also removing population density (urban authorities have few recorded villas)
Z = np.c_[np.ones(len(L)), rz, np.log(L["pop"] / L.area_km2)]
res2 = lambda a: a - Z @ np.linalg.lstsq(Z, a, rcond=None)[0]  # noqa: E731
prho2, pp2 = stats.pearsonr(res2(rx), res2(ry))
# and also removing region
Z = np.c_[Z, pd.get_dummies(L.region, drop_first=True).values.astype(float)]
prho3, pp3 = stats.pearsonr(res2(rx), res2(ry))
top = L[L.villas >= 3].sort_values(["villas_per_100km2", "villas"], ascending=False).head(15)
R["lad"] = dict(n=int(len(L)), with_villa=int((L.villas > 0).sum()), spearman=float(rho), spearman_p=float(p),
                partial_spearman=float(prho), partial_p=float(pp), partial2_spearman=float(prho2), partial2_p=float(pp2),
                partial3_spearman=float(prho3), partial3_p=float(pp3),
                min_villas_for_table=3, with3=int((L.villas >= 3).sum()),
                top_density=[dict(name=r_.lad_nm, region=r_.region, villas=int(r_.villas), density=float(r_.villas_per_100km2),
                                  income=int(r_.income), income_rank=int(r_.income_rank)) for r_ in top.itertuples()],
                top15_median_income_rank=float(top.income_rank.median()),
                top_income=[dict(name=r_.lad_nm, region=r_.region, villas=int(r_.villas), density=float(r_.villas_per_100km2),
                                 income=int(r_.income), density_rank=int(r_.density_rank))
                            for r_ in L.sort_values("income", ascending=False).head(15).itertuples()],
                top15_income_with_villa=int((L.sort_values("income", ascending=False).head(15).villas > 0).sum()),
                no_villa_share=float((L.villas == 0).mean()))
mx = L.villas.idxmax()
R["lad"]["most_villas"] = dict(name=L.lad_nm[mx], villas=int(L.villas[mx]))

# placebo: displace each villa 5 to 15 km in a random direction, on land, and refit the full model
MXY = np.c_[T.transform(M.lon.values, M.lat.values)]
full_rhs = STEPS[4][2]
pl = []
for k in range(200):
    pts = vxy.copy()
    todo = np.arange(len(pts))
    newp = np.zeros_like(pts)
    for _ in range(50):
        if not len(todo):
            break
        a = rng.uniform(0, 2 * np.pi, len(todo)); r_ = rng.uniform(5000, 15000, len(todo))
        cand = vxy[todo] + np.c_[r_ * np.cos(a), r_ * np.sin(a)]
        ok = contains_xy(land, cand[:, 0], cand[:, 1])
        newp[todo[ok]] = cand[ok]
        todo = todo[~ok]
    newp[todo] = vxy[todo]
    M["pv"] = (np.array([len(x) for x in cKDTree(newp).query_ball_point(MXY, 2000)]) > 0).astype(int)
    pl.append(dict(raw=fit(M, "pv", "")["premium"], full=fit(M, "pv", full_rhs)["premium"], region=fit(M, "pv", STEPS[1][2])["premium"]))
P = pd.DataFrame(pl)
real = R["model"]
R["placebo"] = dict(runs=len(P), raw_median=float(P.raw.median()), full_median=float(P.full.median()), region_median=float(P.region.median()),
                    raw_share_ge_real=float((P.raw >= real["raw"]["premium"]).mean()),
                    full_share_ge_real=float((P.full >= real["urban"]["premium"]).mean()),
                    region_share_ge_real=float((P.region >= real["region"]["premium"]).mean()),
                    full_p05=float(P.full.quantile(0.05)), full_p95=float(P.full.quantile(0.95)),
                    raw_p05=float(P.raw.quantile(0.05)), raw_p95=float(P.raw.quantile(0.95)),
                    full_values=[round(float(x), 4) for x in P.full], raw_values=[round(float(x), 4) for x in P.raw])
M = M.drop(columns=["pv"])

# notable villas and their neighbourhoods
famous = ["Chedworth", "Lullingstone", "Bignor", "Fishbourne", "Brading", "North Leigh", "Great Witcombe", "Woodchester",
          "Littlecote", "Crofton", "Rockbourne", "Low Ham", "Bancroft", "Gadebridge"]
fam = []
Vxy_t = cKDTree(MXY)
for f_ in famous:
    hit = V[V.name.str.contains(f_, case=False, na=False)]
    if not len(hit):
        continue
    h = hit.iloc[0]
    j = Vxy_t.query(np.array(T.transform(h.lon, h.lat)))[1]
    fam.append(dict(name=h["name"], lad=h.lad_nm, msoa=M.msoa_nm[j], income=int(M.income[j]),
                    pct=float((M.income < M.income[j]).mean())))
R["famous"] = fam
R["famous_median_pct"] = float(np.median([f_["pct"] for f_ in fam]))

# headline flags
R["headline"] = dict(raw_premium=real["raw"]["premium"], region_premium=real["region"]["premium"],
                     london_premium=real["london"]["premium"], geo_premium=real["geo"]["premium"],
                     full_premium=real["urban"]["premium"], lad_premium=real["lad"]["premium"],
                     full_lo=real["urban"]["lo"], full_hi=real["urban"]["hi"], lad_lo=real["lad"]["lo"], lad_hi=real["lad"]["hi"],
                     shrink_share=1 - real["urban"]["premium"] / real["raw"]["premium"])
json.dump(R, open(os.path.join(ROOT, "data", "results.json"), "w"), indent=1)

# compact site data: villas, MSOA centroids with income, local authorities
site = dict(
    villas=[[round(r_.lat, 4), round(r_.lon, 4), r_.name, r_.lad_nm, int(r_.in_wikipedia), int(r_.in_wikidata), int(r_.in_osm),
             int(r_.in_pleiades), (r_.pastscape_or_coflein if isinstance(r_.pastscape_or_coflein, str) else ""),
             (r_.wikidata.split(";")[0] if isinstance(r_.wikidata, str) else ""),
             (r_.pleiades.split(";")[0].rsplit("/", 1)[-1] if isinstance(r_.pleiades, str) else "")] for r_ in V.itertuples()],
    msoa=[[round(r_.lat, 3), round(r_.lon, 3), int(r_.income), int(r_.villas_2km), r_.msoa_nm] for r_ in M.itertuples()],
    towns=[[round(r_.lat, 3), round(r_.lon, 3), r_.title] for r_ in pd.read_csv(os.path.join(ROOT, "data", "roman_towns.csv")).itertuples()],
    lad=L.sort_values("villas_per_100km2", ascending=False)[["lad_nm", "region", "villas", "villas_per_100km2", "income", "income_rank", "d_london_km"]].values.tolist(),
)
roads = []
for f_ in json.load(open("/home/claude/hist/how-roman-is-your-road/data/itinere_gb.geojson"))["features"]:
    for part in shapely.get_parts(shapely.simplify(shape(f_["geometry"]), 0.003)):
        c = np.round(np.asarray(part.coords)[:, ::-1], 3).tolist()
        if len(c) > 1:
            roads.append(c)
site["roads"] = roads
json.dump(site, open(os.path.join(ROOT, "_site_data.json"), "w"), separators=(",", ":"), ensure_ascii=False)
print(json.dumps({k: R[k] for k in ["raw", "headline", "placebo"]}, indent=1)[:3000])
for r_ in R["models"]:
    print(f"{r_['label']:55s} {r_['premium']*100:6.1f}% ({r_['lo']*100:.1f} to {r_['hi']*100:.1f}) p={r_['p']:.3g} r2={r_['r2']:.2f}")
for s in sens:
    print(s)
print(R["forts"], R["lad"]["spearman"], R["lad"]["partial_spearman"], R["lad"]["partial_p"])
print(pd.DataFrame(bt).to_string())
print(pd.DataFrame(reg).to_string())
print(top.to_string())
print(fam)
