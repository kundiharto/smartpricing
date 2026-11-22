// Hanya dipakai di server (route handler & middleware).
export const SESSION_COOKIE = "spe_token";
export const BACKEND_URL = process.env.SPE_BACKEND_URL ?? "http://127.0.0.1:8000";

// Header kustom wajib untuk request yang mengubah data. Browser tidak bisa mengirim header
// kustom lintas situs tanpa preflight CORS (yang tidak kita izinkan), sehingga ini menahan CSRF.
export const CSRF_HEADER = "x-spe-client";
export const CSRF_VALUE = "web";
