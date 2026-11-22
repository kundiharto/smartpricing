import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE } from "@/lib/server/session";

// Server API gratis bisa 'tidur'; beri waktu menyala (maks. Vercel Hobby 60 detik).
export const maxDuration = 60;

const FORWARD_HEADERS = ["content-type", "x-organization-id", "x-request-id", "accept-language"];

/** Proxy ke backend FastAPI: menambahkan Authorization dari cookie httpOnly. */
async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (req.method !== "GET" && req.headers.get(CSRF_HEADER) !== CSRF_VALUE) {
    return NextResponse.json({ success: false, error: { code: "FORBIDDEN", message: "Invalid client" } }, { status: 403 });
  }
  if (path[0] === "auth" && path[1] === "login") {
    return NextResponse.json({ success: false, error: { code: "NOT_FOUND", message: "Use /api/session" } }, { status: 404 });
  }

  const headers = new Headers();
  for (const name of FORWARD_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  // IP pengguna asli untuk pembatas laju di backend (Vercel mengisi x-forwarded-for).
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (ip) headers.set("x-forwarded-for", ip);
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (token) headers.set("authorization", `Bearer ${token}`);

  const target = `${BACKEND_URL}/api/v1/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.text(),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { success: false, error: { code: "BACKEND_UNAVAILABLE", message: "Server API tidak dapat dihubungi. Jika baru dibuka, server sedang dinyalakan — coba lagi dalam 1 menit." } },
      { status: 502 },
    );
  }

  const res = new NextResponse(upstream.body, { status: upstream.status });
  for (const name of ["content-type", "x-request-id"]) {
    const value = upstream.headers.get(name);
    if (value) res.headers.set(name, value);
  }
  if (upstream.status === 401) res.cookies.delete(SESSION_COOKIE);
  return res;
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
