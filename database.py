import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SEM_TAGS = "sem tags"  # tag virtual gerenciada automaticamente

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

# ── HELPERS INTERNOS ───────────────────────────────────────

def get_or_create_tag(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cursor.lastrowid

def _assign_sem_tags(conn, photo_id: int):
    """Atribui 'sem tags' se a foto não tiver nenhuma tag real."""
    real_tags = conn.execute("""
        SELECT COUNT(*) as c FROM photo_tags pt
        JOIN tags t ON t.id = pt.tag_id
        WHERE pt.photo_id = ? AND t.name != ?
    """, (photo_id, SEM_TAGS)).fetchone()["c"]

    if real_tags == 0:
        tag_id = get_or_create_tag(conn, SEM_TAGS)
        conn.execute(
            "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
            (photo_id, tag_id)
        )
    else:
        # remove "sem tags" se existir
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (SEM_TAGS,)).fetchone()
        if row:
            conn.execute(
                "DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?",
                (photo_id, row["id"])
            )

# ── FOTOS ──────────────────────────────────────────────────

def add_photo(filename: str, original_name: str, file_hash: str, taken_date: str = None) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO photos (filename, original_name, file_hash, import_date, taken_date)
           VALUES (?, ?, ?, ?, ?)""",
        (filename, original_name, file_hash, datetime.now().isoformat(), taken_date)
    )
    photo_id = cursor.lastrowid
    # toda foto nova começa com "sem tags"
    _assign_sem_tags(conn, photo_id)
    conn.commit()
    return photo_id

def hash_exists(file_hash: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT id FROM photos WHERE file_hash = ?", (file_hash,)).fetchone()
    return row is not None

def get_photos_by_tags(tag_names: list, order: str = "recentes") -> list:
    ORDER_MAP = {
        "recentes": ("taken_date DESC, import_date DESC",
                     "p.taken_date DESC, p.import_date DESC"),
        "antigas":  ("taken_date ASC, import_date ASC",
                     "p.taken_date ASC, p.import_date ASC"),
        "nome":     ("original_name COLLATE NOCASE ASC",
                     "p.original_name COLLATE NOCASE ASC"),
    }
    order_simple, order_join = ORDER_MAP.get(order, ORDER_MAP["recentes"])

    conn = get_connection()
    if not tag_names:
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM photos ORDER BY {order_simple}"
        ).fetchall()]

    placeholders = ",".join("?" * len(tag_names))
    query = f"""
        SELECT p.* FROM photos p
        JOIN photo_tags pt ON pt.photo_id = p.id
        JOIN tags t ON t.id = pt.tag_id
        WHERE t.name IN ({placeholders})
        GROUP BY p.id
        HAVING COUNT(DISTINCT t.id) = ?
        ORDER BY {order_join}
    """
    return [dict(r) for r in conn.execute(query, tag_names + [len(tag_names)]).fetchall()]

def get_photo_tags(photo_id: int) -> list:
    """Retorna todas as tags da foto, incluindo 'sem tags' se aplicável."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.name FROM tags t JOIN photo_tags pt ON pt.tag_id = t.id WHERE pt.photo_id = ?",
        (photo_id,)
    ).fetchall()
    return [r["name"] for r in rows]

def get_photo_real_tags(photo_id: int) -> list:
    """Retorna apenas as tags reais (exclui 'sem tags')."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.name FROM tags t
           JOIN photo_tags pt ON pt.tag_id = t.id
           WHERE pt.photo_id = ? AND t.name != ?""",
        (photo_id, SEM_TAGS)
    ).fetchall()
    return [r["name"] for r in rows]

def delete_photo(photo_id: int, filename: str):
    conn = get_connection()
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()
    for folder in [
        os.path.join(BASE_DIR, "photos"),
        os.path.join(BASE_DIR, "thumbnails")
    ]:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            os.remove(path)

def delete_photos_bulk(photos: list):
    conn = get_connection()
    for photo in photos:
        conn.execute("DELETE FROM photos WHERE id = ?", (photo["id"],))
        for folder in [
            os.path.join(BASE_DIR, "photos"),
            os.path.join(BASE_DIR, "thumbnails")
        ]:
            path = os.path.join(folder, photo["filename"])
            if os.path.exists(path):
                os.remove(path)
    conn.commit()

def rename_photo(photo_id: int, new_name: str):
    conn = get_connection()
    conn.execute("UPDATE photos SET original_name = ? WHERE id = ?", (new_name.strip(), photo_id))
    conn.commit()

# ── TAGS ───────────────────────────────────────────────────

