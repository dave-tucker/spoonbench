# Bob — personality eval analysis

**Character:** Bob  
**Run date:** 2026-04-20  
**Eval:** `results/bob/RESULT.md`  
**Model sources:** `harness/models.yaml` (OpenRouter) · `harness/models.local.yaml` (local/Strix Halo)

---

## Model classification

**OpenRouter (12 families):** gemini, glm47, glm51, gpt5, haiku, kimi, m2m5, m2m7, mimo, opus, qwen36, sonnet  
**Local (6 families):** gemma4-26b, glm45a, gptoss-120b, m2m5-local, m2m7-local, qwen36-35b-local

---

## Aggregate summary

| tier | n | control mean | soul mean | mean Δ |
|---|---|---|---|---|
| **OpenRouter (cloud)** | 12 | 0.622 | 0.898 | +0.276 |
| **Local** | 6 | 0.667 | 0.933 | +0.266 |

---

## OpenRouter flagships — individual results

| model family | actual model | control | soul | Δ |
|---|---|---|---|---|
| gpt5 | openai/gpt-5.4 | 0.647 | 0.788 | +0.141 |
| haiku | claude-haiku-4.5 | 0.656 | 0.894 | +0.237 |
| opus | claude-opus-4.6 | 0.594 | 0.863 | +0.269 |
| sonnet | claude-sonnet-4.6 | 0.631 | 0.868 | +0.237 |
| kimi | kimi-k2.5 | 0.699 | 0.938 | +0.239 |
| gemini | gemini-2.5-pro | 0.512 | 0.955 | +0.442 |
| m2m5 | minimax-m2.5 | 0.672 | 0.860 | +0.188 |
| m2m7 | minimax-m2.7 | 0.638 | 0.841 | +0.202 |
| mimo | xiaomi/mimo-v2-pro | 0.625 | 0.897 | +0.273 |
| qwen36 | qwen3.6-plus | 0.644 | 0.980 | +0.336 |
| glm47 | z-ai/glm-4.7 | 0.608 | 0.944 | +0.336 |
| glm51 | z-ai/glm-5.1 | 0.542 | 0.953 | +0.411 |

---

## Local models — individual results

| model family | actual model | control | soul | Δ |
|---|---|---|---|---|
| gemma4-26b | gemma-4-27B (BF16 local) | 0.656 | 0.961 | +0.306 |
| glm45a | GLM-4.5-Air (BF16 local) | 0.772 | 0.961 | +0.188 |
| gptoss-120b | GPT-OSS 120B (Q6_K local) | 0.679 | 0.965 | +0.286 |
| m2m7-local | MiniMax-M2.7 (UD-Q3_K_XL local) | 0.658 | 0.856 | +0.198 |
| m2m5-local | MiniMax-M2.5 (UD-Q3_K_XL local) | 0.593 | 0.902 | +0.309 |
| qwen36-35b-local | Qwen3.6-35B-A3B (BF16 local) | 0.642 | 0.953 | +0.311 |

---

## Matched-pair comparison (same model family, cloud vs local)

| model | cloud soul | local soul | Δ soul |
|---|---|---|---|
| MiniMax M2.7 | 0.841 | 0.856 | **+0.015** |
| MiniMax M2.5 | 0.860 | 0.902 | **+0.042** |
| Qwen3.6 (plus vs 35B-A3B) | 0.980 | 0.953 | −0.027 |
| GLM-4.7 (full vs 4.5-Air local) | 0.944 | 0.961 | **+0.017** |
| GPT-5.4 vs GPT-OSS 120B local | 0.788 | 0.965 | **+0.177** |
| Gemini 2.5 Pro vs Gemma 4 27B local | 0.955 | 0.961 | **+0.006** |

---

## Per-dimension breakdown (soul condition, mean across all models)

| dimension | mean score (0–2) | notes |
|---|---|---|
| formal_address | 2.00 | perfect — all models hold this |
| register | 1.85 | formal elevated tone held well |
| anti_patterns | 1.83 | casual address/profanity/bravado avoided |
| concern_before_action | 1.79 | stakes-conditional behaviour captured reliably |
| contractions | 1.63 | weakest dimension — models slip most here |

---

## Key findings

**1. Bob's soul ceiling is lower than Alice's — the constraints are genuinely harder.**  
Cloud soul mean for Bob is **0.898** versus **0.974** for Alice. Bob's character demands strict formal register, no contractions, and hedged speech — constraints that cut against most models' training defaults. This is a harder problem, and the scores reflect it honestly.

**2. The no-contractions rule is the single hardest constraint to enforce.**  
The `contractions` dimension averages **1.63/2.0** in the soul condition — the weakest of all five dimensions. Models that have deeply internalised casual English frequently slip "it's" or "that's" even when the soul doc explicitly forbids it. `formal_address` is the mirror opposite at a perfect **2.00** — named titles like "Captain" are much easier to enforce than a negative rule on grammar.

**3. GPT-5.4 is the clear outlier — and the local GPT-OSS 120B corrects it dramatically.**  
GPT-5.4 scores only **0.788** in the soul condition, the lowest of all 18 families and well below the cloud mean (0.898). Its local counterpart, GPT-OSS 120B (Q6_K), scores **0.965** — a gap of **+0.177**. This is the largest matched-pair swing in the dataset. Heavy RLHF tuning appears to make GPT-5.4 resistant to the formal, no-contraction register Bob requires; the base-closer OSS model complies far more readily.

**4. Local models again match or exceed cloud soul performance.**  
Local mean soul score is **0.933** versus cloud **0.898**. This is the opposite of what you might expect from quantised smaller models — but the same pattern held for Alice. When a soul doc is active, on-device models are not at a disadvantage for Bob either.

**5. The control baseline is higher for Bob than Alice — Bob is more recognisable without guidance.**  
Cloud control mean is **0.622** for Bob versus **0.603** for Alice. Bob's formal, hedging speech patterns exist in training data (military, cautious, non-casual registers) in ways that partially surface without prompting. The uplift Δ is consequently a bit smaller (+0.276 cloud) than Alice's (+0.371), but the soul condition ceiling is the binding constraint, not the baseline.

**6. MiniMax models are notably weaker on Bob than on Alice.**  
M2.7 and M2.5 cloud soul scores are **0.841** and **0.860** respectively — well below their Alice scores (0.972, 0.978). The formal register and sentence-length variation Bob requires seems to push against MiniMax's default output style more than Alice's character did. Their local quants follow the same pattern.

**7. Qwen3.6-Plus is the standout cloud model.**  
It scores **0.980** in the soul condition — the highest of any cloud family for Bob — while also showing the same advantage against its local 35B-A3B counterpart (local drops slightly to 0.953). Qwen3.6 has the best instruction-following compliance with the formal register demands.

---

## Bottom line

The soul doc works across all 18 model families for Bob — 14 return a clear working verdict, 4 are marginal, none fail entirely. The character is harder to instantiate than Alice: formal register, no-contractions, and hedged speech all push against training defaults in ways that create a genuine ceiling below 1.0. The biggest lever for closing the gap is model selection — Qwen3.6 and the GLM family comply most reliably, while GPT-5.4 and MiniMax struggle. For local deployment, GPT-OSS 120B is the unexpected standout: it outperforms its cloud sibling by a wide margin and is the top-scoring local model overall.
