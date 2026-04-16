"""
runner.py — Async runner for the agent-personality eval harness.

Uses the openai SDK (AsyncOpenAI) for all API calls — generation and judging
both go through OpenRouter or a local openai-compatible endpoint.
extra_body is used for per-model params (e.g. reasoning effort) so they
land correctly in the request body without touching the message structure.

Each model runs sequentially. Within a model, up to CONCURRENCY examples
run in parallel. Each example generates one response then calls all judges
concurrently.

Results are written to results/<character>/ as .md files.
"""

import asyncio
import json
import re
import statistics
import time
from pathlib import Path

from openai import AsyncOpenAI
import yaml

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).parent.parent
HARNESS = Path(__file__).parent

HELPFUL_STUB_PATH = HARNESS / "prompts" / "helpful_assistant_stub.md"
SOUL_WRAPPER_PATH = HARNESS / "prompts" / "soul_wrapper.md"

_DEFAULT_STUB    = HELPFUL_STUB_PATH
_DEFAULT_WRAPPER = SOUL_WRAPPER_PATH

# ── Config ────────────────────────────────────────────────────────────────────

REQUEST_TIMEOUT = 600
MAX_RETRIES     = 3

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/agent-personality",
    "X-Title":      "agent-personality-eval",
}

OPENAI_BASE = "http://localhost:8080/v1"   # default local endpoint


# ── Client factories ──────────────────────────────────────────────────────────

def _openrouter_client(api_key: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE,
        default_headers=OPENROUTER_HEADERS,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )


def _local_client(api_key: str, base_url: str) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or "none",
        base_url=base_url,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )


# ── Rubric loading ────────────────────────────────────────────────────────────

def load_rubric(character: str) -> dict:
    """Load out/{character}/judge_rubric.yaml and return the parsed dict."""
    path = ROOT / "out" / character / "judge_rubric.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Judge rubric not found: {path}")
    return yaml.safe_load(path.read_text())


# ── Prompt loading ────────────────────────────────────────────────────────────

def build_system_prompt(
    soul: bool,
    stub_path: Path = None,
    wrapper_path: Path = None,
    soul_doc_path: Path = None,
    character: str = "",
) -> str:
    stub_path    = stub_path    or _DEFAULT_STUB
    wrapper_path = wrapper_path or _DEFAULT_WRAPPER

    if soul_doc_path is None:
        soul_doc_path = (ROOT / "out" / character / "SOUL.md") if character else None
    if soul_doc_path is None or not soul_doc_path.exists():
        raise FileNotFoundError(
            f"SOUL.md not found at {soul_doc_path}. "
            f"Pass --character <name> or set soul_path in models.yaml."
        )

    stub = stub_path.read_text().strip()
    if not soul:
        return stub
    wrapper  = wrapper_path.read_text()
    soul_doc = soul_doc_path.read_text().strip()
    return stub + "\n\n" + wrapper.replace("{soul_contents}", soul_doc).strip()


# ── Judge prompts ─────────────────────────────────────────────────────────────

def judge_system(character_name: str) -> str:
    return (
        f"You are an expert evaluator assessing whether a piece of dialogue "
        f"sounds like the character {character_name}. Score strictly and return "
        f"only valid JSON — no other text."
    )


def _render_dimensions(rubric: dict) -> str:
    """Render the dimensions block for the judge prompt."""
    dimensions = rubric.get("dimensions", {})
    lines = []
    for dim_name, dim in dimensions.items():
        desc = dim.get("description", "")
        s2   = dim.get("score_2", "")
        s1   = dim.get("score_1", "")
        s0   = dim.get("score_0", "")
        lines.append(
            f"**{dim_name}** ({desc})\n"
            f"  2: {s2}\n"
            f"  1: {s1}\n"
            f"  0: {s0}"
        )
    return "\n\n".join(lines)


def _render_json_template(rubric: dict) -> str:
    """Render the expected JSON response template."""
    dimensions = rubric.get("dimensions", {})
    stk_dim    = rubric.get("stakes_conditional_dimension", "concern_before_action")
    lines = []
    for dim_name in dimensions:
        if dim_name == stk_dim:
            lines.append(
                f'  "{dim_name}": {{"score": <0|1|2|"n/a">, "reason": "<one sentence>"}}'
            )
        else:
            lines.append(
                f'  "{dim_name}": {{"score": <0|1|2>, "reason": "<one sentence>"}}'
            )
    lines.append('  "total": <0–10>')
    lines.append('  "total_possible": <8 or 10>')
    lines.append('  "notes": "<optional>"')
    return "{\n" + ",\n".join(lines) + "\n}"


