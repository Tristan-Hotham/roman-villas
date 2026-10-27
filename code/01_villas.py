"""Step 1. Build an open list of Roman villas in England and Wales from four sources.

Sources (all read in place, nothing large is copied):
  A. English Wikipedia, "List of Roman villas in England" and "List of Roman villas in Wales"
     (wikitext, CC BY-SA 4.0). Name, county section, location and OS grid reference.
  B. Wikidata items of class "Roman villa" or "villa rustica", plus items of class "villa" whose label
     says Roman or Romano (CC0).
  C. OpenStreetMap historic=archaeological_site features whose name contains the word "villa"
     (not "village") (ODbL).
  D. Pleiades places with feature type "villa" (CC BY 3.0).

Each record is kept with its source. Records from different sources that lie within 600 m of each other
(1,000 m when either is a Wikipedia grid reference given only to 1 km), or within 2.5 km when the
distinctive words of one name are contained in the other (e.g. "Ilchester" and "Ilchester Mead"), are
joined into one villa, closest pairs first. Records from the same source within 100 m are treated as
duplicates, and a villa may never hold two records of one source more than 100 m apart. Only points inside England and
Wales (ONS local authority boundaries) are kept.

Writes data/villa_records.csv (one row per source record) and data/villas.csv (one row per villa).

Usage:
    python3 code/01_villas.py
"""
import gzip
import json
import math
import os
import re

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI = "/home/claude/hist/_data9/wikipedia_wikitext.json"
BUNDLE = "/home/claude/hist/_data9/wd_osm_bundle.json"
PLEIADES = "/mnt/user-data/uploads/Downloads/pleiades-places-latest.csv.gz"
LTLA = "/home/claude/hist/how-roman-is-your-road/data/ons/ltla.geojson"

BNG = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
TO_BNG = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)


