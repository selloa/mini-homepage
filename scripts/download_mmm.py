"""Download every file listed in the 'Download-Link (clean)' column of
mmm_episoden_links.csv into E:\\MMM\\.

- Skips rows with an empty download link.
- Skips files that have already been downloaded (by final filename).
- Names files as "<NNN>_<sanitized-episode-title>__<original-filename>" where
  <NNN> is the row index so files appear in CSV order in the folder.
- Honours Content-Disposition when the server provides one, otherwise falls
  back to the URL path basename.
- Prints progress and a final summary; never aborts on a single failure.
"""

from __future__ import annotations

import csv
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

CSV_PATH = Path(r"c:\Users\selloa\Desktop\mini-homepage\mmm_episoden_links.csv")
OUT_DIR = Path(r"E:\MMM")
LOG_PATH = OUT_DIR / "_download_log.txt"
DOWNLOAD_COL = "Download-Link (clean)"
EPISODE_COL = "episode"

CHUNK_SIZE = 1024 * 64
TIMEOUT = 60  # per HTTP request
RETRIES = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str, max_len: int = 80) -> str:
    name = INVALID_FS_CHARS.sub("_", name).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    return name[:max_len] if len(name) > max_len else name


def filename_from_response(resp: requests.Response, fallback_url: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename\*\s*=\s*(?:UTF-8\'\')?([^;]+)', cd, re.IGNORECASE)
    if not m:
        m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, re.IGNORECASE)
    if m:
        return sanitize(unquote(m.group(1).strip()))
    path = urlparse(fallback_url).path
    base = unquote(os.path.basename(path)) or "download.bin"
    return sanitize(base)


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download_one(session: requests.Session, url: str, target_dir: Path,
                 prefix: str) -> tuple[bool, str, int]:
    """Returns (ok, message, bytes_downloaded)."""
    last_err = ""
    for attempt in range(1, RETRIES + 1):
        try:
            with session.get(url, stream=True, timeout=TIMEOUT,
                             allow_redirects=True) as resp:
                resp.raise_for_status()
                base_name = filename_from_response(resp, resp.url)
                final_name = f"{prefix}__{base_name}"
                final_path = target_dir / final_name
                tmp_path = final_path.with_suffix(final_path.suffix + ".part")

                if final_path.exists() and final_path.stat().st_size > 0:
                    return True, f"SKIP (exists) -> {final_name}", 0

                total = int(resp.headers.get("Content-Length") or 0)
                got = 0
                last_print = time.monotonic()
                with open(tmp_path, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        got += len(chunk)
                        now = time.monotonic()
                        if now - last_print > 1.0:
                            if total:
                                pct = got * 100 / total
                                sys.stdout.write(
                                    f"\r    {human_size(got)} / "
                                    f"{human_size(total)} ({pct:5.1f}%)"
                                )
                            else:
                                sys.stdout.write(
                                    f"\r    {human_size(got)} downloaded"
                                )
                            sys.stdout.flush()
                            last_print = now
                sys.stdout.write("\r" + " " * 60 + "\r")
                sys.stdout.flush()
                os.replace(tmp_path, final_path)
                return True, f"OK -> {final_name}", got
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < RETRIES:
                time.sleep(2 * attempt)
        except OSError as e:
            return False, f"OS error: {e}", 0
    return False, f"FAILED after {RETRIES} attempts: {last_err}", 0


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if DOWNLOAD_COL not in (reader.fieldnames or []):
        print(f"ERROR: column {DOWNLOAD_COL!r} not in CSV. "
              f"Columns found: {reader.fieldnames}")
        return 2

    jobs: list[tuple[int, str, str]] = []
    for idx, row in enumerate(rows, start=1):
        url = (row.get(DOWNLOAD_COL) or "").strip()
        episode = (row.get(EPISODE_COL) or "").strip()
        if not url:
            continue
        if not url.lower().startswith(("http://", "https://")):
            continue
        jobs.append((idx, episode, url))

    print(f"Found {len(jobs)} URLs to download into {OUT_DIR}\n")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    ok_count = 0
    skip_count = 0
    fail_count = 0
    total_bytes = 0

    with LOG_PATH.open("a", encoding="utf-8") as log:
        log.write(f"\n===== Run started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        for n, (idx, episode, url) in enumerate(jobs, start=1):
            prefix = f"{idx:03d}_{sanitize(episode) or 'item'}"
            print(f"[{n:3d}/{len(jobs)}] row {idx:03d} | {episode[:60]}")
            print(f"    URL: {url}")
            ok, msg, got = download_one(session, url, OUT_DIR, prefix)
            print(f"    -> {msg}")
            log.write(f"row={idx} ok={ok} bytes={got} url={url} msg={msg}\n")
            log.flush()
            if ok and msg.startswith("SKIP"):
                skip_count += 1
            elif ok:
                ok_count += 1
                total_bytes += got
            else:
                fail_count += 1

    print("\n=========== SUMMARY ===========")
    print(f"  Downloaded: {ok_count}")
    print(f"  Skipped   : {skip_count}")
    print(f"  Failed    : {fail_count}")
    print(f"  Bytes     : {human_size(total_bytes)}")
    print(f"  Log file  : {LOG_PATH}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
