"""Modelos de datos y esquemas para Bookmarks y Categorías."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CategoryEnum(str, Enum):
    AI = "Inteligencia Artificial"
    GAMING = "Videojuegos / Gaming"
    HUMOR = "Humor / Memes"
    DEV = "Desarrollo / Software"
    TECH = "Hardware / Tech"
    SCIENCE = "Ciencia"
    FINANCE = "Finanzas / Crypto"
    OTHER = "Otros / General"


CATEGORIES_LIST = [c.value for c in CategoryEnum]


class Bookmark(BaseModel):
    id: Optional[int] = None
    tweet_id: str
    author_username: str
    author_name: str
    author_avatar: str = ""
    text: str
    tweet_url: str
    created_at: str
    saved_at: str
    media_urls: List[str] = Field(default_factory=list)
    external_urls: List[str] = Field(default_factory=list)
    category: str = CategoryEnum.OTHER.value
    tags: List[str] = Field(default_factory=list)
    ai_summary: str = ""
    is_classified: bool = False
    raw_json: str = ""


class BookmarkCreateRequest(BaseModel):
    url: Optional[str] = None
    tweet_id: Optional[str] = None
    author_username: Optional[str] = None
    author_name: Optional[str] = None
    text: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class BookmarkUpdateRequest(BaseModel):
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    ai_summary: Optional[str] = None
    is_classified: Optional[bool] = None


class BookmarkFilter(BaseModel):
    category: Optional[str] = None
    search: Optional[str] = None
    tag: Optional[str] = None
    has_external_links: Optional[bool] = None
    has_media: Optional[bool] = None
    author: Optional[str] = None
    limit: int = 50
    offset: int = 0


class StatsResponse(BaseModel):
    total_bookmarks: int
    classified_bookmarks: int
    pending_classification: int
    categories_breakdown: dict[str, int]
