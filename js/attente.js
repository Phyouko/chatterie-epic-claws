document.addEventListener("DOMContentLoaded", () => {
  const card = document.querySelector("#litter-card");
  if (!card) return;

  fetch("data/liste-attente.json")
    .then((res) => res.json())
    .then((data) => {
      const portee = String(data.prochaine_portee || "").trim();
      const parents = String(data.parents || "").trim();
      const total = toCount(data.places_total);
      const restantes = toCount(data.places_restantes);

      if (portee) document.querySelector("#litter-value").textContent = portee;
      if (parents) document.querySelector("#litter-parents").textContent = parents;

      if (restantes === null) return;
      const spots = document.querySelector("#litter-spots");
      const text = document.querySelector("#spots-text");
      spots.hidden = false;

      if (restantes === 0) {
        text.textContent = "Liste complète — inscription en liste de réserve";
        return;
      }
      if (total !== null && total >= restantes) {
        text.textContent = `Plus que ${restantes} sur ${total}`;
        document.querySelector("#spots-bar").hidden = false;
        document.querySelector("#spots-fill").style.width = `${Math.round(((total - restantes) / total) * 100)}%`;
      } else {
        text.textContent = restantes === 1 ? "Plus qu'une place" : `Il reste ${restantes} places`;
      }
    })
    .catch(() => {});
});

function toCount(value) {
  if (value === "" || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
}
