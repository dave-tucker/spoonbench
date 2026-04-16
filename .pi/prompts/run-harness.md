---
name: run-harness
description: Run the voice eval harness for a character against the model matrix
argument-hint: "<character> [--pilot]"
arguments:
  - name: character
    description: Character name to evaluate (must have out/<character>/SOUL.md, out/<character>/test.yaml, and out/<character>/judge_rubric.yaml).
  - name: pilot
    description: Optional flag. If present, run only the two opus models (control + soul) as a quick sanity check before committing to the full matrix.
    required: false
---

# run-harness

Run the eval harness for **$1**${2: (pilot mode)}.

## Pre-flight checks

Before running, verify:

```
out/$1/SOUL.md               # must exist
out/$1/test.yaml             # 12 test cases for this character
out/$1/judge_rubric.yaml     # scoring rubric for this character
harness/models.yaml          # model matrix — do not move this file
.env                         # must contain OPENROUTER_API_KEY
```

Examples are loaded automatically from `out/$1/test.yaml`. Use `--examples <path>` to override for debugging.

## Commands

**Pilot — two models, quick signal:**
```bash
cd harness
python eval.py --character $1 --models opus-control,opus-soul
```

**Full matrix:**
```bash
cd harness
python eval.py --character $1
```

**Specific models:**
```bash
cd harness
python eval.py --character $1 --models opus-control,opus-soul,gemini-control,gemini-soul
```

**Dry run (print what would run):**
```bash
cd harness
python eval.py --character $1 --dry-run
```

Results are written to `results/$1/`.

## Interpreting results

The summary table shows `mean` score (0–1 normalised) per model, and `Δ soul−control`.

| Δ | Verdict |
|---|---|
| ≥ 0.20 | ✓ soul working — the doc is moving the needle |
| 0.05–0.20 | △ marginal — soul has some effect, worth investigating |
| < 0.05 | ✗ no improvement — soul doc not landing |

**Common reasons for low Δ:**
1. Examples don't exercise the character's distinctive dimensions. Check `out/$1/test.yaml` — each case targets a specific rubric dimension. Add or revise cases that probe the character's most distinctive traits.
2. The judge rubric may not match the character's voice. Check `out/$1/judge_rubric.yaml` against `out/$1/EVAL.md` — dimension descriptions should reflect what the data actually shows.
3. The soul doc is too abstract. Check exemplars are present in `out/$1/SOUL.md`.

**Disagreement flags (⚠):** judge panel std dev > 0.20. Means the rubric criteria aren't showing up clearly — either the output is genuinely ambiguous, or the judge prompt is under-specified for this character.

## After running

Report back:
- Control mean, soul mean, Δ
- Any models that failed or produced empty generations
- Whether disagreement flags are concentrated on specific examples

If Δ < 0.10, flag it and suggest next steps (new examples, updated judge rubric, or soul doc revision) before running the full matrix.
