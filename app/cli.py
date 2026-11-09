"""CLI Typer para administración de X-Bookmarks Organizer."""

import sys
from pathlib import Path

# Asegurar raíz en sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import typer
import asyncio
from typing import Optional

from app.config import settings
from app.models import BookmarkFilter
from app.storage.database import BookmarkDatabase
from app.ingestion.twitter_client import TwitterClient
from app.ingestion.archive_importer import ArchiveImporter
from app.services.classifier import AIClassifier

app = typer.Typer(help="X-Bookmarks Organizer — Herramienta de gestión y sincronización.")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Dirección host"),
    port: int = typer.Option(8085, help="Puerto de escucha"),
    reload: bool = typer.Option(False, help="Recarga automática en desarrollo"),
):
    """Inicia el servidor web FastAPI y panel de control."""
    import uvicorn
    typer.echo(f"🚀 Iniciando X-Bookmarks Organizer en http://{host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command()
def sync(count: int = typer.Option(100, help="Cantidad máxima a sincronizar")):
    """Sincroniza guardados desde Twitter / X mediante paginación con cookies."""
    async def _run():
        db = BookmarkDatabase(settings.db_path)
        client = TwitterClient(settings.twitter_auth_token, settings.twitter_ct0)
        classifier = AIClassifier()

        if not client.is_configured_for_sync():
            typer.echo("❌ Falta TWITTER_AUTH_TOKEN o TWITTER_CT0 en .env.local", err=True)
            raise typer.Exit(1)

        typer.echo(f"🔄 Sincronizando hasta {count} guardados desde X...")
        bookmarks = await client.fetch_all_bookmarks(max_count=count)
        typer.echo(f"   Descargados {len(bookmarks)} guardados. Guardando en SQLite...")

        for b in bookmarks:
            db.upsert_bookmark(b)

        typer.echo("⚡ Clasificando guardados pendientes con IA...")
        await classifier.classify_pending_batch(db, limit=min(100, len(bookmarks)))

        stats = db.get_stats()
        typer.echo(f"✅ Sincronización completada. Total en la bóveda: {stats.total_bookmarks}")
        db.close()

    asyncio.run(_run())


@app.command()
def add(url: str = typer.Argument(..., help="URL del post de Twitter/X a guardar")):
    """Captura e ingesta un post individual de Twitter/X."""
    async def _run():
        db = BookmarkDatabase(settings.db_path)
        client = TwitterClient(settings.twitter_auth_token, settings.twitter_ct0)
        classifier = AIClassifier()

        typer.echo(f"🔍 Extrayendo post: {url} ...")
        bookmark = await client.fetch_single_tweet(url)
        if not bookmark:
            typer.echo("❌ No se pudo extraer el tweet.", err=True)
            raise typer.Exit(1)

        res = await classifier.classify_bookmark(bookmark)
        bookmark.category = res["category"]
        bookmark.tags = res["tags"]
        bookmark.ai_summary = res["ai_summary"]
        bookmark.is_classified = True

        saved = db.upsert_bookmark(bookmark)
        typer.echo(f"✅ Guardado con éxito: #{saved.tweet_id}")
        typer.echo(f"   Autor:     @{saved.author_username} ({saved.author_name})")
        typer.echo(f"   Categoría: {saved.category}")
        typer.echo(f"   Tags:      {', '.join(saved.tags)}")
        typer.echo(f"   Resumen:   {saved.ai_summary}")
        typer.echo(f"   Enlace:    {saved.tweet_url}")
        db.close()

    asyncio.run(_run())


@app.command()
def import_archive(path: str = typer.Argument(..., help="Ruta al archivo bookmarks.js o ZIP")):
    """Importa guardados desde un archivo exportado de Twitter."""
    async def _run():
        db = BookmarkDatabase(settings.db_path)
        classifier = AIClassifier()

        p = Path(path)
        if not p.exists():
            typer.echo(f"❌ Archivo no encontrado: {path}", err=True)
            raise typer.Exit(1)

        typer.echo(f"📦 Procesando archivo: {p.name} ...")
        bookmarks = ArchiveImporter.parse_bookmarks_file(p)
        typer.echo(f"   Encontrados {len(bookmarks)} guardados. Guardando en SQLite...")

        for b in bookmarks:
            db.upsert_bookmark(b)

        typer.echo("⚡ Clasificando lote inicial con IA...")
        await classifier.classify_pending_batch(db, limit=50)

        stats = db.get_stats()
        typer.echo(f"✅ Importación completada. Total guardados: {stats.total_bookmarks}")
        db.close()

    asyncio.run(_run())


@app.command()
def classify(limit: int = typer.Option(25, help="Cantidad máxima a clasificar")):
    """Clasifica con IA los guardados pendientes."""
    async def _run():
        db = BookmarkDatabase(settings.db_path)
        classifier = AIClassifier()

        typer.echo(f"⚡ Clasificando hasta {limit} guardados pendientes...")
        classified = await classifier.classify_pending_batch(db, limit=limit)
        typer.echo(f"✅ Se procesaron {len(classified)} guardados.")
        db.close()

    asyncio.run(_run())


@app.command()
def stats():
    """Muestra estadísticas actuales de la bóveda."""
    db = BookmarkDatabase(settings.db_path)
    s = db.get_stats()
    typer.echo("\n📊 Estadísticas de X-Bookmarks Organizer:")
    typer.echo(f"   Total Guardados:    {s.total_bookmarks}")
    typer.echo(f"   Clasificados IA:    {s.classified_bookmarks}")
    typer.echo(f"   Pendientes:         {s.pending_classification}")
    typer.echo("\n📁 Desglose por Categorías:")
    for cat, count in s.categories_breakdown.items():
        typer.echo(f"   - {cat:<24}: {count}")
    typer.echo()
    db.close()


@app.command()
def list_items(
    category: Optional[str] = typer.Option(None, help="Filtrar por categoría"),
    search: Optional[str] = typer.Option(None, help="Búsqueda por texto (FTS5)"),
    limit: int = typer.Option(20, help="Límite de resultados"),
):
    """Lista los bookmarks guardados en la base de datos."""
    db = BookmarkDatabase(settings.db_path)
    filters = BookmarkFilter(category=category, search=search, limit=limit)
    items = db.list_bookmarks(filters)

    if not items:
        typer.echo("No se encontraron guardados con los filtros indicados.")
        db.close()
        return

    typer.echo(f"\n🔖 Guardados ({len(items)}):")
    for b in items:
        typer.echo(f"[{b.category}] @{b.author_username}: {b.text[:80]}...")
        typer.echo(f"   👉 {b.tweet_url}\n")
    db.close()


if __name__ == "__main__":
    app()
