import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Proxy API requests in dev so the browser doesn't hit CORS.
   * In production the reverse proxy (Caddy) handles routing.
   */
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
