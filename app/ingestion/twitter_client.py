"""Cliente HTTP para interactuar con Twitter / X (GraphQL Bookmarks, Syndication y oEmbed)."""

import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import httpx

from app.models import Bookmark
from app.ingestion.parser import (
    extract_tweet_id_and_username,
    extract_external_urls,
    build_canonical_tweet_url,
)

# Token Bearer público utilizado por la aplicación web de Twitter / X
TWITTER_WEB_BEARER = (
    "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Query ID del endpoint Bookmarks en Twitter Web
GRAPHQL_BOOKMARKS_URL = "https://x.com/i/api/graphql/q9PdgmY1gyk_Gv1nW9jyPw/Bookmarks"


class TwitterClient:
    """Cliente para extracción directa de bookmarks y posts individuales."""

    def __init__(self, auth_token: str = "", ct0: str = ""):
        self.auth_token = auth_token.strip()
        self.ct0 = ct0.strip()

    def is_configured_for_sync(self) -> bool:
        """Indica si las cookies auth_token y ct0 están configuradas."""
        return bool(self.auth_token and self.ct0)

    async def fetch_single_tweet(self, url_or_id: str) -> Optional[Bookmark]:
        """
        Extrae un post individual a partir de su URL o ID.
        Usa la API pública de sindicación de Twitter (no requiere credenciales).
        """
        tweet_id, username = extract_tweet_id_and_username(url_or_id)
        if not tweet_id:
            return None

        # Intentar con Syndication API pública
        syndication_url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=x"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(syndication_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    user = data.get("user", {})
                    author_user = user.get("screen_name") or username or "i"
                    author_name = user.get("name") or author_user
                    author_avatar = user.get("profile_image_url_https", "")
                    text = data.get("text", "")

                    # Media
                    media_urls: List[str] = []
                    for photo in data.get("photos", []):
                        if "url" in photo:
                            media_urls.append(photo["url"])
                    video = data.get("video")
                    if video and "poster" in video:
                        media_urls.append(video["poster"])

                    ext_urls = extract_external_urls(text)
                    canonical_url = build_canonical_tweet_url(author_user, tweet_id)
                    created_at = data.get("created_at") or datetime.now(timezone.utc).isoformat()

                    return Bookmark(
                        tweet_id=str(tweet_id),
                        author_username=author_user,
                        author_name=author_name,
                        author_avatar=author_avatar,
                        text=text,
                        tweet_url=canonical_url,
                        created_at=str(created_at),
                        saved_at=datetime.now(timezone.utc).isoformat(),
                        media_urls=media_urls,
                        external_urls=ext_urls,
                        raw_json=json.dumps(data),
                    )
            except Exception:
                pass

            # Fallback a oEmbed público si syndication falla
            try:
                oembed_url = f"https://publish.twitter.com/oembed?url={build_canonical_tweet_url(username or 'i', tweet_id)}"
                resp2 = await client.get(oembed_url, headers=headers)
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    author_name = data2.get("author_name", "Usuario de X")
                    author_url = data2.get("author_url", "")
                    author_user = author_url.rstrip("/").split("/")[-1] if author_url else (username or "i")
                    raw_html = data2.get("html", "")
                    # Limpiar texto de HTML básico
                    import re
                    clean_text = re.sub(r"<[^>]+>", " ", raw_html).strip()

                    return Bookmark(
                        tweet_id=str(tweet_id),
                        author_username=author_user,
                        author_name=author_name,
                        text=clean_text or f"Post #{tweet_id}",
                        tweet_url=build_canonical_tweet_url(author_user, tweet_id),
                        created_at=datetime.now(timezone.utc).isoformat(),
                        saved_at=datetime.now(timezone.utc).isoformat(),
                        external_urls=extract_external_urls(clean_text),
                        raw_json=json.dumps(data2),
                    )
            except Exception:
                pass

        # Fallback sintético mínimo si la red falla
        canonical_url = build_canonical_tweet_url(username or "i", tweet_id)
        return Bookmark(
            tweet_id=str(tweet_id),
            author_username=username or "i",
            author_name=username or "Usuario de X",
            text=f"Guardado de Twitter/X: {canonical_url}",
            tweet_url=canonical_url,
            created_at=datetime.now(timezone.utc).isoformat(),
            saved_at=datetime.now(timezone.utc).isoformat(),
        )

    async def fetch_bookmarks_page(
        self, cursor: Optional[str] = None, count: int = 20
    ) -> Dict[str, Any]:
        """
        Consulta una página de guardados desde el endpoint GraphQL de Twitter con cookies.
        """
        if not self.is_configured_for_sync():
            raise ValueError(
                "Faltan credenciales TWITTER_AUTH_TOKEN o TWITTER_CT0 en la configuración."
            )

        variables = {
            "count": count,
            "includePromotedContent": False,
        }
        if cursor:
            variables["cursor"] = cursor

        features = {
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        }

        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(features),
        }

        headers = {
            "authorization": TWITTER_WEB_BEARER,
            "x-csrf-token": self.ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "Cookie": f"auth_token={self.auth_token}; ct0={self.ct0}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(GRAPHQL_BOOKMARKS_URL, params=params, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Error de Twitter API (HTTP {resp.status_code}): {resp.text[:200]}"
                )
            return resp.json()

    def parse_graphql_timeline(self, data: Dict[str, Any]) -> List[Bookmark]:
        """Extrae bookmarks desde la estructura de respuesta GraphQL de Twitter."""
        bookmarks: List[Bookmark] = []
        try:
            instructions = (
                data.get("data", {})
                .get("bookmark_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )
            entries = []
            for inst in instructions:
                if inst.get("type") == "TimelineAddEntries":
                    entries.extend(inst.get("entries", []))

            for entry in entries:
                content = entry.get("content", {})
                item_content = content.get("itemContent", {})
                tweet_results = item_content.get("tweet_results", {}).get("result", {})
                if not tweet_results:
                    continue

                legacy = tweet_results.get("legacy", {})
                core = tweet_results.get("core", {}).get("user_results", {}).get("result", {})
                user_legacy = core.get("legacy", {})

                tweet_id = str(tweet_results.get("rest_id") or legacy.get("id_str", ""))
                if not tweet_id:
                    continue

                author_user = user_legacy.get("screen_name", "")
                author_name = user_legacy.get("name", author_user)
                author_avatar = user_legacy.get("profile_image_url_https", "")
                text = legacy.get("full_text", "")
                created_at = legacy.get("created_at", datetime.now(timezone.utc).isoformat())

                # Media
                media_urls = []
                for m in legacy.get("entities", {}).get("media", []):
                    if "media_url_https" in m:
                        media_urls.append(m["media_url_https"])

                ext_urls = extract_external_urls(text)
                canonical_url = build_canonical_tweet_url(author_user, tweet_id)

                bookmarks.append(
                    Bookmark(
                        tweet_id=tweet_id,
                        author_username=author_user,
                        author_name=author_name,
                        author_avatar=author_avatar,
                        text=text,
                        tweet_url=canonical_url,
                        created_at=str(created_at),
                        saved_at=datetime.now(timezone.utc).isoformat(),
                        media_urls=media_urls,
                        external_urls=ext_urls,
                        raw_json=json.dumps(tweet_results),
                    )
                )
        except Exception:
            pass

        return bookmarks
