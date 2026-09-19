document.addEventListener("DOMContentLoaded", () => {
  const grid = document.querySelector("#articles-grid");
  if (grid) {
    fetch("data/articles.json")
      .then((res) => res.json())
      .then((data) => {
        const articles = (data.articles || []).slice().sort(sortByDateDesc);
        if (articles.length === 0) {
          grid.innerHTML = "<p>Aucun article pour le moment — revenez bientôt !</p>";
          return;
        }
        grid.innerHTML = articles.map(renderArticleCard).join("");
      })
      .catch(() => {
        grid.innerHTML = "<p>Impossible de charger les articles pour le moment.</p>";
      });
  }

  const content = document.querySelector("#article-content");
  if (content) {
    const slug = new URLSearchParams(window.location.search).get("slug") || "";
    fetch("data/articles.json")
      .then((res) => res.json())
      .then((data) => {
        const article = (data.articles || []).find((a) => a.slug === slug);
        if (!article) {
          content.innerHTML = "<p>Cet article n'existe pas ou plus.</p>";
          return;
        }
        document.title = `${article.titre} — Chatterie Epic Claws`;
        content.innerHTML = renderArticleContent(article);
      })
      .catch(() => {
        content.innerHTML = "<p>Impossible de charger cet article pour le moment.</p>";
      });
  }
});

function sortByDateDesc(a, b) {
  return new Date(b.date || 0) - new Date(a.date || 0);
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

function renderArticleCard(article) {
  const bg = article.image ? escapeHtml(article.image) : "images/logo.avif";
  return `
    <a class="teaser-card article-card" style="background-image:url('${bg}')" href="article.html?slug=${encodeURIComponent(article.slug || "")}">
      <div class="teaser-body">
        <span class="article-date">${escapeHtml(formatDate(article.date))}</span>
        <h3>${escapeHtml(article.titre || "")}</h3>
        <p>${escapeHtml(article.extrait || "")}</p>
        <span class="teaser-link">Lire la suite →</span>
      </div>
    </a>
  `;
}

function renderArticleContent(article) {
  const cover = article.image
    ? `<img class="article-cover" src="${escapeHtml(article.image)}" alt="${escapeHtml(article.titre || "")}">`
    : "";
  const bodyHtml = window.marked ? marked.parse(article.corps || "") : escapeHtml(article.corps || "");
  return `
    <div class="article-header">
      <span class="article-date">${escapeHtml(formatDate(article.date))}</span>
      <h1>${escapeHtml(article.titre || "")}</h1>
    </div>
    ${cover}
    <div class="article-body">${bodyHtml}</div>
  `;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
