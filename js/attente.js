document.addEventListener("DOMContentLoaded", () => {
  setupLitterCard();
  setupWaitlistForm();
});

function setupLitterCard() {
  const card = document.querySelector("#litter-card");
  if (!card) return;

  fetch("data/liste-attente.json")
    .then((res) => res.json())
    .then((data) => {
      const portee = String(data.prochaine_portee || "").trim();
      const parents = String(data.parents || "").trim();
      const total = toCount(data.places_total);
      const dejaPrises = toCount(data.places_deja_prises) || 0;

      if (portee) document.querySelector("#litter-value").textContent = portee;
      if (parents) document.querySelector("#litter-parents").textContent = parents;

      if (total === null) return;
      // Les places restantes se calculent toutes seules : total - inscrits sur le site - inscrits hors du site.
      return fetch("/api/places")
        .then((res) => res.json())
        .then(({ count }) => {
          const restantes = Math.max(0, total - dejaPrises - Number(count || 0));
          renderSpots(restantes, total);
        });
    })
    .catch(() => {});
}

function renderSpots(restantes, total) {
  const spots = document.querySelector("#litter-spots");
  const text = document.querySelector("#spots-text");
  spots.hidden = false;

  if (restantes === 0) {
    text.textContent = "Liste complète — inscription en liste de réserve";
    return;
  }
  text.textContent = restantes === 1 ? `Plus qu'une place sur ${total}` : `Plus que ${restantes} sur ${total}`;
  document.querySelector("#spots-bar").hidden = false;
  document.querySelector("#spots-fill").style.width = `${Math.round(((total - restantes) / total) * 100)}%`;
}

function setupWaitlistForm() {
  const form = document.querySelector("form[name='liste-attente']");
  if (!form) return;
  const submitBtn = form.querySelector("button[type=submit]");
  const idleLabel = submitBtn ? submitBtn.textContent : "";
  const successPage = form.dataset.merci || "merci-liste-attente.html";

  const reset = () => {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = idleLabel; }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Envoi en cours…"; }

    try {
      const response = await fetch("/api/inscription", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      if (response.ok) { window.location.href = successPage; return; }
      if (response.status === 400 || response.status === 409) {
        const data = await response.json().catch(() => ({}));
        alert(data.error || "Merci de vérifier les informations saisies.");
        reset();
        return;
      }
      throw new Error("service indisponible");
    } catch (error) {
      // Secours : si le service d'inscription ne répond pas, on utilise le formulaire Netlify classique
      // pour ne perdre aucune inscription (elle arrivera par e-mail et dans le tableau de bord Netlify).
      try {
        await fetch("/", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams(new FormData(form)).toString(),
        });
        window.location.href = successPage;
      } catch (fallbackError) {
        reset();
        alert("Une erreur est survenue lors de l'envoi. Vous pouvez réessayer ou nous appeler directement au +33 6 85 49 99 71.");
      }
    }
  });
}

function toCount(value) {
  if (value === "" || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
}
