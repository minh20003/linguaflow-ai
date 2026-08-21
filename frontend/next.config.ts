import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The standalone bundle is required by the Docker frontend image. Vercel
  // provides its own Next.js runtime and expects the default build output.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
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
