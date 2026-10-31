# LeadSignal-CS

**Does research attention anticipate curriculum change?** LeadSignal-CS measures how research
attention to 50 computing concepts moves on arXiv, relative to the rest of the field, and tests
whether a confirmed rise comes before the concept is adopted into the ACM/IEEE-CS/AAAI computer
science curriculum guidelines (CS2013 to CS2023).

Author: Md. Mazid-Ul-Haque, Department of Computer Science, American International
University-Bangladesh (AIUB). A journal article based on this repository is in preparation.

This repository holds the complete code, the concept lexicon, the curriculum mapping with its
evidence, the result tables and the run logs of the analysis reported in the article, so that every
number can be traced and re-run.

## Repository contents

| Folder or file | What it is |
|---|---|
| `leadsignal/` | The pipeline: harvesting, concept matching, shares, detrended indicator, trend test, lead times, baselines, reports |
| `run_leadsignal.py` | Command-line entry point (one mode per stage) |
| `notebooks/LeadSignal_CS_Colab.ipynb` | The notebook used to run the analysis on free Google Colab |
| `tests/test_leadsignal.py` | 28 automated checks (matching, de-duplication, trend test, event rules, storage) |
| `data/ground_truth/` | Documented field shifts (RQ1), the AI-drafted curriculum mapping and the mapping rules |
| `tools/make_mapping_workbook.py` | Builds the mapping workbook used for the row-by-row check, or a blank one for a second coder |
| `results/2026-10-31/` | Result tables, the author-checked curriculum mapping and the run log of the reported analysis |
| `RUNBOOK.md` | What to do when a run stops |

The arXiv paper table itself (501,503 records, about 370 MB) is too large for GitHub. It will be
archived with a DOI at Zenodo together with the release of this repository. It can be rebuilt from
arXiv's open metadata with the `build` and `update` modes.

## Main results (analysis run of 31 October 2026)

Corpus: 501,503 arXiv papers in cs.AI, cs.LG, cs.CL, cs.CY, cs.SE and cs.CR, first versions from
1 January 2012 to 21 August 2026, matched to lexicon v1.0 (50 concepts, 268 phrases).

| Question | Result |
|---|---|
| RQ1: documented shifts | Large language models detected 2022Q1, three quarters before ChatGPT. Transformer architectures labelled rising 2018 to 2021 but never confirmed by the trend test |
| RQ2: lead before CS2023 adoption | 6 of 13 evaluable adoption events detected, 5 before 2024Q1. Median lead 11.5 quarters (95% CI 1 to 31). False alarms on 4 of 6 negative controls |
| RQ2: baselines | Shares without detrending: 9 of 13 detected, 6 of 6 false alarms. Raw counts: 12 of 13 detected, 6 of 6 false alarms |
| RQ3: volatility classes | Kruskal-Wallis H = 8.11, p = 0.017; median variance of growth 0.31 (stable), 0.41 (moderate), 0.81 (volatile) |
| RQ4: OpenAlex agreement | Weak: median Spearman rho 0.10 across 50 concepts |
| Matching precision | 60% of 1,500 sampled matches judged relevant (AI judge; blind human check of 150 pending); 0.44 stable, 0.73 moderate, 0.60 volatile concepts |

These are mixed results and the article reports them as such. Detected adoptions came early, but
sensitivity is low and most negative controls also rose. Without field detrending every control
rose. See `results/2026-10-31/README.md` for every table.

## How to reproduce

1. Put the code in Google Drive as `MyDrive/leadsignal/LeadSignal-CS-0.1.0.zip`, a zip file whose
   single top folder is `leadsignal-cs/` and contains the files of this repository.
2. Open `notebooks/LeadSignal_CS_Colab.ipynb` in Google Colab and run the cells in order.
   Cells 1 to 6b are setup and checks (expect `28/28 checks passed`).
3. Build the arXiv table (section 7), take the OpenAlex snapshot (section 9), and run the analysis
   (sections 10 and 14).

Only numpy, pandas and scipy are needed; everything runs on the free Colab tier without a GPU.
Command-line equivalents:

```bash
python tests/test_leadsignal.py
D=/path/to/data
python run_leadsignal.py build    --data-dir $D
python run_leadsignal.py openalex --data-dir $D --email you@example.com
python run_leadsignal.py analyse  --data-dir $D --events data/ground_truth/known_shift_events.csv
python run_leadsignal.py events   --data-dir $D        # checked mapping -> curriculum_events.csv
python run_leadsignal.py analyse  --data-dir $D --events $D/ground_truth/curriculum_events.csv
```

## Provenance and transparency

- **Data sources.** arXiv metadata through the arXiv OAI-PMH interface (CC0). OpenAlex works API
  (CC0). GitHub search API (aggregate counts only, no user data).
- **Run log.** `results/2026-10-31/health_log.csv` records every call to the data sources with its
  UTC time and outcome, including failures (an arXiv timeout and a GitHub rate limit on 31 October
  2026).
- **Pre-specification.** The rules for events, negative controls, detection and baselines are in the
  code and were fixed before any lead time against the curriculum was computed. The threshold grid is
  reported in full rather than tuned.
- **Curriculum mapping.** For each concept, a first draft of its status in CS2013 and CS2023, with
  the knowledge area, tier, PDF page and exact supporting sentence, was prepared with the help of an AI
  assistant (`data/ground_truth/claude_draft_mapping.csv`). The author then checked every row against
  the two guideline documents and changed two decisions (data engineering and MLOps). The checked
  workbook is `results/2026-10-31/cs2013_cs2023_mapping.xlsx`. Agreement between draft and final
  decisions was 98% (CS2013) and 96% (CS2023). Because the author checked a draft rather than
  coding blind, this is not an independent reliability estimate; a blank workbook for a blind second
  coder can be made with `tools/make_mapping_workbook.py --blank`.
- **Use of AI assistance.** Claude (Anthropic) was used to write and test the code, to operate the
  Colab notebook, to draft the curriculum mapping as described above, and to draft and edit the
  article text. The research design, the decisions on the curriculum mapping and the responsibility
  for all content are the author's. The article states this in its declaration of AI use.

## Known gaps

- Concept-matching precision was audited on 1,500 sampled matches by an AI model (see
  `results/2026-10-31/audit/`); the author's blind check of 150 of them is pending.
- The GitHub snapshot stopped at the unauthenticated rate limit after two concepts, so the
  practitioner channel was not evaluated.
- The arXiv update beyond 21 August 2026 was not run because arXiv's OAI-PMH list requests timed out
  on 31 October 2026. The analysis does not depend on it.

## Licences

Code: MIT (see `LICENSE`). Lexicon, curriculum mapping, result tables and documentation: CC BY 4.0.
arXiv and OpenAlex metadata: CC0.

## Citation

See `CITATION.cff`. Please cite the article once published.

## Changes

- 2026-09-25: curriculum mapping workbook, `events` mode, optional second-coder agreement.
- 2026-09-30: AI-drafted CS2013/CS2023 mapping with evidence; checking workbook.
- 2026-10-30: first real run on Colab; storage fix (harvest writes small part files); resume by
  position date; `storage` mode.
- 2026-10-31: a stored arXiv resumption token that times out now falls back to the checkpoint date.
  Full analysis run; results added under `results/2026-10-31/`.
- 2026-10-31: precision audit of 1,500 matches added (`results/2026-10-31/audit/`); the
  `precision` mode now skips helper files in the audit folder.
