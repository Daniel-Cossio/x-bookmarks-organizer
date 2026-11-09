"""Aplicación principal FastAPI para X-Bookmarks Organizer."""

import sys
from pathlib import Path

# Asegurar raíz en sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import settings

app = FastAPI(
    title="X-Bookmarks Organizer",
    description="Organizador inteligente de guardados de Twitter / X con IA y búsqueda FTS5",
    version="0.1.0",
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar API
app.include_router(api_router)

# Montar interfaz Web
web_dir = Path(__file__).resolve().parent.parent / "web"
web_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/")
def serve_index():
    """Sirve la aplicación de frontend."""
    index_file = web_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "X-Bookmarks Organizer API activa", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
