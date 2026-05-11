"""
Loest alle Download-Links aus mmm_episoden_links.csv zu klaren URLs auf
und schreibt sie in die letzte Spalte "Download-Link (clean)".
"""

import csv
import re
import sys
import time
from html import unescape
from urllib.parse import urljoin

import requests

CSV_PATH = "mmm_episoden_links.csv"
TIMEOUT = 30
HEADERS = {"User-Agent": "Mozilla/5.0 (resolve-script)"}
CLEAN_COL = "Download-Link (clean)"

session = requests.Session()
session.headers.update(HEADERS)

cache: dict[str, str] = {}


def extract_doc_download(html: str, base_url: str) -> str:
    m = re.search(r'href=["\']([^"\']*doc_download[^"\']*)["\']', html, re.IGNORECASE)
    if not m:
        return ""
    href = unescape(m.group(1))
    return urljoin(base_url, href)


def fetch(url: str) -> tuple[str, str, str]:
    """GET mit Redirects. Liefert (final_url, content_type, body_or_empty)."""
    r = session.get(url, allow_redirects=True, timeout=TIMEOUT, stream=True)
    ctype = r.headers.get("Content-Type", "").lower()
    body = ""
    if "text/html" in ctype or "text/xml" in ctype:
        body = r.text
    r.close()
    return r.url, ctype, body


def try_url(url: str) -> str:
    """Holt URL und gibt finale URL zurueck, wenn Content kein HTML ist."""
    try:
        final_url, ctype, body = fetch(url)
    except requests.RequestException as e:
        print(f"  ! request failed: {e}", file=sys.stderr)
        return ""
    if "text/html" not in ctype:
        return final_url
    doc_url = extract_doc_download(body, final_url)
    if doc_url:
        try:
            doc_final, doc_ctype, _ = fetch(doc_url)
            if "text/html" not in doc_ctype:
                return doc_final
        except requests.RequestException as e:
            print(f"  ! doc fetch failed: {e}", file=sys.stderr)
    return ""


def resolve(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if url in cache:
        return cache[url]

    print(f"-> {url}")
    final = try_url(url)

    # Fallback fuer Joomla-Artikel-Seiten ohne doc_download:
    # /xyz.html -> /xyz/file.html (Joomla liefert dort direkt die Datei aus)
    if not final and url.endswith(".html") and "/file.html" not in url:
        alt = url[: -len(".html")] + "/file.html"
        print(f"   probiere Fallback: {alt}")
        final = try_url(alt)

    if final and "doc_download" in final:
        final = ""

    cache[url] = final
    print(f"   => {final or '(nicht aufloesbar)'}")
    time.sleep(0.3)
    return final


def write_csv(path: str, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writerows(rows)


def main() -> None:
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    header = rows[0]
    dl_idx = header.index("Download-Link")
    clean_idx = header.index(CLEAN_COL)

    total = len(rows) - 1
    for i, row in enumerate(rows[1:], start=1):
        while len(row) <= clean_idx:
            row.append("")
        dl = row[dl_idx].strip()
        if not dl:
            continue
        if row[clean_idx].strip():
            continue
        label = row[1] if len(row) > 1 else ""
        print(f"[{i}/{total}] {label}")
        row[clean_idx] = resolve(dl)

        if i % 10 == 0:
            write_csv(CSV_PATH, rows)
            print(f"--- Zwischenstand gespeichert ({i}/{total}) ---")

    write_csv(CSV_PATH, rows)
    print("Fertig.")


if __name__ == "__main__":
    main()
