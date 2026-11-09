# X-Bookmarks Organizer (Idea 005)

## 1. Especificación Técnica
Sistema para capturar, almacenar, clasificar y visualizar de forma enriquecida los tweets guardados (Bookmarks) de Twitter / X.

### Objetivos Principales:
1. **Ingesta**:
   - Extracción directa mediante GraphQL interno con cookies de sesión (`auth_token`, `ct0`).
   - Importación de exportaciones descargadas de Twitter (`bookmarks.js` o ZIP).
   - Ingesta directa de URLs de tweets.
2. **Clasificación y Enriquecimiento con IA**:
   - Clasificación por categorías (*Inteligencia Artificial*, *Videojuegos / Gaming*, *Humor / Memes*, *Desarrollo de Software*, *Hardware / Gadgets*, *Ciencia*, etc.).
   - Resumen en español para tweets en otros idiomas.
   - Detección y extracción de enlaces relevantes (repositorios de GitHub, papers arXiv, videos, herramientas).
3. **Persistencia & Búsqueda**:
   - Base de datos SQLite con tabla virtual FTS5 para búsqueda instantánea en texto, autor y etiquetas.
4. **Dashboard Web**:
   - Interfaz moderna, mobile-first y dark-mode accesible en el puerto 8085.
   - Enlace directo a cada post en X (`https://x.com/.../status/...`).
   - Filtros por categoría y barra de búsqueda reactiva.
5. **Ecosistema**:
   - Integración directa con IdeaHub mediante `app_url = "http://localhost:8085"`.
