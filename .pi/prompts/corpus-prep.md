---
name: corpus-prep
description: Prepare a corpus of dialogue lines for a single character from raw transcripts
argument-hint: "<character>"
arguments:
  - name: character
    description: Character name to extract dialogue for (TV scripts, screenplays, fan transcripts), producing a JSONL file ready for the dialogue-tagging skill.
---

# corpus-prep

**Character:** $1

Turn raw transcripts into a clean JSONL corpus of one character's lines, with scene context and addressee pre-filled, ready for downstream tagging.

## Script

There is already a parser: `parse.py`. Use it — don't write a new one unless the transcript format is genuinely different from the Discovery `.md` format.

```
python parse.py <character>           # sample: prints first 20 lines
python parse.py <character> --write   # writes out/<character>/lines.jsonl
```

Transcripts live in `data/discovery-s01e*.md`. Output goes to `out/<character>/lines.jsonl`.

## When to write a new parser

Only if `parse.py` produces wrong output — wrong speaker matched, stage directions leaking into text, scene headings missed. Read one transcript first (`data/discovery-s01e03.md` is a good sample) to verify the format before touching the script.

If a new parser is needed, write it as `parse_<show>.py` alongside `parse.py`, following the same structure: `TARGET_SPEAKER`, `SCENE_RE`, `SPEAKER_RE`, `strip_stage_dirs()`, output to `out/<character>/lines.jsonl`.

## Workflow

### 1. Run the sample pass

```
python parse.py <character>
```

Check the first 20 lines:
- Text clean? (no speaker tags, no `[laughs]`, no scene headings)
- Addressees plausible?
- Contexts meaningful?

### 2. If output looks wrong, diagnose first

Common failure modes:
- Speaker tag not matching: `NAME (CONT'D):`, `NAME [OC]:`, `NAME>` — check `SPEAKER_RE` in `parse.py`
- Name collision: "SARU" matching "SARUMAN" — add exact-match guard
- Stage direction leaking: `(sotto voce)` not stripped — check `INLINE_STAGE_RE`

Fix in `parse.py`, re-run sample.

### 3. Write the full corpus

```
python parse.py <character> --write
```

Report back:
- Total lines extracted
- Span (e.g. S1E3 → S1E15)
- Mean line length
- % unknown addressees / contexts (flag if either >50%)

### 4. Hand off

Tell the user output is at `out/<character>/lines.jsonl` and the next step is `dialogue-tagging`.

## What NOT to do

- Don't redistribute raw transcripts. The output JSONL is fine to share; the source `.md` files probably aren't.
- Don't clean up the dialogue (fix typos, normalise punctuation). Preserve verbatim.
- Don't fill `context` or `addressee` with guesses. `"unknown"` is valid and useful.
