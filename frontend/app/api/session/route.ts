import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL, CSRF_HEADER, CSRF_VALUE, SESSION_COOKIE } from "@/lib/server/session";

export const maxDuration = 60;

function csrfOk(req: NextRequest) {
  return req.headers.get(CSRF_HEADER) === CSRF_VALUE;
}

/** Login: token dari backend disimpan sebagai cookie httpOnly, tidak pernah terlihat oleh JavaScript. */
export async function POST(req: NextRequest) {
  if (!csrfOk(req)) {
    return NextResponse.json({ success: false, error: { code: "FORBIDDEN", message: "Invalid client" } }, { status: 403 });
  }
  const body = await req.text();
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json", ...(ip ? { "x-forwarded-for": ip } : {}) },
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { success: false, error: { code: "BACKEND_UNAVAILABLE", message: "Server API tidak dapat dihubungi. Jika baru dibuka, server sedang dinyalakan — coba lagi dalam 1 menit." } },
      { status: 502 },
    );
  }
  const payload = await upstream.json();
  if (!upstream.ok) return NextResponse.json(payload, { status: upstream.status });

  const { access_token, expires_at } = payload.data as { access_token: string; expires_at: string };
  const res = NextResponse.json({ success: true, data: { expires_at } });
  res.cookies.set(SESSION_COOKIE, access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: new Date(expires_at),
  });
  return res;
}

export async function DELETE(req: NextRequest) {
  if (!csrfOk(req)) {
    return NextResponse.json({ success: false, error: { code: "FORBIDDEN", message: "Invalid client" } }, { status: 403 });
  }
  const res = NextResponse.json({ success: true, data: { logged_out: true } });
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
