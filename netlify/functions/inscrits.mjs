import { getStore } from "@netlify/blobs";
import { STORE_NAME, json, checkAdmin, listEntries, setContacte, removeEntry, validateManual, addSignup } from "../lib/waitlist.mjs";

export const config = { path: "/api/inscrits" };

// Réservé aux administrateurs : liste des inscrits dans l'ordre d'arrivée, marquage "contacté", retrait de la liste.
export default async (req) => {
  const admin = await checkAdmin(req);
  if (!admin.ok) return json({ error: admin.error, email: admin.email }, admin.status);

  const store = getStore({ name: STORE_NAME, consistency: "strong" });

  if (req.method === "GET") {
    return json({ admin: admin.email, entries: await listEntries(store) });
  }

  if (req.method === "POST") {
    let body;
    try {
      body = await req.json();
    } catch {
      return json({ error: "Requête invalide." }, 400);
    }
    if (body.action === "ajouter") {
      const check = validateManual(body);
      if (!check.ok) return json({ error: check.error }, 400);
      const result = await addSignup(store, check.entry, check.createdAt);
      if (result.status === "full") return json({ error: "La liste est pleine (500 personnes)." }, 409);
      if (result.status === "duplicate") return json({ error: "Cette adresse e-mail est déjà dans la liste." }, 409);
      return json({ ok: true });
    }
    let done = false;
    if (body.action === "contacte") done = await setContacte(store, body.id, body.value);
    else if (body.action === "retirer") done = await removeEntry(store, body.id);
    else return json({ error: "Action inconnue." }, 400);
    return done ? json({ ok: true }) : json({ error: "Inscrit introuvable." }, 404);
  }

  return json({ error: "Méthode non autorisée." }, 405);
};
