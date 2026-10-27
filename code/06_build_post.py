"""Step 6. Fill code/blog_template.html with numbers from data/results.json and write release/blog/post.html.

Image placeholders ({{IMG|file|alt|caption}}) are left for the uploader to replace.
Usage: python3 code/06_build_post.py
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "data", "results.json")))


def get(path):
    v = R
    for k in path.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def sign(v, d):
    r = round(v * 100, d)
    return ("+" if r > 0 else "−" if r < 0 else "") + f"{abs(v) * 100:.{d}f}%"


F = {"int": lambda v: f"{round(v):,}", "pct": lambda v: f"{round(v * 100)}%", "pct1": lambda v: f"{v * 100:.1f}%",
     "pctabs": lambda v: f"{round(abs(v) * 100)}%", "spct1": lambda v: sign(v, 1), "f1": lambda v: f"{v:.1f}",
     "f2": lambda v: f"{v:.2f}", "gbp": lambda v: f"£{round(v):,}"}
td = R["lad"]["top_density"]
assert (td[5]["name"], td[6]["name"], td[13]["name"]) == ("Cotswold", "South Somerset", "Isle of Wight")
assert R["lad"]["most_villas"]["name"] == "Cotswold" and R["lad"]["top_income"][0]["name"] == "Richmond upon Thames"
s = open(os.path.join(ROOT, "code", "blog_template.html"), encoding="utf-8").read()
s = re.sub(r"\{\{([A-Za-z0-9_.]+)\|(\w+)\}\}", lambda m: F[m.group(2)](get(m.group(1))), s)
assert not re.search(r"\{\{(?!IMG\|)", s)
open(os.path.join(ROOT, "release", "blog", "post.html"), "w", encoding="utf-8").write(s)
text = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", " ", s, flags=re.S))
print("post.html written,", len(text.split()), "words")
