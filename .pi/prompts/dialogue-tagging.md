---
name: dialogue-tagging
description: Tag a corpus of character dialogue with structured linguistic and behavioural features
argument-hint: "<character>"
arguments:
  - name: character
    description: Character name whose dialogue is being tagged.
---

# dialogue-tagging

**Character:** $1

Tag each line in `out/$1/lines.jsonl` with linguistic and behavioural features, producing `out/$1/tagged.jsonl`.

This is the middle stage of the three-skill pipeline:
`corpus-prep` → **`dialogue-tagging`** → `rubric-aggregation`

## Script

There is already a tagger: `tag.py`. Use it.

```
python tag.py <character>           # pilot (50 lines) → report, then stop
python tag.py <character> --pilot   # pilot only, no prompt
python tag.py <character> --full    # full corpus (resumable)
```

Reads `out/<character>/lines.jsonl`. Writes `out/<character>/tagged.jsonl`.
Pilot output goes to `out/<character>/pilot.jsonl` (overwritten each run).

Requires `OPENROUTER_API_KEY` in `.env`.

## Schema

Each output record extends the input with:

```
relationship:        superior | peer | subordinate | unknown
scene_stakes:        low | medium | high | crisis | unknown
word_count:          integer
contractions_used:   bool
contractions_possible: bool
formal_address_used: bool
hedge_words:         list[string]
sentence_structure:  declarative | interrogative | imperative | exclamatory
clause_complexity:   simple | compound | complex
vocabulary_register: colloquial | neutral | elevated | technical
emotional_register:  neutral | concerned | resolute | curious | distressed | warm | unknown | other
threat_response:     list — ignore | register_concern | flee_advocacy | resolute_action | n/a | unknown
deference_marker:    present | absent | unknown
self_reference:      absent | first_person | species_reference
```

## Workflow

### 1. Always pilot first

Run `python tag.py <character>` and review the sanity report. Check:
- Word count mean/min/max plausible?
- `contractions_used` rate consistent with what you'd expect for this character?
- `emotional_register` spread across multiple values (not 70%+ in one bucket)?
- `sentence_structure` values all in schema (no 'complex' or 'compound' leaking in)?
- `vocabulary_register` distribution matches character register?

Spot-check 5–10 individual records against the source text before proceeding.

### 2. Red flags

- `emotional_register` one value >70%: model is flattening. Check system prompt.
- `sentence_structure` out-of-schema values: the normaliser in `tag.py` catches these, but flag count >5% means the description needs strengthening.
- `scene_stakes` >50% unknown: context fields from `corpus-prep` aren't carrying signal. Either fix upstream or accept the loss.

### 3. Full corpus

Only run after the pilot is clean. `--full` is resumable: already-tagged `line_id`s are skipped.

### 4. Contrast set (recommended)

If a contrast character exists in `out/`, tag them too. This is the baseline for `rubric-aggregation`. Without it, frequencies are unanchored.

For Discovery characters, `burnham` is the natural contrast (already tagged at `out/burnham/tagged.jsonl`).

### 5. Hand off

Tell the user:
- Output: `out/<character>/tagged.jsonl`
- Next step: `rubric-aggregation`

## What NOT to do

- Don't run `--full` before the pilot is reviewed.
- Don't modify `context` or `addressee` fields — those are inputs from `corpus-prep`.
- Don't derive rubric rules here. That's `rubric-aggregation`.
