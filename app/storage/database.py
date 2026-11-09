"""Capa de persistencia SQLite con FTS5 para Bookmarks de Twitter / X."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from app.models import Bookmark, BookmarkFilter, StatsResponse, CategoryEnum, CATEGORIES_LIST


class BookmarkDatabase:
    """Base de datos SQLite optimizada con soporte FTS5 para búsquedas instantáneas."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Inicializa el esquema relacional y la tabla virtual FTS5."""
        conn = self._conn
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT UNIQUE NOT NULL,
                author_username TEXT NOT NULL,
                author_name TEXT NOT NULL,
                author_avatar TEXT DEFAULT '',
                text TEXT NOT NULL,
                tweet_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                media_urls TEXT DEFAULT '[]',
                external_urls TEXT DEFAULT '[]',
                category TEXT DEFAULT 'Otros / General',
                tags TEXT DEFAULT '[]',
                ai_summary TEXT DEFAULT '',
                is_classified INTEGER DEFAULT 0,
                raw_json TEXT DEFAULT ''
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_tweet_id ON bookmarks(tweet_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_category ON bookmarks(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_is_classified ON bookmarks(is_classified)")

        # Tabla virtual FTS5 para búsquedas de texto completo
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts USING fts5(
                tweet_id,
                author_username,
                author_name,
                text,
                category,
                tags,
                ai_summary,
                tokenize = 'unicode61'
            )
        """)
        conn.commit()

    def _row_to_bookmark(self, row: sqlite3.Row) -> Bookmark:
        """Convierte una fila SQLite a modelo Bookmark."""
        data = dict(row)
        data["media_urls"] = json.loads(data["media_urls"]) if isinstance(data.get("media_urls"), str) else data.get("media_urls", [])
        data["external_urls"] = json.loads(data["external_urls"]) if isinstance(data.get("external_urls"), str) else data.get("external_urls", [])
        data["tags"] = json.loads(data["tags"]) if isinstance(data.get("tags"), str) else data.get("tags", [])
        data["is_classified"] = bool(data["is_classified"])
        return Bookmark(**data)

    def _sync_fts(self, bookmark: Bookmark) -> None:
        """Sincroniza la entrada del bookmark en la tabla virtual FTS5."""
        tags_str = " ".join(bookmark.tags)
        self._conn.execute("DELETE FROM bookmarks_fts WHERE tweet_id = ?", (bookmark.tweet_id,))
        self._conn.execute(
            """INSERT INTO bookmarks_fts (tweet_id, author_username, author_name, text, category, tags, ai_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                bookmark.tweet_id,
                bookmark.author_username,
                bookmark.author_name,
                bookmark.text,
                bookmark.category,
                tags_str,
                bookmark.ai_summary,
            ),
        )

    def upsert_bookmark(self, bookmark: Bookmark, overwrite_classification: bool = False) -> Bookmark:
        """
        Inserta o actualiza un bookmark de forma idempotente.
        Preserva la clasificación manual existente a menos que overwrite_classification sea True.
        """
        conn = self._conn
        cursor = conn.cursor()

        existing = self.get_by_tweet_id(bookmark.tweet_id)
        if existing and not overwrite_classification and existing.is_classified:
            bookmark.category = existing.category
            bookmark.tags = existing.tags
            bookmark.ai_summary = existing.ai_summary
            bookmark.is_classified = existing.is_classified

        media_json = json.dumps(bookmark.media_urls)
        external_json = json.dumps(bookmark.external_urls)
        tags_json = json.dumps(bookmark.tags)

        cursor.execute(
            """INSERT INTO bookmarks (
                   tweet_id, author_username, author_name, author_avatar,
                   text, tweet_url, created_at, saved_at, media_urls,
                   external_urls, category, tags, ai_summary, is_classified, raw_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tweet_id) DO UPDATE SET
                   author_username=excluded.author_username,
                   author_name=excluded.author_name,
                   author_avatar=excluded.author_avatar,
                   text=excluded.text,
                   tweet_url=excluded.tweet_url,
                   media_urls=excluded.media_urls,
                   external_urls=excluded.external_urls,
                   category=excluded.category,
                   tags=excluded.tags,
                   ai_summary=excluded.ai_summary,
                   is_classified=excluded.is_classified,
                   raw_json=excluded.raw_json
               RETURNING id""",
            (
                bookmark.tweet_id,
                bookmark.author_username,
                bookmark.author_name,
                bookmark.author_avatar,
                bookmark.text,
                bookmark.tweet_url,
                bookmark.created_at,
                bookmark.saved_at,
                media_json,
                external_json,
                bookmark.category,
                tags_json,
                bookmark.ai_summary,
                1 if bookmark.is_classified else 0,
                bookmark.raw_json,
            ),
        )
        row = cursor.fetchone()
        if row:
            bookmark.id = row[0]
        self._sync_fts(bookmark)
        conn.commit()
        return bookmark

    def get_by_tweet_id(self, tweet_id: str) -> Optional[Bookmark]:
        """Obtiene un bookmark por su tweet_id."""
        row = self._conn.execute(
            "SELECT * FROM bookmarks WHERE tweet_id = ?", (str(tweet_id),)
        ).fetchone()
        return self._row_to_bookmark(row) if row else None

    def get_by_id(self, bookmark_id: int) -> Optional[Bookmark]:
        """Obtiene un bookmark por su ID autoincremental."""
        row = self._conn.execute(
            "SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)
        ).fetchone()
        return self._row_to_bookmark(row) if row else None

    def list_bookmarks(self, filters: Optional[BookmarkFilter] = None) -> List[Bookmark]:
        """Consulta bookmarks aplicando filtros dinámicos y búsqueda FTS5."""
        if filters is None:
            filters = BookmarkFilter()

        query_parts = ["SELECT * FROM bookmarks"]
        where_clauses = []
        params: List[Any] = []

        # Si hay búsqueda por texto, usar FTS5
        if filters.search and filters.search.strip():
            search_term = filters.search.strip()
            # Si hay palabras, armar búsqueda FTS5
            where_clauses.append("""
                tweet_id IN (
                    SELECT tweet_id FROM bookmarks_fts WHERE bookmarks_fts MATCH ?
                )
            """)
            # Sanitizar query FTS5 básica
            escaped_term = f'"{search_term}"*'
            params.append(escaped_term)

        if filters.category and filters.category != "all":
            where_clauses.append("category = ?")
            params.append(filters.category)

        if filters.author:
            where_clauses.append("(author_username LIKE ? OR author_name LIKE ?)")
            params.extend([f"%{filters.author}%", f"%{filters.author}%"])

        if filters.has_external_links is True:
            where_clauses.append("external_urls != '[]'")
        elif filters.has_external_links is False:
            where_clauses.append("external_urls = '[]'")

        if filters.has_media is True:
            where_clauses.append("media_urls != '[]'")
        elif filters.has_media is False:
            where_clauses.append("media_urls = '[]'")

        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))

        query_parts.append("ORDER BY id DESC LIMIT ? OFFSET ?")
        params.extend([filters.limit, filters.offset])

        sql = " ".join(query_parts)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_bookmark(r) for r in rows]

    def get_unclassified(self, limit: int = 50) -> List[Bookmark]:
        """Obtiene los bookmarks pendientes de clasificar con IA."""
        rows = self._conn.execute(
            "SELECT * FROM bookmarks WHERE is_classified = 0 ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_bookmark(r) for r in rows]

    def update_classification(
        self,
        tweet_id: str,
        category: str,
        tags: List[str],
        ai_summary: str,
    ) -> Optional[Bookmark]:
        """Actualiza la clasificación por IA de un bookmark."""
        tags_json = json.dumps(tags)
        self._conn.execute(
            """UPDATE bookmarks
               SET category = ?, tags = ?, ai_summary = ?, is_classified = 1
               WHERE tweet_id = ?""",
            (category, tags_json, ai_summary, tweet_id),
        )
        self._conn.commit()

        updated = self.get_by_tweet_id(tweet_id)
        if updated:
            self._sync_fts(updated)
            self._conn.commit()
        return updated

    def delete_bookmark(self, tweet_id: str) -> bool:
        """Elimina un bookmark por tweet_id."""
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM bookmarks WHERE tweet_id = ?", (tweet_id,))
        cursor.execute("DELETE FROM bookmarks_fts WHERE tweet_id = ?", (tweet_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def get_stats(self) -> StatsResponse:
        """Calcula estadísticas generales de la bóveda de bookmarks."""
        total = self._conn.execute("SELECT COUNT(*) FROM bookmarks").fetchone()[0]
        classified = self._conn.execute("SELECT COUNT(*) FROM bookmarks WHERE is_classified = 1").fetchone()[0]
        pending = total - classified

        breakdown_rows = self._conn.execute(
            "SELECT category, COUNT(*) FROM bookmarks GROUP BY category"
        ).fetchall()
        categories_dict = {row[0]: row[1] for row in breakdown_rows}

        # Asegurar todas las categorías del enum
        for cat in CATEGORIES_LIST:
            if cat not in categories_dict:
                categories_dict[cat] = 0

        return StatsResponse(
            total_bookmarks=total,
            classified_bookmarks=classified,
            pending_classification=pending,
            categories_breakdown=categories_dict,
        )

    def close(self) -> None:
        """Cierra la conexión SQLite."""
        self._conn.close()