def get_all_tags() -> list:
    """Retorna todas as tags incluindo 'sem tags' (para filtros e gerenciador)."""
    conn = get_connection()
    rows = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
    return [r["name"] for r in rows]

def get_user_tags() -> list:
    """Retorna apenas as tags criadas pelo usuário (exclui 'sem tags')."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT name FROM tags WHERE name != ? ORDER BY name", (SEM_TAGS,)
    ).fetchall()
    return [r["name"] for r in rows]

def get_tags_with_count() -> list:
    """Retorna lista de (tag_name, count) ordenada alfabeticamente."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.name, COUNT(pt.photo_id) as total
        FROM tags t
        LEFT JOIN photo_tags pt ON pt.tag_id = t.id
        GROUP BY t.id
        ORDER BY t.name
    """).fetchall()
    return [(r["name"], r["total"]) for r in rows]

def set_photo_tags(photo_id: int, tag_names: list):
    """Define as tags de uma foto. Gerencia 'sem tags' automaticamente."""
    conn = get_connection()
    # remove apenas as tags reais (não toca em "sem tags" manualmente)
    real_tag_ids = conn.execute(
        "SELECT id FROM tags WHERE name != ?", (SEM_TAGS,)
    ).fetchall()
    for row in real_tag_ids:
        conn.execute(
            "DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?",
            (photo_id, row["id"])
        )

    for name in tag_names:
        name = name.strip()
        if name == SEM_TAGS:
            continue  # nunca adiciona "sem tags" manualmente
        tag_id = get_or_create_tag(conn, name)
        conn.execute(
            "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
            (photo_id, tag_id)
        )

    _assign_sem_tags(conn, photo_id)
    conn.commit()

def set_tags_bulk(photo_ids: list, tag_names: list):
    """Define as tags para uma lista de fotos, removendo as existentes e adicionando as novas."""
    conn = get_connection()
    for photo_id in photo_ids:
        # Remove todas as tags reais existentes para esta foto
        real_tag_ids = conn.execute(
            "SELECT id FROM tags WHERE name != ?", (SEM_TAGS,)
        ).fetchall()
        for row in real_tag_ids:
            conn.execute(
                "DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?",
                (photo_id, row["id"])
            )

        # Adiciona as novas tags
        for name in tag_names:
            name = name.strip()
            if name == SEM_TAGS:
                continue
            tag_id = get_or_create_tag(conn, name)
            conn.execute(
                "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
                (photo_id, tag_id)
            )
        _assign_sem_tags(conn, photo_id) # Reavalia "sem tags"
    conn.commit()

def add_tags_bulk(photo_ids: list, tag_names: list):
    """Adiciona tags a várias fotos. Remove 'sem tags' automaticamente."""
    conn = get_connection()
    for photo_id in photo_ids:
        for name in tag_names:
            name = name.strip()
            if name == SEM_TAGS:
                continue
            tag_id = get_or_create_tag(conn, name)
            conn.execute(
                "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
                (photo_id, tag_id)
            )
        _assign_sem_tags(conn, photo_id)
    conn.commit()

def remove_tags_bulk(photo_ids: list, tag_names: list):
    """Remove tags de várias fotos. Adiciona 'sem tags' se necessário."""
    conn = get_connection()
    for photo_id in photo_ids:
        for name in tag_names:
            if name == SEM_TAGS:
                continue
            row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            if row:
                conn.execute(
                    "DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?",
                    (photo_id, row["id"])
                )
        _assign_sem_tags(conn, photo_id)
    conn.commit()

def delete_tag(tag_name: str):
    """Remove uma tag do sistema. Não permite deletar 'sem tags'."""
    if tag_name == SEM_TAGS:
        return
    conn = get_connection()
    # pega fotos afetadas antes de deletar
    affected = conn.execute("""
        SELECT pt.photo_id FROM photo_tags pt
        JOIN tags t ON t.id = pt.tag_id
        WHERE t.name = ?
    """, (tag_name,)).fetchall()

    conn.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
    conn.commit()

    # verifica se alguma foto ficou sem tags reais
    for row in affected:
        _assign_sem_tags(conn, row["photo_id"])
    conn.commit()

def rename_tag(old_name: str, new_name: str):
    """Renomeia uma tag. Não permite renomear 'sem tags'."""
    if old_name == SEM_TAGS:
        return
    new_name = new_name.strip()
    if not new_name or new_name == SEM_TAGS:
        return
    conn = get_connection()
    conn.execute("UPDATE tags SET name = ? WHERE name = ?", (new_name, old_name))
    conn.commit()