def build_judge_prompt(rubric: dict, example: dict, response: str) -> str:
    """Build the full judge prompt from a loaded rubric dict."""
    character_name = rubric.get("character_name", "the character")
    stk_dim        = rubric.get("stakes_conditional_dimension", "concern_before_action")
    stk_dim_info   = rubric.get("dimensions", {}).get(stk_dim, {})
    na_condition   = stk_dim_info.get("na_condition", "stakes are low or medium")

    rendered_dims = _render_dimensions(rubric)
    json_template = _render_json_template(rubric)

    return f"""\
## User prompt
{example['prompt'].strip()}

## Stakes level
{example['stakes']}

## Addressee role
{example['addressee_role']}

## Model response
{response}

## Scoring rubric

You are scoring whether this response sounds like {character_name}.
Score each dimension 0, 1, or 2.

{rendered_dims}

**Scoring note:** {stk_dim} is scored "n/a" when {na_condition}. When n/a,
exclude it from the total (total_possible = 8 instead of 10).

Return only this JSON:
{json_template}
"""


# ── Generation ────────────────────────────────────────────────────────────────

async def generate(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    example: dict,
    extra_body: dict | None = None,
) -> str:
    ctx  = example.get("context", "") or ""
    text = example["prompt"].strip()
    user = f"{ctx.strip()}\n\n{text}" if ctx.strip() else text

    response = await client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user},
        ],
        **({"extra_body": extra_body} if extra_body else {}),
    )
    return response.choices[0].message.content


# ── Judging ───────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$",       "", text)
    return text.strip()


def _or_model_id(model: str) -> str:
    """'openrouter/anthropic/claude-sonnet-4.6' → 'anthropic/claude-sonnet-4.6'"""
    return model[len("openrouter/"):] if model.startswith("openrouter/") else model


