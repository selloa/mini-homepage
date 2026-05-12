"""Extract every archive in E:\\MMM into E:\\MMM\\extracted\\<basename>\\.

Uses 7-Zip (7z.exe) which can handle .zip, .rar, .7z, and most
self-extracting .exe archives.
- Skips folders that already contain extracted files.
- Logs every action to E:\\MMM\\_extract_log.txt.
- Continues on error and prints a final summary.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
SRC_DIR = Path(r"E:\MMM")
OUT_DIR = SRC_DIR / "extracted"
LOG_PATH = SRC_DIR / "_extract_log.txt"
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".exe"}


def folder_has_content(folder: Path) -> bool:
    if not folder.exists():
        return False
    try:
        return any(folder.iterdir())
    except OSError:
        return False


def extract(archive: Path, target: Path) -> tuple[bool, str]:
    target.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(SEVEN_ZIP), "x", str(archive),
        f"-o{target}", "-y", "-bso0", "-bsp0", "-bse1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, "timeout after 600s"
    if proc.returncode == 0:
        return True, "OK"
    err = (proc.stderr or proc.stdout or "").strip().splitlines()
    msg = err[-1] if err else f"exit code {proc.returncode}"
    return False, f"rc={proc.returncode}: {msg[:200]}"


def main() -> int:
    if not SEVEN_ZIP.exists():
        print(f"ERROR: 7z.exe not found at {SEVEN_ZIP}")
        return 2
    if not SRC_DIR.exists():
        print(f"ERROR: source dir {SRC_DIR} does not exist")
        return 2

    OUT_DIR.mkdir(exist_ok=True)

    archives = sorted(
        p for p in SRC_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in ARCHIVE_EXTS
    )
    print(f"Found {len(archives)} archives to extract under {SRC_DIR}\n")

    ok = skipped = failed = 0
    failures: list[tuple[str, str]] = []

    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(f"\n===== Run started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        for i, archive in enumerate(archives, start=1):
            target = OUT_DIR / archive.stem
            print(f"[{i:3d}/{len(archives)}] {archive.name}")
            if folder_has_content(target):
                print(f"    SKIP (already extracted) -> {target.name}")
                log.write(f"SKIP {archive.name}\n")
                skipped += 1
                continue
            started = time.monotonic()
            success, msg = extract(archive, target)
            took = time.monotonic() - started
            if success:
                print(f"    OK ({took:.1f}s) -> {target.name}")
                log.write(f"OK   {archive.name} ({took:.1f}s)\n")
                ok += 1
            else:
                print(f"    FAIL ({took:.1f}s): {msg}")
                log.write(f"FAIL {archive.name} :: {msg}\n")
                failed += 1
                failures.append((archive.name, msg))
            log.flush()

    print("\n=========== SUMMARY ===========")
    print(f"  Extracted : {ok}")
    print(f"  Skipped   : {skipped}")
    print(f"  Failed    : {failed}")
    print(f"  Output    : {OUT_DIR}")
    print(f"  Log file  : {LOG_PATH}")
    if failures:
        print("\nFailures:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
