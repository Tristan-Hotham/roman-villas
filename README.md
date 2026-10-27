# The Roman Commuter Belt?

Do Roman villas cluster in the same places as today's richest neighbourhoods? An open list of 617 Roman villas in England and Wales, set against ONS household income for 7,264 neighbourhoods (MSOAs).

**Interactive version:** https://tristan-hotham.github.io/roman-villas/
**Paper (Zenodo):** https://doi.org/10.5281/zenodo.23689960
**Companion study:** [Is Domesday Destiny?](https://tristan-hotham.github.io/domesday-destiny/)

This repository holds the interactive page, the villa list and the analysis data, the computed results and the analysis code for a data study by Dr Tristan Hotham (Independent researcher).

## Headline results

- 617 villas located (592 in England, 25 in Wales), joined from four open sources; 332 are recorded by two or more.
- 395 of 7,264 MSOAs (5.4%) have a villa within 2 km of their population-weighted centre. Their median household income (FYE2023) is £57,822, against £52,315 for the rest: 11% higher.
- The regression "villa premium" is +8.6% with no controls, +2.2% within regions, +0.5% after distance to London, +0.4% with all geographic and urban controls (95% interval −2.0% to +2.8%) and +0.3% within local authorities. Only the uncontrolled estimate is distinguishable from zero.
- Placebo: moving every villa 5 to 15 km at random gives a raw premium at least as large as the real one in 94% of 200 runs.
- Villa density peaks 75 to 100 km from Charing Cross; income falls steadily with distance. The villa belt lies beyond the commuter belt.
- Across 338 local authorities, villa density and income have a rank correlation of 0.27 (0.21 after distance to London, population density and region).

All numbers are in `data/results.json`.

## Files

- `index.html`: the interactive page (map, charts, tables, search). Data embedded; works as a single file.
- `header.png`: social card (1200 by 630).
- `data/villas.csv`: one row per villa (617): name, coordinates and where they came from, grid reference precision, which sources record it, Wikipedia county, PastScape or Coflein reference, Wikidata, Pleiades and OSM identifiers, local authority.
- `data/villa_records.csv`: every source record (1,215 kept records), with the villa it was joined to.
- `data/villa_sources_summary.json`: counts of records by source and stage.
- `data/msoa.csv`: one row per MSOA with income, population, Built-up Area, distances (London, nearest villa, Roman road, Roman town, coast), elevation, relief and villa flags.
- `data/roman_towns.csv`: Pleiades Roman-period settlements used for "distance to Roman town".
- `data/local_authorities.csv`: villa density and population-weighted income by local authority (2025 boundaries).
- `data/results.json`: every number quoted on the page, in the paper and in the blog post.
- `code/01_villas.py`: builds the villa list from Wikipedia, Wikidata, OpenStreetMap and Pleiades and deduplicates it.
- `code/02_msoa.py`: builds the MSOA table and its covariates.
- `code/03_analyse.py`: comparisons, regressions, placebo test, distance bands and local authority figures; writes `results.json` and a temporary `_site_data.json`.
- `code/04_build_page.py`: fills `code/page_template.html` with the results to make `index.html`.
- `code/05_header.py`: renders `header.png` with Playwright.
- `code/06_build_post.py` and `code/blog_template.html`: the blog post text.
- `release/`: the paper (PDF, LaTeX source, figures and build scripts), blog figures and Zenodo files.

## How to rerun

The scripts read their inputs in place; edit the paths at the top of each script. Inputs: the Wikipedia wikitext and Wikidata/OSM extracts (retrieved 27 October 2026), the Pleiades places CSV, the ONS income workbook, MSOA centroids, lookups and Census 2021 TS001, ONS local authority boundaries, Itiner-e roads, the Natural Earth coastline and the Terrain Tiles elevation grid (read with `dem.py` from the Within Sight project).

```
python3 code/01_villas.py
python3 code/02_msoa.py
python3 code/03_analyse.py
python3 code/04_build_page.py
FONT_DIR=/path/to/fonts python3 code/05_header.py
python3 code/06_build_post.py
FONT_DIR=/path/to/fonts python3 release/paper/figures.py
python3 release/paper/build_paper.py
```

It needs Python 3 with pandas, numpy, scipy, statsmodels, shapely, pyproj, matplotlib, openpyxl and playwright, and xelatex for the paper. The placebo test uses a fixed random seed.

## Method in brief

- **Villa list.** Wikipedia grid references are converted to latitude and longitude at the centre of the grid square. Records from different sources are joined when within 600 m (1 km for 1 km grid references), or within 2.5 km when one name contains the other's distinctive words, closest pairs first, never joining two records of one source more than 100 m apart.
- **Villa MSOA.** A villa within 2 km of the MSOA population-weighted centroid (5 km as a check).
- **Models.** OLS on log mean household income, standard errors clustered by local authority; premium = exp(b) minus 1. Controls in blocks: region; log distance to Charing Cross and its square; log distance to Roman road, Roman town and coast, elevation and local relief; Built-up Area population and a rural flag; then local authority fixed effects.
- **Placebo.** 200 runs moving every villa 5 to 15 km in a random direction, on land.

## Known limits

- The list holds excavated or well recorded villas that reached open sources, not all villas. Recording is biased to the south and to well studied, heavily developed counties; villas under towns are under-recorded.
- Income figures are ONS modelled estimates with wide intervals for single MSOAs. Scotland and Northern Ireland are not covered.
- No soil data: elevation and relief stand in for land quality.
- Correlation, not causation.

## Sources and licences

- Wikipedia: List of Roman villas in England; List of Roman villas in Wales (CC BY-SA 4.0), retrieved 27 October 2026.
- Wikidata (CC0), via QLever, retrieved 27 October 2026.
- OpenStreetMap contributors (ODbL), https://www.openstreetmap.org/copyright
- Pleiades, https://pleiades.stoa.org/ (CC BY 3.0).
- Itiner-e, the digital atlas of ancient roads, https://itiner-e.org/
- Office for National Statistics: Income estimates for small areas, England and Wales, FYE2023; Census 2021 TS001; Open Geography portal (MSOA centroids, Built-up Areas, lookups, local authority boundaries). Source: Office for National Statistics licensed under the Open Government Licence v3.0. Contains OS data © Crown copyright and database right 2026.
- Elevation: AWS Terrain Tiles by Mapzen/Tilezen (SRTM, GMTED2010, ETOPO1 and national datasets), https://registry.opendata.aws/terrain-tiles/
- Coastline: Natural Earth (public domain).
- Base map tiles: © Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community.

Because the villa list draws on Wikipedia, the derived data (`data/`) and the page text are released under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/); records and coordinates taken from OpenStreetMap remain under the ODbL. The code is released under the MIT licence (see `LICENSE`).

## Citation

Hotham, T. (2026) The Roman Commuter Belt? Roman Villas and Household Income in England and Wales. Zenodo. https://doi.org/10.5281/zenodo.23689960

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
