"""Export thread titel + link from MMM forum boards: Episoden (6), Mini (21), Specials (2), Trash (13).

- board=6: Kategorie \"MMM-Episodenführer\" (Titel ab „Episode NN …“ nach Episodennummer sortiert)
- board=21: Kategorie \"Mini Episoden\"
- board=2 (Seiten .0, .25, .50): Kategorie \"Specials\"
- board=13 (Seiten .0, .25, .50): Kategorie \"Trash Episoden\"
"""
from __future__ import annotations

import csv
import re
import sys
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE = "https://www.maniac-mansion-mania.de/forum/index.php"
USER_AGENT = "MMM-forum-threads-export/1.0 (+local mini-homepage script)"
KATEGORIE_EPISODEN = "MMM-Episodenführer"
KATEGORIE_MINI = "Mini Episoden"
KATEGORIE_SPECIALS = "Specials"
KATEGORIE_TRASH = "Trash Episoden"

HTML_TOPIC_RE = re.compile(
    r'<a[^>]+href="([^"]*topic=(\d+)\.0[^"]*)"[^>]*>([^<]{1,500})</a>',
    re.IGNORECASE,
)


def is_pagination_or_noise(title: str) -> bool:
    t = unescape(title.strip())
    if not t or t == "Letzter Beitrag":
        return True
    if re.fullmatch(r"\d+", t):
        return True
    return False


def canonical_url(topic_id: str) -> str:
    return f"{BASE}?topic={topic_id}.0"


def extract_topics_from_board_html(html: str) -> list[tuple[str, str]]:
    """Ordered (title, canonical_url), deduped within this page by topic id."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for m in HTML_TOPIC_RE.finditer(html):
        href, tid, title_raw = m.group(1), m.group(2), m.group(3)
        if "action=profile" in href:
            continue
        if is_pagination_or_noise(title_raw):
            continue
        if tid in seen:
            continue
        seen.add(tid)
        title = unescape(title_raw.strip())
        out.append((title, canonical_url(tid)))
    return out


EPISODE_LEADING_NUM = re.compile(r"^Episode\s+(\d+)")


def sort_episodenführer_rows(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Nicht-Episode-Zeilen zuerst (Forum-Reihenfolge), dann Titel mit Episode NN nach Nummer."""
    with_order: list[tuple[int, int, str, str]] = []
    for i, (title, url) in enumerate(items):
        m = EPISODE_LEADING_NUM.match(title)
        if m:
            with_order.append((1, int(m.group(1)), i, title, url))
        else:
            with_order.append((0, 0, i, title, url))
    with_order.sort(key=lambda x: (x[0], x[1], x[2]))
    return [(t, u) for _, _, _, t, u in with_order]


def fetch_board_page(board_id: int, start: int) -> str:
    url = f"{BASE}?board={board_id}.{start}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45) as resp:
        enc = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(enc, errors="replace")


def topic_id_from_url(url: str) -> str:
    return url.rsplit("topic=", 1)[-1].split(".", 1)[0]


def _episode_display_num(n: int) -> str:
    return f"{n:02d}" if n < 100 else str(n)


def _strip_trailing_bracket_paren(rest: str) -> tuple[str, list[str]]:
    """Pull trailing [...] / (...) off rest; return (core, segments in order left-to-right)."""
    bits: list[str] = []
    s = rest.strip()
    while True:
        m = re.search(r"\s+(\[[^\]]+\])\s*$", s)
        if m:
            bits.insert(0, m.group(1).strip())
            s = s[: m.start()].rstrip()
            continue
        m = re.search(r"\s+(\([^)]{0,600}\))\s*$", s)
        if m:
            bits.insert(0, m.group(1).strip())
            s = s[: m.start()].rstrip()
            continue
        break
    return s.strip(), bits


def _suffix_to_extra_segment(s: str) -> str:
    s = s.strip()
    if s.startswith("[") and s.endswith("]"):
        return s
    if s.startswith("(") and s.endswith(")"):
        return f"[{s[1:-1].strip()}]"
    return f"[{s}]"


