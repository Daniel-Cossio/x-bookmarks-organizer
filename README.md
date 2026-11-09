# X-Bookmarks Organizer (Idea #005)

Sistema inteligente para capturar, almacenar, clasificar con IA y explorar los tweets guardados (Bookmarks) de Twitter / X con acceso directo a cada post original y búsqueda instantánea FTS5.

---

## 🚀 Características Principales

1. **Ingesta Híbrida de Guardados**:
   - **Sincronización Web directa (GraphQL)**: Conexión mediante cookies de sesión de X (`auth_token` y `ct0`) sin depender de la API oficial de pago v2.
   - **Importador de Twitter Archive**: Soporte nativo para archivos descargados de Twitter (`bookmarks.js` o ZIP completo).
   - **Ingesta individual**: Guarda cualquier post instantáneamente a partir de su enlace (`https://x.com/.../status/...`) vía Web o CLI.
2. **Clasificación y Enriquecimiento con IA**:
   - Taxonomía estructurada en 8 categorías: *Inteligencia Artificial*, *Videojuegos / Gaming*, *Humor / Memes*, *Desarrollo / Software*, *Hardware / Tech*, *Ciencia*, *Finanzas / Crypto* y *Otros*.
   - Proveedores soportados: **Groq** (`llama-3.3-70b-versatile`), **Gemini Flash** (`gemini-2.5-flash`), y **Motor Heurístico offline** con detección de términos clave y expresiones regulares.
   - Resumen explicativo en español y extracción automática de recursos externos (repositorios de GitHub, papers de arXiv, videos, artículos).
3. **Persistencia & Búsqueda Instantánea**:
   - Base de datos local SQLite 3 con WAL mode y tabla virtual **FTS5** (`bookmarks_fts`) para búsqueda reactiva en texto, autor y etiquetas.
4. **Dashboard Web Mobile-First**:
   - Interfaz visual oscura accesible en el puerto `8085`.
   - Botón prominente **`🔗 Ver en X`** en cada tarjeta que redirige exactamente al post original.
   - Píldoras de filtrado por categoría con contadores en tiempo real.
   - Enlace directo bidireccional hacia **IdeaHub** (`🧠 IdeaHub`).
5. **Integración con IdeaHub**:
   - Asociado a la **Idea #005** en IdeaHub mediante `app_url = "http://localhost:8085"`.
   - Botón directo `🚀 Abrir App` en el card Kanban de IdeaHub y en su menú de cabecera `🚀 Apps`.

---

## 🛠️ Instalación y Uso

### 1. Entorno Virtual y Dependencias
```bash
cd /home/ubuntu/Documentos/git/x-bookmarks-organizer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configuración (`.env.local`)
Copia `.env.example` a `.env.local` y configura tus opciones opcionales:
```ini
HOST=0.0.0.0
PORT=8085
AI_PROVIDER=heuristic # o groq | gemini
GROQ_API_KEY=
TWITTER_AUTH_TOKEN= # opcional para sync masivo
TWITTER_CT0=        # opcional para sync masivo
```

### 3. Comandos CLI
```bash
# Iniciar servidor web en http://localhost:8085
python3 app/cli.py serve --port 8085

# Ver estadísticas de la bóveda
python3 app/cli.py stats

# Listar guardados por categoría o búsqueda
python3 app/cli.py list-items --category "Inteligencia Artificial"

# Guardar un post puntual por URL
python3 app/cli.py add "https://x.com/karpathy/status/1852441112223334445"

# Clasificar pendientes con IA
python3 app/cli.py classify --limit 25

# Importar exportación de Twitter
python3 app/cli.py import-archive "/ruta/a/bookmarks.js"
```

### 4. Pruebas Automatizadas
```bash
pytest tests/ -v
```
