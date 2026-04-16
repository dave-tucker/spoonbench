# spoonbench

Answering the question, does my LLM have more personality than a wooden spoon.

A data-driven pipeline for extracting a character's voice from transcript
corpora, codifying it as a rubric, and measuring how well LLMs maintain that
voice when running inside agentic frameworks.

Built around Saru (codename **Bob**) and Tilly (codename **Alice**) from *Star Trek: Discovery* as reference characters.
The method is general — swap the transcripts and you can run it for anyone.

## How the pipeline works

```
transcripts (.md)
      │
      ▼
 corpus-prep          extract character lines → JSONL
      │
      ▼
 dialogue-tagging      tag each line with 14 linguistic/behavioural features
      │                via Claude (tool-use, structured output)
      ▼
 rubric-aggregation    aggregate tag frequencies → saru-EVAL.md
      │
      ▼
 SOUL.md               distil rubric into a ≤25-line voice doc
      │
      ▼
 test harness          inject SOUL.md into system prompt,
                       generate responses, score with judge panel
```

## Quickstart

### Prerequisites

```bash
pip install openai python-dotenv pyyaml
```

### API keys

Create a `.env` file in the repo root:

```
OPENROUTER_API_KEY=sk-or-...
```

The harness loads `.env` automatically. Environment variables take precedence if already set.

### Run the test harness

```bash
# Dry run — prints what would execute, no API calls
python harness/eval.py --character bob --dry-run

# Single model pair (cheapest smoke test)
python harness/eval.py --character bob --models haiku-control,haiku-soul

# Specific models by codename (comma-separated)
python harness/eval.py --character bob --models opus-control,opus-soul,kimi-control,kimi-soul

# Full matrix (all models in models.yaml)
python harness/eval.py --character bob

# Run for Alice instead
python harness/eval.py --character alice

# Override judge panel
python harness/eval.py --character bob --judges openrouter/anthropic/claude-sonnet-4.6,openrouter/openai/gpt-5.4

# Use a local models file (gitignored)
python harness/eval.py --character bob --models-file harness/models.local.yaml
```

Results are written to `results/{character}/{codename}-{example_id}-{condition}.md`.
A summary is written to `results/{character}/RESULT.md` after each completed run.
A summary table is printed on completion.

### Resumable

The harness is resumable — if a run is interrupted, re-running it skips
already-completed samples. Safe to Ctrl-C and continue.

### Local model overrides

Create `harness/models.local.yaml` (gitignored) with the same schema as `models.yaml`.
Pass it with `--models-file harness/models.local.yaml`.

## Adding models

Edit `harness/models.yaml`. Each entry is one run configuration:

```yaml
- codename: my-model-soul       # used in output filenames
  provider: openrouter          # anthropic | openrouter | openai
  model: org/model-id           # exact provider model ID
  soul: true                    # true = soul injected, false = control
```

Always pair a `soul: false` control with each model you test. The delta
between control and soul is the primary signal.

### Local / self-hosted models (OpenAI-compatible endpoint)

Any sever that exposes an OpenAI-compatible `/v1/chat/completions` endpoint can be used with `provider: openai`:

```yaml
- codename: my-local-model-soul
  provider: openai
  base_url: http://hostname:8080/v1   # defaults to http://localhost:8080/v1
  model: my-model-name                # must match the name in the server config
  soul: true
```

If your server requires authentication, set `OPENAI_API_KEY` in `.env`.
Most local servers accept any non-empty string.

---

## Adding test cases

Edit `out/{character}/test.yaml`. Each case needs:

```yaml
- id: "013"
  label: "short-descriptive-label"
  stakes: high          # low | medium | high | crisis
  addressee_role: peer  # superior | peer | subordinate | unknown
  dimension: register   # primary rubric dimension under test
  context: "Scene description for the model."
  prompt: >
    The actual user-facing prompt.
```

Stakes and addressee_role feed into the judge's scoring rubric — get them
right or the `concern_before_action` and `formal_address` dimensions will be
scored incorrectly.

The judge rubric itself lives at `out/{character}/judge_rubric.yaml` and is
loaded automatically. No code changes needed to add cases or adjust criteria.

## Cost estimate

To run all the tests, across 2 characters costs about $20 at the time of writing.

## Scoring rubric

The judge panel scores each response on five dimensions (0–2 each):

Rubric dimensions are **per-character** and loaded from `out/{character}/judge_rubric.yaml`.
Bob and Alice share the same scoring structure (5 dimensions × 0–2 each, total 0–10) but the criteria differ:

| Dimension | Bob (Saru) | Alice (Tilly) |
|---|---|---|
| `contractions` | Avoids contracted forms | Uses contractions freely |
| `register` | Neutral-to-technical; no colloquial | Colloquial first; elevated is the anti-pattern |
| `formal_address` / `oral_hedges` | Uses rank/title for superiors | Oral hedges (er, I mean, kind of) |
| `concern_before_action` | Stakes-conditional: n/a at low/medium | Same |
| `anti_patterns` | No bravado, casual address, profanity | No sustained formal register or cold resolution |

**Total: 0–10.** `concern_before_action` is excluded (scored n/a, total_possible = 8) for
low/medium stakes prompts.

Final score per sample = mean of panel scores, normalised to 0–1.
Disagreement flagged when panel std dev > 0.20.

Full rubrics: [`out/saru/EVAL.md`](out/saru/EVAL.md) · [`out/alice/EVAL.md`](out/alice/EVAL.md)

## What "soul working" means

A soul is considered to be working if:

- Soul condition mean score > control condition mean score by ≥ 0.20 (on 0–1 scale)
- `anti_patterns` score improves or holds

Observed results on haiku models (Anthropic direct, single-judge):

| Model | Control | Soul | Δ |
|---|---|---|---|
| haiku-4.5 | 0.167 | 1.000 | **+0.833 ✓** |
| haiku-3 | 0.371 | 1.000 | **+0.629 ✓** |

The control prompt explicitly suppresses character inference ("do not roleplay
fictional characters"), so the baseline reflects the model's unguided output.
Without this instruction, models partially infer Saru from the scene prompts
alone — inflating the control score and compressing the delta.

## Reproducing the tagging pipeline

If you want to retag from scratch or run on a different character:

```bash
# Extract lines from transcripts
python parse_saru.py --write        # → saru-lines.jsonl

# Tag (pilot first, then full)
python tag_saru.py                  # pilot: 50 lines, sanity report
python tag_saru.py --full           # full corpus → saru-tagged.jsonl

# Contrast set (Burnham)
python parse_burnham.py --write
python tag_burnham.py --full
```

Tagging uses `claude-haiku-4-5` at ~$0.001 per line. Full Saru corpus
(394 lines) costs under $0.50.

## Repository notes

- Raw transcripts (`discovery-*.md`) are fan-made and unlicensed. The derived
  JSONL files and rubric are your own transformations and are fine to share;
  the raw transcripts are not.
- `.env` is gitignored. Never commit API keys.
- `harness/logs/` and `results/` are gitignored.
- `harness/models.local.yaml` is gitignored — use it for local/self-hosted model overrides.
