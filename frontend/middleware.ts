import { NextRequest, NextResponse } from "next/server";

// HTTP Basic Auth gate. Set BASIC_AUTH_USER + BASIC_AUTH_PASSWORD in
// Vercel project env to enable. Leave them unset locally to skip the prompt.
export function middleware(req: NextRequest) {
  const expectedUser = process.env.BASIC_AUTH_USER;
  const expectedPass = process.env.BASIC_AUTH_PASSWORD;

  // No credentials configured → bypass (useful for local dev)
  if (!expectedUser || !expectedPass) {
    return NextResponse.next();
  }

  const auth = req.headers.get("authorization");
  if (auth) {
    const [scheme, encoded] = auth.split(" ");
    if (scheme === "Basic" && encoded) {
      // atob is available in Edge runtime
      const decoded = atob(encoded);
      const sep = decoded.indexOf(":");
      const user = decoded.slice(0, sep);
      const pass = decoded.slice(sep + 1);
      if (user === expectedUser && pass === expectedPass) {
        return NextResponse.next();
      }
    }
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="Flight Radar JP Pro"',
    },
  });
}

export const config = {
  matcher: [
    // Apply to everything except Next.js internals + static files
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