async def call_judge(
    client: AsyncOpenAI,
    judge_model: str,
    example: dict,
    response: str,
    rubric: dict,
) -> dict | None:
    character_name = rubric.get("character_name", "the character")
    prompt = build_judge_prompt(rubric, example, response)
    try:
        result = await client.chat.completions.create(
            model=_or_model_id(judge_model),
            max_tokens=1024,
            messages=[
                {"role": "system", "content": judge_system(character_name)},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = _strip_fences(result.choices[0].message.content)
        return json.loads(raw)
    except Exception as e:
        print(f"    judge {judge_model} failed: {e}", flush=True)
        return None


def aggregate_scores(judge_results: list[dict | None]) -> dict:
    valid = [r for r in judge_results if r is not None]
    if not valid:
        return {"panel_mean": 0.0, "panel_stderr": 0.0,
                "n_judges": 0, "judges": {}}

    def normalise(r: dict) -> float:
        total    = r.get("total", 0)
        possible = r.get("total_possible", 10)
        return round(total / possible, 4) if possible else 0.0

    normed = [normalise(r) for r in valid]
    mean_  = round(statistics.mean(normed), 4)
    std_   = round(statistics.stdev(normed), 4) if len(normed) > 1 else 0.0

    return {
        "panel_mean":   mean_,
        "panel_stderr": std_,
        "n_judges":     len(valid),
        "disagreement": std_ > 0.20,
        "judges":       {f"judge_{i}": {"raw": r, "normalised": normalise(r)}
                         for i, r in enumerate(valid)},
    }


# ── Result file ───────────────────────────────────────────────────────────────

def write_result(
    codename: str, example: dict, condition: str,
    response: str, score: dict,
    results_dir: Path | None = None,
) -> Path:
    results_dir = results_dir or (ROOT / "results")
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{codename}-{example['id']}-{condition}.md"
    path.write_text(f"""\
---
codename: {codename}
example_id: {example['id']}
label: {example['label']}
condition: {condition}
stakes: {example['stakes']}
addressee_role: {example['addressee_role']}
dimension: {example['dimension']}
panel_mean: {score['panel_mean']}
panel_stderr: {score['panel_stderr']}
n_judges: {score['n_judges']}
---

## Context

{example.get('context', 'none')}

## Prompt

{example['prompt'].strip()}

## Response

{response.strip()}

## Scores

{json.dumps(score, indent=2)}
""")
    return path


# ── Per-example worker ────────────────────────────────────────────────────────

def _result_score(
    codename: str, example: dict, condition: str,
    results_dir: Path | None = None,
) -> float | None:
    results_dir = results_dir or (ROOT / "results")
    path = results_dir / f"{codename}-{example['id']}-{condition}.md"
    if not path.exists():
        return None
    m = re.search(r'^panel_mean:\s*([\d.]+)', path.read_text(), re.MULTILINE)
    return float(m.group(1)) if m else None


async def run_example(
    sem: asyncio.Semaphore,
    gen_client: AsyncOpenAI,
    judge_client: AsyncOpenAI,
    model: str,
    judge_models: list[str],
    system_prompt: str,
    codename: str,
    condition: str,
    example: dict,
    idx: int,
    total: int,
    rubric: dict,
    extra_body: dict | None = None,
    results_dir: Path | None = None,
    character: str = "the character",
    gen_retries: int = 1,
    retry_delay: int = 30,
) -> float | None:
    existing = _result_score(codename, example, condition, results_dir)
    if existing is not None:
        print(f"  [{idx}/{total}] {example['id']}  already scored ({existing:.3f}) — skip",
              flush=True)
        return existing

    async with sem:
        t0 = time.time()
        response = None
        for attempt in range(gen_retries):
            try:
                response = await generate(gen_client, model, system_prompt,
                                          example, extra_body)
                break
            except Exception as e:
                if attempt < gen_retries - 1:
                    wait = retry_delay * (2 ** attempt)
                    print(
                        f"  [{idx}/{total}] {example['id']} GEN FAILED "
                        f"(attempt {attempt + 1}/{gen_retries}): {e} "
                        f"— retrying in {wait}s",
                        flush=True,
                    )
                    await asyncio.sleep(wait)
                else:
                    print(
                        f"  [{idx}/{total}] {example['id']} GEN FAILED "
                        f"after {gen_retries} attempt(s): {e}",
                        flush=True,
                    )
        if response is None:
            return None

        if not response:
            print(f"  [{idx}/{total}] {example['id']} GEN EMPTY — skipping", flush=True)
            return None

        judge_results = await asyncio.gather(
            *[call_judge(judge_client, jm, example, response, rubric)
              for jm in judge_models],
            return_exceptions=False,
        )

        score = aggregate_scores(list(judge_results))
        write_result(codename, example, condition, response, score, results_dir)

        elapsed = time.time() - t0
        disc = "  ⚠ disagree" if score.get("disagreement") else ""
        print(f"  [{idx}/{total}] {example['id']}  "
              f"score={score['panel_mean']:.3f}{disc}  ({elapsed:.0f}s)")
        return score["panel_mean"]


# ── Model runner ──────────────────────────────────────────────────────────────

async def run_model(
    cfg: dict,
    examples: list[dict],
    judge_models: list[str],
    api_keys: dict,
    character: str = "",
    rubric: dict | None = None,
    concurrency: int = 4,
) -> list[float]:
    print('  run_model: start', flush=True)

    codename  = cfg["codename"]
    provider  = cfg["provider"]
    model     = cfg["model"]
    soul      = cfg["soul"]
    condition = "soul" if soul else "control"

    if provider == "anthropic":
        raise ValueError(
            f"provider 'anthropic' is not supported. "
            f"Route {model!r} through openrouter instead."
        )

    # Load rubric if not supplied
    if rubric is None and character:
        rubric = load_rubric(character)
    if rubric is None:
        raise ValueError(
            "No rubric available. Pass --character or supply rubric explicitly."
        )

    # extra_body: per-model params passed straight to the request body
    raw_extra = dict(cfg.get("extra_params") or {})
    extra_body = raw_extra or None

    # Build system prompt
    stub_path    = Path(cfg["stub_path"])    if cfg.get("stub_path")    else None
    wrapper_path = Path(cfg["wrapper_path"]) if cfg.get("wrapper_path") else None
    soul_path    = Path(cfg["soul_path"])    if cfg.get("soul_path")    else None

    sys_prompt = build_system_prompt(
        soul,
        stub_path=stub_path,
        wrapper_path=wrapper_path,
        soul_doc_path=soul_path,
        character=character,
    )
    print('  run_model: prompt built', flush=True)

    results_dir = ROOT / "results" / character if character else ROOT / "results"

    # Build clients
    or_key = api_keys["openrouter"]
    if provider == "openrouter":
        gen_client = _openrouter_client(or_key)
    else:  # openai-compatible local
        base_url = cfg.get("base_url", OPENAI_BASE)
        gen_client = _local_client(api_keys.get("openai", "none"), base_url)

    judge_client = _openrouter_client(or_key)

    print('  run_model: clients ready, launching tasks', flush=True)

    gen_retries  = int(cfg.get("gen_retries",  1))
    retry_delay  = int(cfg.get("retry_delay",  30))

    sem = asyncio.Semaphore(concurrency)
    async with gen_client, judge_client:
        tasks = [
            run_example(
                sem,
                gen_client,
                judge_client,
                model,
                judge_models,
                sys_prompt,
                codename,
                condition,
                ex,
                i + 1,
                len(examples),
                rubric=rubric,
                extra_body=extra_body,
                results_dir=results_dir,
                character=character or "the character",
                gen_retries=gen_retries,
                retry_delay=retry_delay,
            )
            for i, ex in enumerate(examples)
        ]
        results = await asyncio.gather(*tasks)

    scores = [r for r in results if r is not None]
    return scores
