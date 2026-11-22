"use client";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown[] = [],
  ) {
    super(message);
  }
}

export type Paged<T> = { data: T; meta: { total?: number; limit?: number; offset?: number; request_id?: string } };

const ORG_KEY = "spe_org";

export function getOrgId(): string | null {
  try {
    return localStorage.getItem(ORG_KEY);
  } catch {
    return null;
  }
}

export function setOrgId(id: string | null) {
  try {
    if (id) localStorage.setItem(ORG_KEY, id);
    else localStorage.removeItem(ORG_KEY);
  } catch {
    /* penyimpanan tidak tersedia */
  }
}

type Options = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  org?: string | null | false; // false = tanpa header organisasi
};

async function request<T>(path: string, opts: Options = {}): Promise<Paged<T>> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(opts.query ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const headers: Record<string, string> = { "x-spe-client": "web" };
  if (opts.body !== undefined) headers["content-type"] = "application/json";
  const org = opts.org === false ? null : (opts.org ?? getOrgId());
  if (org) headers["x-organization-id"] = org;

  const res = await fetch(`/api/v1${path}${qs.size ? `?${qs}` : ""}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  let payload: { success?: boolean; data?: T; meta?: Paged<T>["meta"]; error?: { code: string; message: string; details?: unknown[] } };
  try {
    payload = await res.json();
  } catch {
    throw new ApiError(res.status, "BAD_RESPONSE", `HTTP ${res.status}`);
  }
  if (!res.ok || payload.success === false) {
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/register")) {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    const e = payload.error ?? { code: "HTTP_ERROR", message: `HTTP ${res.status}` };
    throw new ApiError(res.status, e.code, e.message, e.details ?? []);
  }
  return { data: payload.data as T, meta: payload.meta ?? {} };
}

export const api = {
  get: <T>(path: string, opts?: Omit<Options, "method" | "body">) => request<T>(path, opts).then((r) => r.data),
  page: <T>(path: string, opts?: Omit<Options, "method" | "body">) => request<T>(path, opts),
  post: <T>(path: string, body?: unknown, opts?: Omit<Options, "method" | "body">) =>
    request<T>(path, { ...opts, method: "POST", body: body ?? {} }).then((r) => r.data),
  patch: <T>(path: string, body: unknown, opts?: Omit<Options, "method" | "body">) =>
    request<T>(path, { ...opts, method: "PATCH", body }).then((r) => r.data),
  put: <T>(path: string, body: unknown, opts?: Omit<Options, "method" | "body">) =>
    request<T>(path, { ...opts, method: "PUT", body }).then((r) => r.data),
  del: <T>(path: string, opts?: Omit<Options, "method" | "body">) => request<T>(path, { ...opts, method: "DELETE" }).then((r) => r.data),
};

export async function login(email: string, password: string) {
  const res = await fetch("/api/session", {
    method: "POST",
    headers: { "content-type": "application/json", "x-spe-client": "web" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await res.json();
  if (!res.ok) {
    const e = payload.error ?? { code: "HTTP_ERROR", message: `HTTP ${res.status}` };
    throw new ApiError(res.status, e.code, e.message, e.details ?? []);
  }
}

export async function logout() {
  await fetch("/api/session", { method: "DELETE", headers: { "x-spe-client": "web" } });
  setOrgId(null);
  window.location.href = "/login";
}

/** Pesan error ramah pengguna, termasuk detail validasi per field. */
export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const fields = (err.details as { loc?: (string | number)[]; msg?: string }[])
      .filter((d) => d && d.loc && d.msg)
      .map((d) => `${d.loc!.filter((x) => x !== "body").join(".")}: ${d.msg}`);
    return fields.length ? `${err.message} — ${fields.join("; ")}` : err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

export function engineTrace(err: unknown): string[] {
  if (!(err instanceof ApiError)) return [];
  const first = err.details[0] as { trace?: string[] } | undefined;
  return first?.trace ?? [];
}