def _split_inline_version_suffix(core: str) -> tuple[str, list[str]]:
    """If core is 'Title - Version...' / 'Title - now ...', peel suffix into extra segments."""
    m = re.search(
        r"^(.+?)\s+-\s+((?:now\s|Version|v\d|V[\d.]).+)$",
        core,
        flags=re.IGNORECASE,
    )
    if not m:
        return core, []
    left, right = m.group(1).strip(), m.group(2).strip()
    if len(right) > 120:
        return core, []
    return left, [_suffix_to_extra_segment(right)]


def format_episodenführer_episode_title(title: str) -> str:
    """Nur Titel, die mit 'Episode' beginnen: Episode NN - TITEL - [extras] …"""
    if not title.startswith("Episode"):
        return title
    t = title.strip()
    t = re.sub(r"^Episode\s+9\s*\u00b2\s*", "Episode 92 ", t, flags=re.IGNORECASE)

    body_patterns = (
        r"^Episode\s*:\s*(\d{1,3})\s*-\s*(.*)$",
        r"^Episode\s*№\s*(\d{1,3})\s*-\s*(.*)$",
        r"^Episode\s*(\d{1,3})\s*:\s*(.*)$",
        r"^Episode\s*(\d{1,3})\s*-\s*(.*)$",
        r"^Episode\s*(\d{1,3})-\s*(.*)$",
        r"^Episode\s*(\d{1,3})\s+(.*)$",
    )
    num: int | None = None
    rest = ""
    for pat in body_patterns:
        m = re.match(pat, t, flags=re.IGNORECASE)
        if m:
            num = int(m.group(1))
            rest = m.group(2).strip()
            break
    if num is None:
        return title

    if re.fullmatch(r"\([^)]*\)", rest):
        inner = rest[1:-1].strip()
        nn = _episode_display_num(num)
        return f"Episode {nn} - {inner}"

    core, trail_bits = _strip_trailing_bracket_paren(rest)
    core2, ver_bits = _split_inline_version_suffix(core)
    extra_segments = ver_bits + [_suffix_to_extra_segment(x) for x in trail_bits]

    nn = _episode_display_num(num)
    out = f"Episode {nn} - {core2}"
    for seg in extra_segments:
        out += f" - {seg}"
    return out


def main() -> int:
    rows: list[tuple[str, str, str]] = []
    global_seen: set[str] = set()

    def append_batch(kategorie: str, batch: list[tuple[str, str]]) -> int:
        added = 0
        for title, url in batch:
            tid = topic_id_from_url(url)
            if tid in global_seen:
                continue
            global_seen.add(tid)
            rows.append((kategorie, title, url))
            added += 1
        return added

    episoden_acc: list[tuple[str, str]] = []
    for off in (0, 25, 50, 75, 100):
        try:
            html = fetch_board_page(6, off)
        except URLError as e:
            print(f"Error fetching board=6.{off}: {e}", file=sys.stderr)
            return 1
        batch = extract_topics_from_board_html(html)
        batch = [(format_episodenführer_episode_title(t), u) for t, u in batch]
        for title, url in batch:
            tid = topic_id_from_url(url)
            if tid in global_seen:
                continue
            global_seen.add(tid)
            episoden_acc.append((title, url))
    for title, url in sort_episodenführer_rows(episoden_acc):
        rows.append((KATEGORIE_EPISODEN, title, url))

    off = 0
    while off < 500:
        try:
            html = fetch_board_page(21, off)
        except URLError as e:
            print(f"Error fetching board=21.{off}: {e}", file=sys.stderr)
            return 1
        batch = extract_topics_from_board_html(html)
        if not batch:
            break
        if append_batch(KATEGORIE_MINI, batch) == 0:
            break
        off += 25

    for off in (0, 25, 50):
        try:
            html = fetch_board_page(2, off)
        except URLError as e:
            print(f"Error fetching board=2.{off}: {e}", file=sys.stderr)
            return 1
        append_batch(KATEGORIE_SPECIALS, extract_topics_from_board_html(html))

    for off in (0, 25, 50):
        try:
            html = fetch_board_page(13, off)
        except URLError as e:
            print(f"Error fetching board=13.{off}: {e}", file=sys.stderr)
            return 1
        append_batch(KATEGORIE_TRASH, extract_topics_from_board_html(html))

    out_path = Path(__file__).resolve().parent.parent / "mmm_episoden_forum_threads.csv"
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kategorie", "titel", "link"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
