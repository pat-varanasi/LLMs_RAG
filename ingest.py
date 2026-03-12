import re
import time
from datetime import datetime, timezone
from typing import List, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from db import init_db, upsert_page, clear_chunks_for_url, insert_chunks

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def normalize_ws(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s

def extract_title_and_text(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")

    # Remove junk
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.text:
        title = normalize_ws(soup.title.text)

    # Prefer main content if present
    main = soup.find("main")
    container = main if main else soup.body if soup.body else soup

    text = normalize_ws(container.get_text(" "))
    return title, text

def chunk_text(text: str, max_chars: int = 1100, overlap: int = 120) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk = text[start:end]
        # Try not to cut mid-sentence
        if end < len(text):
            cut = chunk.rfind(". ")
            if cut > 300:
                end = start + cut + 1
                chunk = text[start:end]
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        start = max(0, end - overlap)
        if end == len(text):
            break
    return chunks

def is_probably_pdf(url: str, content_type: str) -> bool:
    if url.lower().endswith(".pdf"):
        return True
    return "application/pdf" in (content_type or "").lower()

def ingest_url(url: str, sleep_s: float = 2.0) -> None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=45)
        ct = resp.headers.get("Content-Type", "")
        fetched_at = datetime.now(timezone.utc).isoformat()
        status = resp.status_code

        if status != 200:
            upsert_page(url, "", fetched_at, status, ct)
            return

        if is_probably_pdf(url, ct):
            # For MVP: store metadata only; later we can add PDF text extraction if needed.
            upsert_page(url, "(PDF)", fetched_at, status, ct)
            return

        title, text = extract_title_and_text(resp.text)
        upsert_page(url, title, fetched_at, status, ct)

        chunks = chunk_text(text)
        clear_chunks_for_url(url)
        insert_chunks(url, title, chunks)

    finally:
        time.sleep(sleep_s)

def ingest_from_file(urls_file: str = "../urls.txt", sleep_s: float = 2.0) -> None:
    init_db()
    with open(urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Ingesting {len(urls)} URLs from {urls_file}")
    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] {url}")
        ingest_url(url, sleep_s=sleep_s)

if __name__ == "__main__":
    ingest_from_file()
