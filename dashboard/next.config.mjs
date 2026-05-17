/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // firebase-admin pulls in Node-only modules; keep it server-side.
  serverExternalPackages: ["firebase-admin"],
};

export default nextConfig;
