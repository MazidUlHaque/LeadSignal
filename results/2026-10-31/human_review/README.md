# Blind human check of the precision audit

150 of the 1,500 AI-judged matches (`../audit/`) were split into 15 sets of 10. Each set was judged by
one colleague of the author, who saw the paper title and abstract and the concept, but not the AI
model's label, and did not use AI tools. Answers: 1 = the paper is about the concept, 0 = it is not.

- `LeadSignal_HumanCheck_Set01.xlsx` to `Set15.xlsx`: the returned workbooks, unchanged.
- `human_vs_ai_agreement_150.csv`: one row per paper with the human and AI labels.
- `human_review_summary.json`: agreement, Cohen's kappa, crosstab and the calibrated precision
  reported in the article.
