"""Tests para los endpoints de la API FastAPI."""

import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from app.main import app
from app.models import CategoryEnum


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_get_categories():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert CategoryEnum.AI.value in data
        assert CategoryEnum.GAMING.value in data
        assert CategoryEnum.HUMOR.value in data


@pytest.mark.asyncio
async def test_get_stats_and_bookmarks():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_bookmarks" in data
        assert "categories_breakdown" in data

        resp2 = await client.get("/api/bookmarks")
        assert resp2.status_code == 200
        assert isinstance(resp2.json(), list)


@pytest.mark.asyncio
async def test_create_and_delete_bookmark():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Guardar un tweet por URL usando url sintética
        resp = await client.post(
            "/api/bookmarks",
            json={"url": "https://x.com/karpathy/status/999123456789"},
        )
        assert resp.status_code == 200
        saved = resp.json()
        assert saved["tweet_id"] == "999123456789"
        assert "https://x.com" in saved["tweet_url"]

        # Recuperar detalle
        resp_get = await client.get("/api/bookmarks/999123456789")
        assert resp_get.status_code == 200

        # Eliminar
        resp_del = await client.delete("/api/bookmarks/999123456789")
        assert resp_del.status_code == 200
