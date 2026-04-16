"""
eval.py — Agent personality voice test harness.

Usage:
  # Run all models defined in models.yaml for a character:
  python eval.py --character bob
  python eval.py --character alice

  # Run a subset by codename:
  python eval.py --character bob --models haiku-control,haiku-soul

  # Use a local models file:
  python eval.py --character bob --models-file harness/models.local.yaml

  # Dry-run: print what would run without calling the API:
  python eval.py --character bob --dry-run

Results are written to:
  results/{character}/{codename}-{example_id}-{condition}.md

A summary file is written to:
  results/{character}/RESULT.md
"""

import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import yaml

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).parent.parent
HARNESS = Path(__file__).parent

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> list[dict]:
    with path.open() as f:
        return yaml.safe_load(f)


def resolve_model_string(cfg: dict) -> str:
    """Convert models.yaml entry to a display string."""
    provider = cfg["provider"]
    model    = cfg["model"]
    if provider == "openrouter":
        return f"openrouter/{model}"
    if provider == "ollama":
        return f"ollama/{model}"
    return f"{provider}/{model}"


# ── Result summary ────────────────────────────────────────────────────────────

def _parse_result_file(path: Path) -> dict | None:
    """
    Parse a result .md file. Returns a dict with frontmatter fields and
    per-dimension scores extracted from the ## Scores JSON block, or None
    on failure.
    """
    try:
        text = path.read_text()
    except Exception:
        return None

    # Extract YAML frontmatter between --- markers
    fm_match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not fm_match:
        return None
    try:
        fm = yaml.safe_load(fm_match.group(1))
    except Exception:
        return None

    # Extract ## Scores JSON block
    scores_match = re.search(r'## Scores\n\n(.*)', text, re.DOTALL)
    dim_scores: dict[str, list[float]] = {}
    if scores_match:
        try:
            score_data = json.loads(scores_match.group(1).strip())
            # Aggregate per-dimension scores across all judges
            judges = score_data.get("judges", {})
            for judge_key, judge_val in judges.items():
                raw = judge_val.get("raw", {})
                for dim_name, dim_val in raw.items():
                    if dim_name in ("total", "total_possible", "notes"):
                        continue
                    if isinstance(dim_val, dict):
                        s = dim_val.get("score")
                        if isinstance(s, (int, float)):
                            dim_scores.setdefault(dim_name, []).append(float(s))
        except Exception:
            pass

    return {
        "codename":      fm.get("codename", ""),
        "example_id":    str(fm.get("example_id", "")),
        "label":         fm.get("label", ""),
        "condition":     fm.get("condition", ""),
        "stakes":        fm.get("stakes", ""),
        "addressee_role": fm.get("addressee_role", ""),
        "dimension":     fm.get("dimension", ""),
        "panel_mean":    float(fm.get("panel_mean", 0.0)),
        "panel_stderr":  float(fm.get("panel_stderr", 0.0)),
        "n_judges":      int(fm.get("n_judges", 0)),
        "dim_scores":    dim_scores,  # {dim_name: [score, ...]}
    }


def _model_family(codename: str) -> str:
    """Strip -soul / -control suffix. bob-kimi-soul → bob-kimi"""
    return re.sub(r'-(soul|control)$', '', codename)


def _verdict(delta: float) -> str:
    if delta >= 0.20:
        return "✓ working"
    if delta >= 0.05:
        return "△ marginal"
    return "✗ no improvement"


