import sqlite3
from pathlib import Path
from typing import Iterable, Tuple, Optional, List

DB_PATH = Path("data.db")

def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def init_db() -> None:
    con = connect()
    cur = con.cursor()

    # Raw docs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pages (
      url TEXT PRIMARY KEY,
      title TEXT,
      fetched_at TEXT,
      status_code INTEGER,
      content_type TEXT
    );
    """)

    # FTS chunks (FTS5 is built into most Ubuntu sqlite builds)
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
      url,
      title,
      chunk,
      chunk_index UNINDEXED,
      tokenize = 'porter'
    );
    """)

    # Helpful index table for chunk metadata (optional but nice)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chunks_meta (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      url TEXT,
      chunk_index INTEGER,
      char_len INTEGER
    );
    """)
    con.commit()
    con.close()

def clear_chunks_for_url(url: str) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute("DELETE FROM chunks_fts WHERE url = ?", (url,))
    cur.execute("DELETE FROM chunks_meta WHERE url = ?", (url,))
    con.commit()
    con.close()

def upsert_page(url: str, title: str, fetched_at: str, status_code: int, content_type: str) -> None:
    con = connect()
    cur = con.cursor()
    cur.execute("""
    INSERT INTO pages(url, title, fetched_at, status_code, content_type)
    VALUES(?,?,?,?,?)
    ON CONFLICT(url) DO UPDATE SET
      title=excluded.title,
      fetched_at=excluded.fetched_at,
      status_code=excluded.status_code,
      content_type=excluded.content_type
    """, (url, title, fetched_at, status_code, content_type))
    con.commit()
    con.close()

def insert_chunks(url: str, title: str, chunks: List[str]) -> None:
    con = connect()
    cur = con.cursor()
    for i, ch in enumerate(chunks):
        cur.execute(
            "INSERT INTO chunks_fts(url, title, chunk, chunk_index) VALUES(?,?,?,?)",
            (url, title, ch, i),
        )
        cur.execute(
            "INSERT INTO chunks_meta(url, chunk_index, char_len) VALUES(?,?,?)",
            (url, i, len(ch)),
        )
    con.commit()
    con.close()

def search_chunks(query: str, k: int = 6) -> List[Tuple[str, str, str, int]]:
    """
    Returns list of (url, title, chunk, chunk_index)
    """
    con = connect()
    cur = con.cursor()
    cur.execute(
        """
        SELECT url, title, chunk, chunk_index
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY bm25(chunks_fts)
        LIMIT ?
        """,
        (query, k),
    )
    rows = cur.fetchall()
    con.close()
    return rows
