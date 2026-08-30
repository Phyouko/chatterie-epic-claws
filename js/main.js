document.addEventListener("DOMContentLoaded", () => {
  const navToggle = document.querySelector(".nav-toggle");
  const navLinks = document.querySelector(".nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      navLinks.classList.toggle("open");
    });
    navLinks.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => navLinks.classList.remove("open"));
    });
  }

  const form = document.querySelector("#contact-form");
  if (!form) return;

  const sujetSelect = form.querySelector("#sujet");
  const messageField = form.querySelector("#message");
  const params = new URLSearchParams(window.location.search);
  const sujet = params.get("sujet");
  const nomCible = params.get("nom");

  if (sujet && sujetSelect) {
    const option = Array.from(sujetSelect.options).find((o) => o.value === sujet);
    if (option) sujetSelect.value = sujet;
  }

  if (nomCible && messageField && !messageField.value) {
    if (sujet === "saillie") {
      messageField.value = `Bonjour, je suis intéressé(e) par une saillie avec ${nomCible}. Pourriez-vous me donner les disponibilités et modalités ? Merci.`;
    } else if (sujet === "adoption") {
      messageField.value = `Bonjour, je suis intéressé(e) par l'adoption de ${nomCible}. Est-il/elle toujours disponible ? Merci.`;
    }
  }

  const submitBtn = form.querySelector("button[type=submit]");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const body = new URLSearchParams(new FormData(form)).toString();

    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Envoi en cours…"; }

    fetch("/", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    })
      .then(() => { window.location.href = "merci.html"; })
      .catch(() => {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Envoyer"; }
        alert("Une erreur est survenue lors de l'envoi. Vous pouvez réessayer ou nous appeler directement au +33 6 85 49 99 71.");
      });
  });
});
