// frontend/lib/deviceKey.ts
// Identity is a random key kept in localStorage and exchanged for a user row
// server-side. Deliberately not authentication — it replaces the single
// global watchlist, it does not secure it.
const STORAGE_KEY = "since.deviceKey";

let cached: string | null = null;

function generate(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${crypto.randomUUID()}${crypto.randomUUID()}`.replace(/-/g, "");
  }
  return Array.from({ length: 48 }, () =>
    Math.floor(Math.random() * 36).toString(36)
  ).join("");
}

export function getDeviceKey(): string {
  if (cached) return cached;
  // Private windows and blocked site data both throw here; fall back to an
  // in-memory key so the session still works, it just will not persist.
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored.length >= 32) {
      cached = stored;
      return cached;
    }
    const fresh = generate();
    localStorage.setItem(STORAGE_KEY, fresh);
    cached = fresh;
    return cached;
  } catch {
    cached = cached ?? generate();
    return cached;
  }
}
