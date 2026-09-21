document.addEventListener("DOMContentLoaded", () => {
  const grid = document.querySelector("#kittens-grid");
  if (grid) {
    fetch("data/chatons.json")
      .then((res) => res.json())
      .then((data) => {
        const chatons = (data.chatons || []).filter((c) => c.visible !== false);
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
        const allChatons = chatonsData.chatons || [];
        const chaton = allChatons.find((c) => c.nom === nom);
        if (!chaton) {
          fiche.innerHTML = `<section class="section section-light"><div class="container"><p>Ce chaton n'est plus disponible ou la fiche demandée n'existe pas.</p><a href="chatons.html" class="btn btn-outline">← Voir tous les chatons disponibles</a></div></section>`;
          return;
        }
        const parentIndex = buildParentIndex(femellesData.reproductrices || [], malesData.reproducteurs || []);
        document.title = `${chaton.nom} — Chatterie Epic Claws`;
        fiche.innerHTML = renderFullFiche(chaton, parentIndex, allChatons);
        initFicheGallery(fiche);
      })
      .catch(() => {
        fiche.innerHTML = `<section class="section section-light"><div class="container"><p>Impossible de charger cette fiche pour le moment.</p></div></section>`;
      });
  }
});

function buildParentIndex(reproductrices, reproducteurs) {
  const map = {};
  reproductrices.forEach((c) => {
    if (c.nom) map[c.nom] = { cat: c, isMale: false };
  });
  reproducteurs.forEach((c) => {
    if (c.nom) map[c.nom] = { cat: c, isMale: true };
  });
  return map;
}

function parseFrenchShortDate(dateStr) {
  const m = String(dateStr || "").match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return null;
  const [, dd, mm, yyyy] = m;
  return new Date(Number(yyyy), Number(mm) - 1, Number(dd));
}

function computeReadyDateLabel(dateStr) {
  const birth = parseFrenchShortDate(dateStr);
  if (!birth) return "";
  const ready = new Date(birth.getTime() + 84 * 24 * 60 * 60 * 1000);
  return ready.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
}

function computeAgeWeeks(dateStr) {
  const birth = parseFrenchShortDate(dateStr);
  if (!birth) return null;
  const diffMs = Date.now() - birth.getTime();
  if (diffMs < 0) return null;
  return Math.floor(diffMs / (7 * 24 * 60 * 60 * 1000));
}

function findSiblings(chaton, allChatons) {
  if (!chaton.pere || !chaton.mere) return [];
  return (allChatons || []).filter(
    (c) => c.nom !== chaton.nom && c.pere === chaton.pere && c.mere === chaton.mere
  );
}

function waLink(nom) {
  const text = `Bonjour, je suis intéressé(e) par ${nom} 🐾`;
  return `https://wa.me/33685499971?text=${encodeURIComponent(text)}`;
}

function renderTraits(traits) {
  if (!Array.isArray(traits) || traits.length === 0) return "";
  return `<div class="trait-tags">${traits
    .map((t) => `<span class="trait-tag"><i class="fa-solid fa-paw"></i> ${escapeHtml(t)}</span>`)
    .join("")}</div>`;
}

function getFichePhotos(chaton) {
  const extra = (chaton.photos_supplementaires || []).map((p) => p && p.image).filter(Boolean);
  return [chaton.photo, ...extra].filter(Boolean);
}

function initFicheGallery(root) {
  const main = root.querySelector(".fiche-gallery-main img");
  const thumbs = root.querySelectorAll(".fiche-thumb");
  if (!main || thumbs.length === 0) return;
  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      const src = thumb.getAttribute("data-src");
      if (!src) return;
      main.setAttribute("src", src);
      thumbs.forEach((t) => t.classList.remove("active"));
      thumb.classList.add("active");
    });
  });
}

