#!/usr/bin/env python3
"""
tag.py — Tag one character's dialogue lines with linguistic and behavioural features.

Uses claude-haiku-4-5 via OpenRouter (OpenAI-compatible, forced tool-use).
Reads  : out/<character>/lines.jsonl
Writes : out/<character>/tagged.jsonl   (full corpus, resumable)
         out/<character>/pilot.jsonl    (50-line sample, overwritten each run)

Usage:
  python tag.py <character>             pilot → report, then stop
  python tag.py <character> --pilot     pilot only (no prompt to continue)
  python tag.py <character> --full      full corpus (skips already-tagged lines)

API key: OPENROUTER_API_KEY env var (or in .env at repo root).
"""

import json
import os
import sys
import time
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).parent

# ── Config ────────────────────────────────────────────────────────────────────

MODEL       = "anthropic/claude-haiku-4-5"
CONCURRENCY = 5
MAX_RETRIES = 4
PILOT_N     = 50

# ── API client ────────────────────────────────────────────────────────────────

def make_client() -> OpenAI:
    load_dotenv(ROOT / ".env", override=False)
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("Error: OPENROUTER_API_KEY not set. Add it to .env", file=sys.stderr)
        sys.exit(1)
    return OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/mariozechner/agent-personality",
            "X-Title": "agent-personality",
        },
    )


# ── Tool schema (OpenAI format) ───────────────────────────────────────────────

TAG_TOOL = {
    "type": "function",
    "function": {
        "name": "tag_line",
        "description": "Tag a single dialogue line with linguistic and behavioural features.",
        "parameters": {
            "type": "object",
            "required": [
                "relationship", "scene_stakes", "word_count",
                "contractions_used", "contractions_possible", "formal_address_used",
                "hedge_words", "sentence_structure", "clause_complexity",
                "vocabulary_register", "emotional_register", "threat_response",
                "deference_marker", "self_reference",
            ],
            "properties": {
                "relationship": {
                    "type": "string",
                    "enum": ["superior", "peer", "subordinate", "unknown"],
                    "description": (
                        "Relationship to the addressee from the speaker's perspective. "
                        "Determined by rank markers in the context/dialogue only — "
                        "do not use prior knowledge. 'superior' = addressee outranks speaker."
                    ),
                },
                "scene_stakes": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "crisis", "unknown"],
                    "description": "Inferred urgency or danger level from the context field.",
                },
                "word_count": {
                    "type": "integer",
                    "description": "Number of whitespace-delimited words in text.",
                },
                "contractions_used": {
                    "type": "boolean",
                    "description": "True iff the text contains at least one contraction (don't, I'm, we'll, it's, etc.).",
                },
                "contractions_possible": {
                    "type": "boolean",
                    "description": "True iff any non-contracted form in the text could be contracted without changing meaning.",
                },
                "formal_address_used": {
                    "type": "boolean",
                    "description": "True iff the line directly addresses someone by rank, rank+name, or honorific. Third-person references don't count.",
                },
                "hedge_words": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Epistemic or intensity modifiers: 'perhaps', 'I think', 'kind of', 'er', 'I mean', etc. Multi-word phrases OK.",
                },
                "sentence_structure": {
                    "type": "string",
                    "enum": ["declarative", "interrogative", "imperative", "exclamatory"],
                    "description": (
                        "Dominant sentence TYPE in the line. Use ONLY these four values. "
                        "'declarative' = makes a statement (even if structurally complex). "
                        "'interrogative' = asks a question. "
                        "'imperative' = command or request. "
                        "'exclamatory' = strong emotion (often ends with !). "
                        "Do NOT use 'complex', 'compound', 'conditional', or 'mixed' — those belong in clause_complexity."
                    ),
                },
                "clause_complexity": {
                    "type": "string",
                    "enum": ["simple", "compound", "complex"],
                },
                "vocabulary_register": {
                    "type": "string",
                    "enum": ["colloquial", "neutral", "elevated", "technical"],
                },
                "emotional_register": {
                    "type": "string",
                    "enum": ["neutral", "concerned", "resolute", "curious", "distressed", "warm", "unknown", "other"],
                },
                "threat_response": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["ignore", "register_concern", "flee_advocacy", "resolute_action", "n/a", "unknown"],
                    },
                    "description": (
                        "How the speaker responds to a threat. Multiple values allowed. "
                        "Use ['n/a'] if no threat is present in the scene context."
                    ),
                },
                "deference_marker": {
                    "type": "string",
                    "enum": ["present", "absent", "unknown"],
                    "description": "'present' if the line contains deferential language.",
                },
                "self_reference": {
                    "type": "string",
                    "enum": ["absent", "first_person", "species_reference"],
                    "description": (
                        "'species_reference' if the line references the speaker's species or group. "
                        "'first_person' for routine I/me/my. 'absent' if neither."
                    ),
                },
            },
        },
    },
}

