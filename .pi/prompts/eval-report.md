---
description: Summarize voice eval results for a character into a report with tier list
argument-hint: "<character>"
---

Produce a voice eval report for the character **$1**.

## Step 1 — gather the data

Read every `.md` file in `results/$1/` (excluding `RESULT.md`). For each file,
extract from the YAML frontmatter:

- `codename`
- `condition` (soul / control)
- `panel_mean` (normalised 0–1)
- `panel_stderr`
- `stakes` (low / medium / high / crisis)
- `label`
- `dimension`

Also parse the `## Scores` JSON block to get per-dimension scores from each judge.
The JSON has a `judges` key; each judge has a `raw` key with the dimension scores.

If `results/$1/` is empty or missing, try `harness/results/` and filter to files
whose codename contains `$1`. Report which directory you found data in.

## Step 2 — summary table

Group result files by codename. For each codename compute:
- `n` — number of scored examples
- `mean` — mean panel_mean across all examples
- `condition` — soul or control

Pair codenames that share the same model family (strip `-soul` / `-control` suffix).
Compute `Δ = soul_mean − control_mean` for each pair.

Render as a markdown table sorted by Δ descending:

| model family | control mean | soul mean | Δ | n |
|---|---|---|---|---|

Verdict thresholds: ✓ working = Δ ≥ 0.20 · △ marginal = 0.05–0.19 · ✗ no improvement = Δ < 0.05

## Step 3 — per-dimension breakdown

For the soul condition only, aggregate mean scores across all models for each rubric
dimension. Extract from the judge JSON — average the `score` values across all
judge_N entries and all examples.

Render as a table:

| dimension | mean score (0–2) | notes |
|---|---|---|

Flag dimensions where the mean is below 1.0 — these are the rubric axes the soul doc
is not moving reliably.

## Step 4 — per-example heatmap

For each test case id, show the mean soul score across all model families.
This reveals which prompts are consistently hard regardless of model.

| id | label | stakes | soul mean | control mean | Δ |
|---|---|---|---|---|---|

Sort by soul mean ascending so the hardest cases are at the top.

## Step 5 — low-scoring cases and judge disagreement

List all soul-condition results where `panel_mean < 0.50`:

| codename | id | stakes | score | notes |
|---|---|---|---|---|

Then list cases where `panel_stderr > 0.20` (judges disagree meaningfully):

| codename | id | panel_mean | panel_stderr |
|---|---|---|---|

## Step 6 — trend commentary

Write 3–6 short paragraphs covering:

- Which model family has the largest soul uplift, and what's driving it
  (which dimension improved most)?
- Is there a model that scores high on control already (the "already sounds like the
  character" case) — and does the soul doc still help it?
- Are any models where the soul condition scores *lower* than control? If so, why
  might that be?
- Which stake levels produce the most disagreement between judges (high panel_stderr)?
- Is the stakes-conditional dimension (`concern_before_action`) being picked up
  reliably, or is it flat across conditions?
- Are there clusters of examples where even the best soul models fail?

Keep observations grounded in the numbers. Don't speculate beyond what the data shows.

## Step 7 — tier list

Rank model families by their **soul condition mean score** (not Δ).
The rationale: Δ measures how much the soul doc helps, but the tier list measures
which model actually produces the most accurate voice when given the soul doc.
A high-baseline model that improves only slightly may still out-rank a
low-baseline model with a large Δ.

Use these thresholds:

| Tier | Normalised mean |
|---|---|
| S | ≥ 0.85 |
| A | 0.75 – 0.84 |
| B | 0.65 – 0.74 |
| C | 0.50 – 0.64 |
| D | < 0.50 |

Render as:

**S-Rank** — [model families]  
**A-Rank** — [model families]  
**B-Rank** — [model families]  
**C-Rank** — [model families]  
**D-Rank** — [model families]  

Add one sentence per tier explaining what characterises that tier's outputs
(e.g. "S-rank models produce concern acknowledgement in all high-stakes cases and
maintain formal register throughout; A-rank models slip occasionally on
contractions or formal address").

If fewer than 3 model families have completed soul runs, note that the tier list
is provisional and may shift with more data.
