"""Tests para la base de datos de bookmarks y FTS5."""

import pytest
from pathlib import Path
from app.models import Bookmark, BookmarkFilter, CategoryEnum
from app.storage.database import BookmarkDatabase


@pytest.fixture
def db(tmp_path: Path):
    db_file = tmp_path / "test_bookmarks.db"
    database = BookmarkDatabase(db_file)
    yield database
    database.close()


def test_upsert_and_get_bookmark(db: BookmarkDatabase):
    b = Bookmark(
        tweet_id="123456789",
        author_username="karpathy",
        author_name="Andrej Karpathy",
        text="Introducing a new LLM architecture for agents.",
        tweet_url="https://x.com/karpathy/status/123456789",
        created_at="2026-11-09T10:00:00Z",
        saved_at="2026-11-09T10:05:00Z",
        external_urls=["https://github.com/karpathy/nano-llm"],
        category=CategoryEnum.AI.value,
        tags=["llm", "ai", "agents"],
        is_classified=True,
    )
    saved = db.upsert_bookmark(b)
    assert saved.id is not None
    assert saved.tweet_id == "123456789"

    retrieved = db.get_by_tweet_id("123456789")
    assert retrieved is not None
    assert retrieved.author_username == "karpathy"
    assert retrieved.category == CategoryEnum.AI.value
    assert len(retrieved.external_urls) == 1


def test_fts5_search(db: BookmarkDatabase):
    b1 = Bookmark(
        tweet_id="101",
        author_username="gamer1",
        author_name="Gaming Pro",
        text="Check out this gameplay video of Elden Ring DLC boss fight",
        tweet_url="https://x.com/gamer1/status/101",
        created_at="2026-11-09T10:00:00Z",
        saved_at="2026-11-09T10:00:00Z",
        category=CategoryEnum.GAMING.value,
    )
    b2 = Bookmark(
        tweet_id="102",
        author_username="dev_guru",
        author_name="FastAPI Fan",
        text="FastAPI version 0.115 is released with huge performance gains",
        tweet_url="https://x.com/dev_guru/status/102",
        created_at="2026-11-09T10:00:00Z",
        saved_at="2026-11-09T10:00:00Z",
        category=CategoryEnum.DEV.value,
    )
    db.upsert_bookmark(b1)
    db.upsert_bookmark(b2)

    # Buscar "Elden Ring"
    results = db.list_bookmarks(BookmarkFilter(search="Elden"))
    assert len(results) == 1
    assert results[0].tweet_id == "101"

    # Buscar "FastAPI"
    results = db.list_bookmarks(BookmarkFilter(search="FastAPI"))
    assert len(results) == 1
    assert results[0].tweet_id == "102"


def test_stats_and_classification(db: BookmarkDatabase):
    b = Bookmark(
        tweet_id="201",
        author_username="testuser",
        author_name="Tester",
        text="A funny meme about software bugs",
        tweet_url="https://x.com/testuser/status/201",
        created_at="2026-11-09T10:00:00Z",
        saved_at="2026-11-09T10:00:00Z",
        is_classified=False,
    )
    db.upsert_bookmark(b)

    unclass = db.get_unclassified()
    assert len(unclass) == 1
    assert unclass[0].tweet_id == "201"

    db.update_classification(
        tweet_id="201",
        category=CategoryEnum.HUMOR.value,
        tags=["meme", "humor"],
        ai_summary="Meme sobre bugs en producción",
    )

    stats = db.get_stats()
    assert stats.total_bookmarks == 1
    assert stats.classified_bookmarks == 1
    assert stats.pending_classification == 0
    assert stats.categories_breakdown[CategoryEnum.HUMOR.value] == 1
