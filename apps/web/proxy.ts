import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "alnia_session";

// Strict CSP: no 'unsafe-inline'. Next.js reads the nonce from this header and applies it to its own scripts.
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // Optimistic check only (the API is the real authority): send visitors without a session to the login page.
  if (pathname === "/app" || pathname.startsWith("/app/")) {
    if (!request.cookies.get(SESSION_COOKIE)) {
      const login = new URL("/entrar", request.url);
      login.searchParams.set("next", pathname + search);
      return NextResponse.redirect(login);
    }
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";
  const isLocal = ["localhost", "127.0.0.1"].includes(request.nextUrl.hostname);
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self'${isDev ? " 'unsafe-inline'" : ` 'nonce-${nonce}'`}`,
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "frame-src 'none'",
    "form-action 'self' https://accounts.google.com https://business-api.tiktok.com",
    "base-uri 'self'",
    "object-src 'none'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "frame-ancestors 'none'",
    ...(isDev || isLocal ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Cache-Control", "no-store");
  if (pathname.startsWith("/app") || pathname.startsWith("/entrar") || pathname.startsWith("/convite")) {
    response.headers.set("X-Robots-Tag", "noindex, nofollow");
  }
  return response;
}

export const config = {
  matcher: [{
    // Static files and the API proxy are excluded by exact prefix, so no page can slip out of the CSP.
    source: "/((?!api/|_next/static/|_next/image|brand/|fonts/|favicon\\.ico$|robots\\.txt$|sitemap\\.xml$|llms\\.txt$|manifest\\.webmanifest$|opengraph-image|\\.well-known/).*)",
    missing: [{ type: "header", key: "next-router-prefetch" }, { type: "header", key: "purpose", value: "prefetch" }],
  }],
};
