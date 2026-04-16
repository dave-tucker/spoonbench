---
name: rubric-aggregation
description: Turn a tagged dialogue JSONL into an EVAL.md persona rubric
argument-hint: "<character>"
arguments:
  - name: character
    description: Character name to generate the rubric for.
---

# rubric-aggregation

**Character:** $1

Aggregate `out/$1/tagged.jsonl` into a defensible voice rubric at `out/$1/EVAL.md`.

This is the final stage of the three-skill pipeline:
`corpus-prep` → `dialogue-tagging` → **`rubric-aggregation`**

## What you produce

`out/<character>/EVAL.md` — a markdown rubric an LLM-as-judge can score against.
Fixed sections: Lexical, Structural, Behavioural, Anti-patterns, Exemplars, Methodology.

## Workflow

### 1. Load and validate

```python
import json
lines = [json.loads(l) for l in open('out/<character>/tagged.jsonl') if l.strip()]
```

Check N ≥ 200. Below that, flag it and continue with caveats.

If a contrast character exists, load `out/<contrast>/tagged.jsonl` too.
For Discovery, the contrast is `out/burnham/tagged.jsonl` (N=912).

### 2. Compute aggregates (no model calls — plain Python)

**Lexical:**
- `% contractions_used` overall; conditioned on `formal_address_used`
- `% formal_address_used` overall; conditioned on `relationship == superior`
- Hedge word frequency: occurrences / N. Keep entries >5%.

**Structural:**
- Distribution of `sentence_structure`, `clause_complexity`, `vocabulary_register`
- Mean / median / stdev of `word_count`

**Behavioural:**
- `emotional_register` conditioned on `scene_stakes`
- `threat_response` conditioned on `scene_stakes ∈ {high, crisis}`
- `% deference_marker == present` given `relationship == superior`
- `% self_reference == species_reference`

**Contrast deltas:** `character_value − contrast_value` for every aggregate.
Large deltas = character-distinctive. Small deltas = source-generic (don't make rules about these).

### 3. Derive rules

| Frequency | Rule type |
|---|---|
| >80% in a condition | Hard rule — penalise absence |
| 5–20% | Soft signal — positive/negative, not a fail |
| <5% | Anti-pattern — presence is a failure |
| Flat distribution | No rule — don't invent one |

Prefer rules with large contrast delta. A trait both characters share isn't useful.

### 4. Pick exemplars

For each major section, pull 1–3 verbatim lines from the corpus that are:
- Unambiguous (clearly demonstrate the trait)
- Standalone (make sense without surrounding scene)
- Representative (typical, not most extreme)

### 5. Write `out/<character>/EVAL.md`

Sections (fixed):
- `## Lexical` — contractions, formal address, hedge lexicon
- `## Structural` — sentence type, clause complexity, line length, vocab register
- `## Behavioural` — stakes-conditional emotional register, threat response, deference
- `## Anti-patterns (auto-fail)` — features <5% in corpus
- `## Exemplars` — at minimum: high-stakes, peer interaction, concise mode
- `## Methodology` — N, span, model used, contrast character, rule derivation method

The methodology section is non-negotiable. The rubric is only auditable with it.

### 6. Also distil a SOUL.md

After writing EVAL.md, produce `out/<character>/SOUL.md`: ≤25 lines, every line earning its place. See `out/bob/SOUL.md` as the template for tone and density.

### 7. Sanity-check with user

Show EVAL.md. Ask:
- Does the rubric match your sense of the character?
- Any rules missing or wrong?

If user says a rule is wrong, investigate rather than deleting it. Either the data doesn't support the intuition (interesting), or the tagging missed something (fix upstream).

## What NOT to do

- Don't write rules the data doesn't support.
- Don't round percentages. "78%" not "around 80%".
- Don't skip contrast deltas if a contrast set exists.
- Don't generate the rubric without exemplars.
- Don't omit the Methodology section.
