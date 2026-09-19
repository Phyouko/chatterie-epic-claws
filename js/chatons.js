document.addEventListener("DOMContentLoaded", () => {
  const grid = document.querySelector("#kittens-grid");
  if (grid) {
    fetch("data/chatons.json")
      .then((res) => res.json())
      .then((data) => {
        const chatons = data.chatons || [];
        if (chatons.length === 0) {
          grid.innerHTML = "";
          return;
        }
        grid.innerHTML = chatons.map(renderKittenCard).join("");
      })
      .catch(() => {
        grid.innerHTML = "<p>Impossible de charger les chatons disponibles pour le moment.</p>";
      });
  }

  const fiche = document.querySelector("#fiche-chaton");
  if (fiche) {
    const nom = new URLSearchParams(window.location.search).get("nom") || "";
    Promise.all([
      fetch("data/chatons.json").then((res) => res.json()),
      fetch("data/reproductrices.json").then((res) => res.json()).catch(() => ({ reproductrices: [] })),
      fetch("data/reproducteurs.json").then((res) => res.json()).catch(() => ({ reproducteurs: [] })),
    ])
      .then(([chatonsData, femellesData, malesData]) => {
        const chaton = (chatonsData.chatons || []).find((c) => c.nom === nom);
        if (!chaton) {
          fiche.innerHTML = "<p>Ce chaton n'est plus disponible ou la fiche demandée n'existe pas.</p>";
          return;
        }
        const parentLinks = buildParentLinks(femellesData.reproductrices || [], malesData.reproducteurs || []);
        document.title = `${chaton.nom} — Chatterie Epic Claws`;
        const titleEl = document.querySelector("#fiche-titre");
        if (titleEl) titleEl.textContent = chaton.nom;
        fiche.innerHTML = renderKittenFiche(chaton, parentLinks);
      })
      .catch(() => {
        fiche.innerHTML = "<p>Impossible de charger cette fiche pour le moment.</p>";
      });
  }
});

function buildParentLinks(reproductrices, reproducteurs) {
  const map = {};
  reproductrices.forEach((c) => {
    if (c.nom) map[c.nom] = `reproductrices.html#${slugify(c.nom)}`;
  });
  reproducteurs.forEach((c) => {
    if (c.nom) map[c.nom] = `reproducteurs.html#${slugify(c.nom)}`;
  });
  return map;
}

function slugify(str) {
  return String(str)
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function renderKittenCard(chaton) {
  const isReserved = chaton.statut === "Réservé";
  const statusClass = isReserved ? "kitten-status reserved" : "kitten-status";
  const nom = chaton.nom || "";
  const fiche = `chaton.html?nom=${encodeURIComponent(nom)}`;
  const photo = chaton.photo
    ? `<img src="${escapeHtml(chaton.photo)}" alt="${escapeHtml(nom)}">`
    : `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="9" r="2"/><circle cx="10.5" cy="6.2" r="2"/><circle cx="15.5" cy="6.2" r="2"/><circle cx="19" cy="9" r="2"/><path d="M12.5 11c3 0 5.5 2.2 5.5 4.6 0 1.9-1.6 3.4-3.6 3.4-1 0-1.6-.4-2.4-.4s-1.4.4-2.4.4c-2 0-3.6-1.5-3.6-3.4C6.5 13.2 9 11 12.5 11Z"/></svg>`;

  return `
    <article class="kitten-card">
      <a href="${fiche}" class="kitten-photo" aria-label="Voir la fiche de ${escapeHtml(nom)}">
        <span class="${statusClass}">${escapeHtml(chaton.statut || "Disponible")}</span>
        ${photo}
      </a>
      <div class="kitten-body">
        <h3>${escapeHtml(nom)}</h3>
        <ul class="kitten-facts">
          <li><strong>Sexe :</strong> ${escapeHtml(chaton.sexe || "à préciser")}</li>
          <li><strong>Couleur :</strong> ${escapeHtml(chaton.couleur || "à préciser")}</li>
          <li><strong>Date de naissance :</strong> ${escapeHtml(chaton.date_naissance || "à préciser")}</li>
          <li><strong>Prix :</strong> ${escapeHtml(chaton.prix || "nous consulter")}</li>
        </ul>
        <div class="kitten-actions">
          <a href="${fiche}" class="btn btn-outline btn-block">Voir sa fiche</a>
          <a href="contact.html?sujet=adoption&nom=${encodeURIComponent(nom)}" class="btn btn-primary btn-block">Je suis intéressé(e)</a>
        </div>
      </div>
    </article>
  `;
}

function renderKittenFiche(chaton, parentLinks) {
  parentLinks = parentLinks || {};
  const isReserved = chaton.statut === "Réservé";
  const statusClass = isReserved ? "kitten-status reserved" : "kitten-status";
  const nom = chaton.nom || "";
  const photo = chaton.photo
    ? `<img src="${escapeHtml(chaton.photo)}" alt="${escapeHtml(nom)}">`
    : `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="9" r="2"/><circle cx="10.5" cy="6.2" r="2"/><circle cx="15.5" cy="6.2" r="2"/><circle cx="19" cy="9" r="2"/><path d="M12.5 11c3 0 5.5 2.2 5.5 4.6 0 1.9-1.6 3.4-3.6 3.4-1 0-1.6-.4-2.4-.4s-1.4.4-2.4.4c-2 0-3.6-1.5-3.6-3.4C6.5 13.2 9 11 12.5 11Z"/></svg>`;

  const ligneeRow = chaton.lignee
    ? `<div><dt>Lignée</dt><dd>${escapeHtml(chaton.lignee)}</dd></div>`
    : "";
  const caractereHtml = chaton.caractere
    ? `<p class="cat-character">« ${escapeHtml(chaton.caractere)} »</p>`
    : "";
  const parentName = (n) => (parentLinks[n] ? `<a href="${parentLinks[n]}">${escapeHtml(n)}</a>` : escapeHtml(n));
  const parentsHtml = chaton.pere || chaton.mere
    ? `<p class="cat-parents">
        ${chaton.pere ? `<strong>Père :</strong> ${parentName(chaton.pere)}<br>` : ""}
        ${chaton.mere ? `<strong>Mère :</strong> ${parentName(chaton.mere)}` : ""}
      </p>`
    : "";

  return `
    <article class="cat-card">
      <div class="cat-photo">
        <span class="${statusClass}">${escapeHtml(chaton.statut || "Disponible")}</span>
        ${photo}
      </div>
      <div class="cat-body">
        <div class="cat-name-row">
          <h3>${escapeHtml(nom)}</h3>
        </div>
        <dl class="cat-facts">
          <div><dt>Sexe</dt><dd>${escapeHtml(chaton.sexe || "à préciser")}</dd></div>
          <div><dt>Couleur</dt><dd>${escapeHtml(chaton.couleur || "à préciser")}</dd></div>
          ${ligneeRow}
          <div><dt>Date de naissance</dt><dd>${escapeHtml(chaton.date_naissance || "à préciser")}</dd></div>
          <div><dt>Prix</dt><dd>${escapeHtml(chaton.prix || "nous consulter")}</dd></div>
        </dl>
        ${caractereHtml}
        ${parentsHtml}
        <a href="contact.html?sujet=adoption&nom=${encodeURIComponent(nom)}" class="btn btn-primary" style="margin-top:1.4rem">Je suis intéressé(e) par ${escapeHtml(nom)}</a>
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
