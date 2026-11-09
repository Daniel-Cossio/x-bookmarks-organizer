"""Tests para el servicio de clasificación de IA y heurística."""

import pytest
from app.models import Bookmark, CategoryEnum
from app.services.classifier import AIClassifier
from app.storage.database import BookmarkDatabase


@pytest.fixture
def classifier():
    return AIClassifier(provider="heuristic")


def test_heuristic_ai_classification(classifier: AIClassifier):
    text = "New open-weights LLM released by DeepSeek with 67B parameters, exceptional for coding and RAG"
    res = classifier.classify_heuristic(text)
    assert res["category"] == CategoryEnum.AI.value
    assert "llm" in res["tags"] or "rag" in res["tags"]


def test_heuristic_gaming_classification(classifier: AIClassifier):
    text = "Check out my new modpack for Project Zomboid build 42 with custom weapons and rpg gameplay"
    res = classifier.classify_heuristic(text)
    assert res["category"] == CategoryEnum.GAMING.value
    assert "zomboid" in res["tags"] or "mod" in res["tags"] or "gameplay" in res["tags"]


def test_heuristic_humor_classification(classifier: AIClassifier):
    text = "jajajaja este meme de cuando el backend falla en produccion es buenisimo xd"
    res = classifier.classify_heuristic(text)
    assert res["category"] == CategoryEnum.HUMOR.value


def test_batch_classification(tmp_path):
    db_file = tmp_path / "test_cls.db"
    db = BookmarkDatabase(db_file)
    clf = AIClassifier(provider="heuristic")

    b1 = Bookmark(
        tweet_id="501",
        author_username="test1",
        author_name="User 1",
        text="A hilarious meme jaja xd",
        tweet_url="https://x.com/test1/status/501",
        created_at="2026-11-09T10:00:00Z",
        saved_at="2026-11-09T10:00:00Z",
        is_classified=False,
    )
    b2 = Bookmark(
        tweet_id="502",
        author_username="test2",
        author_name="User 2",
        text="FastAPI and Docker deployment guide for Python backend",
        tweet_url="https://x.com/test2/status/502",
        created_at="2026-11-09T10:00:00Z",
        saved_at="2026-11-09T10:00:00Z",
        is_classified=False,
    )
    db.upsert_bookmark(b1)
    db.upsert_bookmark(b2)

    import asyncio
    classified = asyncio.run(clf.classify_pending_batch(db))
    assert len(classified) == 2

    r1 = db.get_by_tweet_id("501")
    assert r1.is_classified is True
    assert r1.category == CategoryEnum.HUMOR.value

    r2 = db.get_by_tweet_id("502")
    assert r2.is_classified is True
    assert r2.category == CategoryEnum.DEV.value

    db.close()
