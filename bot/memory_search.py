"""Memory search — SQLite FTS5 full-text search over MEMORY.md and daily logs.

Provides on-demand search so Claude can find relevant history without reading
entire files. Zero new dependencies — uses Python's built-in sqlite3 with FTS5.

Usage:
    python -m bot.memory_search search "cycling preferences" [--limit 5] [--source memory|daily]
    python -m bot.memory_search index
    python -m bot.memory_search stats
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path


# ── Paths ────────────────────────────────────────────────────────────────────

def _project_dir() -> Path:
    """Resolve project directory: ~/clawcode if installed, else source tree."""
    install_dir = Path.home() / "clawcode"
    if install_dir.exists():
        return install_dir
    return Path(__file__).resolve().parent.parent


def _db_path() -> Path:
    return _project_dir() / "data" / "memory.db"


def _memory_file() -> Path:
    return _project_dir() / "MEMORY.md"


def _memory_dir() -> Path:
    return _project_dir() / "memory"


# ── Database ─────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    """Open (or create) the search database."""
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chunks (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            source   TEXT NOT NULL,    -- 'memory' or 'daily'
            section  TEXT NOT NULL,    -- parent ## section
            heading  TEXT NOT NULL,    -- ### heading
            date     TEXT,            -- YYYY-MM-DD or NULL
            content  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS file_meta (
            path        TEXT PRIMARY KEY,
            mtime       REAL NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content,
            heading,
            section,
            content='chunks',
            content_rowid='id',
            tokenize='porter unicode61'
        );

        -- Sync triggers
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content, heading, section)
            VALUES (new.id, new.content, new.heading, new.section);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content, heading, section)
            VALUES ('delete', old.id, old.content, old.heading, old.section);
        END;

        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content, heading, section)
            VALUES ('delete', old.id, old.content, old.heading, old.section);
            INSERT INTO chunks_fts(rowid, content, heading, section)
            VALUES (new.id, new.content, new.heading, new.section);
        END;
    """)


# ── Chunking ─────────────────────────────────────────────────────────────────

