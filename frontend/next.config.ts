import type { NextConfig } from "next";

// The browser only ever talks to this origin. /api/* is proxied to FastAPI, so the session
// cookie is first-party and no CORS is needed. API_URL is read at build time.
const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // gzip buffers Server-Sent Events from the /api proxy; leave compression to a reverse proxy.
  compress: false,
  // Every page shows live, per-user data fetched in the browser (TanStack Query + SSE), so
  // there is nothing to prerender or cache on the server.
  cacheComponents: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
