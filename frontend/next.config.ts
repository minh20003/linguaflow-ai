import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // The local FastAPI server listens on 8000. Production sets
        // NEXT_PUBLIC_API_URL, so browser requests go straight to Railway.
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