def _chunk_memory_md(text: str) -> list[dict]:
    """Split MEMORY.md on ### headings, track parent ## section."""
    chunks = []
    current_section = ""
    current_heading = ""
    current_lines: list[str] = []
    current_date = None

    for line in text.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            # Flush previous chunk
            if current_heading and current_lines:
                chunks.append(_make_chunk(
                    "memory", current_section, current_heading,
                    current_date, current_lines,
                ))
            current_section = line.lstrip("# ").strip()
            current_heading = ""
            current_lines = []
            current_date = None

        elif line.startswith("### "):
            # Flush previous chunk
            if current_heading and current_lines:
                chunks.append(_make_chunk(
                    "memory", current_section, current_heading,
                    current_date, current_lines,
                ))
            current_heading = line.lstrip("# ").strip()
            current_lines = []
            current_date = None

        else:
            # Extract date from **Date:** lines
            date_match = re.match(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", line)
            if date_match:
                current_date = date_match.group(1)
            current_lines.append(line)

    # Flush last chunk
    if current_heading and current_lines:
        chunks.append(_make_chunk(
            "memory", current_section, current_heading,
            current_date, current_lines,
        ))

    return chunks


def _chunk_daily_log(text: str, filename: str) -> list[dict]:
    """Split a daily log on ### HH:MM entries."""
    # Extract date from filename (YYYY-MM-DD.md)
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
    date = date_match.group(1) if date_match else None

    chunks = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("### "):
            if current_heading and current_lines:
                chunks.append(_make_chunk(
                    "daily", f"Daily Log {date or filename}",
                    current_heading, date, current_lines,
                ))
            current_heading = line.lstrip("# ").strip()
            current_lines = []
        elif line.startswith("## "):
            # Section header in daily log — use as heading if no ### yet
            if current_heading and current_lines:
                chunks.append(_make_chunk(
                    "daily", f"Daily Log {date or filename}",
                    current_heading, date, current_lines,
                ))
            current_heading = line.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading and current_lines:
        chunks.append(_make_chunk(
            "daily", f"Daily Log {date or filename}",
            current_heading, date, current_lines,
        ))

    # If no headings found, treat the entire file as one chunk
    if not chunks and text.strip():
        chunks.append(_make_chunk(
            "daily", f"Daily Log {date or filename}",
            filename, date, text.splitlines(),
        ))

    return chunks


def _make_chunk(
    source: str, section: str, heading: str,
    date: str | None, lines: list[str],
) -> dict:
    content = "\n".join(lines).strip()
    # Skip separator-only or empty chunks
    if not content or content.replace("-", "").replace("*", "").strip() == "":
        return {}
    return {
        "source": source,
        "section": section,
        "heading": heading,
        "date": date,
        "content": content,
    }


# ── Indexing ─────────────────────────────────────────────────────────────────

def _index_file(conn: sqlite3.Connection, path: Path, source: str) -> int:
    """Index a single file. Returns chunk count."""
    text = path.read_text(encoding="utf-8")
    mtime = os.path.getmtime(path)
    str_path = str(path)

    # Delete old chunks for this file
    conn.execute("DELETE FROM chunks WHERE source = ? AND section LIKE ?", (
        source,
        f"%{path.name}%" if source == "daily" else "%",
    ))

    if source == "memory":
        # Clear all memory chunks (there's only one MEMORY.md)
        conn.execute("DELETE FROM chunks WHERE source = 'memory'")
        raw_chunks = _chunk_memory_md(text)
    else:
        # Clear chunks for this specific daily log
        conn.execute(
            "DELETE FROM chunks WHERE source = 'daily' AND section LIKE ?",
            (f"%{path.stem}%",),
        )
        raw_chunks = _chunk_daily_log(text, path.name)

    chunks = [c for c in raw_chunks if c]  # filter empty

    for chunk in chunks:
        conn.execute(
            "INSERT INTO chunks (source, section, heading, date, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (chunk["source"], chunk["section"], chunk["heading"],
             chunk["date"], chunk["content"]),
        )

    conn.execute(
        "INSERT OR REPLACE INTO file_meta (path, mtime, chunk_count) VALUES (?, ?, ?)",
        (str_path, mtime, len(chunks)),
    )

    return len(chunks)


def _needs_reindex(conn: sqlite3.Connection, path: Path) -> bool:
    """Check if a file needs re-indexing based on mtime."""
    if not path.exists():
        return False
    current_mtime = os.path.getmtime(path)
    row = conn.execute(
        "SELECT mtime FROM file_meta WHERE path = ?", (str(path),)
    ).fetchone()
    if row is None:
        return True
    return current_mtime > row[0]


def ensure_index(conn: sqlite3.Connection, force: bool = False) -> dict:
    """Lazy index — only re-index files that changed. Returns stats."""
    stats = {"indexed": 0, "skipped": 0, "chunks": 0}

    # MEMORY.md
    mem_file = _memory_file()
    if mem_file.exists() and (force or _needs_reindex(conn, mem_file)):
        count = _index_file(conn, mem_file, "memory")
        stats["indexed"] += 1
        stats["chunks"] += count
    elif mem_file.exists():
        stats["skipped"] += 1

    # Daily logs
    mem_dir = _memory_dir()
    if mem_dir.exists():
        for daily in sorted(mem_dir.glob("*.md")):
            if daily.name == "templates":
                continue
            if force or _needs_reindex(conn, daily):
                count = _index_file(conn, daily, "daily")
                stats["indexed"] += 1
                stats["chunks"] += count
            else:
                stats["skipped"] += 1

    conn.commit()
    return stats


# ── Search ───────────────────────────────────────────────────────────────────

def _prepare_query(query: str) -> str:
    """Prepare a query string for FTS5 MATCH.

    Escapes FTS5 operators and joins terms with OR for broad recall.
    """
    # Remove FTS5 special characters
    cleaned = re.sub(r'["\(\)\*\+\-\^:]', " ", query)
    terms = cleaned.split()
    if not terms:
        return query
    # Quote each term and join with OR
    quoted = [f'"{t}"' for t in terms if t]
    return " OR ".join(quoted)


