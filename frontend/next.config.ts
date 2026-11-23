import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Tailwind CSS v4 requires this Turbopack loader to process @import "tailwindcss" */
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/images/**",
      },
    ],
  },
};

export default nextConfig;
