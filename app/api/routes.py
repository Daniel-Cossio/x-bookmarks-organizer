"""Rutas de la API REST para Bookmarks, Sincronización y Clasificación."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from app.models import (
    Bookmark,
    BookmarkCreateRequest,
    BookmarkUpdateRequest,
    BookmarkFilter,
    StatsResponse,
    CATEGORIES_LIST,
)
from app.config import settings
from app.storage.database import BookmarkDatabase
from app.ingestion.twitter_client import TwitterClient
from app.ingestion.archive_importer import ArchiveImporter
from app.services.classifier import AIClassifier

router = APIRouter(prefix="/api")

# Instancia global de base de datos
db = BookmarkDatabase(settings.db_path)
classifier = AIClassifier()
twitter_client = TwitterClient(
    auth_token=settings.twitter_auth_token,
    ct0=settings.twitter_ct0,
)


@router.get("/categories", response_model=List[str])
def get_categories():
    """Devuelve la lista de categorías predefinidas."""
    return CATEGORIES_LIST


@router.get("/stats", response_model=StatsResponse)
def get_stats():
    """Devuelve estadísticas generales de guardados y desglose por categorías."""
    return db.get_stats()


@router.get("/bookmarks", response_model=List[Bookmark])
def list_bookmarks(
    category: Optional[str] = Query(None, description="Filtrar por categoría"),
    search: Optional[str] = Query(None, description="Búsqueda de texto FTS5"),
    tag: Optional[str] = Query(None, description="Filtrar por etiqueta"),
    author: Optional[str] = Query(None, description="Filtrar por autor"),
    has_links: Optional[bool] = Query(None, description="Solo posts con enlaces externos"),
    has_media: Optional[bool] = Query(None, description="Solo posts con fotos/video"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Consulta la lista de bookmarks con filtros dinámicos."""
    filters = BookmarkFilter(
        category=category,
        search=search,
        tag=tag,
        author=author,
        has_external_links=has_links,
        has_media=has_media,
        limit=limit,
        offset=offset,
    )
    return db.list_bookmarks(filters)


@router.get("/bookmarks/{tweet_id}", response_model=Bookmark)
def get_bookmark(tweet_id: str):
    """Obtiene el detalle de un bookmark por su tweet_id."""
    b = db.get_by_tweet_id(tweet_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bookmark no encontrado")
    return b


@router.post("/bookmarks", response_model=Bookmark)
async def create_or_ingest_bookmark(req: BookmarkCreateRequest):
    """
    Ingesta un nuevo tweet a partir de su URL o crea un registro con datos manuales.
    Si se proporciona URL, extrae automáticamente el contenido desde Twitter/X.
    """
    target = req.url or req.tweet_id
    if not target:
        raise HTTPException(status_code=400, detail="Se requiere 'url' o 'tweet_id'")

    # Extraer desde Twitter
    bookmark = await twitter_client.fetch_single_tweet(target)
    if not bookmark:
        raise HTTPException(status_code=400, detail="No se pudo extraer el tweet solicitado")

    if req.category:
        bookmark.category = req.category
    if req.tags:
        bookmark.tags = req.tags

    # Si no tiene categoría asignada, clasificar automáticamente
    if not bookmark.is_classified:
        cls_res = await classifier.classify_bookmark(bookmark)
        bookmark.category = cls_res["category"]
        bookmark.tags = cls_res["tags"]
        bookmark.ai_summary = cls_res["ai_summary"]
        bookmark.is_classified = True

    saved = db.upsert_bookmark(bookmark)
    return saved


@router.put("/bookmarks/{tweet_id}", response_model=Bookmark)
def update_bookmark(tweet_id: str, req: BookmarkUpdateRequest):
    """Actualiza la categoría, tags o notas de un bookmark existente."""
    existing = db.get_by_tweet_id(tweet_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bookmark no encontrado")

    cat = req.category or existing.category
    tags = req.tags if req.tags is not None else existing.tags
    summary = req.ai_summary if req.ai_summary is not None else existing.ai_summary

    updated = db.update_classification(
        tweet_id=tweet_id,
        category=cat,
        tags=tags,
        ai_summary=summary,
    )
    return updated


@router.delete("/bookmarks/{tweet_id}")
def delete_bookmark(tweet_id: str):
    """Elimina un bookmark de la bóveda."""
    success = db.delete_bookmark(tweet_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bookmark no encontrado")
    return {"message": "Bookmark eliminado correctamente", "tweet_id": tweet_id}


@router.post("/classify")
async def trigger_classification(limit: int = Query(25, ge=1, le=100)):
    """Ejecuta la clasificación con IA en lote para los guardados pendientes."""
    classified = await classifier.classify_pending_batch(db, limit=limit)
    return {
        "processed": len(classified),
        "message": f"Se clasificaron {len(classified)} guardados con IA.",
    }


@router.post("/sync")
async def sync_twitter_bookmarks(count: int = Query(100, ge=5, le=5000)):
    """
    Sincroniza guardados desde Twitter / X mediante paginación con cookies de sesión.
    Soporta desde 20 hasta 5000 guardados (o todos).
    """
    if not twitter_client.is_configured_for_sync():
        return {
            "status": "unconfigured",
            "message": (
                "Para sincronizar automáticamente desde Twitter/X, configura tus cookies "
                "TWITTER_AUTH_TOKEN y TWITTER_CT0 en el archivo .env.local del proyecto. "
                "Mientras tanto, puedes añadir enlaces individuales o importar tu archivo de Twitter."
            ),
            "synced_count": 0,
        }

    try:
        bookmarks = await twitter_client.fetch_all_bookmarks(max_count=count)
        saved_count = 0
        for b in bookmarks:
            db.upsert_bookmark(b)
            saved_count += 1

        # Clasificar automáticamente lote de pendientes
        classified = await classifier.classify_pending_batch(db, limit=min(100, saved_count))

        return {
            "status": "success",
            "message": f"Sincronizados {saved_count} guardados desde X ({len(classified)} clasificados en este lote).",
            "synced_count": saved_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante sincronización: {str(e)}")


@router.post("/import-file")
async def import_archive_file(file_path: str = Query(..., description="Ruta absoluta al archivo ZIP o bookmarks.js")):
    """Importa guardados desde un archivo exportado de Twitter."""
    try:
        bookmarks = ArchiveImporter.parse_bookmarks_file(file_path)
        saved_count = 0
        for b in bookmarks:
            db.upsert_bookmark(b)
            saved_count += 1

        # Clasificar un lote inicial
        await classifier.classify_pending_batch(db, limit=min(50, saved_count))

        return {
            "status": "success",
            "imported_count": saved_count,
            "message": f"Se importaron {saved_count} guardados exitosamente desde {file_path}.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar archivo: {str(e)}")
