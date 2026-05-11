"""Build MMM forum BBCode from mmm_episoden_links.csv.

Am Anfang steht immer der Block „MMM-Wiki“ mit Link zur Episoden-Übersicht.

Danach eine einzige Tabelle für ALLE Kategorien, damit die Spalten
forum/wiki/at über alle Kategorien hinweg an derselben Position stehen.

Hinweis zum Forum-BBCode: `[td]` versteht keine Attribute (kein colspan,
kein width). Deshalb:
  - Kategorienzeilen: erste Zelle mit [b]Kategorie[/b], die anderen leer.
  - Abstand zwischen Titel und forum/wiki/at: nicht via width, sondern via
    Non-breaking Spaces (U+00A0) hinter dem Episodentitel.

  [table]
  [tr][td][b]Kategorie[/b][/td][td][/td][td][/td][td][/td][/tr]
  [tr][td]Episode 1: … …[/td][td][url=…]forum[/url][/td][td][url=…]wiki[/url][/td][td][url=…]at[/url][/td][/tr]
  ...
  [/table]

- Episode: immer Klartext, nie verlinkt.
- „forum“: MMM-Forum-Link. „wiki“: wiki_url. „at“: AT-Forum-Link (neu).
  Nur verlinkt, wenn die jeweilige URL in der CSV gesetzt ist; sonst nur das Wort.
- AT-Forum-Link (alt) wird nie verwendet.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import OrderedDict
from pathlib import Path

COL_KAT = "kategorie"
COL_EP = "episode"
COL_AT_NEU = "AT-Forum-Link (neu)"
COL_MMM = "MMM-Forum-Link"
COL_WIKI = "wiki_url"

WIKI_LEAD = """[b]MMM-Wiki[/b]
[list]
[li][url=http://wiki.maniac-mansion-mania.de/wiki/Episoden]Episoden-Übersicht im MMM-Wiki[/url][/li]
[/list]"""


def bbcode_escape_label(s: str) -> str:
    return s.replace("]", "］")


NBSP = "\u00A0"
TITLE_LEADING_NBSP = 4   # Einrückung der Episodentitel innerhalb einer Kategorie
TITLE_TRAILING_NBSP = 10  # Abstand nach dem Episodentitel bis zur forum-Spalte
BULLET = "•"  # Bullet vor jedem Episodentitel (U+2022)

# Tabelle hat 6 Spalten: Titel | forum | "|" | wiki | "|" | at
N_COLS = 6


def row_to_tr(episode: str, at_neu: str, mmm: str, wiki: str) -> str:
    title = bbcode_escape_label((episode or "").strip())
    at = (at_neu or "").strip()
    m = (mmm or "").strip()
    w = (wiki or "").strip()

    forum = f"[url={m}][i]forum[/i][/url]" if m else "[i]forum[/i]"
    wiki_word = f"[url={w}][i]wiki[/i][/url]" if w else "[i]wiki[/i]"
    at_word = f"[url={at}][i]at[/i][/url]" if at else "[i]at[/i]"

    title_padded = (
        NBSP * TITLE_LEADING_NBSP
        + f"{BULLET}{NBSP}{title}"
        + NBSP * TITLE_TRAILING_NBSP
    )

    return (
        f"[tr][td]{title_padded}[/td]"
        f"[td]{forum}[/td]"
        f"[td]|[/td]"
        f"[td]{wiki_word}[/td]"
        f"[td]|[/td]"
        f"[td]{at_word}[/td][/tr]"
    )


def empty_tr() -> str:
    return "[tr]" + f"[td]{NBSP}[/td]" * N_COLS + "[/tr]"


def category_tr(kat: str) -> str:
    return f"[tr][td][b]{kat}[/b][/td]" + "[td][/td]" * (N_COLS - 1) + "[/tr]"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return [dict(row) for row in r]


def build_forumcode(rows: list[dict[str, str]]) -> str:
    by_cat: OrderedDict[str, list[str]] = OrderedDict()
    for row in rows:
        kat = (row.get(COL_KAT) or "").strip()
        ep = (row.get(COL_EP) or "").strip()
        if not kat or not ep:
            continue
        tr = row_to_tr(
            ep,
            row.get(COL_AT_NEU) or "",
            row.get(COL_MMM) or "",
            row.get(COL_WIKI) or "",
        )
        by_cat.setdefault(kat, []).append(tr)

    if not by_cat:
        return f"{WIKI_LEAD}\n"

    rows: list[str] = []
    first = True
    for kat, trs in by_cat.items():
        if not trs:
            continue
        if not first:
            rows.append(empty_tr())
        rows.append(category_tr(kat))
        rows.extend(trs)
        first = False
    table = "[table]\n" + "\n".join(rows) + "\n[/table]"
    return f"{WIKI_LEAD}\n\n{table}\n"


def default_csv_path() -> Path:
    return Path(__file__).resolve().parent.parent / "mmm_episoden_links.csv"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=None,
        help=f"Input CSV (default: {default_csv_path()})",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write forum code to this file instead of stdout",
    )
    args = p.parse_args()
    csv_path = args.csv_path or default_csv_path()
    if not csv_path.is_file():
        print(f"Not found: {csv_path}", file=sys.stderr)
        return 1
    text = build_forumcode(load_rows(csv_path))
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