VALID_SENTENCE_STRUCTURE = {"declarative", "interrogative", "imperative", "exclamatory"}


def normalise_tags(tags: dict) -> dict:
    ss = tags.get("sentence_structure", "declarative")
    if ss not in VALID_SENTENCE_STRUCTURE:
        tags = {**tags, "sentence_structure": "declarative"}
    return tags


# ── Tagging ───────────────────────────────────────────────────────────────────

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


def tag_one_line(client: OpenAI, record: dict, character: str, attempt: int = 0) -> dict:
    user_msg = (
        f"line_id: {record['line_id']}\n"
        f"text: \"{record['text']}\"\n"
        f"scene context: {record['context']}\n"
        f"addressee: {record['addressee']}"
    )
    system = (
        f"You are extracting linguistic and behavioural features from dialogue spoken by "
        f"a single character ({character}) for use in an LLM persona evaluation harness.\n\n"
        "Rules:\n"
        "1. Be mechanical on linguistic features. contractions_used is true iff the line contains a contraction.\n"
        "2. Be conservative on behavioural features. Use 'unknown' when ambiguous.\n"
        "3. Do not draw on prior knowledge of the character or source material. Score only what is in the text.\n"
        "4. sentence_structure: use declarative/interrogative/imperative/exclamatory ONLY — never 'complex' or 'compound'.\n"
        "5. threat_response accepts multiple values. Use all that apply. Use ['n/a'] when no threat is present."
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_msg},
            ],
            tools=[TAG_TOOL],
            tool_choice={"type": "function", "function": {"name": "tag_line"}},
        )
        args = response.choices[0].message.tool_calls[0].function.arguments
        tags = json.loads(args)
        return {**record, **normalise_tags(tags)}

    except Exception as e:
        if attempt < MAX_RETRIES:
            wait = 2 ** attempt
            log(f"  error on {record['line_id']} ({e}), retry in {wait}s …")
            time.sleep(wait)
            return tag_one_line(client, record, character, attempt + 1)
        raise


def run_batch(client: OpenAI, records: list[dict], out_path: Path,
              character: str, concurrency: int = CONCURRENCY) -> list[dict]:
    existing: dict[str, dict] = {}
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                existing[r["line_id"]] = r

    todo = [r for r in records if r["line_id"] not in existing]
    if not todo:
        log(f"  All {len(records)} records already tagged in {out_path}.")
        return list(existing.values())
    if existing:
        log(f"  Resuming: {len(existing)} done, {len(todo)} remaining.")

    results = list(existing.values())
    done, total = 0, len(todo)

    with out_path.open("a", encoding="utf-8") as f:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(tag_one_line, client, r, character): r for r in todo}
            for fut in as_completed(futures):
                rec = futures[fut]
                try:
                    tagged = fut.result()
                    f.write(json.dumps(tagged, ensure_ascii=False) + "\n")
                    f.flush()
                    results.append(tagged)
                    done += 1
                    log(f"  [{done}/{total}] {rec['line_id']} ✓")
                except Exception as e:
                    log(f"  [{done}/{total}] {rec['line_id']} FAILED: {e}")

    return results


# ── Pilot sampling ────────────────────────────────────────────────────────────

