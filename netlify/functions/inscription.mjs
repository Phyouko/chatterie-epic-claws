import { getStore } from "@netlify/blobs";
import { STORE_NAME, json, validateSignup, addSignup, forwardToForms } from "../lib/waitlist.mjs";

export const config = { path: "/api/inscription" };

export default async (req) => {
  if (req.method !== "POST") return json({ error: "Méthode non autorisée." }, 405);

  const origin = new URL(req.url).origin;
  const from = req.headers.get("origin");
  if (from && from !== origin) return json({ error: "Origine non autorisée." }, 403);

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Requête invalide." }, 400);
  }

  const check = validateSignup(body);
  if (check.spam) return json({ ok: true });
  if (!check.ok) return json({ error: check.error }, 400);

  const store = getStore({ name: STORE_NAME, consistency: "strong" });
  const result = await addSignup(store, check.entry);
  if (result.status === "full") {
    return json({ error: "La liste est momentanément complète. Merci de nous écrire via la page Contact." }, 409);
  }
  if (result.status === "created") {
    try {
      await forwardToForms(origin, check.entry);
    } catch {
      // L'inscription est déjà enregistrée : la copie vers Netlify Forms est un bonus (e-mail de notification).
    }
  }
  return json({ ok: true, duplicate: result.status === "duplicate" });
};
