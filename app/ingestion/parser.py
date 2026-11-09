"""Utilidades de parsing y extracción de URLs y metadatos de tweets."""

import re
from typing import List, Optional, Tuple


TWEET_URL_REGEX = re.compile(
    r"https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/(?P<username>[a-zA-Z0-9_]{1,15})/status/(?P<tweet_id>\d+)"
)

URL_REGEX = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
)


def extract_tweet_id_and_username(url_or_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrae el ID del tweet y el username a partir de una URL o cadena."""
    url_or_id = url_or_id.strip()
    match = TWEET_URL_REGEX.search(url_or_id)
    if match:
        return match.group("tweet_id"), match.group("username")
    if url_or_id.isdigit():
        return url_or_id, None
    return None, None


def extract_external_urls(text: str, exclude_tco: bool = False) -> List[str]:
    """Extrae enlaces externos encontrados dentro del cuerpo del texto."""
    urls = URL_REGEX.findall(text)
    external: List[str] = []
    for u in urls:
        # Limpiar puntuación al final
        clean = u.rstrip(".,;:)>]")
        if "twitter.com" in clean or "x.com" in clean:
            continue
        if exclude_tco and "t.co/" in clean:
            continue
        if clean not in external:
            external.append(clean)
    return external


def build_canonical_tweet_url(author_username: str, tweet_id: str) -> str:
    """Construye la URL canónica y directa hacia el post en X."""
    username = author_username.strip("@") if author_username else "i"
    return f"https://x.com/{username}/status/{tweet_id}"
