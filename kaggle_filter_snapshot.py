"""Run this ONCE inside a free Kaggle Notebook to shrink the arXiv snapshot.

Why: Cornell's full arXiv metadata snapshot is several gigabytes. Inside a
Kaggle Notebook the dataset is already attached, so nothing is downloaded.
This script keeps only computer science papers in the study's categories from
2012 onward and writes a much smaller file you download and put on Google Drive.

Steps:
  1. kaggle.com -> Create -> New Notebook (free account, no API key needed).
  2. Add data -> search "Cornell-University/arxiv" -> Add.
  3. Paste this file into a cell and run it (standard library only).
  4. Download /kaggle/working/cs_arxiv_2012plus.jsonl.gz from the Output panel.
  5. Upload it to your Google Drive folder, e.g. MyDrive/leadsignal/.
Then in Colab: python run_leadsignal.py build --snapshot <path to that file>
"""
import email.utils
import glob
import gzip
import json

CATEGORIES = {"cs.AI", "cs.LG", "cs.CL", "cs.CY", "cs.SE", "cs.CR"}
START_YEAR = 2012
KEEP = ("id", "categories", "title", "abstract", "versions")

src = glob.glob("/kaggle/input/**/arxiv-metadata-oai-snapshot.json", recursive=True)[0]
out = "/kaggle/working/cs_arxiv_2012plus.jsonl.gz"  # compressed: about a third of the size
kept = seen = 0
with open(src) as fin, gzip.open(out, "wt", encoding="utf-8") as fout:
    for line in fin:
        seen += 1
        rec = json.loads(line)
        if not CATEGORIES & set(rec.get("categories", "").split()):
            continue
        try:
            year = email.utils.parsedate_to_datetime(rec["versions"][0]["created"]).year
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if year < START_YEAR:
            continue
        fout.write(json.dumps({k: rec.get(k) for k in KEEP}) + "\n")
        kept += 1
        if kept % 100000 == 0:
            print(f"{kept:,} kept of {seen:,} read")
print(f"done: {kept:,} papers kept of {seen:,} -> {out}")
