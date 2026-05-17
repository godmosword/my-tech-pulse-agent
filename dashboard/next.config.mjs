/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // firebase-admin pulls in Node-only modules; keep it server-side.
    serverComponentsExternalPackages: ["firebase-admin"],
  },
};

export default nextConfig;
