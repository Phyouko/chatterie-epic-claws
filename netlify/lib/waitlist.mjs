// Logique de la liste d'attente (stockage dans Netlify Blobs, une entrée par inscrit).
// Les fonctions du dossier netlify/functions ne font qu'appeler ces helpers : ils prennent le
// "store" en paramètre, ce qui permet de les tester sans Netlify.

export const STORE_NAME = "liste-attente";
export const FORM_NAME = "liste-attente";
export const MAX_ENTRIES = 500;
export const CANAUX = ["Facebook", "Instagram", "Google", "Royal Canin", "Bouche-à-oreille", "Autre"];
const ID_PATTERN = /^\d{4}-\d{2}-\d{2}T[\d:.]+Z_[a-z0-9]{4,12}$/;

export function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...extraHeaders },
  });
}

export function cleanText(value, max) {
  return String(value ?? "")
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max);
}

export function validateSignup(body) {
  if (!body || typeof body !== "object") return { ok: false, error: "Requête invalide." };
  if (cleanText(body["bot-field"], 50)) return { ok: false, spam: true };

  const nom = cleanText(body.nom, 80);
  const email = cleanText(body.email, 120).toLowerCase();
  const telephone = cleanText(body.telephone, 30);
  const canalBrut = cleanText(body.canal, 40);
  const digits = telephone.replace(/\D/g, "");

  if (nom.length < 2) return { ok: false, error: "Merci d'indiquer votre prénom et nom." };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return { ok: false, error: "Cette adresse e-mail ne semble pas valide." };
  if (digits.length < 8 || digits.length > 15) return { ok: false, error: "Ce numéro de téléphone ne semble pas valide." };
  if (!["oui", "on", "true", true].includes(body.consentement)) {
    return { ok: false, error: "Merci de cocher la case de consentement." };
  }
  const canal = CANAUX.includes(canalBrut) ? canalBrut : "Autre";
  return { ok: true, entry: { nom, email, telephone, canal } };
}

// Ajout à la main par l'administratrice (inscription par téléphone, Facebook, ou faite avant la mise en place du site).
export function validateManual(body, now = new Date()) {
  if (!body || typeof body !== "object") return { ok: false, error: "Requête invalide." };
  const nom = cleanText(body.nom, 80);
  const email = cleanText(body.email, 120).toLowerCase();
  const telephone = cleanText(body.telephone, 30);
  const canalBrut = cleanText(body.canal, 40);
  const digits = telephone.replace(/\D/g, "");

  if (nom.length < 2) return { ok: false, error: "Indique au moins un nom." };
  if (!email && !telephone) return { ok: false, error: "Indique au moins un e-mail ou un téléphone." };
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return { ok: false, error: "Cette adresse e-mail ne semble pas valide." };
  if (telephone && (digits.length < 8 || digits.length > 15)) return { ok: false, error: "Ce numéro de téléphone ne semble pas valide." };

  let createdAt = now;
  if (body.created_at) {
    createdAt = new Date(body.created_at);
    if (Number.isNaN(createdAt.getTime())) return { ok: false, error: "Cette date ne semble pas valide." };
    if (createdAt.getTime() > now.getTime() + 24 * 3600 * 1000) return { ok: false, error: "La date d'inscription ne peut pas être dans le futur." };
  }
  const canal = CANAUX.includes(canalBrut) ? canalBrut : "Autre";
  return { ok: true, entry: { nom, email, telephone, canal }, createdAt };
}

export function makeId(now = new Date(), random = Math.random()) {
  return `${now.toISOString()}_${Math.floor(random * 36 ** 6).toString(36).padStart(6, "0")}`;
}

export function isValidId(id) {
  return typeof id === "string" && ID_PATTERN.test(id);
}

export async function listEntries(store) {
  const { blobs } = await store.list();
  const rows = await Promise.all(
    blobs.map(async (blob) => {
      try {
        const value = await store.get(blob.key, { type: "json", consistency: "strong" });
        return value ? { id: blob.key, ...value } : null;
      } catch {
        return null;
      }
    })
  );
  return rows
    .filter(Boolean)
    .sort((a, b) => (a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : a.id.localeCompare(b.id)));
}

export async function countEntries(store) {
  const { blobs } = await store.list();
  return blobs.length;
}

export async function addSignup(store, entry, now = new Date()) {  // `now` = date d'inscription (ordre d'arrivée)
  const existing = await listEntries(store);
  if (existing.length >= MAX_ENTRIES) return { status: "full" };
  const duplicate = entry.email ? existing.find((e) => e.email === entry.email) : null;
  if (duplicate) return { status: "duplicate", id: duplicate.id };
  const id = makeId(now);
  await store.setJSON(id, { ...entry, created_at: now.toISOString(), contacte: false });
  return { status: "created", id };
}

export async function setContacte(store, id, value) {
  if (!isValidId(id)) return false;
  const current = await store.get(id, { type: "json", consistency: "strong" });
  if (!current) return false;
  await store.setJSON(id, { ...current, contacte: Boolean(value) });
  return true;
}

export async function removeEntry(store, id) {
  if (!isValidId(id)) return false;
  await store.delete(id);
  return true;
}

// Copie l'inscription dans Netlify Forms : e-mail de notification + sauvegarde dans le tableau de bord Netlify.
export async function forwardToForms(origin, entry, fetchFn = fetch) {
  const body = new URLSearchParams({ "form-name": FORM_NAME, ...entry, consentement: "oui" }).toString();
  const res = await fetchFn(`${origin}/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  return res.ok;
}

export function adminList(env = process.env) {
  const raw = env.ADMIN_EMAILS || "chatterieepicclaws@gmail.com";
  return raw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}

// Vérifie le jeton Netlify Identity auprès de Netlify, puis contrôle que l'e-mail fait partie des administrateurs.
// L'inscription Identity étant ouverte à tous, être "connecté" ne suffit pas : il faut figurer dans la liste.
export async function checkAdmin(req, fetchFn = fetch, admins = adminList()) {
  const auth = req.headers.get("authorization") || "";
  if (!/^Bearer\s+\S+/i.test(auth)) return { ok: false, status: 401, error: "Connexion requise." };
  let user;
  try {
    const res = await fetchFn(`${new URL(req.url).origin}/.netlify/identity/user`, { headers: { Authorization: auth } });
    if (!res.ok) return { ok: false, status: 401, error: "Session expirée : reconnectez-vous." };
    user = await res.json();
  } catch {
    return { ok: false, status: 401, error: "Impossible de vérifier votre connexion." };
  }
  const email = String(user?.email || "").toLowerCase();
  if (!email || !user.confirmed_at) return { ok: false, status: 401, error: "Compte non confirmé." };
  if (!admins.includes(email)) return { ok: false, status: 403, error: "Ce compte n'a pas accès à la liste d'attente.", email };
  return { ok: true, email };
}
