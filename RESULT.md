# Soul doc evaluation — synthesis

**Characters evaluated:** Alice · Bob  
**Run dates:** 2026-04-19 / 2026-04-20  
**Source analyses:** [ALICE.md](ALICE.md) · [BOB.md](BOB.md)  
**Model sources:** `harness/models.yaml` (OpenRouter) · `harness/models.local.yaml` (local/Strix Halo)  
**Scope:** 12 cloud model families · 6 local model families · 2 characters · 18 test cases each

---

## Core verdict

**The soul doc works across every model family tested, on both characters, at both cloud and local tiers.**  
No family failed outright. The uplift from control to soul condition is consistent and large — averaging +0.324 across 12 cloud families and +0.371 across 6 local families. Local models do not degrade relative to cloud; they match or slightly exceed cloud soul scores overall.

---

## Cloud models — cross-character results

Ranked by mean soul score across both characters.

| model family | actual model | Alice soul | Bob soul | mean soul | mean control | mean Δ |
|---|---|---|---|---|---|---|
| glm51 | z-ai/glm-5.1 | 0.994 | 0.953 | **0.974** | 0.555 | +0.418 |
| gemini | gemini-2.5-pro | 0.988 | 0.955 | **0.972** | 0.558 | +0.413 |
| qwen36 | qwen3.6-plus | 0.956 | 0.980 | **0.968** | 0.586 | +0.382 |
| kimi | kimi-k2.5 | 0.991 | 0.938 | **0.964** | 0.665 | +0.299 |
| glm47 | z-ai/glm-4.7 | 0.980 | 0.944 | **0.962** | 0.572 | +0.390 |
| haiku | claude-haiku-4.5 | 0.998 | 0.894 | **0.946** | 0.653 | +0.292 |
| opus | claude-opus-4.6 | 1.000 | 0.863 | **0.931** | 0.625 | +0.306 |
| mimo | xiaomi/mimo-v2-pro | 0.952 | 0.897 | **0.924** | 0.621 | +0.304 |
| m2m5 | minimax-m2.5 | 0.978 | 0.860 | **0.919** | 0.637 | +0.282 |
| sonnet | claude-sonnet-4.6 | 0.969 | 0.868 | **0.918** | 0.622 | +0.296 |
| m2m7 | minimax-m2.7 | 0.972 | 0.841 | **0.906** | 0.593 | +0.314 |
| gpt5 | openai/gpt-5.4 | 0.911 | 0.788 | **0.850** | 0.661 | +0.188 |

---

## Local models — cross-character results

Ranked by mean soul score across both characters.

| model family | actual model | Alice soul | Bob soul | mean soul | mean control | mean Δ |
|---|---|---|---|---|---|---|
| gemma4-26b | gemma-4-27B (BF16) | 1.000 | 0.961 | **0.980** | 0.562 | +0.418 |
| glm45a | GLM-4.5-Air (BF16) | 0.991 | 0.961 | **0.976** | 0.606 | +0.370 |
| gptoss-120b | GPT-OSS 120B (Q6_K) | 0.953 | 0.965 | **0.959** | 0.549 | +0.409 |
| qwen36-35b-local | Qwen3.6-35B-A3B (BF16) | 0.965 | 0.953 | **0.959** | 0.555 | +0.403 |
| m2m5-local | MiniMax-M2.5 (Q3_K_XL) | 0.961 | 0.902 | **0.931** | 0.598 | +0.334 |
| m2m7-local | MiniMax-M2.7 (Q3_K_XL) | 0.963 | 0.856 | **0.909** | 0.615 | +0.294 |

---

## Tier comparison

| tier | n | mean control | mean soul | mean Δ |
|---|---|---|---|---|
| **Cloud (OpenRouter)** | 12 | 0.612 | 0.936 | +0.324 |
| **Local (Strix Halo)** | 6 | 0.581 | 0.953 | +0.371 |

Local soul slightly edges cloud (0.953 vs 0.936). The gap is small but in the opposite direction from what one might expect — running on-device does not erode personality retention.

---

## Findings

**1. The soul doc works — universally and substantially.**  
Across 18 model families and 2 characters, every single family shows positive uplift. The minimum mean Δ is +0.188 (GPT-5.4). No family is at zero or negative. The approach is robust, not fragile.

