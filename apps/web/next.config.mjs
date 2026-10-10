// The web app talks to the read-only REGEN API. In dev it proxies /api to it, so the browser only ever sees one origin.
const API = process.env.REGEN_API_URL || "http://127.0.0.1:8787";

/** @type {import('next').NextConfig} */
export default {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    // local mode proxies the private API; the public site only serves /api/public (a route handler)
    return process.env.NEXT_PUBLIC_REGEN_MODE === "public" ? [] : [{ source: "/api/:path((?!public).*)", destination: `${API}/api/:path` }];
  },
  async headers() {
    return [{
      // resumes open inline in the Applications page (same-origin iframe only)
      source: "/api/resume/:name",
      headers: [{ key: "Content-Security-Policy", value: "frame-ancestors 'self'" }],
    }, {
      source: "/((?!api/resume).*)",
      headers: [
        { key: "Content-Security-Policy", value: "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self'; frame-ancestors 'none'" },
        { key: "Referrer-Policy", value: "no-referrer" },
      ],
    }];
  },
};
