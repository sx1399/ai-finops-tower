import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for the Docker multi-stage build
  output: "standalone",
};

export default nextConfig;