def write_result_summary(
    character: str,
    examples: list[dict],
    rubric: dict,
    results_dir: Path,
    judge_models: list[str],
) -> None:
    """
    Read all result .md files from results_dir and write RESULT.md.
    """
    md_files = sorted(results_dir.glob("*.md"))
    # Exclude RESULT.md itself
    md_files = [p for p in md_files if p.name != "RESULT.md"]

    records = []
    for p in md_files:
        r = _parse_result_file(p)
        if r:
            records.append(r)

    if not records:
        return

    character_name = rubric.get("character_name", character)
    n_examples = len(examples)
    today = date.today().isoformat()

    # ── Group by model family ─────────────────────────────────────────────────
    family_records: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        fam = _model_family(r["codename"])
        family_records[fam][r["condition"]].append(r)

    # ── Summary table ─────────────────────────────────────────────────────────
    table_rows = []
    for fam in sorted(family_records):
        soul_recs    = family_records[fam].get("soul", [])
        control_recs = family_records[fam].get("control", [])
        if not soul_recs and not control_recs:
            continue
        soul_mean    = (sum(r["panel_mean"] for r in soul_recs) / len(soul_recs)
                        if soul_recs else None)
        control_mean = (sum(r["panel_mean"] for r in control_recs) / len(control_recs)
                        if control_recs else None)
        if soul_mean is not None and control_mean is not None:
            delta   = soul_mean - control_mean
            verdict = _verdict(delta)
            table_rows.append(
                f"| {fam} | {control_mean:.3f} | {soul_mean:.3f} "
                f"| {delta:+.3f} | {verdict} |"
            )

    # ── Per-dimension breakdown (soul condition) ──────────────────────────────
    dim_agg: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r["condition"] == "soul":
            for dim_name, scores in r["dim_scores"].items():
                dim_agg[dim_name].extend(scores)

    dim_rows = []
    for dim_name in sorted(dim_agg):
        scores = dim_agg[dim_name]
        mean_  = sum(scores) / len(scores) if scores else 0.0
        dim_rows.append(f"| {dim_name} | {mean_:.2f} |")

    # ── Low-scoring cases (panel_mean < 0.50, soul) ───────────────────────────
    low_rows = []
    for r in sorted(records, key=lambda x: x["panel_mean"]):
        if r["condition"] == "soul" and r["panel_mean"] < 0.50:
            low_rows.append(
                f"| {r['codename']} | {r['example_id']} | {r['condition']} "
                f"| {r['panel_mean']:.3f} | |"
            )

    # ── Judge disagreement (panel_stderr > 0.20) ──────────────────────────────
    disagree_rows = []
    for r in sorted(records, key=lambda x: -x["panel_stderr"]):
        if r["panel_stderr"] > 0.20:
            disagree_rows.append(
                f"| {r['codename']} | {r['example_id']} "
                f"| {r['panel_mean']:.3f} | {r['panel_stderr']:.3f} |"
            )

    # ── Conclusion (rule-based) ───────────────────────────────────────────────
    all_deltas = []
    for fam in family_records:
        soul_recs    = family_records[fam].get("soul", [])
        control_recs = family_records[fam].get("control", [])
        if soul_recs and control_recs:
            s = sum(r["panel_mean"] for r in soul_recs) / len(soul_recs)
            c = sum(r["panel_mean"] for r in control_recs) / len(control_recs)
            all_deltas.append(s - c)

    if all_deltas:
        mean_delta = sum(all_deltas) / len(all_deltas)
        n_working  = sum(1 for d in all_deltas if d >= 0.20)
        n_marginal = sum(1 for d in all_deltas if 0.05 <= d < 0.20)
        n_total    = len(all_deltas)

        stk_dim = rubric.get("stakes_conditional_dimension", "concern_before_action")
        stk_dim_scores = dim_agg.get(stk_dim, [])
        stk_dim_mean   = (sum(stk_dim_scores) / len(stk_dim_scores)
                          if stk_dim_scores else None)

        ap_scores = dim_agg.get("anti_patterns", [])
        ap_mean   = sum(ap_scores) / len(ap_scores) if ap_scores else None

        conclusion_lines = [
            f"The soul doc produced a mean Δ of {mean_delta:+.3f} across "
            f"{n_total} model families "
            f"({n_working} working, {n_marginal} marginal, "
            f"{n_total - n_working - n_marginal} no improvement)."
        ]
        if stk_dim_mean is not None:
            level = "reliably" if stk_dim_mean >= 1.4 else ("partially" if stk_dim_mean >= 0.8 else "poorly")
            conclusion_lines.append(
                f"The stakes-conditional dimension ({stk_dim}) was captured "
                f"{level} (mean {stk_dim_mean:.2f}/2.0)."
            )
        if ap_mean is not None:
            ap_verdict = "held well" if ap_mean >= 1.5 else ("mixed" if ap_mean >= 1.0 else "weak")
            conclusion_lines.append(
                f"Anti-pattern avoidance was {ap_verdict} (mean {ap_mean:.2f}/2.0)."
            )
        if mean_delta >= 0.20:
            conclusion_lines.append(
                "Overall: the soul doc is working — the majority of model families "
                "show meaningful voice uplift."
            )
        elif mean_delta >= 0.05:
            conclusion_lines.append(
                "Overall: the soul doc is producing marginal improvement. "
                "Further iteration on the soul document may increase uplift."
            )
        else:
            conclusion_lines.append(
                "Overall: the soul doc is not producing consistent improvement. "
                "Review the soul document and rubric alignment."
            )
        conclusion = "  \n".join(conclusion_lines)
    else:
        conclusion = "Insufficient data to generate a conclusion."

    # ── Assemble RESULT.md ────────────────────────────────────────────────────
    judge_lines = "\n".join(f"  · {j}" for j in judge_models)

    summary_table = (
        "| model family | control mean | soul mean | Δ | verdict |\n"
        "|---|---|---|---|---|\n" +
        "\n".join(table_rows)
    ) if table_rows else "_No paired soul/control results found._"

    dim_table = (
        "| dimension | mean score (0–2) |\n"
        "|---|---|\n" +
        "\n".join(dim_rows)
    ) if dim_rows else "_No dimension scores found._"

    low_table = (
        "| codename | id | condition | score | notes |\n"
        "|---|---|---|---|---|\n" +
        "\n".join(low_rows)
    ) if low_rows else "_No low-scoring cases._"

    disagree_table = (
        "| codename | id | panel_mean | panel_stderr |\n"
        "|---|---|---|---|\n" +
        "\n".join(disagree_rows)
    ) if disagree_rows else "_No high-disagreement cases._"

    content = f"""\
# Voice eval results — {character}

**Run date:** {today}
**Character:** {character} ({character_name})
**Examples:** {n_examples}
**Judges:**
{judge_lines}

---

## Summary table

{summary_table}

Verdict thresholds: ✓ working = Δ ≥ 0.20 · △ marginal = 0.05–0.19 · ✗ no improvement = Δ < 0.05

---

## Per-dimension breakdown (soul condition, mean across all models)

{dim_table}

---

## Low-scoring cases (panel_mean < 0.50)

{low_table}

---

## Judge disagreement

Cases where panel_stderr > 0.20 (judges disagree meaningfully):

{disagree_table}

---

## Conclusion

{conclusion}
"""
    out_path = results_dir / "RESULT.md"
    out_path.write_text(content)
    print(f"\n  ✓ RESULT.md written → {out_path}")


