document.addEventListener("DOMContentLoaded", () => {
  const grid = document.querySelector("#kittens-grid");
  if (!grid) return;

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
});

function renderKittenCard(chaton) {
  const isReserved = chaton.statut === "Réservé";
  const statusClass = isReserved ? "kitten-status reserved" : "kitten-status";
  const photo = chaton.photo
    ? `<img src="${escapeHtml(chaton.photo)}" alt="${escapeHtml(chaton.nom)}">`
    : `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="9" r="2"/><circle cx="10.5" cy="6.2" r="2"/><circle cx="15.5" cy="6.2" r="2"/><circle cx="19" cy="9" r="2"/><path d="M12.5 11c3 0 5.5 2.2 5.5 4.6 0 1.9-1.6 3.4-3.6 3.4-1 0-1.6-.4-2.4-.4s-1.4.4-2.4.4c-2 0-3.6-1.5-3.6-3.4C6.5 13.2 9 11 12.5 11Z"/></svg>`;

  return `
    <article class="kitten-card">
      <div class="kitten-photo">
        <span class="${statusClass}">${escapeHtml(chaton.statut || "Disponible")}</span>
        ${photo}
      </div>
      <div class="kitten-body">
        <h3>${escapeHtml(chaton.nom || "")}</h3>
        <ul class="kitten-facts">
          <li><strong>Sexe :</strong> ${escapeHtml(chaton.sexe || "à préciser")}</li>
          <li><strong>Couleur :</strong> ${escapeHtml(chaton.couleur || "à préciser")}</li>
          <li><strong>Date de naissance :</strong> ${escapeHtml(chaton.date_naissance || "à préciser")}</li>
          <li><strong>Prix :</strong> ${escapeHtml(chaton.prix || "nous consulter")}</li>
        </ul>
        <a href="contact.html?sujet=adoption&nom=${encodeURIComponent(chaton.nom || "")}" class="btn btn-outline btn-block">Je suis intéressé(e)</a>
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
