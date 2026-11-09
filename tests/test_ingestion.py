"""Tests para el módulo de ingesta y parseo de Twitter."""

import pytest
import json
from pathlib import Path
from app.ingestion.parser import (
    extract_tweet_id_and_username,
    extract_external_urls,
    build_canonical_tweet_url,
)
from app.ingestion.archive_importer import ArchiveImporter
from app.ingestion.twitter_client import TwitterClient


def test_extract_tweet_id_and_username():
    url1 = "https://x.com/karpathy/status/1852000000000000000"
    tweet_id, user = extract_tweet_id_and_username(url1)
    assert tweet_id == "1852000000000000000"
    assert user == "karpathy"

    url2 = "https://twitter.com/sama/status/1700000000000000000?s=20"
    tweet_id2, user2 = extract_tweet_id_and_username(url2)
    assert tweet_id2 == "1700000000000000000"
    assert user2 == "sama"

    raw_id = "12345678"
    tweet_id3, user3 = extract_tweet_id_and_username(raw_id)
    assert tweet_id3 == "12345678"
    assert user3 is None


def test_extract_external_urls():
    text = (
        "Check our new release on GitHub: https://github.com/fastapi/fastapi and the paper "
        "at https://arxiv.org/abs/2301.00001! Also see https://x.com/status/123"
    )
    urls = extract_external_urls(text)
    assert "https://github.com/fastapi/fastapi" in urls
    assert "https://arxiv.org/abs/2301.00001" in urls
    # Excluye urls internas de x.com
    assert not any("x.com" in u for u in urls)


def test_build_canonical_tweet_url():
    url = build_canonical_tweet_url("elonmusk", "12345")
    assert url == "https://x.com/elonmusk/status/12345"


def test_archive_importer_js(tmp_path: Path):
    js_content = """window.YTD.bookmarks.part0 = [
      {
        "bookmark": {
          "tweetId": "999888777",
          "full_text": "A great thread about reinforcement learning https://rl-tutorial.com",
          "screen_name": "ai_researcher",
          "name": "AI Researcher"
        }
      }
    ];"""
    file_path = tmp_path / "bookmarks.js"
    file_path.write_text(js_content, encoding="utf-8")

    bookmarks = ArchiveImporter.parse_bookmarks_file(file_path)
    assert len(bookmarks) == 1
    assert bookmarks[0].tweet_id == "999888777"
    assert bookmarks[0].author_username == "ai_researcher"
    assert bookmarks[0].tweet_url == "https://x.com/ai_researcher/status/999888777"
    assert "https://rl-tutorial.com" in bookmarks[0].external_urls
