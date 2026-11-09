/* ============================================================
   X-Bookmarks Hub — Lógica Frontend Reactiva
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  let activeCategory = "all";
  let searchTimeout = null;

  // Elementos DOM
  const gridEl = document.getElementById("bookmarks-grid");
  const emptyEl = document.getElementById("empty-state");
  const searchInput = document.getElementById("search-input");
  const btnClearSearch = document.getElementById("btn-clear-search");
  const toggleHasLinks = document.getElementById("toggle-has-links");
  const toggleHasMedia = document.getElementById("toggle-has-media");
  const resultsInfo = document.getElementById("results-info");

  // Stats
  const statTotal = document.getElementById("stat-total");
  const statClassified = document.getElementById("stat-classified");
  const statPending = document.getElementById("stat-pending");

  // Modales
  const modalAdd = document.getElementById("modal-add");
  const modalSync = document.getElementById("modal-sync");
  const modalImport = document.getElementById("modal-import");

  const formAdd = document.getElementById("form-add");
  const inputTweetUrl = document.getElementById("input-tweet-url");
  const selectManualCat = document.getElementById("select-manual-cat");

  const formImport = document.getElementById("form-import");
  const inputArchivePath = document.getElementById("input-archive-path");

  // Helpers de escape HTML
  function esc(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Notificaciones Toast
  function showToast(message, isError = false) {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    if (isError) toast.style.borderColor = "var(--danger)";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 200);
    }, 3500);
  }

  // API Client
  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Error en la petición");
    }
    return res.json();
  }

  // Cargar Categorías en el Select
  async function loadCategories() {
    try {
      const cats = await api("/api/categories");
      selectManualCat.innerHTML = '<option value="">✨ Auto-detectar con IA</option>' +
        cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
    } catch (_) {}
  }

  // Cargar Estadísticas
  async function loadStats() {
    try {
      const s = await api("/api/stats");
      statTotal.textContent = String(s.total_bookmarks);
      statClassified.textContent = String(s.classified_bookmarks);
      statPending.textContent = String(s.pending_classification);

      document.getElementById("count-all").textContent = String(s.total_bookmarks);
      
      const b = s.categories_breakdown;
      const map = {
        "count-ai": b["Inteligencia Artificial"] || 0,
        "count-gaming": b["Videojuegos / Gaming"] || 0,
        "count-humor": b["Humor / Memes"] || 0,
        "count-dev": b["Desarrollo / Software"] || 0,
        "count-tech": b["Hardware / Tech"] || 0,
        "count-science": b["Ciencia"] || 0,
        "count-finance": b["Finanzas / Crypto"] || 0,
        "count-other": b["Otros / General"] || 0,
      };

      for (const [id, count] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el) el.textContent = String(count);
      }
    } catch (_) {}
  }

  // Cargar y Renderizar Bookmarks
  async function loadBookmarks() {
    const params = new URLSearchParams();
    if (activeCategory !== "all") {
      params.append("category", activeCategory);
    }
    const q = searchInput.value.trim();
    if (q) params.append("search", q);
    if (toggleHasLinks.checked) params.append("has_links", "true");
    if (toggleHasMedia.checked) params.append("has_media", "true");

    try {
      const items = await api(`/api/bookmarks?${params.toString()}`);
      renderGrid(items);
      resultsInfo.textContent = `Mostrando ${items.length} guardados`;
      loadStats();
    } catch (err) {
      showToast(err.message, true);
    }
  }

  function renderGrid(items) {
    gridEl.innerHTML = "";
    if (items.length === 0) {
      emptyEl.classList.remove("hidden");
      return;
    }
    emptyEl.classList.add("hidden");

    for (const b of items) {
      const card = document.createElement("article");
      card.className = "bookmark-card";
      card.dataset.id = b.tweet_id;

      // Avatar o inicial
      const initial = (b.author_name || b.author_username || "X").charAt(0).toUpperCase();
      const avatarHtml = b.author_avatar
        ? `<img src="${esc(b.author_avatar)}" alt="${esc(b.author_name)}" class="author-avatar" onerror="this.outerHTML='<div class=\\'author-avatar\\'>${initial}</div>'"/>`
        : `<div class="author-avatar">${initial}</div>`;

      // Enlaces externos
      let externalHtml = "";
      if (b.external_urls && b.external_urls.length > 0) {
        externalHtml = `<div class="external-links-box">` +
          b.external_urls.map(u => {
            let label = u.replace(/^https?:\/\//, "");
            if (label.length > 36) label = label.substring(0, 33) + "...";
            return `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer" class="ext-link-item" title="${esc(u)}">🔗 ${esc(label)}</a>`;
          }).join("") +
          `</div>`;
      }

      // Resumen IA
      let aiSummaryHtml = "";
      if (b.ai_summary) {
        aiSummaryHtml = `
          <div class="ai-summary-box">
            <span class="ai-summary-header">✨ Resumen IA</span>
            <div>${esc(b.ai_summary)}</div>
          </div>`;
      }

      // Media
      let mediaHtml = "";
      if (b.media_urls && b.media_urls.length > 0) {
        mediaHtml = `
          <div class="card-media">
            <img src="${esc(b.media_urls[0])}" alt="Tweet media" loading="lazy" />
          </div>`;
      }

      // Tags
      const tagsHtml = b.tags && b.tags.length > 0
        ? `<div style="font-size:0.75rem; color:var(--text-subtle);"># ${b.tags.map(t => esc(t)).join("  # ")}</div>`
        : "";

      card.innerHTML = `
        <div class="card-top">
          <div class="author-block">
            ${avatarHtml}
            <div class="author-info">
              <span class="author-name">${esc(b.author_name || b.author_username)}</span>
              <span class="author-handle">@${esc(b.author_username)}</span>
            </div>
          </div>
          <span class="cat-badge" data-cat="${esc(b.category)}">${esc(b.category)}</span>
        </div>

        <div class="card-text">${esc(b.text)}</div>

        ${mediaHtml}
        ${externalHtml}
        ${aiSummaryHtml}
        ${tagsHtml}

        <div class="card-footer">
          <a href="${esc(b.tweet_url)}" target="_blank" rel="noopener noreferrer" class="btn-open-x" title="Abrir post original en Twitter / X">
            <span>🔗</span> Ver en X
          </a>
          <div class="card-tools">
            <button class="btn-tool" data-action="edit" title="Editar categoría">✏️</button>
            <button class="btn-tool danger" data-action="delete" title="Eliminar guardado">🗑️</button>
          </div>
        </div>
      `;

      // Eventos de botones
      card.querySelector('[data-action="delete"]').addEventListener("click", async () => {
        if (confirm(`¿Eliminar el post guardado de @${b.author_username}?`)) {
          try {
            await api(`/api/bookmarks/${b.tweet_id}`, { method: "DELETE" });
            showToast("Guardado eliminado");
            loadBookmarks();
          } catch (e) {
            showToast(e.message, true);
          }
        }
      });

      card.querySelector('[data-action="edit"]').addEventListener("click", async () => {
        const newCat = prompt(`Nueva categoría para este tweet (${CATEGORIES_SAMPLE.join(', ')}):`, b.category);
        if (newCat && newCat.trim() !== b.category) {
          try {
            await api(`/api/bookmarks/${b.tweet_id}`, {
              method: "PUT",
              body: JSON.stringify({ category: newCat.trim() }),
            });
            showToast("Categoría actualizada");
            loadBookmarks();
          } catch (e) {
            showToast(e.message, true);
          }
        }
      });

      gridEl.appendChild(card);
    }
  }

  const CATEGORIES_SAMPLE = [
    "Inteligencia Artificial", "Videojuegos / Gaming", "Humor / Memes",
    "Desarrollo / Software", "Hardware / Tech", "Ciencia", "Finanzas / Crypto", "Otros / General"
  ];

  // Filtro por píldoras de Categoría
  document.querySelectorAll(".cat-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".cat-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      activeCategory = pill.dataset.cat;
      loadBookmarks();
    });
  });

  // Búsqueda en tiempo real con debounce
  searchInput.addEventListener("input", () => {
    btnClearSearch.classList.toggle("hidden", !searchInput.value);
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(loadBookmarks, 250);
  });

  btnClearSearch.addEventListener("click", () => {
    searchInput.value = "";
    btnClearSearch.classList.add("hidden");
    loadBookmarks();
  });

  toggleHasLinks.addEventListener("change", loadBookmarks);
  toggleHasMedia.addEventListener("change", loadBookmarks);

  // Manejo de Modales
  function setupModal(modalEl, btnOpenId, btnCloseId, backdropId, btnCancelId) {
    const btnOpen = document.getElementById(btnOpenId);
    const btnClose = document.getElementById(btnCloseId);
    const backdrop = document.getElementById(backdropId);
    const btnCancel = btnCancelId ? document.getElementById(btnCancelId) : null;

    const open = () => modalEl.classList.remove("hidden");
    const close = () => modalEl.classList.add("hidden");

    if (btnOpen) btnOpen.addEventListener("click", open);
    if (btnClose) btnClose.addEventListener("click", close);
    if (backdrop) backdrop.addEventListener("click", close);
    if (btnCancel) btnCancel.addEventListener("click", close);
    return { open, close };
  }

  const modalAddCtrl = setupModal(modalAdd, "btn-open-add", "btn-close-add", "backdrop-add", "btn-cancel-add");
  const modalSyncCtrl = setupModal(modalSync, "btn-open-sync", "btn-close-sync", "backdrop-sync", "btn-cancel-sync");
  const modalImportCtrl = setupModal(modalImport, "btn-open-import", "btn-close-import", "backdrop-import", "btn-cancel-import");

  // Enviar formulario: Guardar Tweet por URL
  formAdd.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = inputTweetUrl.value.trim();
    if (!url) return;

    const cat = selectManualCat.value || undefined;
    const submitBtn = document.getElementById("btn-submit-add");
    submitBtn.disabled = true;
    submitBtn.textContent = "Extrayendo...";

    try {
      await api("/api/bookmarks", {
        method: "POST",
        body: JSON.stringify({ url, category: cat }),
      });
      showToast("✅ Post guardado y analizado con éxito");
      inputTweetUrl.value = "";
      modalAddCtrl.close();
      loadBookmarks();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Guardar y Analizar";
    }
  });

  // Ejecutar Clasificación IA en Lote
  document.getElementById("btn-classify").addEventListener("click", async () => {
    const btn = document.getElementById("btn-classify");
    btn.disabled = true;
    btn.innerHTML = "<span>⏳</span> <span>Procesando...</span>";
    try {
      const res = await api("/api/classify?limit=25", { method: "POST" });
      showToast(res.message);
      loadBookmarks();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = "<span>⚡</span> <span>Clasificar IA</span>";
    }
  });

  // Ejecutar Sincronización X
  document.getElementById("btn-exec-sync").addEventListener("click", async () => {
    const btn = document.getElementById("btn-exec-sync");
    const count = document.getElementById("sync-count").value;
    btn.disabled = true;
    btn.textContent = "Sincronizando...";
    try {
      const res = await api(`/api/sync?count=${count}`, { method: "POST" });
      showToast(res.message, res.status !== "success");
      modalSyncCtrl.close();
      loadBookmarks();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "Iniciar Sincronización";
    }
  });

  // Ejecutar Importación Archivo
  formImport.addEventListener("submit", async (e) => {
    e.preventDefault();
    const filePath = inputArchivePath.value.trim();
    if (!filePath) return;

    const btn = document.getElementById("btn-exec-import");
    btn.disabled = true;
    btn.textContent = "Importando...";
    try {
      const res = await api(`/api/import-file?file_path=${encodeURIComponent(filePath)}`, { method: "POST" });
      showToast(res.message);
      modalImportCtrl.close();
      inputArchivePath.value = "";
      loadBookmarks();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = "Importar Guardados";
    }
  });

  // Inicialización
  loadCategories();
  loadBookmarks();
});