def grid_to_en(ref):
    """OS grid reference (two letters + 2 to 10 digits) to easting, northing of the square centre, and precision in metres."""
    ref = ref.replace(" ", "").upper()
    m = re.fullmatch(r"([A-HJ-Z]{2})(\d+)", ref)
    if not m or len(m.group(2)) % 2:
        return None
    letters, digits = m.group(1), m.group(2)
    l1 = ord(letters[0]) - 65 - (ord(letters[0]) > 73)
    l2 = ord(letters[1]) - 65 - (ord(letters[1]) > 73)
    e100 = ((l1 - 2) % 5) * 5 + l2 % 5
    n100 = (19 - (l1 // 5) * 5) - l2 // 5
    k = len(digits) // 2
    prec = 10 ** (5 - k)
    e = e100 * 100000 + int(digits[:k]) * prec + prec / 2
    n = n100 * 100000 + int(digits[k:]) * prec + prec / 2
    return e, n, prec


NAME_TOL = 2500
GENERIC = {"roman", "romano", "british", "villa", "villas", "site", "of", "the", "remains", "rustica", "and", "at", "a"}


def name_tokens(s):
    """Distinctive words of a villa name, used to join records of one villa whose points differ by up to 2.5 km."""
    return frozenset(w for w in re.findall(r"[a-z]+", str(s).lower()) if w not in GENERIC and len(w) > 1)


def clean(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    return re.sub(r"\s+", " ", s).strip()


def wiki_records():
    w = json.load(open(WIKI, encoding="utf-8"))
    out = []
    # England: one table per county section
    t = w["List of Roman villas in England"]["text"]
    county = None
    for line_block in re.split(r"\n(?===)", t):
        h = re.match(r"(=+)\s*([^=]+?)\s*=+", line_block)
        if h:
            name = h.group(2).strip()
            if len(h.group(1)) == 2:
                county = name
            sub = name if len(h.group(1)) == 3 else None
        for row in re.split(r"\n\|-", line_block)[1:]:
            cells = [c for c in re.split(r"\n\|\s?", "\n" + row.split("\n|}")[0]) if c is not None][1:]
            if len(cells) < 3:
                continue
            g = re.search(r"gbmappingsmall\|\s*([A-Z]{2}\s*[\d ]+)", row)
            ps = re.search(r"PastScape\s*\|[^}]*num=(\d+)", row)
            out.append(dict(src="wikipedia", src_id=f"wp-en-{len(out)}", name=clean(cells[0]), place=clean(cells[1]),
                            county=(sub or county), grid=g.group(1).replace(" ", "") if g else "",
                            ref=f"PastScape {ps.group(1)}" if ps else "", note=clean(cells[4]) if len(cells) > 4 else ""))
    # Wales: one table with local authority and historic county columns
    t = w["List of Roman villas in Wales"]["text"]
    for row in re.split(r"\n\|-", t)[1:]:
        row = row.split("\n|}")[0]
        cells = re.split(r"\n\|\s?", "\n" + row)[1:]
        if len(cells) < 5:
            continue
        g = re.search(r"gbmappingsmall\|\s*([A-Z]{2}\s*[\d ]+)", row)
        cf = re.search(r"Coflein\|num=(\d+)", row)
        out.append(dict(src="wikipedia", src_id=f"wp-cy-{len(out)}", name=clean(cells[0]), place=clean(cells[1]),
                        county=clean(cells[3]), grid=g.group(1).replace(" ", "") if g else "",
                        ref=f"Coflein {cf.group(1)}" if cf else "", note=clean(cells[6]) if len(cells) > 6 else ""))
    recs = []
    for r in out:
        en = grid_to_en(r["grid"]) if r["grid"] else None
        if not en:
            r.update(lat=np.nan, lon=np.nan, prec_m=np.nan)
        else:
            lon, lat = BNG.transform(en[0], en[1])
            r.update(lat=lat, lon=lon, prec_m=en[2])
        r["coord_source"] = "Wikipedia OS grid reference, square centre"
        recs.append(r)
    return recs


def wikidata_records():
    b = json.load(open(BUNDLE, encoding="utf-8"))
    rows = {}
    for line in b["wd_roman_sites_tsv"].split("\n")[1:]:
        p = line.split("\t")
        if len(p) < 5:
            continue
        qid = p[0].rsplit("/", 1)[-1].strip(">")
        label = re.sub(r'^"|"@\w+$', "", p[1])
        cls = re.sub(r'^"|"@\w+$', "", p[2])
        m = re.search(r"POINT\(([-\d.]+) ([-\d.]+)\)", p[3])
        if not m:
            continue
        keep = cls in ("Roman villa", "villa rustica") or (cls == "villa" and re.search(r"\broman|romano", label, re.I))
        if not keep:
            continue
        rows[qid] = dict(src="wikidata", src_id=qid, name=label, place="", county="", grid="", ref=qid, note=cls,
                         lat=float(m.group(2)), lon=float(m.group(1)), prec_m=np.nan,
                         coord_source="Wikidata P625")
    return list(rows.values())


def osm_records():
    b = json.load(open(BUNDLE, encoding="utf-8"))
    out = []
    for x in b["osm_roman_archaeological_sites_uk"]:
        nm = x.get("name") or ""
        if re.search(r"\bvillas?\b", nm, re.I):
            out.append(dict(src="osm", src_id=x["osm"], name=nm, place="", county="", grid="", ref=x["osm"],
                            note=x.get("wd") or "", lat=x["lat"], lon=x["lon"], prec_m=np.nan,
                            coord_source="OpenStreetMap feature location"))
    return out


def pleiades_records():
    p = pd.read_csv(PLEIADES, usecols=["id", "title", "featureTypes", "reprLat", "reprLong", "locationPrecision", "timePeriodsKeys"])
    p = p[p.featureTypes.fillna("").str.split(",").apply(lambda l: "villa" in [s.strip() for s in l])]
    p = p.dropna(subset=["reprLat", "reprLong"])
    return [dict(src="pleiades", src_id=f"pleiades-{int(r.id)}", name=r.title, place="", county="", grid="",
                 ref=f"https://pleiades.stoa.org/places/{int(r.id)}", note=str(r.locationPrecision),
                 lat=r.reprLat, lon=r.reprLong, prec_m=np.nan, coord_source="Pleiades representative point")
            for r in p.itertuples()]


def main():
    recs = wiki_records() + wikidata_records() + osm_records() + pleiades_records()
    df = pd.DataFrame(recs)
    n_raw = df.groupby("src").size().to_dict()
    wiki_nogrid = int(((df.src == "wikipedia") & df.lat.isna()).sum())
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

    # keep England and Wales only, and record local authority
    g = json.load(open(LTLA, encoding="utf-8"))
    feats = [f for f in g["features"] if f["properties"]["areacd"][0] in "EW"]
    polys = [shape(f["geometry"]) for f in feats]
    tree = STRtree(polys)
    lad_cd, lad_nm = [], []
    for r in df.itertuples():
        pt = Point(r.lon, r.lat)
        hit = [i for i in tree.query(pt) if polys[i].contains(pt)]
        if hit:
            lad_cd.append(feats[hit[0]]["properties"]["areacd"]); lad_nm.append(feats[hit[0]]["properties"]["areanm"])
        else:
            # coastal points just outside the generalised boundary: nearest authority within 2 km
            d = [polys[i].distance(pt) for i in range(len(polys))]
            i = int(np.argmin(d))
            if d[i] < 0.03:
                lad_cd.append(feats[i]["properties"]["areacd"]); lad_nm.append(feats[i]["properties"]["areanm"])
            else:
                lad_cd.append(""); lad_nm.append("")
    df["lad_cd"], df["lad_nm"] = lad_cd, lad_nm
    outside = df[df.lad_cd == ""].groupby("src").size().to_dict()
    df = df[df.lad_cd != ""].reset_index(drop=True)
    df["country"] = np.where(df.lad_cd.str[0] == "W", "Wales", "England")

    # join records into villas (union-find)
    e, n = TO_BNG.transform(df.lon.values, df.lat.values)
    df["e"], df["n"] = np.round(e), np.round(n)
    xy = np.c_[e, n]
    par = list(range(len(df)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i

    coarse = (df.prec_m.fillna(0) >= 1000).values
    src = df.src.values
    toks = [name_tokens(x) for x in df.name.values]
    pairs = []
    for i in range(len(df)):
        d = np.hypot(xy[:, 0] - xy[i, 0], xy[:, 1] - xy[i, 1])
        for j in np.where(d < NAME_TOL)[0]:
            if j <= i:
                continue
            if src[i] == src[j]:
                ok = d[j] < 100
            else:
                near = d[j] < (1000 if (coarse[i] or coarse[j]) else 600)
                same_name = bool(toks[i]) and bool(toks[j]) and (toks[i] <= toks[j] or toks[j] <= toks[i])
                ok = near or same_name
            if ok:
                pairs.append((d[j], i, j))
    members = {i: [i] for i in range(len(df))}
    for dist, i, j in sorted(pairs):
        a, b = find(i), find(j)
        if a == b:
            continue
        # never join two records of the same source that lie more than 100 m apart (e.g. the two Hambleden villas)
        clash = any(src[p] == src[q] and math.hypot(*(xy[p] - xy[q])) >= 100 for p in members[a] for q in members[b])
        if clash:
            continue
        par[a] = b
        members[b] += members.pop(a)
    df["villa_id"] = [find(i) for i in range(len(df))]
    pri = {"wikipedia": 0, "pleiades": 1, "wikidata": 2, "osm": 3}
    df["pri"] = df.src.map(pri) + np.where(coarse, 3.5, 0)
    villas = []
    for k, (vid, grp) in enumerate(df.sort_values("pri").groupby("villa_id", sort=False)):
        best = grp.iloc[0]
        named = grp[~grp.name.str.fullmatch(r"(?i)(site of )?roman villa( \(site of\))?|villa", na=False)]
        nm = named.iloc[0]["name"] if len(named) else best["name"]
        villas.append(dict(
            name=nm, lat=round(best.lat, 5), lon=round(best.lon, 5), coord_source=best.coord_source,
            coord_precision_m=best.prec_m if best.src == "wikipedia" else "",
            in_wikipedia=int((grp.src == "wikipedia").any()), in_wikidata=int((grp.src == "wikidata").any()),
            in_osm=int((grp.src == "osm").any()), in_pleiades=int((grp.src == "pleiades").any()),
            n_sources=grp.src.nunique(),
            wikipedia_county=next((c for c in grp.county if c), ""),
            pastscape_or_coflein=next((c for c in grp.ref if str(c).startswith(("PastScape", "Coflein"))), ""),
            wikidata=";".join(grp[grp.src == "wikidata"].src_id), pleiades=";".join(grp[grp.src == "pleiades"].ref),
            osm=";".join(grp[grp.src == "osm"].src_id), lad_cd=best.lad_cd, lad_nm=best.lad_nm, country=best.country,
            vid=vid))
    V = pd.DataFrame(villas).sort_values(["country", "lad_nm", "name"]).reset_index(drop=True)
    V.insert(0, "villa_id", [f"V{i + 1:04d}" for i in range(len(V))])
    vmap = dict(zip(V.vid, V.villa_id))
    df["villa_id"] = df.villa_id.map(vmap)
    V = V.drop(columns="vid")
    df.drop(columns=["pri"]).to_csv(os.path.join(ROOT, "data", "villa_records.csv"), index=False)
    V.to_csv(os.path.join(ROOT, "data", "villas.csv"), index=False)
    meta = dict(raw_records=n_raw, wikipedia_without_grid=wiki_nogrid, outside_england_wales=outside,
                records_kept=df.groupby("src").size().to_dict(), villas=len(V),
                villas_by_country=V.country.value_counts().to_dict(),
                villas_by_nsources=V.n_sources.value_counts().sort_index().to_dict(),
                only_one_source={s: int(((V[f"in_{s}"] == 1) & (V.n_sources == 1)).sum()) for s in pri})
    json.dump(meta, open(os.path.join(ROOT, "data", "villa_sources_summary.json"), "w"), indent=1, default=int)
    print(json.dumps(meta, indent=1, default=int))


if __name__ == "__main__":
    main()
