# Precision audit of concept matching

Question: when the keyword matcher assigns an arXiv paper to a concept, is the paper really about
that concept? For each of the 50 concepts, 30 matched papers were drawn at random
(`run_leadsignal.py audit`, fixed seed), 1,500 papers in total.

## Who judged and how

- **Judge.** The 1,500 papers were judged by Claude (Anthropic), an AI model, on 31 October 2026,
  one concept at a time, from the title and abstract only. Full texts were not used.
- **Criterion.** "Would a researcher looking for papers on this concept want this paper?"
  1 = the concept is the main topic, or the paper substantially uses, studies or improves it.
  0 = the concept appears only in passing, with a different meaning, or the paper is about something
  else. The same criterion is printed in the human check files.
- **Human validation.** The author judges a blind random subset of 150 of these papers (3 per
  concept, shuffled, without seeing the AI labels) in `human_check_150.xlsx` or `.docx`;
  `human_check_150_key.csv` links each numbered paper back to its concept and arXiv id. The AI labels
  were committed to this repository before the human check was done, so they cannot have been
  adjusted to agree with it. Agreement (percent and Cohen's kappa) will be added here.

## Files

| File | Content |
|---|---|
| `<concept_id>.xlsx` (50 files) | The 30 sampled papers with arXiv id, first-version date, title, abstract and the `relevant` label |
| `audit_precision.csv` | Precision per concept (share of the 30 papers judged relevant) with volatility class |
| `audit_summary.json` | Pooled precision overall, by volatility class, and without the six tool concepts |
| `human_check_150.xlsx`, `human_check_150.docx` | The blind check files given to the author (added with the author's answers once complete) |
| `human_check_150_key.csv` | Number, concept and arXiv id of each of the 150 papers |

## Result

| Measure | Value |
|---|---|
| Papers judged relevant | 905 of 1,500 (60%) |
| Median precision across 50 concepts | 0.63 |
| Stable / moderate / volatile concepts | 0.44 / 0.73 / 0.60 |
| Without the six tool concepts (44 concepts) | 0.63 |

Precision varies strongly by concept. It is high for distinctive technical terms (for example deep
learning, reinforcement learning, retrieval-augmented generation, diffusion models, federated
learning: 0.97) and low for generic phrases that also occur in passing in unrelated papers (data
structures and computational complexity: 0.10; TensorFlow and AWS: 0.23). Low precision adds noise
to a concept's share series; it does not by itself create a rise, because the detector works on the
change of the detrended share over time.