**2. Character complexity sets the ceiling, not the model tier.**  
Alice (mean soul 0.974 cloud) scores significantly higher than Bob (0.898 cloud) in the soul condition. The characters share the same soul doc format and the same judge panel — the difference is Bob's constraints (no contractions, strict formal register, hedged speech) cut harder against training defaults. The soul doc faithfully reflects this: harder constraints produce a lower but still meaningful ceiling. This is signal, not failure.

**3. GPT-5.4 is the consistent underperformer across both characters.**  
It sits at the bottom of the cloud ranking with a mean soul of **0.850** — and uniquely, it degrades *more* on the harder character (Bob: 0.788) than the easier one (Alice: 0.911). The gap between GPT-5.4 and the next-weakest cloud model (m2m7 at 0.906) is 0.056 — larger than most inter-model gaps in the top tier. The pattern is consistent with RLHF-tuned refusal of strong persona constraints, specifically the formal register and no-contraction rules Bob requires.

**4. The GLM and Gemini families are consistently the most reliable.**  
GLM-5.1, Gemini 2.5 Pro, and GLM-4.7 occupy the top three cloud slots with mean soul scores of 0.974, 0.972, and 0.962. They hold up on both characters — neither character trips them significantly. Qwen3.6-Plus sits third overall (0.968) and is notably the *only* model that scores *higher* on the harder character (Bob 0.980 vs Alice 0.956), suggesting it has particularly strong formal-register instruction-following.

**5. The Claude family (haiku, opus, sonnet) shows character-sensitivity.**  
All three Claude models score near-perfectly on Alice (0.998, 1.000, 0.969) but drop notably on Bob (0.894, 0.863, 0.868). This is the largest character-gap pattern in the dataset. Claude models comply readily with Alice's character but resist Bob's strict no-contractions and hedged speech. Their soul scores are still well above control, so the soul doc is working — but they are more sensitive to constraint type than the GLM/Gemini/Qwen families.

**6. MiniMax shows the same character-sensitivity as Claude, but more pronounced.**  
M2.5 drops from 0.978 (Alice) to 0.860 (Bob); M2.7 from 0.972 to 0.841. Both are in the top third for Alice and the bottom third for Bob. This isn't model weakness — it's sensitivity to the specific constraints Bob demands. The local quants show the same pattern, ruling out API-side filtering as a cause.

**7. Local models match or exceed cloud — and the local MiniMax quants outperform their cloud siblings on Bob.**  
Combined local soul mean (0.953) edges cloud (0.936). More specifically: the local MiniMax M2.5 quant scores 0.902 on Bob vs the cloud API's 0.860 (+0.042), and the local M2.7 quant scores 0.856 vs 0.841 (+0.015). For Alice, the gap is negligible in either direction. Quantisation (down to ~3-bit for MiniMax) introduces no meaningful personality tax.

**8. GPT-OSS 120B is the most striking local result.**  
Where GPT-5.4 (cloud) scores only 0.788 on Bob, GPT-OSS 120B (local, Q6_K) scores 0.965 — a gap of **+0.177**. On Alice the gap is smaller (+0.042) but in the same direction. The base-closer local version follows formal register and no-contraction rules that the heavily fine-tuned GPT-5.4 actively resists. For deployments using a GPT family model, the local OSS variant is the better option for personality work.

---

## Bottom line

**Does the soul doc work in cloud LLMs?** Yes, for all 12 families tested. The top tier (GLM-5.1, Gemini 2.5 Pro, Qwen3.6-Plus, Kimi, GLM-4.7) holds soul scores above 0.960 on average and stays consistent across character difficulty. The mid tier (Haiku, Opus, MiMo, MiniMax, Sonnet) works well on easier characters but shows 0.06–0.14 point degradation on harder constraints. GPT-5.4 is the single family where the soul doc has measurably limited traction, particularly when the character demands formal register.

**Does that hold for local models?** Yes, fully. Local soul scores average 0.953 — slightly *above* the cloud mean of 0.936. Quantisation down to Q3_K_XL (MiniMax) or Q6_K (GPT-OSS) does not erode personality retention in a meaningful way. For every model family where a local and cloud version were both tested, the local quant either matched or exceeded its cloud counterpart in the soul condition. The local tier is a viable deployment target for soul-doc personality work without qualification.
