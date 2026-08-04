/**
 * Prefa.News — front-end v2 (vanilla JS, sem jQuery/plugins).
 * Substitui assets/js/functions.js, news.js, star_news.js e os
 * ~6 arquivos news_sector_*.js duplicados por região da versão antiga.
 */
(function () {
  "use strict";

  const API_BASE = "/api";

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  // ---- Abas de região na home ----
  function initSectorTabs() {
    const tabs = qsa(".tab-btn");
    if (!tabs.length) return;
    tabs.forEach((btn) => {
      btn.addEventListener("click", () => {
        tabs.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        qsa(".sector-panel").forEach((p) => p.classList.remove("active"));
        const panel = qs('.sector-panel[data-panel="' + btn.dataset.tab + '"]');
        if (panel) panel.classList.add("active");
      });
    });
  }

  // ---- Registro de clique + abertura da notícia em nova aba ----
  function initNewsCardClicks() {
    document.addEventListener("click", (event) => {
      const card = event.target.closest(".news-card");
      if (!card) return;
      // Evita duplo-disparo quando o clique já foi no link interno
      if (event.target.closest(".news-open-link")) return;

      const newsId = card.dataset.newsId;
      const link = card.dataset.newsLink;
      if (newsId) {
        fetch(API_BASE + "/access", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ news_id: Number(newsId), type: "card" }),
        }).catch(() => {});
      }
      if (link) window.open(link, "_blank", "noopener");
    });
  }

  // ---- Scroll infinito nas páginas de região ----
  function initLoadMore() {
    const btn = qs("#load-more-btn");
    const grid = qs("#region-news-grid");
    if (!btn || !grid) return;

    const sector = grid.dataset.sectorSlug;
    const sectorMap = {
      sul: "SUL",
      grandefloripa: "GRANDE FLORIPA",
      norte: "NORTE",
      oeste: "OESTE",
      serrana: "SERRANA",
      vale: "VALE",
    };
    const sectorParam = sectorMap[sector] || "";

    btn.addEventListener("click", async () => {
      const pointer = Number(btn.dataset.pointer || 0);
      btn.disabled = true;
      btn.textContent = "Carregando…";
      try {
        const url = new URL(API_BASE + "/news/more", window.location.origin);
        url.searchParams.set("pointer", pointer);
        if (sectorParam) url.searchParams.set("sector", sectorParam);
        const resp = await fetch(url);
        const items = await resp.json();
        if (!items.length) {
          btn.textContent = "Não há mais notícias";
          btn.disabled = true;
          return;
        }
        items.forEach((item) => grid.appendChild(renderCard(item)));
        btn.dataset.pointer = pointer + 4;
        btn.disabled = false;
        btn.textContent = "Carregar mais notícias";
      } catch (err) {
        console.error(err);
        btn.textContent = "Erro ao carregar. Tente novamente.";
        btn.disabled = false;
      }
    });
  }

  function renderCard(item) {
    const article = document.createElement("article");
    const regCode = (item.reg_code || "").trim();
    article.className = "news-card region-" + regCode;
    article.dataset.newsId = item.id;
    article.dataset.newsLink = item.link;

    const date = new Date(item.date);
    const dateLabel = isNaN(date) ? "" : date.toLocaleDateString("pt-BR");

    article.innerHTML =
      '<div class="news-card__eyebrow">' +
      '<span class="region-tag">' + escapeHtml(item.city) + "</span>" +
      "<time>" + dateLabel + "</time>" +
      "</div>" +
      '<h3 class="news-card__title"><a class="news-open-link" href="' + item.link +
      '" target="_blank" rel="noopener noreferrer">' + escapeHtml(item.title) + "</a></h3>" +
      (item.description
        ? '<p class="news-card__excerpt">' + escapeHtml(item.description).slice(0, 160) + "…</p>"
        : "");
    return article;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  // ---- Newsletter ----
  function initNewsletterForm() {
    const form = qs("#newsletter-form");
    const feedback = qs("#newsletter-feedback");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const mail = form.querySelector('input[name="mail"]').value;
      feedback.textContent = "Enviando…";
      try {
        const resp = await fetch(API_BASE + "/newsletter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mail: mail }),
        });
        const data = await resp.json();
        if (resp.ok) {
          feedback.textContent = "E-mail cadastrado com sucesso!";
          form.reset();
        } else {
          feedback.textContent = data.detail || "Não foi possível cadastrar o e-mail.";
        }
      } catch (err) {
        feedback.textContent = "Erro de conexão. Tente novamente.";
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initSectorTabs();
    initNewsCardClicks();
    initLoadMore();
    initNewsletterForm();
  });
})();