def search(
    query: str,
    limit: int = 5,
    source: str | None = None,
) -> dict:
    """Search memory using FTS5. Returns JSON-serializable result dict."""
    conn = _connect()

    # Lazy index before searching
    ensure_index(conn)

    fts_query = _prepare_query(query)

    if source:
        sql = """
            SELECT c.source, c.section, c.heading, c.date, c.content,
                   bm25(chunks_fts, 1.0, 2.0, 1.5) AS score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
              AND c.source = ?
            ORDER BY score
            LIMIT ?
        """
        rows = conn.execute(sql, (fts_query, source, limit)).fetchall()
    else:
        sql = """
            SELECT c.source, c.section, c.heading, c.date, c.content,
                   bm25(chunks_fts, 1.0, 2.0, 1.5) AS score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """
        rows = conn.execute(sql, (fts_query, limit)).fetchall()

    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    file_count = conn.execute("SELECT COUNT(*) FROM file_meta").fetchone()[0]
    conn.close()

    results = []
    for row in rows:
        results.append({
            "score": round(abs(row[5]), 2),  # bm25 returns negative scores
            "source": row[0],
            "section": row[1],
            "heading": row[2],
            "date": row[3],
            "content": row[4],
        })

    return {
        "query": query,
        "results": results,
        "total_chunks": total_chunks,
        "indexed_files": file_count,
    }


# ── Stats ────────────────────────────────────────────────────────────────────

def stats() -> dict:
    """Return index statistics."""
    db = _db_path()
    if not db.exists():
        return {"exists": False, "chunks": 0, "files": 0, "db_size_kb": 0}

    conn = _connect()
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    file_count = conn.execute("SELECT COUNT(*) FROM file_meta").fetchone()[0]
    memory_chunks = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE source = 'memory'"
    ).fetchone()[0]
    daily_chunks = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE source = 'daily'"
    ).fetchone()[0]

    files = conn.execute("SELECT path, mtime, chunk_count FROM file_meta").fetchall()
    conn.close()

    db_size = os.path.getsize(db)

    return {
        "exists": True,
        "chunks": total_chunks,
        "memory_chunks": memory_chunks,
        "daily_chunks": daily_chunks,
        "files": file_count,
        "db_size_kb": round(db_size / 1024, 1),
        "indexed_files": [
            {"path": f[0], "mtime": f[1], "chunks": f[2]} for f in files
        ],
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="clawcode memory",
        description="Search ClawCode memory (MEMORY.md + daily logs)",
    )
    sub = parser.add_subparsers(dest="command")

    # search
    sp_search = sub.add_parser("search", help="Search memory")
    sp_search.add_argument("query", help="Search query")
    sp_search.add_argument("--limit", "-n", type=int, default=5,
                           help="Max results (default: 5)")
    sp_search.add_argument("--source", "-s", choices=["memory", "daily"],
                           help="Filter by source")

    # index
    sub.add_parser("index", help="Force full re-index")

    # stats
    sub.add_parser("stats", help="Show index statistics")

    args = parser.parse_args()

    if args.command == "search":
        result = search(args.query, limit=args.limit, source=args.source)
        print(json.dumps(result, indent=2))
        return 0

    elif args.command == "index":
        conn = _connect()
        idx_stats = ensure_index(conn, force=True)
        conn.close()
        print(f"Indexed {idx_stats['indexed']} file(s), {idx_stats['chunks']} chunk(s)")
        s = stats()
        print(f"Total: {s['chunks']} chunks across {s['files']} file(s)")
        return 0

    elif args.command == "stats":
        s = stats()
        if not s["exists"]:
            print("No index found. Run: clawcode memory index")
            return 1
        print(f"Chunks:  {s['chunks']} ({s['memory_chunks']} memory, {s['daily_chunks']} daily)")
        print(f"Files:   {s['files']}")
        print(f"DB size: {s['db_size_kb']} KB")
        if s.get("indexed_files"):
            print("\nIndexed files:")
            for f in s["indexed_files"]:
                print(f"  {f['path']} ({f['chunks']} chunks)")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
