document.addEventListener("DOMContentLoaded", () => {
  const femellesGrid = document.querySelector("#reproductrices-grid");
  if (femellesGrid) {
    fetch("data/reproductrices.json")
      .then((res) => res.json())
      .then((data) => {
        femellesGrid.innerHTML = (data.reproductrices || []).map((c) => renderCatCard(c, false)).join("");
      })
      .catch(() => {
        femellesGrid.innerHTML = "<p>Impossible de charger les reproductrices pour le moment.</p>";
      });
  }

  const malesGrid = document.querySelector("#reproducteurs-grid");
  if (malesGrid) {
    fetch("data/reproducteurs.json")
      .then((res) => res.json())
      .then((data) => {
        malesGrid.innerHTML = (data.reproducteurs || []).map((c) => renderCatCard(c, true)).join("");
      })
      .catch(() => {
        malesGrid.innerHTML = "<p>Impossible de charger les reproducteurs pour le moment.</p>";
      });
  }
});

function renderCatCard(cat, isMale) {
  const nom = cat.nom || "";
  const priceHtml = cat.prix_saillie
    ? `<span class="cat-price">Saillie — ${escapeHtml(cat.prix_saillie)}&nbsp;€</span>`
    : "";
  const titreHtml = cat.titre
    ? `<div><dt>Titre</dt><dd>${escapeHtml(cat.titre)}</dd></div>`
    : "";
  const ctaHtml = isMale
    ? `<a href="contact.html?sujet=saillie&nom=${encodeURIComponent(nom)}" class="btn btn-primary" style="margin-top:1.4rem">Demander une saillie avec ${escapeHtml(nom)}</a>`
    : "";
  const alt = `${escapeHtml(nom)}, ${isMale ? "mâle reproducteur" : "chatte reproductrice"} Maine Coon`;

  return `
    <article class="cat-card">
      <div class="cat-photo">
        <img src="${escapeHtml(cat.photo || "")}" alt="${alt}">
      </div>
      <div class="cat-body">
        <div class="cat-name-row">
          <h3>${escapeHtml(nom)}</h3>
          ${priceHtml}
        </div>
        <span class="cattery">${escapeHtml(cat.chatterie_origine || "")}</span>
        <dl class="cat-facts">
          <div><dt>Couleur</dt><dd>${escapeHtml(cat.couleur || "")}</dd></div>
          <div><dt>Lignée</dt><dd>${escapeHtml(cat.lignee || "")}</dd></div>
          <div><dt>Date de naissance</dt><dd>${escapeHtml(cat.date_naissance || "")}</dd></div>
          ${titreHtml}
        </dl>
        <p class="cat-character">« ${escapeHtml(cat.caractere || "")} »</p>
        <p class="cat-parents">
          <strong>Père :</strong> ${escapeHtml(cat.pere || "")}<br>
          <strong>Mère :</strong> ${escapeHtml(cat.mere || "")}
        </p>
        ${ctaHtml}
      </div>
    </article>
  `;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
