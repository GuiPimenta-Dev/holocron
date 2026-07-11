import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray lockfile in the user's home dir otherwise makes Next guess the wrong root.
  turbopack: { root: path.join(__dirname) },
};

export default nextConfig;
