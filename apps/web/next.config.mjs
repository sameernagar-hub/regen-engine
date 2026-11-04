// No proxy: the browser calls the API container directly (lib/types.ts api()); the API's CORS allows this origin only.
const API = process.env.NEXT_PUBLIC_REGEN_API || "http://127.0.0.1:8787";
// The desk's noVNC page, framed by /desk (local mode only).
const DESK = process.env.NEXT_PUBLIC_REGEN_DESK || "http://127.0.0.1:6080";

/** @type {import('next').NextConfig} */
export default {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    const local = process.env.NEXT_PUBLIC_REGEN_MODE !== "public";
    const api = local ? ` ${API}` : "";
    const desk = local ? ` ${DESK}` : "";
    return [{
      source: "/:path*",
      headers: [
        { key: "Content-Security-Policy", value: `default-src 'self'; img-src 'self' data:${api}; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self'${api}; frame-src 'self'${api}${desk}; frame-ancestors 'none'` },
        { key: "Referrer-Policy", value: "no-referrer" },
      ],
    }, {  // the demo's resume pages are framed by the Applications and Reach pages (same origin only); listed last so it wins
      source: "/proxy/:path*",
      headers: [{ key: "Content-Security-Policy", value: "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'self'" }],
    }];
  },
};
