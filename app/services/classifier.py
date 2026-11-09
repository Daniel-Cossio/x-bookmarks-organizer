"""Servicio de clasificación inteligente y enriquecimiento con IA."""

import re
import json
from typing import Dict, Any, List, Optional
import httpx

from app.models import Bookmark, CategoryEnum, CATEGORIES_LIST
from app.config import settings
from app.storage.database import BookmarkDatabase


# Taxonomía y palabras clave heurísticas (para modo offline o fallback)
HEURISTIC_KEYWORDS = {
    CategoryEnum.AI.value: [
        "ai", "llm", "gpt", "claude", "gemini", "llama", "deepseek", "openai", "anthropic",
        "machine learning", "deep learning", "neural", "prompt", "transformer", "diffusion",
        "huggingface", "weights", "fine-tuning", "rag", "embedding", "agent", "agente"
    ],
    CategoryEnum.GAMING.value: [
        "game", "gaming", "juego", "videojuego", "playstation", "ps5", "xbox", "nintendo",
        "steam", "gameplay", "mod", "modpack", "rpg", "zomboid", "minecraft", "odin2",
        "fps", "gpu", "unreal engine", "unity"
    ],
    CategoryEnum.HUMOR.value: [
        "jaja", "meme", "humor", "risas", "chiste", "funny", "lol", "lmao", "xd",
        "comedia", "broma", "shitpost"
    ],
    CategoryEnum.DEV.value: [
        "python", "fastapi", "react", "javascript", "typescript", "rust", "golang", "docker",
        "github", "gitlab", "commit", "api", "backend", "frontend", "sqlite", "postgres",
        "linux", "bash", "terminal", "cachyos", "kernel", "css", "html"
    ],
    CategoryEnum.TECH.value: [
        "hardware", "cpu", "arm64", "snapdragon", "intel", "amd", "nvidia", "oled",
        "monitor", "xiaomi", "poco f3", "gadget", "smartphone", "laptop", "server"
    ],
    CategoryEnum.FINANCE.value: [
        "crypto", "bitcoin", "btc", "eth", "ethereum", "finanzas", "dinero", "inversion",
        "trading", "bolsa", "acciones", "mercado"
    ],
    CategoryEnum.SCIENCE.value: [
        "ciencia", "fisica", "astronomia", "espacio", "nasa", "biologia", "quimica",
        "matematica", "paper", "arxiv", "investigacion"
    ],
}


class AIClassifier:
    """Clasificador de bookmarks multi-proveedor con fallback heurístico."""

    def __init__(
        self,
        provider: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.provider = provider or settings.ai_provider
        self.groq_api_key = groq_api_key or settings.groq_api_key
        self.gemini_api_key = gemini_api_key or settings.gemini_api_key

    def classify_heuristic(self, text: str) -> Dict[str, Any]:
        """Clasificación basada en reglas y frecuencias de términos clave."""
        lower = text.lower()
        scores: Dict[str, int] = {cat: 0 for cat in HEURISTIC_KEYWORDS}

        for cat, kw_list in HEURISTIC_KEYWORDS.items():
            for kw in kw_list:
                # Búsqueda por palabra completa o subcadena clave
                pattern = rf"\b{re.escape(kw)}\b" if len(kw) <= 4 else re.escape(kw)
                matches = len(re.findall(pattern, lower))
                scores[cat] += matches * 2

        best_category = max(scores, key=scores.get)
        if scores[best_category] == 0:
            best_category = CategoryEnum.OTHER.value

        # Extraer tags sugeridos
        tags = []
        for cat, kw_list in HEURISTIC_KEYWORDS.items():
            for kw in kw_list:
                if kw in lower and kw not in tags:
                    tags.append(kw)
                if len(tags) >= 5:
                    break

        summary = f"Post relacionado con {best_category}."
        if tags:
            summary += f" Temas clave: {', '.join(tags[:3])}."

        return {
            "category": best_category,
            "tags": tags[:5],
            "ai_summary": summary,
        }

    async def classify_with_groq(self, text: str, author: str) -> Dict[str, Any]:
        """Clasificación mediante Groq API con Llama 3.3 70B."""
        if not self.groq_api_key:
            return self.classify_heuristic(text)

        system_prompt = (
            "Eres un categorizador de contenido de Twitter / X. "
            f"Debes clasificar el post en EXACTAMENTE UNA de estas categorías: {CATEGORIES_LIST}. "
            "Responde estrictamente en formato JSON con las claves: "
            "'category' (string), 'tags' (lista de 2-4 strings en minúsculas), 'ai_summary' (string en español de máx 2 frases explicando de qué trata y qué recurso aporta)."
        )
        user_prompt = f"Autor: @{author}\nTexto del tweet:\n{text}"

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                cat = parsed.get("category", CategoryEnum.OTHER.value)
                if cat not in CATEGORIES_LIST:
                    cat = CategoryEnum.OTHER.value
                return {
                    "category": cat,
                    "tags": parsed.get("tags", []),
                    "ai_summary": parsed.get("ai_summary", ""),
                }
        return self.classify_heuristic(text)

    async def classify_with_gemini(self, text: str, author: str) -> Dict[str, Any]:
        """Clasificación mediante Google Gemini API."""
        if not self.gemini_api_key:
            return self.classify_heuristic(text)

        prompt = (
            "Eres un categorizador de tweets para una bóveda personal. "
            f"Clasifica el siguiente post en una de estas categorías: {CATEGORIES_LIST}. "
            "Responde únicamente un JSON válido con: "
            '{"category": "...", "tags": ["tag1", "tag2"], "ai_summary": "resumen en español de 1-2 frases"}\n\n'
            f"Autor: @{author}\nTweet: {text}"
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={self.gemini_api_key}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            if resp.status_code == 200:
                res_data = resp.json()
                text_out = res_data["candidates"][0]["content"]["parts"][0]["text"]
                clean_json = re.search(r"\{.*\}", text_out, re.DOTALL)
                if clean_json:
                    parsed = json.loads(clean_json.group(0))
                    cat = parsed.get("category", CategoryEnum.OTHER.value)
                    if cat not in CATEGORIES_LIST:
                        cat = CategoryEnum.OTHER.value
                    return {
                        "category": cat,
                        "tags": parsed.get("tags", []),
                        "ai_summary": parsed.get("ai_summary", ""),
                    }
        return self.classify_heuristic(text)

    async def classify_bookmark(self, bookmark: Bookmark) -> Dict[str, Any]:
        """Clasifica un bookmark según el proveedor configurado."""
        if self.provider == "groq" and self.groq_api_key:
            try:
                return await self.classify_with_groq(bookmark.text, bookmark.author_username)
            except Exception:
                pass
        elif self.provider == "gemini" and self.gemini_api_key:
            try:
                return await self.classify_with_gemini(bookmark.text, bookmark.author_username)
            except Exception:
                pass

        # Fallback heurístico predeterminado y seguro
        return self.classify_heuristic(bookmark.text)

    async def classify_pending_batch(
        self, db: BookmarkDatabase, limit: int = 20
    ) -> List[Bookmark]:
        """Procesa un lote de bookmarks pendientes de clasificación."""
        pending = db.get_unclassified(limit=limit)
        classified: List[Bookmark] = []

        for b in pending:
            result = await self.classify_bookmark(b)
            updated = db.update_classification(
                tweet_id=b.tweet_id,
                category=result["category"],
                tags=result["tags"],
                ai_summary=result["ai_summary"],
            )
            if updated:
                classified.append(updated)

        return classified
