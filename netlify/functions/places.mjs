import { getStore } from "@netlify/blobs";
import { STORE_NAME, json, countEntries } from "../lib/waitlist.mjs";

export const config = { path: "/api/places" };

// Public : ne renvoie que le NOMBRE d'inscrits (aucune donnée personnelle).
export default async (req) => {
  if (req.method !== "GET") return json({ error: "Méthode non autorisée." }, 405);
  const store = getStore({ name: STORE_NAME, consistency: "strong" });
  const count = await countEntries(store);
  return json({ count }, 200, {
    "Cache-Control": "public, max-age=0, must-revalidate",
    "Netlify-CDN-Cache-Control": "public, max-age=30, stale-while-revalidate=60",
  });
};
