#!/usr/bin/env python3
"""
fetch_transcripts.py — Download chakoteya Discovery transcripts and convert to .md

Each HTML page at http://chakoteya.net/STDisco17/{id}.html is converted to the
plain-text format used by discovery-s01e01.md:

  [Scene heading]

  SPEAKER: dialogue
  (stage direction)
  SPEAKER: dialogue

Usage:
  python fetch_transcripts.py            # fetch 102–115, write discovery-s01eXX.md
  python fetch_transcripts.py --dry-run  # print first page to stdout, don't write
"""

import re
import sys
import time
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

BASE_URL = "http://chakoteya.net/STDisco17/{id}.html"

# page id → (season, episode)
PAGES = {
    102: (1, 2),
    103: (1, 3),
    104: (1, 4),
    105: (1, 5),
    106: (1, 6),
    107: (1, 7),
    108: (1, 8),
    109: (1, 9),
    110: (1, 10),
    111: (1, 11),
    112: (1, 12),
    113: (1, 13),
    114: (1, 14),
    115: (1, 15),
}


def fetch_html(page_id: int) -> str:
    url = BASE_URL.format(id=page_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def lines_from_block(tag: Tag) -> list[str]:
    """
    Extract text lines from a dialogue <p> block, splitting on <br> tags.
    Each <br> is a line boundary; leading/trailing whitespace is stripped.
    """
    parts: list[str] = []
    current: list[str] = []

    for child in tag.descendants:
        if isinstance(child, NavigableString):
            # Collapse HTML-source line-wraps (\r\n or \n) to a single space
            current.append(re.sub(r"[\r\n]+", " ", str(child)))
        elif isinstance(child, Tag) and child.name == "br":
            line = re.sub(r" +", " ", "".join(current).strip())
            if line:
                parts.append(line)
            current = []

    # flush any text after the last <br>
    line = re.sub(r" +", " ", "".join(current).strip())
    if line:
        parts.append(line)

    return parts


def is_scene_heading(p: Tag) -> tuple[bool, str]:
    """Return (True, heading_text) if <p> contains a bold [Scene] heading."""
    b = p.find("b")
    if b:
        text = b.get_text(strip=True)
        if text.startswith("[") and text.endswith("]"):
            return True, text[1:-1]  # strip the outer brackets
    return False, ""


def is_footer(p: Tag) -> bool:
    """Skip the Paramount copyright paragraph."""
    text = p.get_text()
    return "Star Trek" in text and "copyright" in text.lower()


def html_to_md(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[str] = []

    for p in soup.find_all("p"):
        if is_footer(p):
            continue

        heading, heading_text = is_scene_heading(p)
        if heading:
            blocks.append(f"[{heading_text}]")
            continue

        lines = lines_from_block(p)
        if lines:
            blocks.append("\n".join(lines))

    # Join blocks with a blank line between each
    return "\n\n".join(blocks).strip() + "\n"


def main():
    dry_run = "--dry-run" in sys.argv

    for page_id, (season, episode) in PAGES.items():
        filename = f"discovery-s{season:02d}e{episode:02d}.md"
        out_dir  = Path(__file__).parent / "data"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / filename

        if not dry_run and out_path.exists():
            print(f"  {filename} already exists, skipping")
            continue

        print(f"  Fetching {page_id} → {filename} …", end=" ", flush=True)
        try:
            html = fetch_html(page_id)
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        md = html_to_md(html)

        if dry_run:
            print()
            print(md[:3000])
            print("… (dry-run, stopping after first page)")
            break

        out_path.write_text(md, encoding="utf-8")
        line_count = md.count("\n")
        print(f"done ({line_count} lines)")

        time.sleep(1)   # be polite to the server


if __name__ == "__main__":
    main()