# ── Summary (console) ─────────────────────────────────────────────────────────

def _enrich_from_logs(all_results: list[dict],
                      results_dir: Path) -> None:
    """Back-fill scores from result .md frontmatter (panel_mean field)."""
    for entry in all_results:
        if entry["scores"]:
            continue
        codename = entry["codename"]
        scores = []
        for path in sorted(results_dir.glob(f"{codename}-*-*.md")):
            try:
                text = path.read_text()
                m = re.search(r"^panel_mean:\s*([0-9.]+)", text, re.MULTILINE)
                if m:
                    scores.append(float(m.group(1)))
            except Exception:
                pass
        entry["scores"] = scores


def print_summary(all_results: list[dict]) -> None:
    """Print a comparison table: soul vs control per model family."""
    print("\n" + "═" * 70)
    print("  RESULTS SUMMARY")
    print("═" * 70)
    print(f"  {'codename':<28} {'condition':<10} {'mean':>6}  {'n':>4}")
    print("  " + "─" * 55)

    groups: dict[str, list] = defaultdict(list)
    for r in all_results:
        base = re.sub(r'-(soul|control)$', '', r["codename"])
        groups[base].append(r)

    for base in sorted(groups):
        for r in sorted(groups[base], key=lambda x: x["codename"]):
            scores = r["scores"]
            if scores:
                mean = sum(scores) / len(scores)
                print(f"  {r['codename']:<28} {r['condition']:<10} "
                      f"{mean:>6.3f}  {len(scores):>4}")
        soul_r    = next((r for r in groups[base] if r["condition"] == "soul"),    None)
        control_r = next((r for r in groups[base] if r["condition"] == "control"), None)
        if soul_r and control_r and soul_r["scores"] and control_r["scores"]:
            soul_mean    = sum(soul_r["scores"])    / len(soul_r["scores"])
            control_mean = sum(control_r["scores"]) / len(control_r["scores"])
            delta = soul_mean - control_mean
            sign  = "+" if delta >= 0 else ""
            marker = ("  ✓ soul working" if delta >= 0.20
                      else ("  △ marginal" if delta > 0 else "  ✗ no improvement"))
            print(f"  {'  Δ soul−control':<28} {'':10} {sign}{delta:>+.3f}{marker}")
        print()

    print("═" * 70)


