"""Step 2. One row per MSOA (England and Wales, 2021 boundaries) with household income, villas nearby and
the geography used as controls.

Inputs (read in place):
  ONS income estimates for small areas, FYE2023 (mean total annual household income and net income after
  housing costs), ONS MSOA 2021 population-weighted centroids, MSOA to Built-up Area 2022 lookup, LSOA to
  BUA lookup, Census 2021 TS001 populations, Itiner-e Roman roads, Pleiades Roman settlements and forts,
  Natural Earth coastline, the Terrain Tiles elevation grid, and data/villas.csv from step 1.

Distances are straight-line distances on the British National Grid from each MSOA's population-weighted
centroid. Writes data/msoa.csv and data/roman_towns.csv.

Usage:
    python3 code/02_msoa.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/home/claude/hist/within-sight/code")
from dem import DEM  # noqa: E402  (Terrain Tiles reader from the Within Sight project)

D8 = "/home/claude/hist/_data8"
ITINERE = "/home/claude/hist/how-roman-is-your-road/data/itinere_gb.geojson"
LTLA = "/home/claude/hist/how-roman-is-your-road/data/ons/ltla.geojson"
PLEIADES = "/mnt/user-data/uploads/Downloads/pleiades-places-latest.csv.gz"
COAST = "/home/claude/hist/_data3/ne/geojson/ne_10m_coastline.geojson"
T = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
CHARING_CROSS = (-0.1276, 51.5073)


def bng(lon, lat):
    e, n = T.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.c_[e, n]


def line_points(coords, step=100.0):
    """Densify a lon/lat polyline to points about every 100 m on the British National Grid."""
    xy = bng([c[0] for c in coords], [c[1] for c in coords])
    out = [xy[:1]]
    for a, b in zip(xy[:-1], xy[1:]):
        k = max(1, int(np.hypot(*(b - a)) // step))
        t = np.linspace(0, 1, k + 1)[1:, None]
        out.append(a + (b - a) * t)
    return np.vstack(out)


def main():
    # income
    xl = os.path.join(D8, "ons_msoa_income_fye2023.xlsx")
    inc = pd.read_excel(xl, sheet_name="Total annual income", header=3)
    inc.columns = ["msoa", "msoa_nm", "la_cd", "la_nm", "rgn_cd", "rgn_nm", "income", "inc_hi", "inc_lo", "inc_ci"]
    ahc = pd.read_excel(xl, sheet_name="Net income after housing costs", header=3).iloc[:, [0, 6]]
    ahc.columns = ["msoa", "income_ahc"]
    m = inc.merge(ahc, on="msoa")
    geo = json.load(open(os.path.join(D8, "ons_geo.json")))
    pwc = pd.DataFrame(geo["msoa21_pwc"])[["MSOA21CD", "_x", "_y"]].rename(columns={"MSOA21CD": "msoa", "_x": "lon", "_y": "lat"})
    m = m.merge(pwc, on="msoa")
    pop = pd.read_csv(os.path.join(D8, "census", "census2021-ts001-msoa.csv"))
    pop = pop.rename(columns={"geography code": "msoa", "Residence type: Total; measures: Value": "pop"})[["msoa", "pop"]]
    m = m.merge(pop, on="msoa")

    # urbanness: population of the Built-up Area (2022) each MSOA best fits, from LSOA populations
    lk = pd.DataFrame(geo["msoa21_bua22_lookup"])[["MSOA21CD", "BUA22CD", "BUA22NM"]].rename(columns={"MSOA21CD": "msoa"})
    ll = pd.DataFrame(json.load(open(os.path.join(D8, "lsoa21_bua22_lookup.json"))))
    lpop = pd.read_csv(os.path.join(D8, "census", "census2021-ts001-lsoa.csv"))
    lpop = lpop.rename(columns={"geography code": "LSOA21CD", "Residence type: Total; measures: Value": "p"})[["LSOA21CD", "p"]]
    lcol = [c for c in ll.columns if c.upper().startswith("LSOA21CD")][0]
    ll = ll.rename(columns={lcol: "LSOA21CD"}).merge(lpop, on="LSOA21CD")
    ll = ll[ll.BUA22CD.notna() & (ll.BUA22CD.astype(str).str.len() > 3)]
    buapop = ll.groupby("BUA22CD").p.sum()
    lk["bua_pop"] = lk.BUA22CD.map(buapop)
    m = m.merge(lk, on="msoa", how="left")
    m["bua_pop"] = m.bua_pop.fillna(0)
    m["in_bua"] = (m.bua_pop > 0).astype(int)

    XY = bng(m.lon, m.lat)
    lon_xy = bng([CHARING_CROSS[0]], [CHARING_CROSS[1]])[0]
    m["d_london_km"] = np.hypot(*(XY - lon_xy).T) / 1000

    # villas
    V = pd.read_csv(os.path.join(ROOT, "data", "villas.csv"))
    VXY = bng(V.lon, V.lat)
    vt = cKDTree(VXY)
    dv, iv = vt.query(XY)
    m["d_villa_km"] = dv / 1000
    m["nearest_villa"] = V.name.values[iv]
    m["villas_2km"] = [len(x) for x in vt.query_ball_point(XY, 2000)]
    m["villas_5km"] = [len(x) for x in vt.query_ball_point(XY, 5000)]
    m["villa_2km"] = (m.villas_2km > 0).astype(int)
    m["villa_5km"] = (m.villas_5km > 0).astype(int)
    W = V[V.in_wikipedia == 1]
    wt = cKDTree(bng(W.lon, W.lat))
    m["villa_2km_wp"] = (np.array([len(x) for x in wt.query_ball_point(XY, 2000)]) > 0).astype(int)

    # Roman roads (Itiner-e): all roads, and main roads only
    roads = json.load(open(ITINERE))
    pts_all, pts_main = [], []
    for f in roads["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for c in parts:
            p = line_points(c)
            pts_all.append(p)
            if f["properties"].get("type") == "Main Road":
                pts_main.append(p)
    m["d_road_km"] = cKDTree(np.vstack(pts_all)).query(XY)[0] / 1000
    m["d_mainroad_km"] = cKDTree(np.vstack(pts_main)).query(XY)[0] / 1000

    # England and Wales land, for Pleiades filtering
    g = json.load(open(LTLA))
    feats = [f for f in g["features"] if f["properties"]["areacd"][0] in "EW"]
    polys = [shape(f["geometry"]) for f in feats]
    tree = STRtree(polys)

    def in_ew(lon, lat):
        pt = Point(lon, lat)
        return any(polys[i].contains(pt) for i in tree.query(pt))

    p = pd.read_csv(PLEIADES, usecols=["id", "title", "featureTypes", "reprLat", "reprLong", "timePeriodsKeys"])
    p = p.dropna(subset=["reprLat", "reprLong"])
    p = p[(p.reprLong > -6) & (p.reprLong < 2) & (p.reprLat > 49.8) & (p.reprLat < 56)]
    ft = p.featureTypes.fillna("")
    roman = p.timePeriodsKeys.fillna("").str.contains("roman")
    towns = p[ft.str.contains("settlement|urban") & roman & ~p.title.str.contains("villa", case=False)]
    towns = towns[[in_ew(a, b) for a, b in zip(towns.reprLong, towns.reprLat)]]
    forts = p[ft.str.contains(r"\bfort") & roman]
    forts = forts[[in_ew(a, b) for a, b in zip(forts.reprLong, forts.reprLat)]]
    towns.assign(url="https://pleiades.stoa.org/places/" + towns.id.astype(str))[["title", "reprLat", "reprLong", "featureTypes", "url"]] \
        .rename(columns={"reprLat": "lat", "reprLong": "lon"}).to_csv(os.path.join(ROOT, "data", "roman_towns.csv"), index=False)
    m["d_town_km"] = cKDTree(bng(towns.reprLong, towns.reprLat)).query(XY)[0] / 1000
    fxy = bng(forts.reprLong, forts.reprLat)
    m["fort_2km"] = (np.array([len(x) for x in cKDTree(fxy).query_ball_point(XY, 2000)]) > 0).astype(int)

    # coast
    cpts = []
    for f in json.load(open(COAST))["features"]:
        gg = f["geometry"]
        parts = gg["coordinates"] if gg["type"] == "MultiLineString" else [gg["coordinates"]]
        for c in parts:
            c = [q for q in c if -7 < q[0] < 2.5 and 49.5 < q[1] < 56.5]
            if len(c) > 1:
                cpts.append(line_points(c, 500))
    m["d_coast_km"] = cKDTree(np.vstack(cpts)).query(XY)[0] / 1000

    # elevation and local relief (standard deviation of elevation on a 1 km ring of 16 points plus centre)
    dem = DEM()
    m["elev_m"] = dem.elev(m.lat.values, m.lon.values)
    ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    samples = [m.elev_m.values]
    for r in (500, 1000):
        for a in ang:
            e = XY[:, 0] + r * np.cos(a); n = XY[:, 1] + r * np.sin(a)
            lo, la = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True).transform(e, n)
            samples.append(dem.elev(la, lo))
    m["relief_m"] = np.std(np.vstack(samples), axis=0)

    # local authority by polygon (2025 boundaries) for the league table
    lad = []
    for lo_, la_ in zip(m.lon, m.lat):
        pt = Point(lo_, la_)
        hit = [i for i in tree.query(pt) if polys[i].contains(pt)]
        if not hit:  # a few island or shoreline centroids: nearest authority
            hit = [int(np.argmin([q.distance(pt) for q in polys]))]
        lad.append(feats[hit[0]]["properties"]["areacd"])
    m["lad25_cd"] = lad
    m["country"] = np.where(m.msoa.str[0] == "W", "Wales", "England")
    cols = ["msoa", "msoa_nm", "la_cd", "la_nm", "lad25_cd", "rgn_cd", "rgn_nm", "country", "lat", "lon", "pop", "income",
            "inc_lo", "inc_hi", "income_ahc", "BUA22CD", "BUA22NM", "bua_pop", "in_bua", "d_london_km", "d_villa_km",
            "nearest_villa", "villas_2km", "villas_5km", "villa_2km", "villa_5km", "villa_2km_wp", "fort_2km",
            "d_road_km", "d_mainroad_km", "d_town_km", "d_coast_km", "elev_m", "relief_m"]
    out = m[cols].copy()
    for c in ["lat", "lon"]:
        out[c] = out[c].round(5)
    for c in ["d_london_km", "d_villa_km", "d_road_km", "d_mainroad_km", "d_town_km", "d_coast_km", "elev_m", "relief_m"]:
        out[c] = out[c].round(2)
    out.to_csv(os.path.join(ROOT, "data", "msoa.csv"), index=False)
    print(len(out), "MSOAs;", len(towns), "Roman towns;", len(forts), "forts;", (out.lad25_cd == "").sum(), "without LAD")
    print(out.describe().T.to_string())


if __name__ == "__main__":
    main()
