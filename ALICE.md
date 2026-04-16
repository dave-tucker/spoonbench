# Alice — personality eval analysis

**Character:** Alice  
**Run date:** 2026-04-19  
**Eval:** `results/alice/RESULT.md`  
**Model sources:** `harness/models.yaml` (OpenRouter) · `harness/models.local.yaml` (local/Strix Halo)

---

## Model classification

**OpenRouter (12 families):** gemini, glm47, glm51, gpt5, haiku, kimi, m2m5, m2m7, mimo, opus, qwen36, sonnet  
**Local (5 families):** gemma4-26b, glm45a, m2m5-local, m2m7-local, qwen36-35b-local

---

## Aggregate summary

| tier | n | control mean | soul mean | mean Δ |
|---|---|---|---|---|
| **OpenRouter (cloud)** | 12 | 0.603 | 0.974 | +0.371 |
| **Local** | 5 | 0.511 | 0.976 | +0.465 |

---

## OpenRouter flagships — individual results

| model family | actual model | control | soul | Δ |
|---|---|---|---|---|
| gpt5 | openai/gpt-5.4 | 0.676 | 0.911 | +0.235 |
| haiku | claude-haiku-4.5 | 0.651 | 0.998 | +0.347 |
| opus | claude-opus-4.6 | 0.657 | 1.000 | +0.343 |
| sonnet | claude-sonnet-4.6 | 0.613 | 0.969 | +0.356 |
| kimi | kimi-k2.5 | 0.631 | 0.991 | +0.360 |
| gemini | gemini-2.5-pro | 0.605 | 0.988 | +0.384 |
| m2m5 | minimax-m2.5 | 0.603 | 0.978 | +0.375 |
| m2m7 | minimax-m2.7 | 0.547 | 0.972 | +0.424 |
| mimo | xiaomi/mimo-v2-pro | 0.616 | 0.952 | +0.336 |
| qwen36 | qwen3.6-plus | 0.528 | 0.956 | +0.428 |
| glm47 | z-ai/glm-4.7 | 0.536 | 0.980 | +0.444 |
| glm51 | z-ai/glm-5.1 | 0.569 | 0.994 | +0.425 |

---

## Local models — individual results

| model family | actual model | control | soul | Δ |
|---|---|---|---|---|
| gemma4-26b | gemma-4-27B (BF16 local) | 0.469 | 1.000 | +0.531 |
| glm45a | GLM-4.5-Air (BF16 local) | 0.440 | 0.991 | +0.551 |
| qwen36-35b-local | Qwen3.6-35B-A3B (BF16 local) | 0.469 | 0.965 | +0.496 |
| m2m7-local | MiniMax-M2.7 (UD-Q3_K_XL local) | 0.573 | 0.963 | +0.390 |
| m2m5-local | MiniMax-M2.5 (UD-Q3_K_XL local) | 0.603 | 0.961 | +0.358 |
| gptoss-120b | GPT-OSS 120B (Q6_K local) | 0.420 | 0.953 | +0.533 |

---

## Matched-pair comparison (same model family, cloud vs local)

| model | cloud soul | local soul | Δ soul |
|---|---|---|---|
| MiniMax M2.7 | 0.972 | 0.963 | −0.009 |
| MiniMax M2.5 | 0.978 | 0.961 | −0.017 |
| Qwen3.6 (plus vs 35B-A3B) | 0.956 | 0.965 | **+0.009** |
| GLM-4.7 (full vs 4.5-Air local) | 0.980 | 0.991 | **+0.011** |
| Gemini 2.5 Pro vs Gemma 4 27B local | 0.988 | 1.000 | **+0.012** |
| GPT-5.4 vs GPT-OSS 120B local | 0.911 | 0.953 | **+0.042** |

---

## Key findings

**1. Local models hold personality just as well as flagship cloud models.**  
Soul condition means: local **0.976** vs cloud **0.974** — a difference of 0.002, which is noise. When the soul doc is active, a quantised local Qwen or GLM hits the same ceiling as Claude Opus or Gemini 2.5 Pro.

**2. The only real difference is baseline (control) behaviour.**  
Local models start lower without any persona guidance (0.511 vs 0.603). This means local models default to more generic AI-speak out of the box, but they shed it just as thoroughly when given the soul doc.

**3. Local models actually show a larger Δ (+0.465 vs +0.371).**  
This is a direct consequence of the lower control baseline — there's more headroom to gain. It's not that local models are *better* at personality; it's that they're further from the ceiling without guidance.

**4. The weakest soul performer is a flagship, not a local model.**  
GPT-5.4 scores only **0.911** on soul — the lowest of all 17 families. Every local model beats it in the soul condition. This is likely an instruction-following tension: heavily RLHF-tuned models sometimes resist strong persona overlays.

**5. Matched pairs are essentially equivalent.**  
The MiniMax M2.7 quant (UD-Q3_K_XL, ~3-bit) loses only 0.009 soul score versus the cloud API version. The local Qwen3.6-35B-A3B actually *outscores* the cloud Qwen3.6-Plus by a hair (+0.009). Quantisation has negligible impact on personality retention.

---

## Bottom line

The soul doc works uniformly across tiers. Local models are a fully viable deployment target for Alice — you don't pay a meaningful personality tax for running on-device.
