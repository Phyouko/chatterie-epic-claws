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

  document.querySelectorAll(".faq-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const card = btn.closest(".faq-card");
      const isOpen = card.classList.contains("open");
      document.querySelectorAll(".faq-card.open").forEach((c) => {
        if (c !== card) {
          c.classList.remove("open");
          c.querySelector(".faq-toggle").setAttribute("aria-expanded", "false");
        }
      });
      card.classList.toggle("open", !isOpen);
      btn.setAttribute("aria-expanded", String(!isOpen));
    });
  });

  const contactForm = document.querySelector("#contact-form");
  if (contactForm) {
    const sujetSelect = contactForm.querySelector("#sujet");
    const messageField = contactForm.querySelector("#message");
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
  }

  // Netlify retire data-netlify au déploiement : on cible donc le formulaire de contact par son id
  // et les autres formulaires par data-success (qui, lui, est conservé).
  document.querySelectorAll("#contact-form, form[data-success]").forEach((form) => {
    const submitBtn = form.querySelector("button[type=submit]");
    const idleLabel = submitBtn ? submitBtn.textContent : "";
    const successPage = form.dataset.success || "merci.html";

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const body = new URLSearchParams(new FormData(form)).toString();

      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Envoi en cours…"; }

      fetch("/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      })
        .then(() => { window.location.href = successPage; })
        .catch(() => {
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = idleLabel; }
          alert("Une erreur est survenue lors de l'envoi. Vous pouvez réessayer ou nous appeler directement au +33 6 85 49 99 71.");
        });
    });
  });
});
