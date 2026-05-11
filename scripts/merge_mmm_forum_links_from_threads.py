"""Fill MMM-Forum-Link in mmm_episoden_links.csv from mmm_episoden_forum_threads.csv.

Uses only MMM-Episodenführer rows whose titel starts with 'Episode <digits>'.
For duplicate episode numbers, picks the forum thread that best matches the wiki
episode cell (text after 'Episode N:').
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THREADS = ROOT / "mmm_episoden_forum_threads.csv"
LINKS = ROOT / "mmm_episoden_links.csv"

EP_FORUM_TITLE = re.compile(r"^Episode\s+(\d+)\b", re.IGNORECASE)
EP_LINKS_CELL = re.compile(r"^Episode\s+(\d{1,3})\s*:", re.IGNORECASE)
TOPIC_RE = re.compile(r"topic=(\d+)", re.IGNORECASE)


def topic_id(url: str) -> str:
    m = TOPIC_RE.search(url or "")
    return m.group(1) if m else ""


def norm_url(url: str) -> str:
    return topic_id(url)


def hint_after_colon(episode_cell: str) -> str:
    m = re.match(r"Episode\s+\d+\s*:\s*(.+)", episode_cell.strip(), flags=re.IGNORECASE)
    return (m.group(1) if m else episode_cell).strip().lower()


def hint_tokens(hint: str) -> list[str]:
    return [t for t in re.split(r"[^\wäöüß]+", hint, flags=re.IGNORECASE) if len(t) >= 3]


def pick_url(ep: int, candidates: list[tuple[str, str]], wiki_episode: str) -> str:
    if len(candidates) == 1:
        return candidates[0][1]
    hint = hint_after_colon(wiki_episode)
    toks = hint_tokens(hint)

    def score(item: tuple[str, str]) -> tuple[int, int]:
        title, url = item
        tl = title.lower()
        s = sum(len(t) for t in toks if t in tl)
        tid = int(topic_id(url) or 0)
        return (s, tid)

    return max(candidates, key=score)[1]


def load_forum_episode_map() -> dict[int, list[tuple[str, str]]]:
    out: dict[int, list[tuple[str, str]]] = {}
    with THREADS.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("kategorie") != "MMM-Episodenführer":
                continue
            titel = row.get("titel") or ""
            m = EP_FORUM_TITLE.match(titel.strip())
            if not m:
                continue
            ep = int(m.group(1))
            url = (row.get("link") or "").strip()
            if not url:
                continue
            out.setdefault(ep, []).append((titel, url))
    return out


def main() -> int:
    forum = load_forum_episode_map()

    with LINKS.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    if "MMM-Forum-Link" not in fieldnames:
        print("Column MMM-Forum-Link missing", fieldnames)
        return 1

    filled = 0
    unchanged = 0
    mismatches: list[str] = []
    no_forum: list[int] = []

    for row in rows:
        if row.get("kategorie") != "MMM-Episodenführer":
            continue
        ep_cell = row.get("episode") or ""
        m = EP_LINKS_CELL.match(ep_cell.strip())
        if not m:
            continue
        ep = int(m.group(1))
        cand = forum.get(ep)
        if not cand:
            no_forum.append(ep)
            continue
        chosen = pick_url(ep, cand, ep_cell)
        cur = (row.get("MMM-Forum-Link") or "").strip()
        if cur:
            if norm_url(cur) and norm_url(chosen) and norm_url(cur) != norm_url(chosen):
                mismatches.append(
                    f"Episode {ep}: bestehend topic={norm_url(cur)} vs. Forum-Threads topic={norm_url(chosen)} | wiki-Zelle: {ep_cell[:70]!r}"
                )
            else:
                unchanged += 1
            continue
        row["MMM-Forum-Link"] = chosen
        filled += 1

    with LINKS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    print(f"MMM-Forum-Link neu gesetzt: {filled}")
    print(f"Bereits gesetzt (unverändert / gleiche Topic-ID): {unchanged}")
    if no_forum:
        uniq = sorted(set(no_forum))
        print(f"Kein passender 'Episode …'-Thread im Forum-Export für Episoden-Nr.: {uniq}")
    if mismatches:
        print("Abweichende bestehende Links (nicht überschrieben):")
        for line in mismatches:
            print(" ", line)
    else:
        print("Keine Abweichung zwischen bestehendem MMM-Forum-Link und gewähltem Forum-Thread.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
