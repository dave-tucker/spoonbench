#!/usr/bin/env python3
"""
parse.py — Extract one character's lines from Star Trek: Discovery transcripts.

Transcript format (plain-text .md in data/):
  [Scene heading]
  SPEAKER: dialogue text
  SPEAKER [OC]: dialogue text
  SPEAKER [hologram]: dialogue text
  SPEAKER (CONT'D): dialogue text
  (stage direction on own line)

Usage:
  python parse.py <character>           sample: prints first 20 lines
  python parse.py <character> --write   writes out/<character>/lines.jsonl
"""

import re
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# ── Patterns ──────────────────────────────────────────────────────────────────

SPEAKER_RE     = re.compile(r'^([A-Z][A-Z0-9 \'\-]*)(?:\s+\[[^\]]+\])?(?:\s+\([^)]*\))?:\s*(.+)$')
SPEAKER_ALT_RE = re.compile(r'^([A-Z][A-Z0-9 \'\-]*)>\s*(.+)$')
SCENE_RE       = re.compile(r'^\[([^\]]+)\]\s*$')
INLINE_STAGE_RE = re.compile(r'\([^)]*\)')
EMBEDDED_TAG_RE = re.compile(r'\s+[A-Z][A-Z\']{2,}(?:\s+[A-Z][A-Z\']{2,})*[>:]\s+')

SKIP_ADDRESSEE = {"BOTH", "COMPUTER", "ALL"}


def titlecase_name(raw: str) -> str:
    return raw.title()


def strip_stage_dirs(text: str) -> str:
    text = INLINE_STAGE_RE.sub('', text)
    return re.sub(r'  +', ' ', text).strip()


def truncate_at_embedded_speaker(text: str) -> str:
    m = EMBEDDED_TAG_RE.search(text)
    return text[:m.start()].strip() if m else text


def parse_episode(path: Path, episode_code: str, target: str) -> list[dict]:
    results: list[dict] = []
    current_scene  = "unknown"
    last_addressee = None
    line_n         = 0

    for raw in path.read_text(encoding='utf-8').splitlines():
        raw = raw.rstrip()

        m = SCENE_RE.match(raw)
        if m:
            current_scene = m.group(1).strip()
            continue

        m = SPEAKER_RE.match(raw) or SPEAKER_ALT_RE.match(raw)
        if not m:
            continue

        speaker      = m.group(1).strip()
        dialogue_raw = truncate_at_embedded_speaker(m.group(2).strip())
        dialogue     = strip_stage_dirs(dialogue_raw)
        if not dialogue:
            continue

        if speaker == target:
            line_n += 1
            results.append({
                "line_id":   f"{episode_code}_{line_n:03d}",
                "text":      dialogue,
                "context":   current_scene,
                "addressee": last_addressee or "unknown",
            })
        elif speaker not in SKIP_ADDRESSEE:
            last_addressee = titlecase_name(speaker)

    return results


def derive_episode_code(path: Path) -> str:
    m = re.search(r's(\d+)e(\d+)', path.stem, re.IGNORECASE)
    return f"s{m.group(1)}e{m.group(2)}" if m else path.stem


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith('-'):
        print("Usage: python parse.py <character> [--write]", file=sys.stderr)
        sys.exit(1)

    character  = args[0].lower()
    write_mode = "--write" in args
    target     = character.upper()

    transcripts = sorted((ROOT / "data").glob("discovery-*.md"))
    if not transcripts:
        print("No data/discovery-*.md files found.", file=sys.stderr)
        sys.exit(1)

    all_records: list[dict] = []
    codes_seen:  list[str]  = []

    for t in transcripts:
        code    = derive_episode_code(t)
        records = parse_episode(t, code, target)
        if records:
            all_records.extend(records)
            codes_seen.append(code)
            print(f"  {t.name}: {len(records)} lines (code: {code})")
        else:
            print(f"  {t.name}: (none)")

    if not all_records:
        print(f"\nNo lines found for {target!r} — check the character name.")
        sys.exit(1)

    if write_mode:
        out_dir = ROOT / "out" / character
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "lines.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for r in all_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        texts        = [r["text"] for r in all_records]
        mean_len     = sum(len(t) for t in texts) / len(texts)
        unknown_addr = sum(1 for r in all_records if r["addressee"] == "unknown")
        unknown_ctx  = sum(1 for r in all_records if r["context"]   == "unknown")

        print(f"\n{'─'*50}")
        print(f"Wrote {len(all_records)} lines → {out}")
        print(f"Span             : {codes_seen[0]} → {codes_seen[-1]}")
        print(f"Mean line length : {mean_len:.0f} chars")
        print(f"Unknown addressee: {unknown_addr}/{len(all_records)} ({100*unknown_addr/len(all_records):.0f}%)")
        print(f"Unknown context  : {unknown_ctx}/{len(all_records)}  ({100*unknown_ctx/len(all_records):.0f}%)")
        if unknown_addr / len(all_records) > 0.50:
            print("⚠  >50% unknown addressees — review transcript structure.")
        if unknown_ctx / len(all_records) > 0.50:
            print("⚠  >50% unknown contexts — review scene heading regex.")
    else:
        print(f"\n=== SAMPLE: first 20 {target} lines ===\n")
        for r in all_records[:20]:
            print(json.dumps(r, ensure_ascii=False))
        print(f"\n(Total: {len(all_records)} — run with --write to produce out/{character}/lines.jsonl)")


if __name__ == "__main__":
    main()
