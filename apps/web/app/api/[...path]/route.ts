import type { NextRequest } from "next/server";

// Server-side proxy to the API (Railway private network in production). The browser only talks to this origin,
// so the session cookie is first-party and the CSP can keep connect-src 'self'.
const API = (process.env.API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/$/, "");
const FORWARD_REQUEST = ["accept", "content-type", "cookie", "idempotency-key", "origin", "user-agent", "x-requested-with", "x-workspace-id"];
const DROP_RESPONSE = new Set(["connection", "content-encoding", "content-length", "keep-alive", "set-cookie", "transfer-encoding"]);

export const dynamic = "force-dynamic";

function clientIp(request: NextRequest): string {
  return request.headers.get("x-real-ip") ?? request.headers.get("cf-connecting-ip")
    ?? request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "";
}

async function forward(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  if (!path.length || path.some(part => part === ".." || part.includes("/"))) return new Response(null, { status: 400 });
  const headers = new Headers();
  for (const name of FORWARD_REQUEST) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("x-aln-client-ip", clientIp(request));
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(`${API}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
      method: request.method, headers, body, redirect: "manual", cache: "no-store",
    });
  } catch {
    return Response.json({ detail: "API indisponível no momento." }, { status: 502 });
  }
  const out = new Headers();
  upstream.headers.forEach((value, key) => { if (!DROP_RESPONSE.has(key.toLowerCase())) out.set(key, value); });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { forward as DELETE, forward as GET, forward as PATCH, forward as POST, forward as PUT };