function renderSiblingCard(sibling) {
  const isReserved = sibling.statut === "Réservé";
  const statusClass = isReserved ? "sibling-status-inline reserved" : "sibling-status-inline";
  const photo = sibling.photo
    ? `<img src="${escapeHtml(sibling.photo)}" alt="${escapeHtml(sibling.nom)}">`
    : "";
  return `
    <a class="sibling-card" href="chaton.html?nom=${encodeURIComponent(sibling.nom)}">
      <div class="sibling-photo">
        ${photo}
      </div>
      <div class="sibling-body">
        <span class="${statusClass}">${escapeHtml(sibling.statut || "Disponible")}</span>
        <h4>${escapeHtml(sibling.nom)}</h4>
        <span>${escapeHtml(sibling.sexe || "")}${sibling.couleur ? " · " + escapeHtml(sibling.couleur) : ""}</span>
      </div>
    </a>
  `;
}

function renderParentsSection(chaton, parentIndex) {
  if (!chaton.pere && !chaton.mere) return "";
  const pereSlot = chaton.pere ? renderParentSlot("Père", chaton.pere, parentIndex[chaton.pere]) : "";
  const mereSlot = chaton.mere ? renderParentSlot("Mère", chaton.mere, parentIndex[chaton.mere]) : "";
  return `
    <div class="section-head">
      <span class="kicker">Origines</span>
      <h2>Ses parents</h2>
    </div>
    <div class="grid grid-2">
      ${pereSlot}
      ${mereSlot}
    </div>
  `;
}

function renderParentSlot(label, nom, match) {
  if (!match) {
    return `
      <div class="parent-card">
        <div class="parent-unknown">
          <svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="9" r="2"/><circle cx="10.5" cy="6.2" r="2"/><circle cx="15.5" cy="6.2" r="2"/><circle cx="19" cy="9" r="2"/><path d="M12.5 11c3 0 5.5 2.2 5.5 4.6 0 1.9-1.6 3.4-3.6 3.4-1 0-1.6-.4-2.4-.4s-1.4.4-2.4.4c-2 0-3.6-1.5-3.6-3.4C6.5 13.2 9 11 12.5 11Z"/></svg>
        </div>
        <div class="parent-body">
          <span class="cattery">${escapeHtml(label)}</span>
          <h4>${escapeHtml(nom)}</h4>
        </div>
      </div>
    `;
  }
  const cat = match.cat;
  const isMale = match.isMale;
  const linkHref = `${isMale ? "reproducteurs.html" : "reproductrices.html"}#${slugify(cat.nom)}`;
  const photo = cat.photo
    ? `<img src="${escapeHtml(cat.photo)}" alt="${escapeHtml(cat.nom)}">`
    : "";
  const caractereHtml = cat.caractere
    ? `<p class="cat-character">« ${escapeHtml(cat.caractere)} »</p>`
    : "";
  return `
    <div class="parent-card">
      <div class="parent-photo">
        <span class="parent-label">${escapeHtml(label)}</span>
        ${photo}
      </div>
      <div class="parent-body">
        <h4><a href="${linkHref}">${escapeHtml(cat.nom)}</a></h4>
        <span class="cattery">${escapeHtml(cat.chatterie_origine || "")}</span>
        <ul class="kitten-facts">
          <li><strong>Couleur :</strong> ${escapeHtml(cat.couleur || "à préciser")}</li>
          <li><strong>Lignée :</strong> ${escapeHtml(cat.lignee || "à préciser")}</li>
        </ul>
        ${caractereHtml}
      </div>
    </div>
  `;
}

var ACCENT_MAP = {
  "à": "a", "â": "a", "ä": "a",
  "é": "e", "è": "e", "ê": "e", "ë": "e",
  "î": "i", "ï": "i",
  "ô": "o", "ö": "o",
  "ù": "u", "û": "u", "ü": "u",
  "ç": "c", "œ": "oe", "æ": "ae"
};

