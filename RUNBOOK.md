# Runbook: if you see this, do this

| What you see | What it means | What to do |
|---|---|---|
| `[STOPPED] FileNotFoundError: no arXiv papers yet` | The analysis ran before any data was built | Run `build` first (snapshot or OAI-PMH) |
| `[STOPPED] SyntheticDataError` | You tried to export demo data | Expected. Build real data, then export |
| `[health] arxiv unavailable ... trying next` | One arXiv endpoint did not answer | Nothing. The next endpoint is tried automatically |
| `[STOPPED] SourceUnavailable: no arXiv OAI-PMH endpoint answered` | Neither endpoint answered | Wait an hour and rerun `update`. Check `health_log.csv` |
| `[health] arxiv degraded stopped early ... rerun update to resume` | The run hit its time budget or failure limit | Rerun `update`. It resumes from the saved checkpoint |
| `resumption token rejected; restarting from the checkpoint date` | arXiv expired the paging token | Nothing. The overlap is removed by de-duplication |
| `[http] failure n/5: HTTP 429` or `503` | Rate limited | Nothing. The client waits as asked. Five in a row stops the run |
| `[health] openalex unavailable` | OpenAlex refused or was down | Set `--email`. If it persists, set a free `OPENALEX_API_KEY`. Analysis still runs without it |
| `[health] github ... HTTP 403` | GitHub rate limit | Add a read-only token (see below) or rerun later |
| `[DECISION NEEDED] <source> has been unavailable for 3 consecutive checks` | A source may have changed its terms | Decide: wait, replace or drop. Write the decision in your research log. Do not edit the code to hide it |
| `H1b volatility test: {'H': nan ...}` | Too few concepts (for example in `--sample` mode) | Expected in sample mode. Run without `--sample` |
| `concept sparse around event` | Too few matched papers to judge | Reported as unevaluable, which is correct. Do not lower the floor to force a number |
| `precision` shows `judged 0` for a concept | That sheet has no 1s or 0s yet, or was saved as a separate Google Sheets copy | Edit the `.xlsx` file itself (double-click it in Drive), not a converted copy |
| `[mapping] still to fill (n): ...` | Those rows are not checked yet (or have no status) | Normal while you are working. Mark them OK or changed and run Cell 14b again |
| `[mapping] note: ... marked OK but status changed` | You changed a status but left the check as OK | Set that check to `changed` |
| `[mapping] note: ... marked changed but status is still ...` | You chose `changed` but did not change the status | Change the status, or set the check back to `OK` |
| `[mapping] status given but evidence column empty` | A status is chosen but the evidence column is blank | Write the unit, tier and page. Until then the event does not count as a finding |
| `[STOPPED] FileNotFoundError: no mapping found` | The workbook is not in `MyDrive/leadsignal/ground_truth/` | Run Cell 14a, or upload your filled `cs2013_cs2023_mapping.xlsx` to that folder |
| `[STOPPED] ValueError: mapping has no 'concept_id' column` | The header row was changed or deleted | Undo the change, or copy your answers into a fresh workbook |
| Colab disconnects | Session ended | Rerun from the top. Every stage saves to Drive and restarts from its last file |

## GitHub token (optional, about two minutes)

1. github.com -> Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens -> Generate.
2. Repository access: **Public repositories (read-only)**. No other permissions.
3. In Colab: the key icon (Secrets) -> add `GITHUB_TOKEN` -> paste -> allow notebook access.
4. The notebook reads it into the environment. It is never written to disk.

## Two-week rule

If any step stays stuck for more than two weeks, simplify it or cut it, and log the decision.