# ── Entry point ───────────────────────────────────────────────────────────────

DEFAULT_JUDGES = [
    "openrouter/openai/gpt-5.4",
    "openrouter/anthropic/claude-sonnet-4.6",
    "openrouter/google/gemini-2.5-flash",
]

MODEL_TIMEOUT = 360   # seconds per model before we give up


def _is_complete(codename: str, n_examples: int, results_dir: Path) -> bool:
    """True if all result files exist AND are scored (have panel_mean)."""
    existing = list(results_dir.glob(f"{codename}-*-*.md"))
    if len(existing) < n_examples:
        return False
    return all(
        re.search(r'^panel_mean:', p.read_text(), re.MULTILINE)
        for p in existing
    )


def _run_single(cfg: dict, examples: list[dict],
                judge_models: list[str], api_keys: dict,
                character: str = "",
                rubric: dict | None = None,
                concurrency: int = 4) -> list[float]:
    """Run one model via the direct asyncio runner."""
    from runner import run_model
    codename  = cfg["codename"]
    model     = cfg["model"]
    condition = "soul" if cfg["soul"] else "control"

    print(f"\n── {codename} ({model}, condition={condition}) ──")
    scores = asyncio.run(
        run_model(cfg, examples, judge_models, api_keys, character, rubric,
                  concurrency=concurrency)
    )
    mean_ = sum(scores) / len(scores) if scores else 0.0
    print(f"  Done. {len(scores)}/{len(examples)} scored.  mean={mean_:.3f}")
    return scores


