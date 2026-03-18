import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _get_db_path():
    return os.path.join(BASE_DIR, "photomanager.db")

_conn = None

def get_connection():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.execute("PRAGMA journal_mode = WAL")
    return _conn

def initialize_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS photos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT NOT NULL UNIQUE,
            original_name TEXT,
            file_hash     TEXT NOT NULL UNIQUE,
            import_date   TEXT NOT NULL,
            taken_date    TEXT
        );

        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS photo_tags (
            photo_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
            tag_id   INTEGER REFERENCES tags(id)   ON DELETE CASCADE,
            PRIMARY KEY (photo_id, tag_id)
        );
    """)
    conn.commit()

# ── FOTOS ──────────────────────────────────────────────────

def add_photo(filename: str, original_name: str, file_hash: str, taken_date: str = None) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO photos (filename, original_name, file_hash, import_date, taken_date)
           VALUES (?, ?, ?, ?, ?)""",
        (filename, original_name, file_hash, datetime.now().isoformat(), taken_date)
    )
    conn.commit()
    return cursor.lastrowid

def hash_exists(file_hash: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT id FROM photos WHERE file_hash = ?", (file_hash,)).fetchone()
    return row is not None

def get_photos_by_tags(tag_names: list) -> list:
    conn = get_connection()
    if not tag_names:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM photos ORDER BY taken_date DESC, import_date DESC"
        ).fetchall()]

    placeholders = ",".join("?" * len(tag_names))
    query = f"""
        SELECT p.* FROM photos p
        JOIN photo_tags pt ON pt.photo_id = p.id
        JOIN tags t ON t.id = pt.tag_id
        WHERE t.name IN ({placeholders})
        GROUP BY p.id
        HAVING COUNT(DISTINCT t.id) = ?
        ORDER BY p.taken_date DESC, p.import_date DESC
    """
    return [dict(r) for r in conn.execute(query, tag_names + [len(tag_names)]).fetchall()]

def get_photo_tags(photo_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.name FROM tags t JOIN photo_tags pt ON pt.tag_id = t.id WHERE pt.photo_id = ?",
        (photo_id,)
    ).fetchall()
    return [r["name"] for r in rows]

def delete_photo(photo_id: int, filename: str):
    conn = get_connection()
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()
    for folder in ["photos", "thumbnails"]:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            os.remove(path)

def delete_photos_bulk(photos: list):
    """Remove uma lista de fotos de uma vez. Cada item deve ter 'id' e 'filename'."""
    conn = get_connection()
    for photo in photos:
        conn.execute("DELETE FROM photos WHERE id = ?", (photo["id"],))
        for folder in ["photos", "thumbnails"]:
            path = os.path.join(folder, photo["filename"])
            if os.path.exists(path):
                os.remove(path)
    conn.commit()

# ── TAGS ───────────────────────────────────────────────────

def get_or_create_tag(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cursor.lastrowid

def get_all_tags() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    return [r["name"] for r in rows]

def set_photo_tags(photo_id: int, tag_names: list):
    conn = get_connection()
    conn.execute("DELETE FROM photo_tags WHERE photo_id = ?", (photo_id,))
    for name in tag_names:
        tag_id = get_or_create_tag(conn, name.strip())
        conn.execute(
            "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
            (photo_id, tag_id)
        )
    conn.commit()

def add_tags_bulk(photo_ids: list, tag_names: list):
    """Adiciona as tags informadas a várias fotos sem remover as existentes."""
    conn = get_connection()
    for photo_id in photo_ids:
        for name in tag_names:
            tag_id = get_or_create_tag(conn, name.strip())
            conn.execute(
                "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
                (photo_id, tag_id)
            )
    conn.commit()

def remove_tags_bulk(photo_ids: list, tag_names: list):
    """Remove as tags informadas de várias fotos."""
    conn = get_connection()
    for photo_id in photo_ids:
        for name in tag_names:
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            if row:
                conn.execute(
                    "DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?",
                    (photo_id, row["id"])
                )
    conn.commit()

def delete_tag(tag_name: str):
    """Remove uma tag do sistema e de todas as fotos que a possuem."""
    conn = get_connection()
    conn.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
    conn.commit()