def pilot_sample(records: list[dict], n: int = PILOT_N) -> list[dict]:
    sorted_recs = sorted(records, key=lambda r: r["line_id"])
    step = max(1, len(sorted_recs) // n)
    return sorted_recs[::step][:n]


# ── Sanity report ─────────────────────────────────────────────────────────────

def pct(count: int, total: int) -> str:
    return f"{100 * count / total:.0f}%"


def dist_str(counter: Counter, total: int) -> str:
    return "  " + "\n  ".join(
        f"{val:<22} {cnt:>4}  ({pct(cnt, total)})"
        for val, cnt in counter.most_common()
    )


def sanity_report(tagged: list[dict], character: str) -> None:
    n  = len(tagged)
    wc = [r.get("word_count", len(r["text"].split())) for r in tagged]

    print("\n" + "═" * 58)
    print(f"  {character.upper()} PILOT SANITY REPORT  ({n} lines)")
    print("═" * 58)

    print(f"\n  word_count")
    print(f"  mean={sum(wc)/n:.1f}  min={min(wc)}  max={max(wc)}")

    for field in ("contractions_used", "contractions_possible", "formal_address_used"):
        true_n = sum(1 for r in tagged if r.get(field) is True)
        print(f"\n  {field}")
        print(f"  True: {true_n}/{n} ({pct(true_n, n)})")

    for field in ("vocabulary_register", "emotional_register", "scene_stakes",
                  "relationship", "sentence_structure", "clause_complexity",
                  "deference_marker", "self_reference"):
        c = Counter(r.get(field, "missing") for r in tagged)
        print(f"\n  {field}")
        print(dist_str(c, n))

    threat_values: list[str] = []
    for r in tagged:
        val = r.get("threat_response", ["missing"])
        threat_values.extend(val if isinstance(val, list) else [val])
    print(f"\n  threat_response  (multi-select; {len(threat_values)} tags on {n} lines)")
    print(dist_str(Counter(threat_values), len(threat_values)))

    all_hedges: list[str] = []
    for r in tagged:
        all_hedges.extend(r.get("hedge_words", []))
    hedge_counter = Counter(h.lower() for h in all_hedges)
    print(f"\n  hedge_words  (top 15)")
    for hw, cnt in hedge_counter.most_common(15):
        print(f"  {hw:<28} {cnt}")

    print("\n  ── RED FLAGS ──────────────────────────────────────")
    flags: list[str] = []

    er_top_val, er_top_cnt = Counter(r.get("emotional_register") for r in tagged).most_common(1)[0]
    if er_top_cnt / n > 0.70:
        flags.append(f"  ⚠  emotional_register '{er_top_val}' = {pct(er_top_cnt, n)} — model may be flattening.")

    ss_bad = [r for r in tagged if r.get("sentence_structure") not in VALID_SENTENCE_STRUCTURE]
    if ss_bad:
        flags.append(f"  ⚠  {len(ss_bad)} sentence_structure values outside schema — normalised to 'declarative'.")

    unk_stakes = sum(1 for r in tagged if r.get("scene_stakes") == "unknown")
    if unk_stakes / n > 0.50:
        flags.append(f"  ⚠  scene_stakes 'unknown' = {pct(unk_stakes, n)} — context fields may not be carrying signal.")

    if flags:
        for f in flags:
            print(f)
    else:
        print("  ✓  No red flags detected.")

    print("═" * 58 + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith('-'):
        print("Usage: python tag.py <character> [--pilot|--full]", file=sys.stderr)
        sys.exit(1)

    character  = args[0].lower()
    pilot_mode = "--pilot" in args
    full_mode  = "--full"  in args

    out_dir = ROOT / "out" / character
    if not out_dir.exists():
        print(f"Error: {out_dir} does not exist. Run parse.py first.", file=sys.stderr)
        sys.exit(1)

    input_file  = out_dir / "lines.jsonl"
    pilot_file  = out_dir / "pilot.jsonl"
    output_file = out_dir / "tagged.jsonl"

    if not input_file.exists():
        print(f"Error: {input_file} not found. Run: python parse.py {character} --write", file=sys.stderr)
        sys.exit(1)

    corpus = [json.loads(l) for l in input_file.read_text().splitlines() if l.strip()]
    client = make_client()

    if full_mode:
        print(f"Running full corpus ({len(corpus)} lines) → {output_file}", file=sys.stderr)
        run_batch(client, corpus, output_file, character)
        print(f"\nDone. Output: {output_file}", file=sys.stderr)
        return

    # Pilot
    sample = pilot_sample(corpus)
    print(f"Running pilot ({len(sample)} lines) → {pilot_file}", file=sys.stderr)
    # Clear previous pilot so we always get fresh tags
    if pilot_file.exists():
        pilot_file.unlink()
    tagged = run_batch(client, sample, pilot_file, character, concurrency=CONCURRENCY)
    tagged.sort(key=lambda r: r["line_id"])

    sanity_report(tagged, character)

    if not pilot_mode:
        print(
            f"Pilot complete. Review the report above, then run:\n"
            f"  python tag.py {character} --full\n"
            f"to tag all {len(corpus)} lines → {output_file}"
        )


if __name__ == "__main__":
    main()