def run_all(model_cfgs: list[dict], examples: list[dict],
            dry_run: bool, judge_models: list[str] = DEFAULT_JUDGES,
            api_keys: dict | None = None,
            character: str = "",
            rubric: dict | None = None,
            concurrency: int = 4) -> None:
    api_keys = api_keys or {}
    all_results = []
    n = len(examples)
    results_dir = (ROOT / "results" / character) if character else (ROOT / "results")
    results_dir.mkdir(parents=True, exist_ok=True)

    for cfg in model_cfgs:
        codename  = cfg["codename"]
        condition = "soul" if cfg["soul"] else "control"
        model_str = resolve_model_string(cfg)

        print(f"\n── {codename} ({model_str}, condition={condition}) ──")

        if dry_run:
            print(f"  [dry-run] would run {n} examples × {len(judge_models)} judges")
            continue

        if _is_complete(codename, n, results_dir):
            print(f"  Already complete ({n}/{n} result files). Skipping.")
            all_results.append({
                "codename":  codename,
                "condition": condition,
                "model":     model_str,
                "scores":    [],
            })
            continue

        scores = _run_single(cfg, examples, judge_models, api_keys,
                              character, rubric, concurrency)
        all_results.append({
            "codename":  codename,
            "condition": condition,
            "model":     model_str,
            "scores":    scores,
        })

    if not dry_run:
        _enrich_from_logs(all_results, results_dir)
        print_summary(all_results)
        if rubric is not None:
            write_result_summary(character, examples, rubric, results_dir,
                                 judge_models)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent personality eval harness")
    parser.add_argument("--character", default="",
                        help="Character name (e.g. alice, bob). Determines soul doc, "
                             "test cases, rubric, and results dir.")
    parser.add_argument("--models",  default=None,
                        help="Comma-separated codenames to run (default: all)")
    parser.add_argument("--models-file", default=None,
                        help="Path to alternate models yaml (default: harness/models.yaml)")
    parser.add_argument("--examples", default=None,
                        help="Path to override examples yaml (default: out/{character}/test.yaml)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would run without calling APIs")
    parser.add_argument("--judges", default=None,
                        help="Comma-separated judge model strings (overrides default panel)")
    parser.add_argument("--concurrency", type=int, default=4,
                        help="Max parallel examples per model (default: 4)")
    args = parser.parse_args()

    # ── Resolve character ────────────────────────────────────────────────────
    character = args.character.lower() if args.character else ""
    if not character and not args.examples:
        print(
            "Error: --character is required (e.g. --character bob) unless "
            "--examples is given.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Resolve examples path ─────────────────────────────────────────────────
    if args.examples:
        examples_path = Path(args.examples)
    elif character:
        examples_path = ROOT / "out" / character / "test.yaml"
    else:
        print("Error: cannot determine examples path.", file=sys.stderr)
        sys.exit(1)

    if not examples_path.exists():
        print(f"Error: examples file not found: {examples_path}", file=sys.stderr)
        sys.exit(1)

    # ── Validate rubric ───────────────────────────────────────────────────────
    rubric = None
    if character:
        rubric_path = ROOT / "out" / character / "judge_rubric.yaml"
        if not rubric_path.exists():
            print(f"Error: {rubric_path} not found", file=sys.stderr)
            sys.exit(1)
        rubric = yaml.safe_load(rubric_path.read_text())

    # ── Load models file ──────────────────────────────────────────────────────
    models_path = Path(args.models_file) if args.models_file else HARNESS / "models.yaml"
    if not models_path.exists():
        print(f"Error: models file not found: {models_path}", file=sys.stderr)
        sys.exit(1)

    examples   = load_yaml(examples_path)
    model_cfgs = [m for m in load_yaml(models_path)
                  if isinstance(m, dict) and "codename" in m]

    if args.models:
        wanted = set(args.models.split(","))
        model_cfgs = [m for m in model_cfgs if m["codename"] in wanted]
        if not model_cfgs:
            print(f"No models matched: {args.models}")
            sys.exit(1)

    judge_models = (
        [j.strip() for j in args.judges.split(",")]
        if args.judges
        else DEFAULT_JUDGES
    )

    print(f"Character : {character or '(none)'}")
    if character:
        soul_path = ROOT / "out" / character / "SOUL.md"
        if not soul_path.exists():
            print(f"Error: {soul_path} not found.", file=sys.stderr)
            sys.exit(1)
        print(f"Soul doc  : {soul_path}")
        print(f"Rubric    : {ROOT / 'out' / character / 'judge_rubric.yaml'}")
        print(f"Results   : {ROOT / 'results' / character}")
    print(f"Examples  : {len(examples)}  ({examples_path})")
    print(f"Models    : {len(model_cfgs)}")
    print(f"Matrix    : {len(examples) * len(model_cfgs)} total runs")
    print(f"Judges    : {len(judge_models)}")
    for j in judge_models:
        print(f"  · {j}")

    # Load .env from repo root (won't override already-set env vars)
    import os
    load_dotenv(ROOT / ".env")

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY not set. Add it to .env", file=sys.stderr)
        sys.exit(1)

    api_keys = {
        "openrouter": os.environ.get("OPENROUTER_API_KEY", ""),
        "openai":     os.environ.get("OPENAI_API_KEY", "none"),
    }

    if args._single if hasattr(args, '_single') else False:
        _run_single(model_cfgs[0], examples, judge_models, api_keys,
                    character, rubric)
    else:
        run_all(model_cfgs, examples, args.dry_run, judge_models, api_keys,
                character, rubric, concurrency=args.concurrency)


if __name__ == "__main__":
    main()
