## Title

[OC] Did the Romans pick the commuter belt? 617 Roman villas against household income in 7,264 neighbourhoods of England and Wales: villa areas earn 11% more, but only +0.4% once you allow for region, distance to London and terrain

## Body (optional)

I built an open list of Roman villas in England and Wales from Wikipedia, Wikidata, OpenStreetMap and Pleiades, and compared ONS household income (2022/23) in neighbourhoods with and without a villa within 2 km.

Villa neighbourhoods do look richer: a median of £57,822 against £52,315. But the gap is geography. Compare within regions and at the same distance from London and the "villa premium" falls to +0.4%. When I moved every villa 5 to 15 km in a random direction, 94% of 200 runs showed as big a raw premium as the real villas. Villas are densest 75 to 100 km from London, beyond the commuter belt proper.

Caveat: the list holds known, recorded villas only, and recording leans to the south.

Interactive version: https://tristan-hotham.github.io/roman-villas/

## Source comment

Source: Wikipedia, List of Roman villas in England and List of Roman villas in Wales (CC BY-SA 4.0); Wikidata (CC0); OpenStreetMap contributors (ODbL); Pleiades gazetteer of ancient places (CC BY 3.0); Itiner-e Roman roads; Office for National Statistics, Income estimates for small areas, England and Wales, FYE2023, Census 2021 and Open Geography portal (Open Government Licence v3.0, contains OS data © Crown copyright and database right 2026); AWS Terrain Tiles; Natural Earth.

Tools: Python (pandas, NumPy, SciPy, statsmodels, shapely, pyproj, matplotlib).

Interactive: https://tristan-hotham.github.io/roman-villas/
Blog post: https://blog.tristanhotham.com/2026/10/27/roman-villas/
Paper: https://doi.org/10.5281/zenodo.23689960
