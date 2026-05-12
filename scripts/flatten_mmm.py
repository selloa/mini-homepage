"""Flatten 'lonely subdirectory' wrappers under E:\\MMM\\extracted\\.

For every episode folder, while it contains exactly one entry and that
entry is a directory, move the contents of that single subdirectory up
one level and remove the now-empty wrapper.

This handles cases like:
    001_Episode 1__mmm01/MMM/<game files>
        -> 001_Episode 1__mmm01/<game files>
and even deeper nestings like A/B/C/<files> if every level has just one
sub-folder.

Safety:
- Never crosses out of E:\\MMM\\extracted\\.
- If a name collision would occur during the move (shouldn't happen for
  a true single-child wrapper), stops flattening that folder and logs it.
- Idempotent: re-running does nothing if all folders are already flat.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(r"E:\MMM\extracted")
LOG_PATH = Path(r"E:\MMM") / "_flatten_log.txt"
MAX_LEVELS = 10  # safety cap


def flatten_one(episode_dir: Path, log) -> tuple[int, str]:
    """Returns (levels_flattened, status)."""
    levels = 0
    for _ in range(MAX_LEVELS):
        try:
            entries = list(episode_dir.iterdir())
        except OSError as e:
            return levels, f"ERROR listing: {e}"
        if len(entries) != 1 or not entries[0].is_dir():
            return levels, "OK"
        wrapper = entries[0]
        for child in list(wrapper.iterdir()):
            target = episode_dir / child.name
            if target.exists():
                msg = (f"COLLISION: {child.name!r} already exists in "
                       f"{episode_dir.name}; stopping flatten here")
                log.write(msg + "\n")
                return levels, msg
            shutil.move(str(child), str(target))
        try:
            wrapper.rmdir()
        except OSError as e:
            log.write(f"WARN could not remove wrapper {wrapper}: {e}\n")
            return levels, f"WARN: {e}"
        levels += 1
    return levels, f"STOP at MAX_LEVELS={MAX_LEVELS}"


def main() -> int:
    if not ROOT.exists():
        print(f"ERROR: {ROOT} does not exist")
        return 2

    episode_dirs = sorted(p for p in ROOT.iterdir() if p.is_dir())
    print(f"Scanning {len(episode_dirs)} extracted folders under {ROOT}\n")

    changed = unchanged = warned = 0
    total_levels = 0

    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(f"\n===== Run started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        for i, episode in enumerate(episode_dirs, start=1):
            levels, status = flatten_one(episode, log)
            if levels > 0:
                print(f"[{i:3d}/{len(episode_dirs)}] FLAT {levels}x  "
                      f"{episode.name}  ({status})")
                log.write(f"FLAT {levels}x {episode.name} :: {status}\n")
                changed += 1
                total_levels += levels
            else:
                if status != "OK":
                    print(f"[{i:3d}/{len(episode_dirs)}] WARN  "
                          f"{episode.name}: {status}")
                    log.write(f"WARN {episode.name} :: {status}\n")
                    warned += 1
                else:
                    unchanged += 1
            log.flush()

    print("\n=========== SUMMARY ===========")
    print(f"  Folders scanned   : {len(episode_dirs)}")
    print(f"  Already flat      : {unchanged}")
    print(f"  Flattened         : {changed} (total wrapper layers removed: {total_levels})")
    print(f"  Warnings          : {warned}")
    print(f"  Log               : {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
