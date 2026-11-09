"""Importador para archivos exportados de datos de Twitter (ZIP o bookmarks.js)."""

import json
import zipfile
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any

from app.models import Bookmark
from app.ingestion.parser import build_canonical_tweet_url, extract_external_urls


class ArchiveImporter:
    """Procesador de archivos descargados de Twitter (Twitter Archive)."""

    @staticmethod
    def _strip_js_prefix(content: str) -> str:
        """Elimina la cabecera 'window.YTD.bookmarks.part0 = ' para dejar JSON puro."""
        match = re.search(r"=\s*(\[.*\])\s*;?\s*$", content, re.DOTALL)
        if match:
            return match.group(1)
        # Si ya es un array o dict JSON
        content = content.strip()
        if content.startswith("[") or content.startswith("{"):
            return content
        return content

    @classmethod
    def parse_bookmarks_file(cls, file_path: Path | str) -> List[Bookmark]:
        """Lee y parsea un archivo bookmarks.js o bookmarks.json."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {path}")

        # Si es un archivo ZIP
        if path.suffix.lower() == ".zip":
            return cls.parse_zip_archive(path)

        content = path.read_text(encoding="utf-8")
        return cls.parse_json_content(content)

    @classmethod
    def parse_zip_archive(cls, zip_path: Path) -> List[Bookmark]:
        """Extrae y procesa bookmarks.js dentro de un ZIP de Twitter Archive."""
        with zipfile.ZipFile(zip_path, "r") as z:
            # Buscar archivo de bookmarks en el ZIP
            target_name = None
            for name in z.namelist():
                if name.endswith("bookmarks.js") or name.endswith("bookmark.js") or name.endswith("bookmarks.json"):
                    target_name = name
                    break

            if not target_name:
                raise ValueError("No se encontró archivo de bookmarks en el ZIP (data/bookmarks.js).")

            with z.open(target_name) as f:
                content = f.read().decode("utf-8")
                return cls.parse_json_content(content)

    @classmethod
    def parse_json_content(cls, content: str) -> List[Bookmark]:
        """Parsea el contenido de texto JSON o JavaScript de Twitter."""
        clean_json = cls._strip_js_prefix(content)
        data = json.loads(clean_json)

        bookmarks: List[Bookmark] = []
        now = datetime.now(timezone.utc).isoformat()

        if isinstance(data, list):
            for item in data:
                b_data = item.get("bookmark") or item.get("tweet") or item
                tweet_id = str(b_data.get("tweetId") or b_data.get("id") or b_data.get("id_str") or "")
                if not tweet_id:
                    continue

                full_text = b_data.get("full_text") or b_data.get("text") or f"Post guardado #{tweet_id}"
                author_username = b_data.get("screen_name") or b_data.get("username") or "i"
                author_name = b_data.get("name") or author_username
                created_at = b_data.get("created_at") or now
                ext_urls = extract_external_urls(full_text)
                canonical_url = build_canonical_tweet_url(author_username, tweet_id)

                media_urls = []
                for m in b_data.get("entities", {}).get("media", []):
                    if "media_url_https" in m:
                        media_urls.append(m["media_url_https"])

                bookmarks.append(
                    Bookmark(
                        tweet_id=tweet_id,
                        author_username=author_username,
                        author_name=author_name,
                        text=full_text,
                        tweet_url=canonical_url,
                        created_at=str(created_at),
                        saved_at=now,
                        media_urls=media_urls,
                        external_urls=ext_urls,
                        raw_json=json.dumps(b_data),
                    )
                )

        return bookmarks
