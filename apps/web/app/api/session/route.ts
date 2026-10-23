import { cookies } from "next/headers";

const COOKIE_NAME = "stocklab_token";
const MAX_AGE = 60 * 60 * 24 * 30;

export async function POST(request: Request) {
  let payload: { token?: unknown };
  try {
    payload = (await request.json()) as { token?: unknown };
  } catch {
    return Response.json({ error: "invalid body" }, { status: 400 });
  }
  if (typeof payload.token !== "string" || payload.token.length < 20) {
    return Response.json({ error: "invalid token" }, { status: 400 });
  }

  const store = await cookies();
  store.set(COOKIE_NAME, payload.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE,
  });
  return Response.json({ ok: true });
}

export async function DELETE() {
  const store = await cookies();
  store.delete(COOKIE_NAME);
  return Response.json({ ok: true });
}