function slugify(str) {
  return String(str)
    .toLowerCase()
    .split("")
    .map((ch) => ACCENT_MAP[ch] || ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function renderKittenCard(chaton) {
  const isReserved = chaton.statut === "Réservé";
  const statusClass = isReserved ? "kitten-status reserved" : "kitten-status";
  const nom = chaton.nom || "";
  const ficheHref = `chaton.html?nom=${encodeURIComponent(nom)}`;
  const photo = chaton.photo
    ? `<img src="${escapeHtml(chaton.photo)}" alt="${escapeHtml(nom)}">`
    : `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="9" r="2"/><circle cx="10.5" cy="6.2" r="2"/><circle cx="15.5" cy="6.2" r="2"/><circle cx="19" cy="9" r="2"/><path d="M12.5 11c3 0 5.5 2.2 5.5 4.6 0 1.9-1.6 3.4-3.6 3.4-1 0-1.6-.4-2.4-.4s-1.4.4-2.4.4c-2 0-3.6-1.5-3.6-3.4C6.5 13.2 9 11 12.5 11Z"/></svg>`;

  return `
    <article class="kitten-card">
      <a href="${ficheHref}" class="kitten-photo" aria-label="Voir la fiche de ${escapeHtml(nom)}">
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
          <a href="${ficheHref}" class="btn btn-outline btn-block">Voir sa fiche</a>
          <a href="contact.html?sujet=adoption&nom=${encodeURIComponent(nom)}" class="btn btn-primary btn-block">Je suis intéressé(e)</a>
        </div>
      </div>
    </article>
  `;
}

function renderFullFiche(chaton, parentIndex, allChatons) {
  const nom = chaton.nom || "";
  const isFemale = chaton.sexe === "Femelle";
  const isReserved = chaton.statut === "Réservé";
  const statusClass = isReserved ? "kitten-status reserved" : "kitten-status";
  const sexIcon = isFemale ? "fa-venus" : "fa-mars";
  const photos = getFichePhotos(chaton);
  const mainPhoto = photos[0]
    ? `<img src="${escapeHtml(photos[0])}" alt="${escapeHtml(nom)}, chaton Maine Coon disponible à l'adoption">`
    : "";
  const thumbsHtml = photos.length > 1
    ? `<div class="fiche-gallery-thumbs">${photos
        .map((p, i) => `<button type="button" class="fiche-thumb${i === 0 ? " active" : ""}" data-src="${escapeHtml(p)}"><img src="${escapeHtml(p)}" alt="${escapeHtml(nom)}, photo ${i + 1}"></button>`)
        .join("")}</div>`
    : "";
  const readyLabel = computeReadyDateLabel(chaton.date_naissance);
  const ageWeeks = computeAgeWeeks(chaton.date_naissance);
  const dateValue = chaton.date_naissance
    ? `${escapeHtml(chaton.date_naissance)}${ageWeeks !== null ? ` (${ageWeeks} sem.)` : ""}`
    : "à préciser";
  const tagline = chaton.tagline ? `<p class="fiche-tagline">« ${escapeHtml(chaton.tagline)} »</p>` : "";
  const contactHref = `contact.html?sujet=adoption&nom=${encodeURIComponent(nom)}`;
  const wa = waLink(nom);
  const traitsHtml = renderTraits(chaton.traits);

  const hero = `
    <section class="section section-light">
      <div class="container">
        <div class="fiche-hero-grid">
          <div class="fiche-gallery">
            <div class="fiche-gallery-main">
              <span class="${statusClass}">${escapeHtml(chaton.statut || "Disponible")}</span>
              <span class="fiche-sex-badge"><i class="fa-solid ${sexIcon}"></i></span>
              ${mainPhoto}
            </div>
            ${thumbsHtml}
          </div>
          <h1 class="fiche-name">${escapeHtml(nom)}</h1>
          <div class="fiche-hero-info">
            ${tagline}
            <div class="quick-facts">
              <div class="quick-fact">
                <span class="qf-icon"><i class="fa-solid ${sexIcon}"></i></span>
                <span><span class="qf-label">Sexe</span><span class="qf-value">${escapeHtml(chaton.sexe || "à préciser")}</span></span>
              </div>
              <div class="quick-fact">
                <span class="qf-icon"><i class="fa-solid fa-palette"></i></span>
                <span><span class="qf-label">Couleur</span><span class="qf-value">${escapeHtml(chaton.couleur || "à préciser")}</span></span>
              </div>
              <div class="quick-fact full">
                <span class="qf-icon"><i class="fa-solid fa-cake-candles"></i></span>
                <div class="qf-stack">
                  <div><span class="qf-label">Né le</span><span class="qf-value">${dateValue}</span></div>
                  ${readyLabel ? `<div class="qf-divider"></div><div><span class="qf-label">Prêt à partir du</span><span class="qf-value">${readyLabel}</span></div>` : ""}
                </div>
              </div>
              <div class="quick-fact full">
                <span class="qf-icon"><i class="fa-solid fa-tag"></i></span>
                <span><span class="qf-label">Prix</span><span class="qf-value">${escapeHtml(chaton.prix || "nous consulter")}</span></span>
              </div>
            </div>
            ${traitsHtml}
            <div class="cta-row" style="display:flex;gap:0.8rem;flex-wrap:wrap">
              <a href="${contactHref}" class="btn btn-primary">Je suis intéressé(e) par ${escapeHtml(nom)}</a>
              <a href="${wa}" target="_blank" rel="noopener" class="btn btn-whatsapp"><i class="fa-brands fa-whatsapp"></i> WhatsApp</a>
            </div>
          </div>
        </div>

        <div class="trust-strip-mini">
          <div class="trust-item-mini"><span class="ti-icon"><i class="fa-solid fa-scroll"></i></span><span>Pedigree</span></div>
          <div class="trust-item-mini"><span class="ti-icon"><i class="fa-solid fa-syringe"></i></span><span>Vacciné</span></div>
          <div class="trust-item-mini"><span class="ti-icon"><i class="fa-solid fa-pump-soap"></i></span><span>Vermifugé</span></div>
          <div class="trust-item-mini"><span class="ti-icon"><i class="fa-solid fa-microchip"></i></span><span>Identifié (puce)</span></div>
          <div class="trust-item-mini"><span class="ti-icon"><i class="fa-solid fa-gift"></i></span><span>Kit de départ</span></div>
        </div>
      </div>
    </section>
  `;

  const parentsInner = renderParentsSection(chaton, parentIndex);
  const parentsSection = parentsInner ? `
    <section class="section section-light">
      <div class="container">${parentsInner}</div>
    </section>
  ` : "";

  const siblings = findSiblings(chaton, allChatons);
  const siblingsSection = siblings.length > 0 ? `
    <section class="section section-alt">
      <div class="container">
        <div class="section-head">
          <span class="kicker">Même portée</span>
          <h2>Ses frères et sœurs</h2>
        </div>
        <div class="siblings-row">${siblings.map(renderSiblingCard).join("")}</div>
      </div>
    </section>
  ` : "";

  const process = `
    <section class="section section-dark">
      <div class="container">
        <div class="section-head">
          <span class="kicker">Étapes</span>
          <h2>Comment se passe l'adoption ?</h2>
        </div>
        <div class="process-steps">
          <div class="process-step">
            <div class="process-num">1</div>
            <h4>Prise de contact</h4>
            <p>Vous nous parlez de votre projet, on répond à toutes vos questions.</p>
          </div>
          <div class="process-step">
            <div class="process-num">2</div>
            <h4>Rencontre</h4>
            <p>En visio ou à la chatterie au Soler, pour faire connaissance avec ${escapeHtml(nom)}.</p>
          </div>
          <div class="process-step">
            <div class="process-num">3</div>
            <h4>Réservation</h4>
            <p>Un acompte de 300 € valide votre réservation jusqu'au départ du chaton.</p>
          </div>
          <div class="process-step">
            <div class="process-num">4</div>
            <h4>Départ</h4>
            <p>Remise dès 12 semaines, avec pedigree, carnet de santé et kit de départ.</p>
          </div>
        </div>
      </div>
    </section>
  `;

  const finalCta = `
    <section class="section section-alt" style="text-align:center">
      <div class="container">
        <h2>Craquez pour ${escapeHtml(nom)} ?</h2>
        <p style="max-width:520px;margin:0 auto 1.6rem">Une question, un coup de cœur ? Nous serons ravis d'échanger avec vous.</p>
        <div class="cta-row" style="display:flex;gap:0.8rem;flex-wrap:wrap;justify-content:center;margin-bottom:1.6rem">
          <a href="${contactHref}" class="btn btn-primary">Je suis intéressé(e) par ${escapeHtml(nom)}</a>
          <a href="${wa}" target="_blank" rel="noopener" class="btn btn-whatsapp"><i class="fa-brands fa-whatsapp"></i> WhatsApp</a>
        </div>
        <a href="chatons.html" class="btn btn-outline">← Voir tous les chatons disponibles</a>
      </div>
    </section>
  `;

  return hero + parentsSection + siblingsSection + process + finalCta;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
