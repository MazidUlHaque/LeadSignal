# Ground truth

Two inputs, one generated file. Only rows with `citation_status = sourced` count as findings.

## 0. `claude_draft_mapping.csv` (the draft, 2026-09-30)

Claude read Appendix A of the CS2013 PDF and the CS2023 Body of Knowledge PDF, searched every
concept with a script (every mention recorded with its unit, tier or category and PDF page), and
drafted a status for each concept with the exact supporting sentence. All 50 x 2 quotes were checked
automatically against the PDF text. Ten rows are marked `CHECK FIRST`: they are judgement calls
explained in the notes. The draft is kept unchanged so that the agreement between draft and final
decisions can be reported; the researcher's checked workbook is the ground truth.

Decision rule used in the draft, added to the rules below: a concept is named when its label, one
of its lexicon v1.0 aliases (the same words searched on arXiv) or an unmistakable synonym appears; a
knowledge area or unit whose title is the concept also counts when it contains core topics.

## 1. `cs2013_cs2023_mapping.xlsx` (checked by hand)

The author-checked workbook used in the reported analysis is in `results/2026-10-31/`. The
workbook is created with `tools/make_mapping_workbook.py` (pre-filled from the draft) and is not
stored in this folder.

One row per lexicon concept. For each curriculum, record the status and where it was found:

- `cs2013_status`: `core` (Core-Tier1 or Core-Tier2), `minor` (Elective only, or only in learning
  outcomes or unit descriptions) or `absent` (not named in the Body of Knowledge).
- `cs2023_status`: `core` (CS Core or KA Core), `minor` (Non-core only, or only in learning outcomes
  or unit descriptions) or `absent`.
- `cs20xx_knowledge_area` and `cs20xx_evidence`: knowledge area, unit, tier and PDF page, so every
  row can be checked. For `absent`, write the words searched.
- Only the Body of Knowledge counts. Course exemplars, course packaging, preambles, introductions and
  essays go in `notes`.
- In the checking workbook, a row counts only after both checks (`check_2013`, `check_2023`) are set
  to `OK` or `changed`.
- When a concept appears in several places, the highest status is recorded.

The step-by-step instructions are in the Curriculum Mapping Guide and the workbook's own
"Start here" and "Rules" tabs. `cs2013_cs2023_mapping_TEMPLATE.csv` holds the same columns for
anyone who prefers a CSV file.

## 2. `curriculum_events.csv` (generated, never edited by hand)

`python run_leadsignal.py events --data-dir <DATA_DIR>` applies fixed rules
(`leadsignal/groundtruth.py`):

| CS2013 | CS2023 | change | used as |
|---|---|---|---|
| absent or minor | core | adoption | adoption event (layer systematic) |
| absent | minor | expansion | adoption event (layer systematic) |
| core | minor | reduction | decline event (layer systematic) |
| minor or core | absent | removal | decline event (layer systematic) |
| absent | absent | none | negative control (topics only) |
| same level | same level | none | no event |

All events are dated `2024Q1` (CS2023 final report, endorsed January to February 2024).
The rule depends only on the curriculum mapping, never on the detector's output, so the
false-alarm rate cannot be tuned by choosing controls after seeing results.

### Rule amendment, 2026-09-25 (made before any lead-time analysis)

Products and frameworks (TensorFlow, PyTorch, Kubernetes, Docker, React, AWS) are no longer used
as negative controls. Curriculum guidelines avoid naming products by design, so a tool's absence
from CS2013 and CS2023 is not evidence that its underlying idea was not adopted. Counting them as
controls would inflate the false-alarm rate for reasons unrelated to the detector. They can still
become adoption events if a curriculum names them.

## 3. `known_shift_events.csv` (measurement check, RQ1, not RQ2)

Documented shifts in the field itself (BERT, ChatGPT, PyTorch, Kubernetes, MLOps). They test
whether the arXiv signal picks up changes that are known to have happened. They are NOT
curriculum-adoption events and must not be used as RQ2 evidence, because using research
events to validate a research signal would be circular. Three still need a citable source.

## 4. Optional: a second coder

A colleague fills a separate copy of the workbook independently (at least 15 concepts, without
seeing your answers). `events --second-coder <their file>` reports percent agreement and Cohen's
kappa for each curriculum and lists disagreements to discuss.
