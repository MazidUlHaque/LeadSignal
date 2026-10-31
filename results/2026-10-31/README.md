# Results of the analysis run of 31 October 2026

Produced in Google Colab with the code in this repository (notebook cells 9, 10, 14b and 14c).
Corpus: 501,503 arXiv papers, first versions 1 January 2012 to 21 August 2026. Lexicon v1.0.
Parquet outputs were converted to CSV for reading on GitHub; values are rounded to 5 decimals.

## Curriculum ground truth (checked by the author)

| File | Content |
|---|---|
| `cs2013_cs2023_mapping.xlsx` | The mapping workbook after the author's row-by-row check (sheet `Mapping`) |
| `mapping_workbook__Mapping.csv` | The `Mapping` sheet as CSV |
| `mapping_check.csv` | Per-concept final decisions as read by the `events` mode |
| `draft_agreement.csv` | Agreement between the AI draft and the checked decisions (percent and Cohen's kappa) |
| `curriculum_events.csv` | Events derived by fixed rule: 15 adoption events, 6 negative controls, all dated 2024Q1, with sources and notes |

## Lead times (RQ1 and RQ2)

| File | Content |
|---|---|
| `lead_times_known_shift_events.csv`, `lead_time_summary_known_shift_events.json` | RQ1: documented field shifts (BERT 2018Q4, ChatGPT 2022Q4) |
| `lead_times_curriculum_events.csv`, `lead_time_summary_curriculum_events.json` | RQ2: one row per event or control with status, detection quarter and lead |
| `baselines_*.csv` | Main method compared with shares without detrending and raw counts |
| `sensitivity_*.csv` | Main method across the threshold grid 0.10 to 0.40 |

## Indicator and other tests

| File | Content |
|---|---|
| `trends_quarterly.csv` | Per concept and quarter: count, share, relative log share, growth, four-quarter mean growth, label, Mann-Kendall p, adjusted p, confirmed, sparse flag |
| `trends_yearly_arxiv.csv` | The same at yearly resolution (used for RQ4) |
| `matches_per_concept.csv` | Number of matched papers per concept |
| `churn.csv`, `volatility_test.json` | RQ3: churn per concept and the Kruskal-Wallis test across volatility classes |
| `openalex_2026-10-31.csv`, `channel_agreement.csv`, `order_of_arrival.csv` | RQ4: OpenAlex snapshot, agreement with arXiv, first rising year per channel |
| `github_2026-10-31.csv` | Partial GitHub snapshot (two concepts before the rate limit; not used) |
| `curriculum_review_report.md` | The advisory report for the latest quarter (2026Q3, partial) |
| `health_log.csv` | Every data-source check and failure with its UTC time |
